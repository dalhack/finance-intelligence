-- Local Development and CI Postgres Role Provisioning
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
        CREATE ROLE db_api_user WITH LOGIN PASSWORD 'dev_api_user_pass_123';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
        CREATE ROLE db_ingestion_worker WITH LOGIN PASSWORD 'dev_worker_pass_123';
    END IF;
END
$$;
