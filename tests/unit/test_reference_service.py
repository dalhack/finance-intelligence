from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.api.app.models.stored_object import StoredObject
from services.api.app.services.reference_service import ReferenceService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reference_service_release():
    db = AsyncMock()
    org_id = uuid4()
    stored_obj = StoredObject(id=uuid4(), organization_id=org_id, reference_count=2)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = stored_obj
    db.execute.return_value = mock_res

    ref_count = await ReferenceService.release_reference(db, org_id, stored_obj.id)
    assert ref_count == 1
    assert stored_obj.reference_count == 1
