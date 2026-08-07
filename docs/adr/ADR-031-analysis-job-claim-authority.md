# ADR 031 — Analysis Job Claim Authority, Fencing and Recovery

## Metadata
- **Status**: Accepted
- **Date**: 2026-08-07
- **Decision Owners**: Product / Engineering
- **Accepted Migration Revision**: `031_analysis_job_claim_authority`
- **Accepted Implementation Commits**:
  - `e440d15ca684c421d7c4d90a26c857f71fb7f236`
  - `dac8e7e1fcc55400644e1280f218b6e0419804b0`
- **Supersedes**: Ad-hoc route background execution, unfenced worker claims, and broad `db_owner` RLS policies.

---

## 1. Context

In a multi-tenant, distributed financial intelligence platform, analysis requests require multi-step asynchronous processing (request understanding, planning, tool execution, financial calculation, and structured report generation). 

Prior implementations suffered from potential concurrency hazards, including:
- Race conditions during job acquisition when multiple worker nodes polled for work.
- Split-brain execution and late-writer data corruption when network partitions or long-running tool calls caused a worker's lease to expire while execution continued.
- Unbounded automatic crash recoveries leading to infinite execution loops.
- Overly permissive database policies (`db_owner` broad RLS) that violated least-privilege principles.

To address these vulnerabilities, Revision 031 establishes an immutable, database-enforced Claim Authority, Lease Heartbeat, and Fencing contract.

---

## 2. Decision

The system officially adopts the following bound architecture:

```text
CRASH_RECOVERY_MODEL = CR2
RECOVERY_LIMIT_MODEL = RC2
FENCING_MODEL = UNIQUE_CLAIM_TOKEN
MAX_AUTOMATIC_STALE_RECOVERY_COUNT = 1
FUNCTION_AUTHORITY_MODEL = DEDICATED_NOLOGIN_CLAIM_OWNER
```

### Core Architecture Principles:
1. **CR2 Model**: Stale jobs in safe pre-side-effect statuses are reclaimed atomically by issuing a fresh `claim_token`, renewing the lease, incrementing `recovery_count` from 0 to 1, and marking the previous open attempt as `ABANDONED`.
2. **RC2 Model**: Automatic crash recovery is strictly capped at `max_recovery_count = 1`. A second stale recovery attempt is denied automatically.
3. **Fencing Model**: Every claim or recovery generates a cryptographically strong UUID `claim_token`. All authoritative state writes by the canonical worker engine must present a matching `claim_token`.
4. **Dedicated Role Authority**: Stored procedures execute as `SECURITY DEFINER` owned by a dedicated `NOLOGIN` internal database role (`db_analysis_claim_owner`) subject to narrow, state-checked RLS policies.

---

## 3. Security Invariants

- **Multi-Tenant Isolation**: Row Level Security (RLS) is forced across all tables (`FORCE ROW LEVEL SECURITY`).
- **Dedicated NOLOGIN Function Owner Role**:
  ```sql
  CREATE ROLE db_analysis_claim_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  ```
- **Privilege Minimization**: `db_analysis_claim_owner` is granted column-level `SELECT` and `UPDATE` privileges restricted exclusively to necessary job lifecycle and attempt status columns.
- **Runtime Boundary**:
  - `PUBLIC` execution is explicitly revoked on all claim functions.
  - `EXECUTE` privilege is granted strictly to the runtime API role (`db_api_user`).
  - Direct login as `db_analysis_claim_owner` is impossible (`NOLOGIN`).

---

## 4. Claim Lifecycle

Fresh job acquisition proceeds according to the following strict rules:

1. **Eligibility**: A job is eligible for a fresh claim if and only if:
   - `status = 'RECEIVED'`
   - `claim_token IS NULL`
   - `locked_by IS NULL`
   - `lease_expires_at IS NULL`
2. **Concurrency Control**: Acquisition uses `FOR UPDATE SKIP LOCKED` sorted by FIFO (`created_at ASC, id ASC`) to ensure zero lock contention between competing worker instances.
3. **State Mutation**: Upon claim:
   - `locked_by` is set to `p_worker_id`.
   - `claim_token` is populated with `gen_random_uuid()`.
   - `locked_at` is set to `now()`.
   - `lease_expires_at` is set to `now() + INTERVAL '15 minutes'`.
4. **Data Minimization**: The procedure `claim_next_analysis_job` returns strictly `(job_id, organization_id, claim_token)`. Prompts and payload data are omitted from the claim tuple.

---

## 5. Stale Recovery Lifecycle

When a worker crashes or loses network connectivity before completing an analysis job:

1. **Eligibility**: A job is eligible for automatic stale recovery if and only if:
   - `status` is in the safe recovery allowlist: `RECEIVED`, `UNDERSTANDING_REQUEST`, `PLANNING`, `POLICY_CHECK`, `RETRIEVING_INTERNAL_SOURCES`, `VALIDATING_SOURCES`.
   - `claim_token IS NOT NULL`.
   - `lease_expires_at < now()`.
   - `recovery_count = 0` (strictly enforced by `RC2`).
2. **Attempt Abandonment**: The open attempt associated with the stale job (`status = 'RUNNING'`) is transitioned to `status = 'ABANDONED'`.
3. **Reclaim Execution**:
   - `status` is reset to `'RECEIVED'`.
   - `locked_by` is updated to the new worker ID.
   - `claim_token` is replaced with a new `gen_random_uuid()`.
   - `lease_expires_at` is reset to `now() + INTERVAL '15 minutes'`.
   - `recovery_count` is incremented from 0 to 1.

---

## 6. Lease Heartbeat Contract

- **Initial Lease Duration**: 15 minutes.
- **Heartbeat Frequency**: 60 seconds.
- **Session Isolation**: Heartbeat renewals run in a separate, short-lived worker database session, completely decoupled from long-running engine or LLM transactions.
- **Verification Signature**: `renew_analysis_job_lease(p_job_id, p_claim_token, p_worker_id)` checks `id`, `claim_token`, `locked_by`, and valid active status simultaneously.
- **Loss Handling**: If renewal returns `false`, ownership has been lost (`CLAIM_OWNERSHIP_LOST`). The worker must immediately abort processing and cancel background tasks in a `finally` block.
- **Forbidden Renewals**: Heartbeat renewal is prohibited on terminal or human-waiting statuses.

---

## 7. Fencing and Late-Writer Rejection

- **Unique Fencing Token**: `claim_token` is the sole authoritative fencing token. Neither `locked_by` nor `locked_at` alone provides fencing guarantees.
- **Late-Writer Prevention**: All R2 engine database updates (state transitions, result snapshots, event emission, failure persistence) must include `WHERE claim_token = :claim_token`.
- **Rejection Behavior**: If a worker attempts to commit changes after its lease has expired and been reclaimed by another worker, the update affects 0 rows, throwing a `CLAIM_OWNERSHIP_LOST` exception.
- **Side-Effect Scope**: Fencing guarantees that a stale worker cannot write future state to the database, but does not automatically undo external side effects (e.g., third-party API calls) executed prior to lease expiry.

---

## 8. Failure Transaction Contract (Model B)

When an unhandled exception or engine failure occurs during processing:

1. The failed engine transaction is immediately rolled back.
2. A new, isolated tenant-scoped database session/transaction is opened.
3. Ownership is re-verified against `claim_token`.
4. If ownership is valid:
   - The current attempt is updated to `FAILED` with error details.
   - An `analysis.failed` domain event is recorded.
   - The job `status` is set to `'FAILED'` using a fenced update.
   - All failure persistence steps commit in a single atomic transaction.
5. If the attempt record was rolled back, the failure event references a `NULL` attempt ID.
6. If ownership was lost (`claim_token` mismatch), failure persistence is suppressed to prevent overwriting the new owner's active job.

---

## 9. Automatic Recovery Boundary

### Safe Automatic Recovery Allowlist (Eligible for Stale Recovery):
- `RECEIVED`
- `UNDERSTANDING_REQUEST`
- `PLANNING`
- `POLICY_CHECK`
- `RETRIEVING_INTERNAL_SOURCES`
- `VALIDATING_SOURCES`

### Side-Effect Risk States (Excluded - Manual Reconciliation Required):
- `EXECUTING_TOOLS`
- `RECONCILING_RESULTS`
- `GENERATING_STRUCTURED_RESULT`
- `QUALITY_GATE`

### Human-Waiting States (Excluded - Manual Action Required):
- `NEEDS_CLARIFICATION`
- `AWAITING_HUMAN_REVIEW`

### Terminal States (Excluded):
- `COMPLETED`, `REJECTED_BY_POLICY`, `FAILED`, `CANCELLED`, `EXPIRED`, `BUDGET_EXCEEDED`

> **Note**: Jobs entering Side-Effect Risk or Human-Waiting states whose leases expire cannot be automatically recovered. They require manual operational reconciliation to verify external side effects before retrying.

---

## 10. Role and RLS Authority

```text
ROLE = db_analysis_claim_owner
LOGIN = false
SUPERUSER = false
BYPASSRLS = false
PERMANENT_MEMBERSHIP = none
```

- **Stored Procedures**: Owns `claim_next_analysis_job`, `recover_next_stale_analysis_job`, and `renew_analysis_job_lease`.
- **Narrow RLS Policies**:
  - `analysis_jobs_claim_owner_select_policy`
  - `analysis_jobs_claim_owner_update_policy`
  - `analysis_attempts_claim_owner_select_policy`
  - `analysis_attempts_claim_owner_update_policy`
- **Restrictions**: `db_analysis_claim_owner` is denied `INSERT`, `DELETE`, or `TRUNCATE` privileges on any table.

---

## 11. Revision 031 versus R2 Ownership Split

| Domain | Revision 031 Responsibilities | R2 Engine Responsibilities |
| :--- | :--- | :--- |
| **Database Schema** | `claim_token`, `recovery_count` columns, indexes, CHECK constraints | Consumes database schema via asyncpg / SQLAlchemy |
| **Procedures & Authority** | `SECURITY DEFINER` stored procedures, `db_analysis_claim_owner` role, narrow RLS | Invokes procedures via `db_api_user` role |
| **Concurrency & Claims** | `FOR UPDATE SKIP LOCKED`, atomic claim & stale recovery SQL | Claim transaction boundary, worker process loop |
| **Heartbeat & Fencing** | `renew_analysis_job_lease` procedure definition | Async background heartbeat task, `claim_token` predicate on writes |
| **Failure Persistence** | Attempt status updates & job status RLS policies | Model B failure transaction handling, `CLAIM_OWNERSHIP_LOST` catching |

> **Critical Rule**: Revision 031 alone does not provide end-to-end fencing. R2 implementation is required before real analysis worker execution is authorized.

---

## 12. Operational Constraints

- **Worker ID Validation**: Worker IDs are validated against regex `^[^\s[:cntrl:]]{1,100}$`. NULL, empty, whitespace, control characters, or strings >100 characters are strictly rejected.
- **Attempt Isolation**: Recovery updates on `analysis_attempts` apply strictly to `status = 'RUNNING'` attempts matching the specific reclaimed `analysis_job_id`. Unrelated running attempts across the same or different organizations remain untouched.

---

## 13. Consequences

### Positive:
- Eliminates race conditions and double-claim issues between parallel workers.
- Prevents stale late-writers from corrupting database state after lease expiration.
- Limits cascading failure loops by capping automatic recovery to exactly 1 attempt.
- Preserves zero-trust multi-tenant isolation with least-privilege dedicated roles.

### Negative / Trade-offs:
- Jobs timing out during tool execution (`EXECUTING_TOOLS`) require manual reconciliation rather than instant automatic retry.

---

## 14. Superseded Alternatives

- **Ad-hoc Route Background Tasks**: Rejected due to process crash vulnerability and loss of job state on container restarts.
- **Granting `BYPASSRLS` to Worker Roles**: Rejected due to high risk of cross-tenant data leaks.
- **Broad `db_owner USING (true)` RLS Policies**: Rejected for violating least-privilege security principles.
- **Using `locked_by` or `locked_at` as Fencing Tokens**: Rejected because worker names can be reused and timestamps lack cryptographic uniqueness.
- **Unlimited Automatic Stale Recoveries**: Rejected due to potential infinite poison-pill retry loops.

---

## 15. ADR Governance & Implementation Sequence

### Governance Note
This ADR is the authoritative contract for R2. All R2 implementation prompts and code reviews must reference this ADR. Any incompatible change requires an explicit superseding ADR. Implementation convenience is not sufficient to silently alter this contract.

### Sequential Implementation Roadmap:
1. **Revision 031** — Accepted
2. **K4 ADR Freeze** — Completed (`ADR-031-analysis-job-claim-authority.md`)
3. **R2 Canonical Worker and Engine Fencing**
4. **R2 Independent Acceptance**
5. **R3/R4 Fixture and Mobile Completion**
6. **Single Authorized Real iOS E2E**
7. **Slice 4 Final Independent Acceptance**
8. **CI Push/Pull_Request Trigger Hardening**
9. **Explicitly Authorized Backup Branch Push**
10. **Infrastructure Reentry Decision**
