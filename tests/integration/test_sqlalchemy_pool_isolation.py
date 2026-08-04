import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from services.api.app.db.session import ApiSessionLocal
from services.api.app.db.tenant_context import tenant_transaction_context
from services.api.app.models.document import Document

API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")


@pytest.mark.asyncio
async def test_sqlalchemy_pool_reuse_isolation():
    org_a = uuid4()

    # Session 1: Set Tenant A context inside transaction via ApiSessionLocal
    async with ApiSessionLocal() as session1, tenant_transaction_context(session1, org_a):
        result = await session1.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        setting_val = result.scalar()
        assert setting_val == str(org_a)
        await session1.commit()

    # Session 2: Fresh session reusing the pool connection without setting context
    async with ApiSessionLocal() as session2:
        await session2.execute(text("SELECT set_config('app.current_organization_id', '', true);"))

        res = await session2.execute(__import__("sqlalchemy").select(Document))
        rows = res.scalars().all()
        assert len(rows) == 0
