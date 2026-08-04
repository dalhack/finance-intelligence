"""027_auth_context_lookup_security_plane

Revision ID: 027_auth_context_lookup_security_plane
Revises: 026_public_schema_acl_hardening
Create Date: 2026-08-04 12:00:00.000000

"""

from alembic import op

revision = "027_auth_context_lookup_security_plane"
down_revision = "026_public_schema_acl_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create permissions and role_permissions schema tables
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.permissions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code text NOT NULL UNIQUE,
            description text NULL,
            created_at timestamp with time zone NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.role_permissions (
            role_id uuid NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
            permission_id uuid NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            PRIMARY KEY (role_id, permission_id)
        );
    """)

    # 2. Seed 13 Canonical Permissions and Role-Permission Mappings
    op.execute("""
        -- Seed 13 Canonical Permissions
        INSERT INTO public.permissions (code, description) VALUES
            ('documents:read', 'Read documents and metadata'),
            ('ingestion:read', 'Read document ingestion status'),
            ('evidence:read', 'Read extraction evidence'),
            ('calculations:read', 'Read calculation results'),
            ('comparisons:read', 'Read comparison analysis results'),
            ('facts:read', 'Read financial facts'),
            ('facts:candidates:read', 'Read financial fact candidates'),
            ('documents:upload', 'Upload new documents'),
            ('documents:finalize', 'Finalize uploaded document versions'),
            ('calculations:run', 'Execute financial calculations'),
            ('comparisons:run', 'Execute comparison analysis'),
            ('facts:candidates:review', 'Review fact candidates'),
            ('facts:verify_revision', 'Verify fact revisions')
        ON CONFLICT (code) DO NOTHING;

        -- Ensure VIEWER role exists in roles table
        INSERT INTO public.roles (id, name, description) VALUES
            ('a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d'::uuid, 'VIEWER', 'Viewer Role')
        ON CONFLICT (name) DO NOTHING;

        -- Map VIEWER permissions
        INSERT INTO public.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM public.roles r
          CROSS JOIN public.permissions p
         WHERE r.name = 'VIEWER'
           AND p.code IN (
               'documents:read',
               'ingestion:read',
               'evidence:read',
               'calculations:read',
               'comparisons:read',
               'facts:read',
               'facts:candidates:read'
           )
        ON CONFLICT (role_id, permission_id) DO NOTHING;

        -- Map ANALYST permissions (VIEWER permissions + upload, finalize, calculations:run, comparisons:run)
        INSERT INTO public.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM public.roles r
          CROSS JOIN public.permissions p
         WHERE r.name = 'ANALYST'
           AND p.code IN (
               'documents:read',
               'ingestion:read',
               'evidence:read',
               'calculations:read',
               'comparisons:read',
               'facts:read',
               'facts:candidates:read',
               'documents:upload',
               'documents:finalize',
               'calculations:run',
               'comparisons:run'
           )
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)

    # 3. Create SECURITY DEFINER functions: resolve_auth_context and get_current_user_id
    op.execute("""
        CREATE OR REPLACE FUNCTION public.resolve_auth_context(
            p_firebase_uid text,
            p_organization_id uuid
        )
        RETURNS TABLE (
            actor_user_id uuid,
            active_organization_id uuid,
            roles text[],
            permissions text[]
        )
        LANGUAGE plpgsql
        STRICT
        SECURITY DEFINER
        SET search_path = public, pg_catalog, pg_temp
        AS $$
        DECLARE
            v_user_id uuid;
            v_user_status text;
            v_org_status text;
            v_membership_id uuid;
            v_membership_status text;
            v_roles text[];
            v_permissions text[];
        BEGIN
            -- 1. Input Sanitization
            IF p_firebase_uid IS NULL OR trim(p_firebase_uid) = '' OR p_organization_id IS NULL THEN
                RETURN;
            END IF;

            -- 2. Lookup exact user by external_subject (Firebase UID)
            SELECT u.id, u.status
              INTO v_user_id, v_user_status
              FROM public.users u
             WHERE u.external_subject = p_firebase_uid;

            IF v_user_id IS NULL OR lower(v_user_status) <> 'active' THEN
                RETURN;
            END IF;

            -- 3. Lookup organization status
            SELECT o.status
              INTO v_org_status
              FROM public.organizations o
             WHERE o.id = p_organization_id;

            IF v_org_status IS NULL OR lower(v_org_status) <> 'active' THEN
                RETURN;
            END IF;

            -- 4. Lookup exact membership by (user_id, organization_id)
            SELECT m.id, m.status
              INTO v_membership_id, v_membership_status
              FROM public.memberships m
             WHERE m.user_id = v_user_id
               AND m.organization_id = p_organization_id;

            IF v_membership_id IS NULL OR lower(v_membership_status) <> 'active' THEN
                RETURN;
            END IF;

            -- 5. Collect assigned role names for this membership
            SELECT COALESCE(array_agg(DISTINCT r.name ORDER BY r.name), '{}'::text[])
              INTO v_roles
              FROM public.membership_roles mr
              JOIN public.roles r ON r.id = mr.role_id
             WHERE mr.membership_id = v_membership_id
               AND mr.organization_id = p_organization_id;

            -- 6. Collect permissions dynamically from DB relationship JOIN
            SELECT COALESCE(array_agg(DISTINCT p.code ORDER BY p.code), '{}'::text[])
              INTO v_permissions
              FROM public.membership_roles mr
              JOIN public.roles r ON r.id = mr.role_id
              JOIN public.role_permissions rp ON rp.role_id = r.id
              JOIN public.permissions p ON p.id = rp.permission_id
             WHERE mr.membership_id = v_membership_id
               AND mr.organization_id = p_organization_id;

            RETURN QUERY
            SELECT v_user_id, p_organization_id, v_roles, v_permissions;
        END;
        $$;

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
    """)

    # 4. Set Function Owner to db_owner if role exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                ALTER FUNCTION public.resolve_auth_context(text, uuid) OWNER TO db_owner;
                ALTER FUNCTION public.get_current_user_id(uuid) OWNER TO db_owner;
            END IF;
        END
        $$;
    """)

    # 5. Explicit ACL Permissions: Revoke PUBLIC, Grant db_api_user on Functions, Revoke Direct Table SELECT (Option 3B)
    op.execute("""
        REVOKE EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) FROM PUBLIC;
        REVOKE EXECUTE ON FUNCTION public.get_current_user_id(uuid) FROM PUBLIC;

        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                REVOKE EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) FROM db_bootstrap;
                REVOKE EXECUTE ON FUNCTION public.get_current_user_id(uuid) FROM db_bootstrap;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                REVOKE EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) FROM db_ingestion_worker;
                REVOKE EXECUTE ON FUNCTION public.get_current_user_id(uuid) FROM db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                REVOKE EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) FROM db_maintenance_worker;
                REVOKE EXECUTE ON FUNCTION public.get_current_user_id(uuid) FROM db_maintenance_worker;
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) TO db_owner;
                GRANT EXECUTE ON FUNCTION public.get_current_user_id(uuid) TO db_owner;
                GRANT SELECT ON public.permissions, public.role_permissions TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT EXECUTE ON FUNCTION public.resolve_auth_context(text, uuid) TO db_api_user;
                GRANT EXECUTE ON FUNCTION public.get_current_user_id(uuid) TO db_api_user;
                GRANT SELECT ON public.permissions, public.role_permissions TO db_api_user;
                -- Direct Table Access Decision (Option 3B): Revoke direct SELECT on users and memberships from db_api_user
                REVOKE SELECT ON public.users, public.memberships FROM db_api_user;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.get_current_user_id(uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.resolve_auth_context(text, uuid);")
    op.execute("DROP TABLE IF EXISTS public.role_permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.permissions CASCADE;")

    # Restore direct SELECT on users and memberships to db_api_user if needed on downgrade
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT ON public.users, public.memberships TO db_api_user;
            END IF;
        END
        $$;
    """)
