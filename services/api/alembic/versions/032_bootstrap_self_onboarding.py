"""032_bootstrap_self_onboarding

Revision ID: 032_bootstrap_self_onboarding
Revises: 031_analysis_job_claim_authority
Create Date: 2026-08-13 21:30:00.000000

Adds the SECURITY DEFINER onboarding function used by
POST /api/v1/organizations/bootstrap. db_bootstrap holds no direct table
privileges (per role-separation design); it may only execute this function,
which provisions a personal organization + ANALYST membership idempotently.
"""

from alembic import op

revision = "032_bootstrap_self_onboarding"
down_revision = "031_analysis_job_claim_authority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.bootstrap_self_organization(
            p_subject text,
            p_provider text,
            p_display_name text
        )
        RETURNS TABLE(org_id uuid, was_created boolean)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            v_org_id uuid;
            v_user_id uuid;
            v_membership_id uuid;
        BEGIN
            SELECT m.organization_id INTO v_org_id
            FROM users u
            JOIN memberships m ON m.user_id = u.id AND m.status = 'ACTIVE'
            WHERE u.external_subject = p_subject
            LIMIT 1;

            IF v_org_id IS NOT NULL THEN
                RETURN QUERY SELECT v_org_id, false;
                RETURN;
            END IF;

            v_org_id := gen_random_uuid();
            v_membership_id := gen_random_uuid();

            INSERT INTO organizations (id, name, slug, status, created_at, updated_at)
            VALUES (
                v_org_id,
                left(p_display_name || ' Organizasyonu', 255),
                'org-' || replace(gen_random_uuid()::text, '-', ''),
                'ACTIVE', now(), now()
            );

            INSERT INTO users (id, external_subject, identity_provider, display_name, status, created_at, updated_at)
            VALUES (gen_random_uuid(), p_subject, p_provider, left(p_display_name, 255), 'ACTIVE', now(), now())
            ON CONFLICT (external_subject) DO NOTHING;

            SELECT u.id INTO v_user_id FROM users u WHERE u.external_subject = p_subject;

            INSERT INTO memberships (id, user_id, organization_id, status, created_at, updated_at)
            VALUES (v_membership_id, v_user_id, v_org_id, 'ACTIVE', now(), now());

            INSERT INTO membership_roles (id, organization_id, membership_id, role_id)
            SELECT gen_random_uuid(), v_org_id, v_membership_id, r.id
            FROM roles r WHERE r.name = 'ANALYST';

            RETURN QUERY SELECT v_org_id, true;
        END
        $$;
    """)

    op.execute("""
        REVOKE ALL ON FUNCTION public.bootstrap_self_organization(text, text, text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.bootstrap_self_organization(text, text, text) TO db_bootstrap;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.bootstrap_self_organization(text, text, text);")
