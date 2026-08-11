import os

import pytest
from app.core.config import DEFAULT_DEV_MIGRATION_URL
from app.db.session import ApiSessionLocal
from app.orchestration.circuit_breaker import DistributedCircuitBreaker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

owner_url = os.environ.get("TEST_OWNER_DATABASE_URL", DEFAULT_DEV_MIGRATION_URL)
owner_engine = create_async_engine(owner_url)


@pytest.mark.asyncio
async def test_distributed_circuit_breaker_postgres_state_transitions():
    """Verify PostgreSQL-backed record_provider_failure and record_provider_success transitions."""
    cb = DistributedCircuitBreaker(
        provider_key="test_anthropic_dist",
        model_alias="finance_analysis_balanced",
        failure_threshold=2,
        cooldown_seconds=10,
    )

    async with owner_engine.begin() as conn:
        await conn.execute(text("DELETE FROM provider_circuit_states WHERE provider_key = 'test_anthropic_dist';"))

    async with ApiSessionLocal() as session:
        # Failure 1 -> CLOSED
        state1 = await cb.record_failure_async(session, is_transient=True)
        assert state1 == "CLOSED"

        # Failure 2 (Threshold reached) -> OPEN
        state2 = await cb.record_failure_async(session, is_transient=True)
        assert state2 == "OPEN"

        # Success -> CLOSED & reset failures
        state3 = await cb.record_success_async(session)
        assert state3 == "CLOSED"

    async with owner_engine.begin() as conn:
        await conn.execute(text("DELETE FROM provider_circuit_states WHERE provider_key = 'test_anthropic_dist';"))
