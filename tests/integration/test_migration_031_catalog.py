import os
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_migration_031_catalog_and_security():
    """Verify Migration 031 schema objects, function security, worker ID validation, claim authority, fencing, and lease renewal."""
    owner_url = os.environ.get("TEST_OWNER_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/finance_intelligence_test")
    api_url = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test")

    owner_engine = create_async_engine(owner_url)
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    api_engine = create_async_engine(api_url)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as owner_db:
        # 1. Verify Columns & CHECK constraint
        cols = await owner_db.execute(text(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'analysis_jobs' AND column_name IN ('claim_token', 'recovery_count');"
        ))
        col_map = {row.column_name: (row.data_type, row.is_nullable) for row in cols.fetchall()}
        assert "claim_token" in col_map
        assert "recovery_count" in col_map
        assert col_map["claim_token"][0] == "uuid"
        assert col_map["recovery_count"][0] == "integer"

        # 2. Verify Partial Indexes
        idx_res = await owner_db.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'analysis_jobs' AND indexname IN ('idx_analysis_jobs_fresh', 'idx_analysis_jobs_stale');"
        ))
        idx_names = {r[0] for r in idx_res.fetchall()}
        assert "idx_analysis_jobs_fresh" in idx_names
        assert "idx_analysis_jobs_stale" in idx_names

        # 3. Verify Functions Security & Ownership
        fn_res = await owner_db.execute(text(
            "SELECT proname, prosecdef, proconfig FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND proname IN ('claim_next_analysis_job', 'recover_next_stale_analysis_job', 'renew_analysis_job_lease');"
        ))
        fn_rows = fn_res.fetchall()
        assert len(fn_rows) == 3
        for r in fn_rows:
            assert r.prosecdef is True  # SECURITY DEFINER
            assert "search_path=pg_catalog, public" in (r.proconfig or [])

        # 4. Verify PUBLIC execute revoked & db_api_user execute granted
        acl_res = await owner_db.execute(text(
            "SELECT proname, has_function_privilege('public', p.oid, 'EXECUTE') as public_exec, "
            "has_function_privilege('db_api_user', p.oid, 'EXECUTE') as api_exec "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND proname IN ('claim_next_analysis_job', 'recover_next_stale_analysis_job', 'renew_analysis_job_lease');"
        ))
        for r in acl_res.fetchall():
            assert r.public_exec is False, f"PUBLIC should not have EXECUTE on {r.proname}"
            assert r.api_exec is True, f"db_api_user must have EXECUTE on {r.proname}"

    # 5. Worker ID validation testing via db_api_user role
    async with ApiSession() as api_db:
        invalid_worker_ids = [
            None,
            "",
            "   ",
            "a" * 101,
            "worker\n1",
            "worker\r1",
            "worker\t1",
            "worker\x001",
            "worker\x7f1",
            "worker\x1b1",
        ]
        for bad_id in invalid_worker_ids:
            with pytest.raises(Exception) as exc_info:
                await api_db.execute(text("SELECT * FROM public.claim_next_analysis_job(:w);"), {"w": bad_id})
            assert any(k in str(exc_info.value) for k in ("CRITICAL_SECURITY_VIOLATION", "CharacterNotInRepertoireError", "invalid byte sequence"))
            await api_db.rollback()

    # 6. Fixture setup using OwnerSession (db_owner)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with OwnerSession() as owner_db:
        await owner_db.execute(text(
            "INSERT INTO public.organizations (id, name, slug, created_at, updated_at) "
            "VALUES (:id, 'Test Org 031', :slug, now(), now());"
        ), {"id": org_id, "slug": f"test-org-{uuid.uuid4().hex[:8]}"})

        await owner_db.execute(text(
            "INSERT INTO public.users (id, external_subject, identity_provider, display_name, status, created_at, updated_at) "
            "VALUES (:uid, :sub, 'firebase', 'Test User 031', 'ACTIVE', now(), now());"
        ), {"uid": user_id, "sub": f"firebase_sub_{uuid.uuid4().hex[:12]}"})

        await owner_db.execute(text("DELETE FROM public.analysis_jobs WHERE status = 'RECEIVED';"))
        await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
        await owner_db.execute(text(
            "INSERT INTO public.analysis_jobs (id, organization_id, user_id, status, request_prompt, created_at, updated_at) "
            "VALUES (:jid, :oid, :uid, 'RECEIVED', 'What is net debt 031?', now(), now());"
        ), {"jid": job_id, "oid": org_id, "uid": user_id})
        await owner_db.commit()

    try:
        # 7. Fresh Claim Test via db_api_user role
        async with ApiSession() as api_db:
            claim_res = await api_db.execute(text("SELECT job_id, organization_id, claim_token FROM public.claim_next_analysis_job('worker-031-a');"))
            claim_row = claim_res.fetchone()
            assert claim_row is not None
            assert claim_row.job_id == job_id
            assert claim_row.organization_id == org_id
            claimed_token = claim_row.claim_token
            assert claimed_token is not None
            await api_db.commit()

        # Verify job row updated properly
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            job_res = await owner_db.execute(text("SELECT status, locked_by, claim_token, recovery_count FROM public.analysis_jobs WHERE id = :jid;"), {"jid": job_id})
            j_row = job_res.fetchone()
            assert j_row.status == "RECEIVED"
            assert j_row.locked_by == "worker-031-a"
            assert j_row.claim_token == claimed_token
            assert j_row.recovery_count == 0

        # Lease Renewal Test via db_api_user role
        async with ApiSession() as api_db:
            renew_ok = await api_db.execute(text("SELECT public.renew_analysis_job_lease(:jid, :tok, 'worker-031-a');"), {"jid": job_id, "tok": claimed_token})
            assert renew_ok.scalar() is True

            renew_fail = await api_db.execute(text("SELECT public.renew_analysis_job_lease(:jid, :tok, 'worker-031-a');"), {"jid": job_id, "tok": uuid.uuid4()})
            assert renew_fail.scalar() is False
            await api_db.commit()

        # Stale Recovery Test: simulate expired lease and open attempt via OwnerSession
        att_id = uuid.uuid4()
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            await owner_db.execute(text(
                "UPDATE public.analysis_jobs SET lease_expires_at = now() - INTERVAL '1 minute', status = 'UNDERSTANDING_REQUEST' WHERE id = :jid;"
            ), {"jid": job_id})

            await owner_db.execute(text(
                "INSERT INTO public.analysis_attempts (id, analysis_job_id, organization_id, attempt_number, status, created_at) "
                "VALUES (:aid, :jid, :oid, 1, 'RUNNING', now());"
            ), {"aid": att_id, "jid": job_id, "oid": org_id})
            await owner_db.commit()

        # Execute stale recovery via db_api_user role
        async with ApiSession() as api_db:
            stale_res = await api_db.execute(text("SELECT job_id, organization_id, claim_token FROM public.recover_next_stale_analysis_job('worker-031-b');"))
            stale_row = stale_res.fetchone()
            assert stale_row is not None
            assert stale_row.job_id == job_id
            assert stale_row.claim_token != claimed_token  # New token generated!
            await api_db.commit()

        # Verify previous attempt was ABANDONED and job recovery_count is 1
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            att_res = await owner_db.execute(text("SELECT status FROM public.analysis_attempts WHERE id = :aid;"), {"aid": att_id})
            att_row = att_res.fetchone()
            assert att_row.status == "ABANDONED"

            job_res2 = await owner_db.execute(text("SELECT recovery_count FROM public.analysis_jobs WHERE id = :jid;"), {"jid": job_id})
            assert job_res2.scalar() == 1

        # Second stale recovery attempt must be rejected (recovery_count = 1 >= limit)
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            await owner_db.execute(text("UPDATE public.analysis_jobs SET lease_expires_at = now() - INTERVAL '1 minute' WHERE id = :jid;"), {"jid": job_id})
            await owner_db.commit()

        async with ApiSession() as api_db:
            stale_res2 = await api_db.execute(text("SELECT job_id FROM public.recover_next_stale_analysis_job('worker-031-c');"))
            assert stale_res2.fetchone() is None
            await api_db.commit()

    finally:
        # Clean up test rows using OwnerSession
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            await owner_db.execute(text("DELETE FROM public.analysis_attempts WHERE analysis_job_id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.analysis_jobs WHERE id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.users WHERE id = :uid;"), {"uid": user_id})
            await owner_db.execute(text("DELETE FROM public.organizations WHERE id = :oid;"), {"oid": org_id})
            await owner_db.commit()
