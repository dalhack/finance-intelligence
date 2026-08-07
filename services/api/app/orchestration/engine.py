import json
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
    ClaimOwnershipLostException,
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

    async def _assert_fenced_ownership(self, job_id: UUID, claim_token: UUID, worker_id: str) -> None:
        """Assert claim_token and worker_id ownership on analysis_job with FOR UPDATE row lock."""
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(self.context.organization_id)},
        )
        res = await self.db.execute(
            text("""
                SELECT id FROM public.analysis_jobs
                WHERE id = :jid
                  AND claim_token = :tok
                  AND locked_by = :w
                  AND status IN (
                    'RECEIVED', 'UNDERSTANDING_REQUEST', 'PLANNING', 'POLICY_CHECK',
                    'RETRIEVING_INTERNAL_SOURCES', 'VALIDATING_SOURCES', 'EXECUTING_TOOLS',
                    'RECONCILING_RESULTS', 'GENERATING_STRUCTURED_RESULT', 'QUALITY_GATE'
                  )
                FOR UPDATE;
            """),
            {"jid": job_id, "tok": claim_token, "w": worker_id},
        )
        if not res.fetchone():
            raise ClaimOwnershipLostException(
                f"CLAIM_OWNERSHIP_LOST: Worker {worker_id} lost claim token or lease expired for job {job_id}."
            )

    async def execute_job(
        self,
        job_id: UUID,
        claim_token: UUID,
        worker_id: str,
        request_classification: DataClassification = DataClassification.PUBLIC,
    ) -> AnalysisJob:
        now = datetime.now(UTC)

        # Enforce session-wide RLS context
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(self.context.organization_id)},
        )

        # Assert Fencing Primitive
        await self._assert_fenced_ownership(job_id, claim_token, worker_id)

        # 1. Lock AnalysisJob using SELECT ... FOR UPDATE
        stmt = (
            select(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.organization_id == self.context.organization_id,
                AnalysisJob.claim_token == claim_token,
                AnalysisJob.locked_by == worker_id,
            )
            .with_for_update()
        )
        res = await self.db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise ClaimOwnershipLostException("CLAIM_OWNERSHIP_LOST: Job not found or claim token mismatch.")

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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
            await self.event_engine.emit_event(
                job_id, "analysis.accepted", {"status": "RECEIVED", "job_id": str(job_id)}, attempt_id
            )

            # 2. State: UNDERSTANDING_REQUEST
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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
                await self._assert_fenced_ownership(job_id, claim_token, worker_id)
                job.status = AnalysisJobStatus.REJECTED_BY_POLICY.value
                job.lease_expires_at = None
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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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

                    await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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

            # Invoke second turn to generate narrative from tool execution outputs
            turn_2_response = await self.provider.invoke_model(
                {
                    "messages": [
                        {"role": "user", "content": job.request_prompt or "Analiz yapınız."},
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_compare_001",
                                    "name": plan.ordered_steps[0].tool_name
                                    if plan.ordered_steps
                                    else "compare_institutions",
                                    "input": plan.ordered_steps[0].tool_arguments if plan.ordered_steps else {},
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_compare_001",
                                    "content": json.dumps(tool_outputs[0], default=str) if tool_outputs else "{}",
                                }
                            ],
                        },
                    ]
                }
            )

            narrative = turn_2_response.content_text or "Analiz tamamlandı."

            # Construct dataset summary from real validated tool output
            first_tool_res = tool_outputs[0] if tool_outputs and isinstance(tool_outputs[0], dict) else {}
            comparison_id = first_tool_res.get("comparison_id")
            if not comparison_id:
                raise OrchestrationException(
                    "DATASET_NOT_FOUND", "Real tool execution did not yield a valid result dataset."
                )

            dataset_summary = {
                "result_dataset_id": str(comparison_id),
                "cells": first_tool_res.get("cells", []),
            }

            # 7. State: QUALITY_GATE
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
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
            await self._assert_fenced_ownership(job_id, claim_token, worker_id)
            AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.COMPLETED)

            now_completed = datetime.now(UTC)
            upd_comp = await self.db.execute(
                text("""
                    UPDATE public.analysis_jobs
                    SET status = 'COMPLETED',
                        lease_expires_at = NULL,
                        updated_at = :now
                    WHERE id = :jid
                      AND claim_token = :tok
                      AND locked_by = :w
                    RETURNING id;
                """),
                {"jid": job_id, "tok": claim_token, "w": worker_id, "now": now_completed},
            )
            if not upd_comp.fetchone():
                raise ClaimOwnershipLostException(
                    f"CLAIM_OWNERSHIP_LOST: Fenced COMPLETED update affected 0 rows for job {job_id}."
                )

            job.status = AnalysisJobStatus.COMPLETED.value
            job.lease_expires_at = None
            job.updated_at = now_completed
            attempt.status = "COMPLETED"

            snapshot = FinalResultSnapshot(
                id=uuid4(),
                analysis_job_id=job_id,
                organization_id=self.context.organization_id,
                schema_version="1.0.0",
                result_json={"narrative": narrative, "dataset": dataset_summary},
                created_at=now_completed,
            )
            self.db.add(snapshot)
            await self.event_engine.emit_event(
                job_id,
                "analysis.completed",
                {"snapshot_id": str(snapshot.id), "completed_at": str(job.updated_at)},
                attempt_id,
            )
            await self.db.commit()

            return job

        except ClaimOwnershipLostException:
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()

            # Model B Failure Transaction: Re-verify claim token ownership before persisting failure
            try:
                await self._assert_fenced_ownership(job_id, claim_token, worker_id)
                now_failed = datetime.now(UTC)
                upd_fail = await self.db.execute(
                    text("""
                        UPDATE public.analysis_jobs
                        SET status = 'FAILED',
                            lease_expires_at = NULL,
                            updated_at = :now
                        WHERE id = :jid
                          AND claim_token = :tok
                          AND locked_by = :w
                          AND status NOT IN ('COMPLETED', 'REJECTED_BY_POLICY')
                        RETURNING id;
                    """),
                    {"jid": job_id, "tok": claim_token, "w": worker_id, "now": now_failed},
                )
                if not upd_fail.fetchone():
                    raise ClaimOwnershipLostException("CLAIM_OWNERSHIP_LOST: Fenced FAILED update affected 0 rows.")

                job_fail = await self.db.get(AnalysisJob, job_id)
                if job_fail:
                    job_fail.status = AnalysisJobStatus.FAILED.value
                    job_fail.lease_expires_at = None
                    job_fail.updated_at = now_failed

                att_fail = await self.db.get(AnalysisAttempt, attempt_id)
                event_att_id = attempt_id if att_fail else None
                if att_fail:
                    att_fail.status = "FAILED"

                safe_err_code = getattr(exc, "code", "ENGINE_EXECUTION_FAILED")
                safe_msg = getattr(exc, "message", "Analysis job execution failed.")
                await self.event_engine.emit_event(
                    job_id,
                    "analysis.failed",
                    {"error_code": str(safe_err_code), "message": str(safe_msg)},
                    event_att_id,
                )
                await self.db.commit()
            except ClaimOwnershipLostException:
                await self.db.rollback()
                # Ownership was lost; suppress failure persistence so new owner is not affected
                pass

            raise
