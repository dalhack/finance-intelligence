import json
import os
import subprocess
import urllib.request
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.main import app
from services.api.app.models.membership import Membership
from services.api.app.models.organization import Organization
from services.api.app.models.role import Role
from services.api.app.models.user import User


def obtain_staging_firebase_id_token() -> tuple[str, str]:
    """Obtain a real signed Firebase ID Token for fi-staging-test-user-2a1b@finance-intel.internal."""
    secret = (
        subprocess.check_output(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "1",
                "--secret=fi-firebase-staging-auth-test-password",
                "--project=finance-intel-staging-8f2a",
            ]
        )
        .decode("utf-8")
        .strip()
    )
    api_key = "AIzaSyB6GVuWJ4xkH1rf9DUx2QPk1aHn10UT8xA"
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = json.dumps(
        {
            "email": "fi-staging-test-user-2a1b@finance-intel.internal",
            "password": secret,
            "returnSecureToken": True,
        }
    ).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        id_token = res["idToken"]
        uid = res["localId"]
        return id_token, uid


@pytest.mark.integration
@pytest.mark.live_acceptance
@pytest.mark.asyncio
async def test_live_firebase_authentication_and_auth_context_resolution():
    """Live acceptance test: real signed Firebase token -> production verifier -> resolve_auth_context -> ExecutionContext."""
    id_token, firebase_uid = obtain_staging_firebase_id_token()

    assert id_token is not None and len(id_token) > 100
    assert firebase_uid == "rjGDaHght0UbcxcBALew186w4Qx1"

    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    org_authorized_id = uuid4()
    org_forbidden_id = uuid4()
    user_id = uuid4()
    mem_id = uuid4()

    # 1. Seed user and membership in PostgreSQL
    async with OwnerSession() as db_owner:
        org_auth = Organization(
            id=org_authorized_id, name="Staging Auth Org", slug=f"stg-auth-{org_authorized_id.hex[:6]}"
        )
        org_forb = Organization(
            id=org_forbidden_id, name="Staging Forb Org", slug=f"stg-forb-{org_forbidden_id.hex[:6]}"
        )
        db_owner.add_all([org_auth, org_forb])

        res_user = await db_owner.execute(
            text("SELECT id FROM users WHERE external_subject = :sub;"), {"sub": firebase_uid}
        )
        existing_user_id = res_user.scalar()
        if not existing_user_id:
            user = User(
                id=user_id,
                external_subject=firebase_uid,
                identity_provider="firebase",
                display_name="Staging Test User",
                status="active",
            )
            db_owner.add(user)
        else:
            user_id = existing_user_id

        await db_owner.commit()

    async with OwnerSession() as db_owner:
        from app.db.tenant_context import tenant_transaction_context

        async with tenant_transaction_context(db_owner, org_authorized_id):
            mem = Membership(id=mem_id, organization_id=org_authorized_id, user_id=user_id, status="active")
            db_owner.add(mem)
            await db_owner.commit()

        # Retrieve ANALYST role ID
        res = await db_owner.execute(text("SELECT id FROM roles WHERE name = 'ANALYST';"))
        role_id = res.scalar()
        if not role_id:
            role_id = uuid4()
            analyst_role = Role(id=role_id, name="ANALYST", description="Analyst role")
            db_owner.add(analyst_role)
            await db_owner.commit()

        await db_owner.execute(
            text(
                "INSERT INTO public.membership_roles (id, membership_id, role_id, organization_id) "
                "VALUES (:id, :mem_id, :role_id, :org_id);"
            ),
            {"id": uuid4(), "mem_id": mem_id, "role_id": role_id, "org_id": org_authorized_id},
        )
        await db_owner.commit()

    # 2. Production Call (Zero dependency overrides)
    assert len(app.dependency_overrides) == 0, "Dependency overrides MUST be 0 for live acceptance."

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Scenario 1: Valid Token + Valid Organization Membership
        resp1 = await client.post(
            "/api/v1/analyses",
            headers={
                "Authorization": f"Bearer {id_token}",
                "X-Organization-ID": str(org_authorized_id),
            },
            json={"prompt": "Staging real Firebase token acceptance test."},
        )
        assert resp1.status_code == 201
        job_data = resp1.json()
        assert job_data["user_id"] == str(user_id)
        assert job_data["organization_id"] == str(org_authorized_id)

        # Scenario 2: Valid Token + Non-member Organization ID -> 403
        resp2 = await client.post(
            "/api/v1/analyses",
            headers={
                "Authorization": f"Bearer {id_token}",
                "X-Organization-ID": str(org_forbidden_id),
            },
            json={"prompt": "Forbidden org request."},
        )
        assert resp2.status_code == 403

        # Scenario 3: Malformed / Modified Token -> 401
        corrupted_token = id_token[:-5] + "XXXXX"
        resp3 = await client.post(
            "/api/v1/analyses",
            headers={
                "Authorization": f"Bearer {corrupted_token}",
                "X-Organization-ID": str(org_authorized_id),
            },
            json={"prompt": "Corrupted token request."},
        )
        assert resp3.status_code == 401
