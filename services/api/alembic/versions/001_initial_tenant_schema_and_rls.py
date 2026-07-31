"""001_initial_tenant_schema_and_rls

Revision ID: 001_initial_schema_and_rls
Revises:
Create Date: 2026-07-29

Shared-schema tenant-aware tables, composite referential integrity, and PostgreSQL RLS policies migration.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema_and_rls"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Global Identity & Control Plane Tables
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_subject", sa.String(length=255), nullable=False, unique=True),
        sa.Column("identity_provider", sa.String(length=50), nullable=False, server_default="firebase"),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. Association & Tenant-Aware Tables with Composite Keys for Referential Integrity
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
        sa.UniqueConstraint("id", "organization_id", name="uq_memberships_id_org"),
    )

    op.create_table(
        "membership_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["memberships.id", "memberships.organization_id"],
            ondelete="CASCADE",
            name="fk_membership_roles_membership_org",
        ),
        sa.UniqueConstraint("membership_id", "role_id", name="uq_membership_role"),
    )

    # 3. Append-Only Audit Event Table
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_hash", sa.String(length=64), nullable=False),
        sa.Column("org_hash", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("previous_hash", sa.String(length=64), nullable=False, server_default="0" * 64),
        sa.Column("current_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 4. Schema Usage & Least-Privilege Role Grants
    op.execute("""
        DO $$
        BEGIN
            GRANT USAGE ON SCHEMA public TO db_app_user, db_bootstrap, db_owner;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                GRANT SELECT ON organizations, users, roles, membership_roles, alembic_version TO db_app_user;
                GRANT SELECT, INSERT, UPDATE ON memberships TO db_app_user;
                GRANT SELECT, INSERT ON audit_events TO db_app_user;
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                GRANT SELECT ON alembic_version TO db_bootstrap;
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO db_owner;
            END IF;
        END
        $$;
    """)

    # 5. Hardened Bootstrap Security Definer Lookup Function
    op.execute("""
        CREATE OR REPLACE FUNCTION public.lookup_user_membership(p_external_subject text, p_organization_id uuid)
        RETURNS TABLE (
            user_id uuid,
            organization_id uuid,
            membership_id uuid,
            membership_status text
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_catalog, pg_temp
        AS $$
        BEGIN
            IF p_external_subject IS NULL OR trim(p_external_subject) = '' OR p_organization_id IS NULL THEN
                RETURN;
            END IF;

            RETURN QUERY
            SELECT u.id, m.organization_id, m.id, m.status::text
            FROM public.users u
            JOIN public.memberships m ON m.user_id = u.id
            WHERE u.external_subject = trim(p_external_subject)
              AND m.organization_id = p_organization_id
              AND m.status = 'ACTIVE';
        END;
        $$;

        ALTER FUNCTION public.lookup_user_membership(text, uuid) OWNER TO db_owner;
        REVOKE EXECUTE ON FUNCTION public.lookup_user_membership(text, uuid) FROM PUBLIC;
        
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                GRANT EXECUTE ON FUNCTION public.lookup_user_membership(text, uuid) TO db_bootstrap;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT EXECUTE ON FUNCTION public.lookup_user_membership(text, uuid) TO db_owner;
            END IF;
        END
        $$;
    """)

    # 6. Row-Level Security (RLS) & FORCE RLS Activation across ALL domain tables
    for table in ["organizations", "users", "memberships", "membership_roles", "audit_events"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

        # Owner full access policy under FORCE RLS
        op.execute(f"""
            CREATE POLICY owner_full_access_policy ON {table}
                FOR ALL
                TO db_owner
                USING (true)
                WITH CHECK (true);
        """)

    # Tenant-scoped RLS policies for db_app_user
    op.execute("""
        CREATE POLICY tenant_organization_policy ON organizations
            FOR SELECT
            TO db_app_user
            USING (id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
            
        CREATE POLICY tenant_users_policy ON users
            FOR SELECT
            TO db_app_user
            USING (id IN (
                SELECT user_id FROM memberships
                WHERE organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
            ));
    """)

    for table in ["memberships", "membership_roles", "audit_events"]:
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {table}
                FOR ALL
                TO db_app_user
                USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
        """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.lookup_user_membership(text, uuid);")

    for table in ["organizations", "users", "memberships", "membership_roles", "audit_events"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_organization_policy ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_users_policy ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"DROP POLICY IF EXISTS owner_full_access_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("audit_events")
    op.drop_table("membership_roles")
    op.drop_table("memberships")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("organizations")
