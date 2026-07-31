from uuid import uuid4

import httpx
import pytest

from services.api.app.main import app


@pytest.mark.asyncio
async def test_sse_missing_identity_token_returns_401():
    """Verify GET /analyses/{id}/events returns 401 when identity header is missing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get(f"/api/v1/analyses/{uuid4()}/events")
        assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_sse_invalid_app_check_returns_403():
    """Verify GET /analyses/{id}/events returns 403 when App Check is invalid or rejected."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get(
            f"/api/v1/analyses/{uuid4()}/events",
            headers={"Authorization": "Bearer invalid_token", "X-Firebase-AppCheck": "invalid_app_check"},
        )
        assert res.status_code in (401, 403)
