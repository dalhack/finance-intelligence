import pytest
from app.core.config import Settings
from pydantic import ValidationError

PROD_SALT = "prod-salt-1234567890123456789012345678"
VALID_API_URL = "postgresql+asyncpg://db_api_user:mock_prod_pass_123@10.0.0.5:5432/prod_db"
VALID_WORKER_URL = "postgresql+asyncpg://db_ingestion_worker:mock_worker_pass_123@10.0.0.5:5432/prod_db"
VALID_BOOTSTRAP_URL = "postgresql+asyncpg://db_bootstrap:mock_bootstrap_pass_123@10.0.0.5:5432/prod_db"
VALID_FIREBASE_PROJECT_ID = "finance-intel-staging-8f2a"


@pytest.mark.unit
def test_production_config_valid():
    s = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        PSEUDONYMIZATION_SALT=PROD_SALT,
        API_DATABASE_URL=VALID_API_URL,
        WORKER_DATABASE_URL=VALID_WORKER_URL,
        BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
        FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
    )
    assert s.API_DATABASE_URL == VALID_API_URL


@pytest.mark.unit
def test_production_missing_api_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL=None,
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "API_DATABASE_URL must be explicitly provided" in str(exc_info.value)


@pytest.mark.unit
def test_production_missing_worker_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL=VALID_API_URL,
            WORKER_DATABASE_URL=None,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "WORKER_DATABASE_URL must be explicitly provided" in str(exc_info.value)


@pytest.mark.unit
def test_production_missing_bootstrap_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL=VALID_API_URL,
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=None,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "BOOTSTRAP_DATABASE_URL must be explicitly provided" in str(exc_info.value)


@pytest.mark.unit
def test_production_wrong_api_role():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL="postgresql+asyncpg://wrong_role:mock_secret_pass_123@10.0.0.5:5432/prod_db",
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "API_DATABASE_URL must use role 'db_api_user'" in str(exc_info.value)


@pytest.mark.unit
def test_production_same_roles():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL=VALID_API_URL,
            WORKER_DATABASE_URL=VALID_API_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "WORKER_DATABASE_URL must use role 'db_ingestion_worker'" in str(exc_info.value)


@pytest.mark.unit
def test_production_localhost_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL="postgresql+asyncpg://db_api_user:mock_secret_pass_123@localhost:5432/prod_db",
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "uses localhost in production/staging" in str(exc_info.value)


@pytest.mark.unit
def test_production_dev_password_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL="postgresql+asyncpg://db_api_user:dev_api_user_pass_123@10.0.0.5:5432/prod_db",
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "uses default dev password in production/staging" in str(exc_info.value)


@pytest.mark.unit
def test_production_migration_owner_role_as_runtime_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            PSEUDONYMIZATION_SALT=PROD_SALT,
            API_DATABASE_URL="postgresql+asyncpg://db_owner:mock_secret_pass_123@10.0.0.5:5432/prod_db",
            WORKER_DATABASE_URL=VALID_WORKER_URL,
            BOOTSTRAP_DATABASE_URL=VALID_BOOTSTRAP_URL,
            FIREBASE_PROJECT_ID=VALID_FIREBASE_PROJECT_ID,
        )
    assert "API_DATABASE_URL must use role 'db_api_user'" in str(exc_info.value)
