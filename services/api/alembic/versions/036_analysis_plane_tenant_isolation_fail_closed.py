"""Make the analysis plane's tenant isolation fail closed like every other table

Sixteen tables scope themselves with NULLIF(current_setting(...), '')::uuid.
The ten tables of the analysis plane cast the setting directly, and an empty
string is not a uuid: any statement touching them from a session whose tenant
setting is blank raises `invalid input syntax for type uuid: ""` instead of
simply matching no rows.

That is what stopped analysis from ever running. The worker claims analysis
jobs before a tenant is known, so its claim query hits this policy; whenever a
claimable job existed the claim raised, the worker loop caught it, and retried
five seconds later — for as long as a job was waiting. Jobs sat in RECEIVED and
no analysis ever produced a result.

Only the empty-string guard is added. Which rows each policy admits is
unchanged: a blank setting now yields NULL, and `organization_id = NULL` is not
true for any row, so a session without a tenant still sees nothing.

Revision ID: 036_analysis_plane_tenant_isolation_fail_closed
Revises: 035_metric_hierarchy_and_statement_lines
Create Date: 2026-08-18
"""

from alembic import op

revision = "036_analysis_plane_tenant_isolation_fail_closed"
down_revision = "035_metric_hierarchy_and_statement_lines"
branch_labels = None
depends_on = None

ANALYSIS_PLANE_TABLES = (
    "analysis_attempts",
    "analysis_clarifications",
    "analysis_events",
    "analysis_jobs",
    "analysis_plans",
    "final_result_snapshots",
    "model_invocations",
    "policy_decisions",
    "quality_gate_results",
    "tool_invocations",
)

FAIL_CLOSED = "organization_id = (NULLIF(current_setting('app.current_organization_id', true), ''))::uuid"
UNGUARDED = "organization_id = (SELECT current_setting('app.current_organization_id', true)::uuid)"


def _recreate(expression: str) -> None:
    for table in ANALYSIS_PLANE_TABLES:
        policy = f"{table}_tenant_isolation"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON public.{table};")
        op.execute(f"""
            CREATE POLICY {policy} ON public.{table}
                FOR ALL
                TO public
                USING ({expression});
        """)


def upgrade() -> None:
    _recreate(FAIL_CLOSED)


def downgrade() -> None:
    _recreate(UNGUARDED)
