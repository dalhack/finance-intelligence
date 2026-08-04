"""028_remove_organization_only_actor_lookup

Revision ID: 028_remove_organization_only_actor_lookup
Revises: 027_auth_context_lookup_security_plane
Create Date: 2026-08-04 14:30:00.000000

"""

from alembic import op

revision = "028_remove_organization_only_actor_lookup"
down_revision = "027_auth_context_lookup_security_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove organization-only actor lookup function (get_current_user_id)
    # Actor attribution must come from authenticated ExecutionContext.authenticated_user_id
    op.execute("DROP FUNCTION IF EXISTS public.get_current_user_id(uuid);")


def downgrade() -> None:
    # Re-create historical 027 get_current_user_id function for 027 schema compliance
    op.execute("""
        CREATE OR REPLACE FUNCTION public.get_current_user_id(
            p_organization_id uuid
        )
        RETURNS uuid
        LANGUAGE plpgsql
        STRICT
        SECURITY DEFINER
        SET search_path = public, pg_catalog, pg_temp
        AS $$
        DECLARE
            v_user_id uuid;
            v_guc_org text;
        BEGIN
            IF p_organization_id IS NULL THEN
                RETURN NULL;
            END IF;

            v_guc_org := current_setting('app.current_organization_id', true);
            IF v_guc_org IS NULL OR v_guc_org = '' OR v_guc_org <> p_organization_id::text THEN
                RETURN NULL;
            END IF;

            SELECT m.user_id INTO v_user_id
              FROM public.memberships m
              JOIN public.users u ON u.id = m.user_id
             WHERE m.organization_id = p_organization_id
               AND lower(m.status) = 'active'
               AND lower(u.status) = 'active'
             ORDER BY m.created_at ASC
             LIMIT 1;

            RETURN v_user_id;
        END;
        $$;

        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                ALTER FUNCTION public.get_current_user_id(uuid) OWNER TO db_owner;
            END IF;
        END
        $$;

        REVOKE EXECUTE ON FUNCTION public.get_current_user_id(uuid) FROM PUBLIC;

        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT EXECUTE ON FUNCTION public.get_current_user_id(uuid) TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT EXECUTE ON FUNCTION public.get_current_user_id(uuid) TO db_api_user;
            END IF;
        END
        $$;
    """)
