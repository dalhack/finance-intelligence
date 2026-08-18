"""Grant candidate review permissions to the analyst role

Reviewing an extracted figure is the step that turns it into a verified fact,
and it is an analyst's job. The permissions existed in the catalog but were
never attached to a role, so no user could approve or reject anything: the
review queue rendered its candidates and every action returned 403.

Revision ID: 034_grant_candidate_review_permissions
Revises: 033_worker_queue_visibility
Create Date: 2026-08-18
"""

from alembic import op

revision = "034_grant_candidate_review_permissions"
down_revision = "033_worker_queue_visibility"
branch_labels = None
depends_on = None

REVIEW_PERMISSIONS = ("facts:candidates:review", "facts:verify_revision")


def upgrade() -> None:
    op.execute("""
        INSERT INTO public.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM public.roles r
          CROSS JOIN public.permissions p
         WHERE r.name = 'ANALYST'
           AND p.code IN ('facts:candidates:review', 'facts:verify_revision')
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM public.role_permissions rp
         USING public.roles r, public.permissions p
         WHERE rp.role_id = r.id
           AND rp.permission_id = p.id
           AND r.name = 'ANALYST'
           AND p.code IN ('facts:candidates:review', 'facts:verify_revision');
    """)
