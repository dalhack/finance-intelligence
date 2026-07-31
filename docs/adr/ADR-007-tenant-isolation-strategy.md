# ADR-007: Multi-Tenant Isolation Strategy (Defense-in-Depth RLS)

* **Decision ID**: `ADR-007`
* **Status**: `Proposed`
* **Context**: The platform processes sensitive financial data for multiple organizational tenants. Multi-tenant isolation must significantly reduce cross-tenant data leakage risks (BOLA/IDOR) through structured defense-in-depth layers.
* **Decision**: Adopt **PostgreSQL Row-Level Security (RLS)** as the Primary Security Boundary, supported by a defense-in-depth architecture across PostgreSQL and Firestore:

### 1. PostgreSQL Row-Level Security (RLS) Controls
1. **Primary Security Boundary**: PostgreSQL RLS policies enforce tenant access constraints at the database engine level.
2. **`USING` and `WITH CHECK` Clauses**: RLS policies enforce visibility filters (`USING`) for `SELECT` and `DELETE` operations, and validation filters (`WITH CHECK`) for `INSERT` and `UPDATE` operations:
   ```sql
   CREATE POLICY tenant_isolation_policy ON financial_facts
       FOR ALL
       TO db_app_user
       USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
       WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
   ```
3. **Single Standard Context Key**: The tenant context key is strictly standardized across all SQL queries and connection parameters as **`app.current_organization_id`**.
4. **Fail-Closed Behavior**: If `app.current_organization_id` is missing, null, or empty, the `NULLIF` evaluation yields `NULL`, causing RLS queries to return zero rows and block writes (fail-closed).
5. **Transaction-Scoped Context (`SET LOCAL`)**: Every database transaction executes `SET LOCAL app.current_organization_id = :org_id` at transaction start. Because `SET LOCAL` automatically resets at transaction `COMMIT` or `ROLLBACK`, session state is cleaned up by the database engine. Connection pool `RESET app.current_organization_id` checkout/checkin hooks serve strictly as a defense-in-depth safety net against pool connection reuse edge cases.
6. **Role Segregation & `NOBYPASSRLS`**: Application runtime database role `db_app_user` is configured with `NOBYPASSRLS` privileges. Migration and schema owner role `db_owner` MUST NOT be used by application connection pools.
7. **Table Owner Enforcement**: All tenant tables execute `ALTER TABLE ... FORCE ROW LEVEL SECURITY` to ensure table owners are also subject to RLS policy checks.
8. **Server-Injected Context**: The API Gateway constructs an immutable `ExecutionContext`. LLM tool schemas MUST NOT accept tenant IDs from client bodies or LLM inputs.
9. **Raw SQL & Worker Execution**: All raw SQL queries and background worker tasks MUST run wrapped inside the same RLS context manager.
10. **Context Cleanup Verification Tests**: Integration tests execute automated checks verifying context reset after transaction commit or rollback.

### 2. Firestore Security & Membership Validation
Firestore tenant isolation DOES NOT rely solely on client-side JWT custom claims:
1. **Custom Claim Freshness & Token Refresh**: Custom claims inside Firebase ID tokens require token refresh to propagate. When a user switches active organizations or changes roles, the application forces a token refresh via the Firebase Auth SDK.
2. **Membership Revocation & Active Organization Switching**: The backend API Gateway validates user organization membership against PostgreSQL on every protected API call, independent of JWT claims.
3. **Token Revocation Check**: Revoked user tokens or revoked organization memberships immediately block API access via server-side session validation.
4. **No Sensitive Canonical Data in Firestore**: Firestore is restricted strictly to transient real-time chat state and UI progress indicators; canonical financial facts, balance sheets, and evidence lineage reside exclusively in PostgreSQL.

* **Rationale**: Combining PostgreSQL engine-enforced RLS policies with server-validated membership checks reduces multi-tenant data leakage risks even if application-level code or ORM queries contain bugs.
* **Alternatives Considered**:
  1. *SQLAlchemy ORM Filter Only*: Rejected as primary boundary because developer oversight in raw SQL or async workers could leak tenant data.
  2. *Schema-per-Tenant*: Rejected for MVP due to high Alembic migration overhead across hundreds of schemas.
* **Security Impact**: Significantly reduces BOLA/IDOR data leakage risks.
* **Data Integrity Impact**: Foreign key constraints and composite keys enforce organizational consistency.
* **MVP Impact**: Provides defense-in-depth security on a cost-effective shared database.
* **Cost Impact**: Single Cloud SQL PostgreSQL instance serves all MVP organization tenants safely.
* **Scalability Impact**: Supports thousands of tenants; migration path to dedicated databases preserved for enterprise tiers.
* **Risks**: Misconfigured RLS policy or improper role privilege assignment (mitigated by automated RLS negative integration tests).
* **Revisit Trigger**: Enterprise customer requires dedicated database instance isolation for compliance signoff.
