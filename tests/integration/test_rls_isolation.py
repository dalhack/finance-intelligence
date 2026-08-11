import pytest
from app.db.tenant_context import tenant_transaction_context


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_context_fail_closed_on_empty_org():
    """
    Tests that initializing tenant transaction context with empty/null organization_id fails closed.
    """

    class MockSession:
        pass

    session = MockSession()
    with pytest.raises(ValueError, match="organization_id cannot be null or empty"):
        async with tenant_transaction_context(session, None):
            pass
