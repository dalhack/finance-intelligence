from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.core.config import settings
from services.api.app.core.logging import PseudonymizingFormatter
from services.api.app.middleware.execution_context import ExecutionContext


@pytest.mark.unit
def test_config_settings():
    assert settings.PROJECT_NAME == "Finance Intelligence API"
    assert settings.VERSION == "0.1.0"


@pytest.mark.unit
def test_pseudonymization_formatter():
    formatter = PseudonymizingFormatter(salt="test-salt-123")
    hash1 = formatter.pseudonymize("user_id_100")
    hash2 = formatter.pseudonymize("user_id_100")
    hash3 = formatter.pseudonymize("user_id_200")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 16


@pytest.mark.unit
def test_execution_context_immutability():
    u_id = uuid4()
    o_id = uuid4()
    m_id = uuid4()

    ctx = ExecutionContext(
        authenticated_user_id=u_id,
        active_organization_id=o_id,
        membership_id=m_id,
        roles=["ANALYST"],
        permissions=["read_facts"],
        request_id="req_123",
        correlation_id="corr_123",
        authentication_method="test",
        environment="test",
    )

    assert ctx.authenticated_user_id == u_id
    assert ctx.active_organization_id == o_id

    with pytest.raises(ValidationError):
        ctx.roles = ["ADMIN"]  # Immutable frozen Pydantic model check
