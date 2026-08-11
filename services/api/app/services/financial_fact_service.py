import hashlib
from datetime import UTC, datetime
from uuid import UUID

from app.models.candidate_evidence import CandidateEvidence
from app.models.document_version import DocumentVersion
from app.models.fact_review_decision import FactReviewDecision
from app.models.financial_fact import FinancialFact
from app.models.financial_fact_candidate import FinancialFactCandidate
from app.models.metric_definition import MetricDefinition
from app.services.audit_service import AuditService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialFactService:
    @staticmethod
    async def _verify_evidence_and_basis(
        db: AsyncSession,
        organization_id: UUID,
        candidate: FinancialFactCandidate,
        target_reporting_basis: str | None = None,
    ) -> str:
        """Verify candidate has valid DB evidence and a resolved SOLO/CONSOLIDATED reporting basis."""
        # 1. Evidence Completeness & Lineage Check
        ev_res = await db.execute(
            select(CandidateEvidence).where(
                CandidateEvidence.organization_id == organization_id,
                CandidateEvidence.candidate_id == candidate.id,
            )
        )
        evidences = ev_res.scalars().all()
        if not evidences:
            raise ValueError("EVIDENCE_INCOMPLETE: Candidate evidence missing from database")

        for ev in evidences:
            if ev.organization_id != organization_id:
                raise ValueError("EVIDENCE_SOURCE_MISMATCH: Cross-tenant evidence attempt rejected")

            if ev.source_document_version_id != candidate.source_document_version_id:
                raise ValueError("EVIDENCE_LINEAGE_INCOMPLETE: Candidate evidence document version mismatch")

            doc_ver_res = await db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.id == ev.source_document_version_id,
                    DocumentVersion.organization_id == organization_id,
                )
            )
            doc_ver = doc_ver_res.scalar_one_or_none()
            if not doc_ver or doc_ver.document_id != candidate.source_document_id:
                raise ValueError("EVIDENCE_LINEAGE_INCOMPLETE: Document lineage mismatch")

            # Format-based structural coordinate check from verified detected_mime_type
            mime = (doc_ver.detected_mime_type or doc_ver.declared_mime_type or "").lower()
            if "pdf" in mime:
                if ev.page_number is None or ev.page_number < 1:
                    raise ValueError("EVIDENCE_LINEAGE_INCOMPLETE: PDF evidence requires valid page_number >= 1")
                bbox = ev.bounding_box or {}
                if not isinstance(bbox, dict) or not all(k in bbox for k in ("x0", "y0", "x1", "y1")):
                    raise ValueError(
                        "EVIDENCE_LINEAGE_INCOMPLETE: PDF evidence requires valid bounding_box coordinates"
                    )
            elif "sheet" in mime or "excel" in mime or "spreadsheet" in mime:
                if (ev.row_index is None or ev.row_index < 0) or (ev.column_index is None or ev.column_index < 0):
                    raise ValueError(
                        "EVIDENCE_LINEAGE_INCOMPLETE: XLSX evidence requires non-negative row_index and column_index"
                    )
            elif "csv" in mime:
                if (ev.row_index is None or ev.row_index < 0) or (ev.column_index is None or ev.column_index < 0):
                    raise ValueError(
                        "EVIDENCE_LINEAGE_INCOMPLETE: CSV evidence requires non-negative row_index and column_index"
                    )

        # 2. Reporting Basis Check
        effective_basis = target_reporting_basis or candidate.detected_reporting_basis
        if not effective_basis or effective_basis.upper() == "UNKNOWN":
            raise ValueError(
                "REPORTING_BASIS_REQUIRED: UNKNOWN reporting basis cannot be approved without explicit selection"
            )

        if effective_basis.upper() not in {"SOLO", "CONSOLIDATED"}:
            raise ValueError(f"UNSUPPORTED_REPORTING_BASIS: Invalid basis '{effective_basis}'")

        return effective_basis.upper()

    @staticmethod
    async def approve_candidate(
        db: AsyncSession,
        organization_id: UUID,
        candidate_id: UUID,
        reviewer_user_id: UUID,
        target_reporting_basis: str | None = None,
        notes: str | None = None,
    ) -> tuple[FinancialFactCandidate, FinancialFact]:
        """Approve candidate and create immutable FinancialFact in 1 atomic database transaction.

        Fails with FACT_VALUE_CONFLICT if an active fact with a different value exists for the natural key.
        """
        cand_res = await db.execute(
            select(FinancialFactCandidate)
            .where(
                FinancialFactCandidate.id == candidate_id,
                FinancialFactCandidate.organization_id == organization_id,
            )
            .with_for_update()
        )
        candidate = cand_res.scalar_one_or_none()

        if not candidate:
            raise ValueError("CANDIDATE_NOT_FOUND")

        if candidate.review_status != "PENDING":
            raise ValueError("CANDIDATE_ALREADY_REVIEWED")

        if candidate.normalized_value is None:
            raise ValueError("CANNOT_APPROVE_UNPARSED_VALUE")

        if not candidate.metric_definition_id:
            raise ValueError("CANNOT_APPROVE_WITHOUT_METRIC_DEFINITION")

        # Verify evidence & reporting basis
        effective_basis = await FinancialFactService._verify_evidence_and_basis(
            db, organization_id, candidate, target_reporting_basis
        )

        # 1. Fetch metric definition
        metric_res = await db.execute(
            select(MetricDefinition).where(MetricDefinition.id == candidate.metric_definition_id)
        )
        metric_def = metric_res.scalar_one()

        # 2. Check existing fact by Natural Key
        existing_res = await db.execute(
            select(FinancialFact)
            .where(
                FinancialFact.organization_id == organization_id,
                FinancialFact.institution_id == candidate.institution_id,
                FinancialFact.reporting_period_id == candidate.reporting_period_id,
                FinancialFact.metric_definition_id == candidate.metric_definition_id,
                FinancialFact.reporting_basis == effective_basis,
                FinancialFact.currency == candidate.normalized_currency,
                FinancialFact.unit == candidate.normalized_unit,
                FinancialFact.valid_to.is_(None),
            )
            .with_for_update()
        )
        existing_fact = existing_res.scalar_one_or_none()

        now_utc = datetime.now(UTC)

        if existing_fact:
            if existing_fact.normalized_value == candidate.normalized_value:
                # Corroborating evidence: update review metadata on candidate, return existing fact
                candidate.review_status = "APPROVED"
                candidate.validation_status = "APPROVED"
                candidate.detected_reporting_basis = effective_basis
                db.add(candidate)

                decision = FactReviewDecision(
                    organization_id=organization_id,
                    candidate_id=candidate.id,
                    reviewer_user_id=reviewer_user_id,
                    decision="APPROVED",
                    decision_notes=notes or "Corroborating candidate approved",
                    created_fact_id=existing_fact.id,
                )
                db.add(decision)
                await db.commit()
                return candidate, existing_fact
            else:
                # Conflict: Record conflict target persistence on candidate and FAIL approval
                val_hash = hashlib.sha256(str(existing_fact.normalized_value).encode()).hexdigest()
                candidate.conflicting_fact_id = existing_fact.id
                candidate.conflict_detected_at = now_utc
                candidate.conflict_reason = "VALUE_MISMATCH"
                candidate.detected_value_hash = val_hash
                candidate.validation_status = "CONFLICTED"
                db.add(candidate)
                await db.commit()
                raise ValueError(
                    "FACT_VALUE_CONFLICT: Active fact with different value exists. Use explicit revision approval."
                )

        # 3. Create new verified FinancialFact
        fact = FinancialFact(
            organization_id=organization_id,
            institution_id=candidate.institution_id,
            reporting_period_id=candidate.reporting_period_id,
            metric_definition_id=metric_def.id,
            metric_code=metric_def.metric_code,
            value=candidate.parsed_decimal_value or candidate.normalized_value,
            currency=candidate.normalized_currency,
            unit=candidate.normalized_unit,
            scale=candidate.normalized_scale,
            normalized_value=candidate.normalized_value,
            reporting_basis=effective_basis,
            source_candidate_id=candidate.id,
            source_document_id=candidate.source_document_id,
            source_location=candidate.source_location,
            extraction_method=candidate.extraction_method,
            confidence_score=candidate.confidence_score,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=reviewer_user_id,
            verified_at=now_utc,
            supersedes_fact_id=None,
            valid_from=now_utc,
            value_origin=candidate.value_origin or "SOURCE_REPORTED",
        )
        db.add(fact)
        await db.flush()

        # Update candidate status
        candidate.review_status = "APPROVED"
        candidate.validation_status = "APPROVED"
        candidate.detected_reporting_basis = effective_basis
        db.add(candidate)

        # Record review decision
        decision = FactReviewDecision(
            organization_id=organization_id,
            candidate_id=candidate.id,
            reviewer_user_id=reviewer_user_id,
            decision="APPROVED",
            decision_notes=notes,
            created_fact_id=fact.id,
        )
        db.add(decision)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="FACT_CANDIDATE_APPROVED",
            target_type="financial_fact_candidate",
            target_id=candidate.id,
            actor_id=reviewer_user_id,
            payload={
                "created_fact_id": str(fact.id),
                "metric_code": fact.metric_code,
            },
        )

        await db.commit()
        return candidate, fact

    @staticmethod
    async def approve_candidate_as_revision(
        db: AsyncSession,
        organization_id: UUID,
        candidate_id: UUID,
        expected_existing_fact_id: UUID,
        reviewer_user_id: UUID,
        target_reporting_basis: str | None = None,
        notes: str | None = None,
    ) -> tuple[FinancialFactCandidate, FinancialFact]:
        """Explicit revision approval: Supersedes targeted active fact and creates new verified FinancialFact."""
        cand_res = await db.execute(
            select(FinancialFactCandidate)
            .where(
                FinancialFactCandidate.id == candidate_id,
                FinancialFactCandidate.organization_id == organization_id,
            )
            .with_for_update()
        )
        candidate = cand_res.scalar_one_or_none()

        if not candidate:
            raise ValueError("CANDIDATE_NOT_FOUND")

        if candidate.review_status != "PENDING" and candidate.validation_status != "CONFLICTED":
            raise ValueError("CANDIDATE_ALREADY_REVIEWED")

        if candidate.normalized_value is None or not candidate.metric_definition_id:
            raise ValueError("CANNOT_APPROVE_INVALID_CANDIDATE")

        if candidate.conflicting_fact_id and candidate.conflicting_fact_id != expected_existing_fact_id:
            raise ValueError("REVISION_TARGET_MISMATCH: Target fact ID does not match candidate conflict target.")

        effective_basis = await FinancialFactService._verify_evidence_and_basis(
            db, organization_id, candidate, target_reporting_basis
        )

        # Single Query Row Lock on expected active fact
        old_fact_res = await db.execute(
            select(FinancialFact)
            .where(
                FinancialFact.id == expected_existing_fact_id,
                FinancialFact.organization_id == organization_id,
                FinancialFact.valid_to.is_(None),
            )
            .with_for_update()
        )
        old_fact = old_fact_res.scalar_one_or_none()

        if not old_fact:
            raise ValueError("REVISION_CONCURRENCY_CONFLICT: Expected active fact not found or already invalidated.")

        # Natural Key Matching (7 fields)
        if (
            old_fact.organization_id != organization_id
            or old_fact.institution_id != candidate.institution_id
            or old_fact.reporting_period_id != candidate.reporting_period_id
            or old_fact.metric_definition_id != candidate.metric_definition_id
            or old_fact.reporting_basis != effective_basis
            or old_fact.currency != candidate.normalized_currency
            or old_fact.unit != candidate.normalized_unit
        ):
            raise ValueError("REVISION_NATURAL_KEY_MISMATCH: Revision target does not match candidate natural key.")

        # Value Unchanged Check
        if old_fact.normalized_value == candidate.normalized_value:
            raise ValueError("REVISION_VALUE_UNCHANGED: Candidate normalized value is identical to active fact value.")

        now_utc = datetime.now(UTC)

        # Close valid_to on old fact
        old_fact.valid_to = now_utc
        db.add(old_fact)

        metric_res = await db.execute(
            select(MetricDefinition).where(MetricDefinition.id == candidate.metric_definition_id)
        )
        metric_def = metric_res.scalar_one()

        # Create new superseding FinancialFact
        new_fact = FinancialFact(
            organization_id=organization_id,
            institution_id=candidate.institution_id,
            reporting_period_id=candidate.reporting_period_id,
            metric_definition_id=metric_def.id,
            metric_code=metric_def.metric_code,
            value=candidate.parsed_decimal_value or candidate.normalized_value,
            currency=candidate.normalized_currency,
            unit=candidate.normalized_unit,
            scale=candidate.normalized_scale,
            normalized_value=candidate.normalized_value,
            reporting_basis=effective_basis,
            source_candidate_id=candidate.id,
            source_document_id=candidate.source_document_id,
            source_location=candidate.source_location,
            extraction_method=candidate.extraction_method,
            confidence_score=candidate.confidence_score,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=reviewer_user_id,
            verified_at=now_utc,
            supersedes_fact_id=old_fact.id,
            valid_from=now_utc,
            value_origin=candidate.value_origin or "SOURCE_REPORTED",
        )
        db.add(new_fact)
        await db.flush()

        candidate.review_status = "APPROVED"
        candidate.validation_status = "APPROVED"
        candidate.detected_reporting_basis = effective_basis
        db.add(candidate)

        decision = FactReviewDecision(
            organization_id=organization_id,
            candidate_id=candidate.id,
            reviewer_user_id=reviewer_user_id,
            decision="APPROVED",
            decision_notes=notes or f"Explicit revision superseding fact {old_fact.id}",
            created_fact_id=new_fact.id,
        )
        db.add(decision)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="FINANCIAL_FACT_SUPERSEDED",
            target_type="financial_fact",
            target_id=old_fact.id,
            actor_id=reviewer_user_id,
            payload={
                "superseded_by_fact_id": str(new_fact.id),
                "candidate_id": str(candidate.id),
            },
        )

        await db.commit()
        return candidate, new_fact

    @staticmethod
    async def reject_candidate(
        db: AsyncSession,
        organization_id: UUID,
        candidate_id: UUID,
        reviewer_user_id: UUID,
        reason_code: str,
        notes: str | None = None,
    ) -> FinancialFactCandidate:
        """Reject candidate and record audit decision in 1 transaction."""
        cand_res = await db.execute(
            select(FinancialFactCandidate)
            .where(
                FinancialFactCandidate.id == candidate_id,
                FinancialFactCandidate.organization_id == organization_id,
            )
            .with_for_update()
        )
        candidate = cand_res.scalar_one_or_none()

        if not candidate:
            raise ValueError("CANDIDATE_NOT_FOUND")

        if candidate.review_status != "PENDING":
            raise ValueError("CANDIDATE_ALREADY_REVIEWED")

        candidate.review_status = "REJECTED"
        candidate.validation_status = "REJECTED"
        db.add(candidate)

        decision = FactReviewDecision(
            organization_id=organization_id,
            candidate_id=candidate.id,
            reviewer_user_id=reviewer_user_id,
            decision="REJECTED",
            rejection_reason_code=reason_code,
            decision_notes=notes,
        )
        db.add(decision)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="FACT_CANDIDATE_REJECTED",
            target_type="financial_fact_candidate",
            target_id=candidate.id,
            actor_id=reviewer_user_id,
            payload={
                "reason_code": reason_code,
            },
        )

        await db.commit()
        return candidate
