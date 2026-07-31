import os

import httpx
import pytest

from services.api.app.db.session import ApiSessionLocal, get_db_session
from services.api.app.main import app

RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
API_USER_URL = RAW_API_USER_URL if RAW_API_USER_URL else None


@pytest.mark.asyncio
async def test_health_endpoint_returns_pass():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "pass"


@pytest.mark.asyncio
async def test_readiness_endpoint_db_ready():
    async def override_get_db_session():
        async with ApiSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "pass"
    finally:
        app.dependency_overrides.clear()
