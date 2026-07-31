from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def tenant_transaction_context(session: AsyncSession, organization_id: UUID) -> AsyncGenerator[None, None]:
    if not organization_id:
        raise ValueError("Tenant context initialization failed: organization_id cannot be null or empty.")

    org_id_str = str(organization_id)
    await session.execute(
        text("SELECT set_config('app.current_organization_id', :org_id, true);"),
        {"org_id": org_id_str},
    )
    try:
        yield
    finally:
        try:
            await session.execute(text("SELECT set_config('app.current_organization_id', '', true);"))
        except Exception:  # noqa: BLE001, S110
            pass
