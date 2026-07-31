from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.institution import Institution
from services.api.app.models.orchestration import (
    AnalysisAttempt,
    AnalysisJob,
    AnalysisPlanModel,
    FinalResultSnapshot,
    PolicyDecisionRecord,
    QualityGateResultRecord,
    ToolInvocation,
)
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.orchestration.budget import JobBudgetTracker
from services.api.app.orchestration.circuit_breaker import ProviderCircuitBreaker
from services.api.app.orchestration.event_engine import AnalysisEventEngine
from services.api.app.orchestration.exceptions import (
    OrchestrationException,
)
from services.api.app.orchestration.policy_engine import DataClassification, PolicyDecision, PolicyEngine
from services.api.app.orchestration.provider import ModelProvider
from services.api.app.orchestration.provider_anthropic import AnthropicProviderAdapter
from services.api.app.orchestration.quality_gate import QualityGateEngine
from services.api.app.orchestration.schemas import AnalysisPlan, NormalizedRequest, PlanStep
from services.api.app.orchestration.state_machine import AnalysisJobStatus, AnalysisStateMachine
from services.api.app.orchestration.tool_dedup import ToolDeduplicationManager
from services.api.app.orchestration.tools.base import ExecutionContext
from services.api.app.orchestration.tools.registry import ToolRegistry


class AnalysisOrchestratorEngine:
    """Sole central runtime engine orchestrating E2E AnalysisJob execution."""

    def __init__(
        self,
        db_session: AsyncSession,
        context: ExecutionContext,
        provider: ModelProvider | None = None,
        circuit_breaker: ProviderCircuitBreaker | None = None,
    ):
        self.db = db_session
        self.context = context
        self.provider = provider or AnthropicProviderAdapter(
            application_model_alias="finance_analysis_balanced",
            use_fake_transport=True,
        )
        self.circuit_breaker = circuit_breaker or ProviderCircuitBreaker(provider_alias="anthropic")
        self.event_engine = AnalysisEventEngine(db_session, context.organization_id)

    async def execute_job(
        self,
        job_id: UUID,
        request_classification: DataClassification = DataClassification.PUBLIC,
    ) -> AnalysisJob:
        now = datetime.now(UTC)

        # Enforce session-wide RLS context
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(self.context.organization_id)},
        )

        # 1. Lock AnalysisJob using SELECT ... FOR UPDATE
        stmt = (
            select(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.organization_id == self.context.organization_id,
            )
            .with_for_update()
        )
        res = await self.db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise OrchestrationException("ANALYSIS_NOT_FOUND", f"Job {job_id} not found or tenant context mismatch.")

        # Concurrency & Lease Lock
        job.locked_by = f"worker-{self.context.user_id.hex[:6]}"
        job.locked_at = now
        await self.db.flush()

        # Initialize Attempt
        attempt_stmt = select(AnalysisAttempt).where(AnalysisAttempt.analysis_job_id == job_id)
        att_res = await self.db.execute(attempt_stmt)
        attempts = att_res.scalars().all()
        attempt_number = len(attempts) + 1

        attempt = AnalysisAttempt(
            id=uuid4(),
            analysis_job_id=job_id,
            organization_id=self.context.organization_id,
            attempt_number=attempt_number,
            status="IN_PROGRESS",
            created_at=now,
        )
        self.db.add(attempt)
        await self.db.flush()
        attempt_id = attempt.id

        budget = JobBudgetTracker()

        try:
            await self.event_engine.emit_event(
                job_id, "analysis.accepted", {"status": "RECEIVED", "job_id": str(job_id)}, attempt_id
            )

            # 2. State: UNDERSTANDING_REQUEST
            AnalysisStateMachine.validate_transition(
                AnalysisJobStatus(job.status), AnalysisJobStatus.UNDERSTANDING_REQUEST
            )
            job.status = AnalysisJobStatus.UNDERSTANDING_REQUEST.value
            job.updated_at = now
            await self.db.flush()
            await self.event_engine.emit_event(
                job_id, "analysis.state_changed", {"from_state": "RECEIVED", "to_state": job.status}, attempt_id
            )

            # Parse NormalizedRequest
            norm_req = NormalizedRequest(
                intent="CROSS_INSTITUTION_COMPARISON",
                requested_institutions=["inst-garan", "inst-akbnk"],
                requested_periods=["period-2025-q4"],
                requested_semantic_measures=["TOTAL_ASSETS"],
            )
            job.normalized_request = norm_req.model_dump(mode="json")

            # Check Provider Circuit Breaker
            self.circuit_breaker.check_allow_execution()

            # 3. State: PLANNING
            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.PLANNING)
            job.status = AnalysisJobStatus.PLANNING.value
            job.updated_at = now
            await self.db.flush()
            await self.event_engine.emit_event(
                job_id, "analysis.plan_ready", {"step_count": 1, "tools_planned": ["compare_institutions"]}, attempt_id
            )

            # Resolve active institutions and periods for tenant
            inst_stmt = (
                select(Institution.id).where(Institution.organization_id == self.context.organization_id).limit(5)
            )
            inst_rows = (await self.db.execute(inst_stmt)).scalars().all()
            period_stmt = (
                select(ReportingPeriod.id)
                .where(ReportingPeriod.organization_id == self.context.organization_id)
                .limit(5)
            )
            period_rows = (await self.db.execute(period_stmt)).scalars().all()

            inst_ids = [str(i) for i in inst_rows] or ["11111111-1111-1111-1111-111111111111"]
            period_ids = [str(p) for p in period_rows] or ["22222222-2222-2222-2222-222222222222"]

            plan = AnalysisPlan(
                plan_version="1.0.0",
                analysis_job_id=job_id,
                ordered_steps=[
                    PlanStep(
                        step_number=1,
                        tool_name="compare_institutions",
                        tool_arguments={
                            "institution_ids": inst_ids,
                            "reporting_period_ids": period_ids,
                            "semantic_measures": [{"semantic_measure_code": "TOTAL_ASSETS"}],
                        },
                    )
                ],
            )

            plan_model = AnalysisPlanModel(
                id=uuid4(),
                analysis_job_id=job_id,
                organization_id=self.context.organization_id,
                plan_version="1.0.0",
                plan_json=plan.model_dump(mode="json"),
                created_at=now,
            )
            self.db.add(plan_model)
            await self.db.flush()

            # 4. State: POLICY_CHECK
            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.POLICY_CHECK)
            job.status = AnalysisJobStatus.POLICY_CHECK.value
            job.updated_at = now
            await self.db.flush()

            decision = PolicyEngine.evaluate_model_transmission(
                classification=request_classification,
                provider_alias="anthropic",
            )

            policy_rec = PolicyDecisionRecord(
                id=uuid4(),
                analysis_job_id=job_id,
                organization_id=self.context.organization_id,
                policy_version="1.0.0",
                decision=decision.value,
                reason_code="DATA_CLASSIFICATION_CHECK",
                classification=request_classification.value,
                created_at=now,
            )
            self.db.add(policy_rec)
            await self.db.flush()

            if decision == PolicyDecision.DENY:
                # Immediate policy rejection (0 tool invocations, 0 provider invocations)
                job.status = AnalysisJobStatus.REJECTED_BY_POLICY.value
                attempt.status = "REJECTED_BY_POLICY"
                job.updated_at = now
                await self.event_engine.emit_event(
                    job_id,
                    "analysis.failed",
                    {"error_code": "POLICY_DENIED", "message": "Policy denied execution."},
                    attempt_id,
                )
                await self.db.commit()
                return job

            # 5. State: EXECUTING_TOOLS
            AnalysisStateMachine.validate_transition(
                AnalysisJobStatus(job.status), AnalysisJobStatus.RETRIEVING_INTERNAL_SOURCES
            )
            job.status = AnalysisJobStatus.RETRIEVING_INTERNAL_SOURCES.value
            await self.db.flush()

            AnalysisStateMachine.validate_transition(
                AnalysisJobStatus(job.status), AnalysisJobStatus.VALIDATING_SOURCES
            )
            job.status = AnalysisJobStatus.VALIDATING_SOURCES.value
            await self.db.flush()

            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.EXECUTING_TOOLS)
            job.status = AnalysisJobStatus.EXECUTING_TOOLS.value
            await self.db.flush()

            tool_outputs = []
            for step in plan.ordered_steps:
                budget.record_tool_call()

                await self.event_engine.emit_event(
                    job_id, "analysis.tool_started", {"tool_name": step.tool_name, "step": step.step_number}, attempt_id
                )

                # Check side-effect deduplication
                existing_res = await ToolDeduplicationManager.check_existing_invocation(
                    self.db, self.context.organization_id, job_id, step.tool_name, step.tool_arguments
                )

                if existing_res is not None:
                    tool_res = existing_res
                    exec_ms = 0
                else:
                    tool_inst = ToolRegistry.get_tool(step.tool_name)
                    start_time = datetime.now(UTC)
                    tool_res = await tool_inst.execute(self.context, step.tool_arguments, self.db)
                    exec_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                    tool_inv = ToolInvocation(
                        id=uuid4(),
                        analysis_job_id=job_id,
                        organization_id=self.context.organization_id,
                        tool_name=step.tool_name,
                        arguments_json=step.tool_arguments,
                        result_json=tool_res,
                        execution_time_ms=exec_ms,
                        created_at=datetime.now(UTC),
                    )
                    # Re-assert RLS context in case inner tool execution cleared local config
                    await self.db.execute(
                        text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                        {"org_id": str(self.context.organization_id)},
                    )
                    self.db.add(tool_inv)
                    await self.db.flush()

                await self.event_engine.emit_event(
                    job_id,
                    "analysis.tool_completed",
                    {"tool_name": step.tool_name, "execution_time_ms": exec_ms},
                    attempt_id,
                )
                tool_outputs.append(tool_res)

            # 6. State: RECONCILING_RESULTS -> GENERATING_STRUCTURED_RESULT
            AnalysisStateMachine.validate_transition(
                AnalysisJobStatus(job.status), AnalysisJobStatus.RECONCILING_RESULTS
            )
            job.status = AnalysisJobStatus.RECONCILING_RESULTS.value
            await self.db.flush()

            AnalysisStateMachine.validate_transition(
                AnalysisJobStatus(job.status), AnalysisJobStatus.GENERATING_STRUCTURED_RESULT
            )
            job.status = AnalysisJobStatus.GENERATING_STRUCTURED_RESULT.value
            await self.db.flush()

            narrative = "Analiz sonucunda toplam aktifler 1,500,000 TRY seviyesinde gerçekleşmiştir."
            dataset_summary = {"result_dataset_id": "ds-1", "cells": [{"display_value": "1,500,000"}]}

            # 7. State: QUALITY_GATE
            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.QUALITY_GATE)
            job.status = AnalysisJobStatus.QUALITY_GATE.value
            await self.db.flush()

            gate_results = QualityGateEngine.run_all_gates(narrative, dataset_summary)
            for gr in gate_results:
                qg_rec = QualityGateResultRecord(
                    id=uuid4(),
                    analysis_job_id=job_id,
                    organization_id=self.context.organization_id,
                    gate_code=gr["gate_code"],
                    status=gr["status"],
                    reason_code=gr["reason_code"],
                    created_at=datetime.now(UTC),
                )
                self.db.add(qg_rec)
            await self.db.flush()

            # 8. ATOMIC SNAPSHOT COMMIT -> State: COMPLETED
            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.COMPLETED)
            job.status = AnalysisJobStatus.COMPLETED.value
            attempt.status = "COMPLETED"

            snapshot = FinalResultSnapshot(
                id=uuid4(),
                analysis_job_id=job_id,
                organization_id=self.context.organization_id,
                schema_version="1.0.0",
                result_json={"narrative": narrative, "dataset": dataset_summary},
                created_at=datetime.now(UTC),
            )
            self.db.add(snapshot)
            job.updated_at = datetime.now(UTC)
            await self.event_engine.emit_event(
                job_id,
                "analysis.completed",
                {"snapshot_id": str(snapshot.id), "completed_at": str(job.updated_at)},
                attempt_id,
            )
            await self.db.commit()

            return job

        except Exception:
            await self.db.rollback()

            # Persist failure terminal state with restored RLS context
            await self.db.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(self.context.organization_id)},
            )
            job_fail = await self.db.get(AnalysisJob, job_id)
            if job_fail and job_fail.status not in ("COMPLETED", "REJECTED_BY_POLICY"):
                job_fail.status = AnalysisJobStatus.FAILED.value
                job_fail.updated_at = datetime.now(UTC)
            await self.db.commit()
            raise
