"""029_analysis_authorization_policy

Revision ID: 029_analysis_authorization_policy
Revises: 028_remove_organization_only_actor_lookup
Create Date: 2026-08-04 16:00:00.000000

"""

from alembic import op

revision = "029_analysis_authorization_policy"
down_revision = "028_remove_organization_only_actor_lookup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Seed 4 new Analyses canonical permissions and role-permission mappings
    op.execute("""
        INSERT INTO public.permissions (code, description) VALUES
            ('analyses:read', 'Read AI financial analysis jobs, results, events, and clarifications'),
            ('analyses:run', 'Execute new AI financial analysis jobs'),
            ('analyses:clarifications:respond', 'Respond to open AI analysis clarification requests'),
            ('analyses:cancel', 'Cancel active AI financial analysis jobs or clarification requests')
        ON CONFLICT (code) DO NOTHING;

        -- Ensure VIEWER, ANALYST, ADMIN roles exist in public.roles
        INSERT INTO public.roles (id, name, description) VALUES
            ('a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d'::uuid, 'VIEWER', 'Viewer Role'),
            ('b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e'::uuid, 'ANALYST', 'Analyst Role'),
            ('c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f'::uuid, 'ADMIN', 'Admin Role')
        ON CONFLICT (name) DO NOTHING;

        -- Map base ANALYST permissions if missing from 027
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

        -- Map VIEWER permissions (analyses:read)
        INSERT INTO public.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM public.roles r
          CROSS JOIN public.permissions p
         WHERE r.name = 'VIEWER'
           AND p.code IN ('analyses:read')
        ON CONFLICT (role_id, permission_id) DO NOTHING;

        -- Map ANALYST permissions (analyses:read, analyses:run, analyses:clarifications:respond, analyses:cancel)
        INSERT INTO public.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM public.roles r
          CROSS JOIN public.permissions p
         WHERE r.name = 'ANALYST'
           AND p.code IN (
               'analyses:read',
               'analyses:run',
               'analyses:clarifications:respond',
               'analyses:cancel'
           )
        ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)


def downgrade() -> None:
    # Downgrade: Remove the 4 Analyses role mappings and permissions
    op.execute("""
        DELETE FROM public.role_permissions
         WHERE permission_id IN (
             SELECT id FROM public.permissions
              WHERE code IN (
                  'analyses:read',
                  'analyses:run',
                  'analyses:clarifications:respond',
                  'analyses:cancel'
              )
         );

        DELETE FROM public.permissions
         WHERE code IN (
             'analyses:read',
             'analyses:run',
             'analyses:clarifications:respond',
             'analyses:cancel'
         );
    """)
