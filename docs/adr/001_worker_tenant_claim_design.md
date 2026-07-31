# ADR 001: Worker Control-Plane Job Claim Architecture & RLS Boundary Security

- **Status**: Approved
- **Date**: 2026-07-29
- **Deciders**: Finance Intelligence Platform Architecture Team
- **Technical Area**: Background Ingestion Worker, Row-Level Security (RLS), Multitenancy

---

## 1. Context & Problem Statement

Under PostgreSQL Row-Level Security (RLS), the background worker runtime role (`db_ingestion_worker`) operates without `BYPASSRLS` privileges to enforce strict multitenant isolation. Every query executed by `db_ingestion_worker` requires a valid tenant session setting (`app.current_organization_id`) to be set in PostgreSQL GUC context.

However, a background queue worker polling for available jobs across all tenants faces a bootstrap paradox:
- Without a tenant context set (`app.current_organization_id = NULL`), RLS policies evaluate to `FALSE` (fail-closed), preventing the worker from querying `QUEUED` jobs in `ingestion_jobs`.
- Setting a specific tenant context before polling limits the worker to that single tenant and prevents global fair queue processing.
- Giving the worker role `BYPASSRLS` or using `db_owner` / superuser at runtime destroys tenant security boundaries and creates high-risk cross-tenant data leakage vectors.

---

## 2. Decision & Design

We adopt the **Control-Plane SECURITY DEFINER Claim Function Pattern** (`public.claim_next_ingestion_job(p_worker_id text)`).

### Key Architectural Components:
1. **Narrow Control-Plane Claim Function**:
   - Implemented in PostgreSQL PL/pgSQL as `public.claim_next_ingestion_job(p_worker_id text)`.
   - Annotated with `SECURITY DEFINER` and owned by `db_owner`.
   - Explicitly sets `search_path = public, pg_catalog, pg_temp` to prevent search_path hijacking attacks.
   - Atomically selects the oldest `QUEUED` job using `FOR UPDATE SKIP LOCKED` to prevent concurrent worker lock contention.
   - Updates `ingestion_jobs.status` to `'PARSING'`, sets `locked_by` and `locked_at`.
   - Returns ONLY the tuple `(job_id, organization_id, document_version_id)`.

2. **Strict Access Control List (ACL)**:
   - `REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM PUBLIC;`
   - `GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) TO db_ingestion_worker, db_owner;`
   - Arbitrary table enumeration or querying is NOT permitted.

3. **Transaction-Scoped Tenant Context Binding**:
   - Upon receiving `(job_id, organization_id, document_version_id)` from `claim_next_ingestion_job`, the worker opens a dedicated transaction on `WorkerSessionLocal`.
   - The worker immediately executes `SELECT set_config('app.current_organization_id', :org_id, true);` (transaction-local).
   - All subsequent parsing operations (reading binary objects from `StoredObject`, writing `document_pages`, `document_chunks`, `extraction_results`, `extraction_warnings`, `ingestion_attempts`, and `audit_events`) execute under `db_ingestion_worker` subject to RLS enforcement for that specific tenant.
   - Tenant context is derived strictly from the claimed job record in PostgreSQL, never from untrusted client payloads.

---

## 3. Security Consequences & Invariants

- **Zero Superuser / BYPASSRLS at Runtime**: `db_ingestion_worker` maintains `NOBYPASSRLS`.
- **Zero Cross-Tenant Leakage**: All data-plane operations run within transaction-scoped RLS context.
- **Zero Race Conditions**: PostgreSQL `FOR UPDATE SKIP LOCKED` guarantees atomicity across multiple concurrent worker replicas.
- **Zero Table Enumeration**: Public cannot execute the claim function; worker cannot list non-queued tenant data.
