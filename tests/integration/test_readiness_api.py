import os

import httpx
import pytest
from app.db.session import get_system_db_session
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")


@pytest.mark.asyncio
async def test_health_endpoint_returns_pass():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "pass"


class ReadinessSessionWrapper:
    def __init__(self, session):
        self._session = session

    async def execute(self, statement, *args, **kwargs):
        sql_str = str(statement)
        if "alembic_version" in sql_str:

            class MockResult:
                def fetchone(self):
                    return ("031_analysis_job_claim_authority",)

            return MockResult()
        return await self._session.execute(statement, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.mark.asyncio
async def test_readiness_endpoint_db_ready():
    async def override_get_system_db_session():
        engine = create_async_engine(API_USER_URL)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            try:
                yield ReadinessSessionWrapper(session)
            finally:
                await session.close()
        await engine.dispose()

    app.dependency_overrides[get_system_db_session] = override_get_system_db_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/ready")
            print("READINESS RESPONSE:", res.json())
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "pass"
    finally:
        app.dependency_overrides.clear()
