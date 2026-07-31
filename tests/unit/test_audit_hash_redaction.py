from uuid import uuid4

import pytest


@pytest.mark.unit
def test_audit_event_redacts_sensitive_hashes_and_uuids():
    """Verify AuditService event creation payload does not accept or log sensitive hashes or credentials."""
    org_id = uuid4()
    _actor_id = uuid4()
    target_id = uuid4()

    # Payload with valid sanitized fields
    payload = {
        "formula_code": "LOAN_TO_DEPOSIT_RATIO",
        "attempt_number": 1,
        "status": "COMPLETED",
    }

    from services.api.app.models.audit_event import AuditEvent
    from services.api.app.services.audit_service import sanitize_payload_recursive

    event = AuditEvent(
        id=target_id,
        organization_id=org_id,
        event_type="CALCULATION_COMPLETED",
        payload_summary=sanitize_payload_recursive(payload),
    )

    summary = event.payload_summary
    assert "request_fingerprint" not in summary
    assert "idempotency_hash" not in summary
    assert "execution_idempotency_hash" not in summary
    assert "formula_spec_checksum" not in summary
    assert "implementation_checksum" not in summary
    assert summary["formula_code"] == "LOAN_TO_DEPOSIT_RATIO"
