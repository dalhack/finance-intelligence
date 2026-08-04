from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.db.session import get_system_db_session
from services.api.app.schemas.common import HealthResponseDTO

router = APIRouter()


@router.get("/health", response_model=HealthResponseDTO)
async def health_check():
    return HealthResponseDTO(status="pass", timestamp=datetime.now(UTC).isoformat())


@router.get("/ready")
async def readiness_check(
    response: Response,
    db: AsyncSession = Depends(get_system_db_session),  # noqa: B008
) -> dict[str, Any]:
    try:
        await db.execute(text("SELECT 1;"))
        alembic_res = await db.execute(text("SELECT version_num FROM alembic_version;"))
        row = alembic_res.fetchone()
        if not row or row[0] not in [
            "004_revoke_app_user",
            "005_worker_claim_downgrade",
            "006_claim_tokens",
            "007_drop_legacy_overload",
            "008_facts_and_envelope",
            "009_facts_integrity",
            "010_fact_revision_uniqueness",
            "011_calculation_engine",
            "012_calc_correctness",
            "013_calc_checksum_lineage",
            "014_calc_identity_evidence",
            "015_sec_context_calc_integrity",
            "016_traceability_integrity_repair",
            "017_comparison_dataset",
            "018_comparison_dataset_correctness",
            "019_comparison_semantics_and_snapshot_integrity",
            "020_ai_orchestration_foundation",
            "022_model_provider_and_analysis_events",
            "023_analysis_clarification_workflow",
            "024_maintenance_scheduler_and_operational_resilience",
            "025_distributed_provider_circuit_breaker",
            "026_public_schema_acl_hardening",
        ]:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return {"status": "fail", "timestamp": datetime.now(UTC).isoformat()}

        await db.execute(text("SELECT 1 FROM organizations LIMIT 1;"))
        return {"status": "pass", "timestamp": datetime.now(UTC).isoformat()}

    except Exception:  # noqa: BLE001
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "fail", "timestamp": datetime.now(UTC).isoformat()}
