from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.ingestion_job import IngestionJob
from app.models.upload_session import UploadSession
from app.services.state_machine import InvalidStateTransitionException, StateMachineService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_state_machine_invalid_transition_raises_exception():
    db = AsyncMock()
    db.add = MagicMock()
    job = IngestionJob(id=uuid4(), organization_id=uuid4(), status="PENDING_UPLOAD")
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute.return_value = mock_res

    with pytest.raises(InvalidStateTransitionException) as exc_info:
        await StateMachineService.transition_job(db, job.id, "PENDING_UPLOAD", "COMPLETED", job.organization_id)

    assert "forbidden" in str(exc_info.value.message)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_state_machine_upload_session_valid_transition():
    db = AsyncMock()
    db.add = MagicMock()
    session_id = uuid4()
    org_id = uuid4()
    session = UploadSession(id=session_id, organization_id=org_id, status="PENDING_UPLOAD")
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = session
    db.execute.return_value = mock_res

    updated_session = await StateMachineService.transition_upload_session(
        db, session_id, "PENDING_UPLOAD", "UPLOADED", org_id
    )
    assert updated_session.status == "UPLOADED"
