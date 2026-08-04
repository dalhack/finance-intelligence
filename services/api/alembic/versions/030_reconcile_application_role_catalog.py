"""030_reconcile_application_role_catalog

Revision ID: 030_reconcile_application_role_catalog
Revises: 029_analysis_authorization_policy
Create Date: 2026-08-04 18:00:00.000000

"""

from alembic import op

revision = "030_reconcile_application_role_catalog"
down_revision = "029_analysis_authorization_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Upgrade: Preflight validation, safe ADMIN cleanup, and uppercase role name constraint
    op.execute("""
        DO $$
        DECLARE
            v_dup_count int;
            v_viewer_id uuid;
            v_analyst_id uuid;
            v_viewer_perm_count int;
            v_analyst_perm_count int;
            v_admin_id uuid;
            v_admin_mem_count int;
            v_admin_perm_count int;
            v_non_upper_count int;
        BEGIN
            -- 1. Check for case-insensitive duplicate role names
            SELECT COUNT(*) INTO v_dup_count
              FROM (
                  SELECT lower(name)
                    FROM public.roles
                   GROUP BY lower(name)
                  HAVING COUNT(*) > 1
              ) t;
            IF v_dup_count > 0 THEN
                RAISE EXCEPTION 'MIGRATION_030_FAILED: Duplicate case-insensitive role names found in public.roles';
            END IF;

            -- 2. Validate presence of authoritative roles VIEWER and ANALYST
            SELECT id INTO v_viewer_id FROM public.roles WHERE name = 'VIEWER';
            SELECT id INTO v_analyst_id FROM public.roles WHERE name = 'ANALYST';

            IF v_viewer_id IS NULL OR v_analyst_id IS NULL THEN
                RAISE EXCEPTION 'MIGRATION_030_FAILED: Required authoritative roles VIEWER or ANALYST missing from public.roles';
            END IF;

            -- 3. Validate permission counts for VIEWER (8) and ANALYST (15)
            SELECT COUNT(*) INTO v_viewer_perm_count
              FROM public.role_permissions WHERE role_id = v_viewer_id;
            SELECT COUNT(*) INTO v_analyst_perm_count
              FROM public.role_permissions WHERE role_id = v_analyst_id;

            IF v_viewer_perm_count <> 8 THEN
                RAISE EXCEPTION 'MIGRATION_030_FAILED: VIEWER permission count mismatch (expected 8, got %)', v_viewer_perm_count;
            END IF;
            IF v_analyst_perm_count <> 15 THEN
                RAISE EXCEPTION 'MIGRATION_030_FAILED: ANALYST permission count mismatch (expected 15, got %)', v_analyst_perm_count;
            END IF;

            -- 4. Check for non-uppercase role names before adding constraint
            SELECT COUNT(*) INTO v_non_upper_count
              FROM public.roles WHERE name <> upper(name);
            IF v_non_upper_count > 0 THEN
                RAISE EXCEPTION 'MIGRATION_030_FAILED: Non-uppercase role names exist in public.roles';
            END IF;

            -- 5. Safe ADMIN role cleanup
            SELECT id INTO v_admin_id FROM public.roles WHERE name = 'ADMIN';
            IF v_admin_id IS NOT NULL THEN
                IF v_admin_id <> 'c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f'::uuid THEN
                    RAISE EXCEPTION 'MIGRATION_030_FAILED: ADMIN role exists with non-deterministic UUID %', v_admin_id;
                END IF;

                SELECT COUNT(*) INTO v_admin_mem_count FROM public.membership_roles WHERE role_id = v_admin_id;
                SELECT COUNT(*) INTO v_admin_perm_count FROM public.role_permissions WHERE role_id = v_admin_id;

                IF v_admin_mem_count > 0 OR v_admin_perm_count > 0 THEN
                    RAISE EXCEPTION 'MIGRATION_030_FAILED: ADMIN role has references (memberships: %, permissions: %)', v_admin_mem_count, v_admin_perm_count;
                END IF;

                DELETE FROM public.roles WHERE id = 'c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f'::uuid AND name = 'ADMIN';
            END IF;
        END $$;

        -- Add uppercase check constraint on public.roles(name)
        ALTER TABLE public.roles
            ADD CONSTRAINT check_roles_name_uppercase CHECK (name = upper(name));
    """)


def downgrade() -> None:
    # Downgrade: Drop uppercase constraint and restore unmapped 029 ADMIN role if absent
    op.execute("""
        ALTER TABLE public.roles
            DROP CONSTRAINT IF EXISTS check_roles_name_uppercase;

        INSERT INTO public.roles (id, name, description) VALUES
            ('c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f'::uuid, 'ADMIN', 'Admin Role')
        ON CONFLICT (name) DO NOTHING;
    """)
