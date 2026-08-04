from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.core.config import settings
from services.api.app.db.tenant_context import tenant_transaction_context
from services.api.app.dependencies import get_optional_execution_context
from services.api.app.middleware.execution_context import ExecutionContext

# 1. API Role Engine & Session Factory (db_api_user)
api_engine = create_async_engine(
    settings.effective_api_database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

ApiSessionLocal = async_sessionmaker(
    bind=api_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 2. Worker Role Engine & Session Factory (db_ingestion_worker)
worker_engine = create_async_engine(
    settings.effective_worker_database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

WorkerSessionLocal = async_sessionmaker(
    bind=worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 3. Maintenance Role Engine & Session Factory (db_maintenance_worker)
maintenance_engine = create_async_engine(
    settings.effective_maintenance_database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

MaintenanceSessionLocal = async_sessionmaker(
    bind=maintenance_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 4. Bootstrap Role Engine & Session Factory (db_bootstrap)
bootstrap_engine = create_async_engine(
    settings.effective_bootstrap_database_url,
    pool_size=5,
    max_overflow=5,
    echo=settings.DEBUG,
)

BootstrapSessionLocal = async_sessionmaker(
    bind=bootstrap_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session(
    ctx: ExecutionContext | None = Depends(get_optional_execution_context),  # noqa: B008
) -> AsyncGenerator[AsyncSession, None]:
    """Primary DB session provider for FastAPI requests using db_api_user role with transaction-local tenant GUC setting."""
    async with ApiSessionLocal() as session:
        if ctx and ctx.active_organization_id:
            async with tenant_transaction_context(session, ctx.active_organization_id):
                try:
                    yield session
                finally:
                    await session.close()
        else:
            try:
                yield session
            finally:
                await session.close()


async def get_worker_db_session() -> AsyncGenerator[AsyncSession, None]:
    """DB session provider for background ingestion worker using db_ingestion_worker role."""
    async with WorkerSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_maintenance_db_session() -> AsyncGenerator[AsyncSession, None]:
    """DB session provider for background maintenance worker using db_maintenance_worker role."""
    async with MaintenanceSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_bootstrap_db_session() -> AsyncGenerator[AsyncSession, None]:
    """DB session provider for bootstrap membership initialization using db_bootstrap role."""
    async with BootstrapSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
