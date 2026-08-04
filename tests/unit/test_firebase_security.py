import pytest

from services.api.app.core.config import Settings
from services.api.app.core.security import FirebaseIdentityVerifier, get_or_create_firebase_app


def test_staging_missing_firebase_project_id_fails_closed():
    """Verify missing FIREBASE_PROJECT_ID in staging/production raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="staging",
            FIREBASE_PROJECT_ID="",
            API_DATABASE_URL="postgresql+asyncpg://db_api_user:pass@remote:5432/db",
            WORKER_DATABASE_URL="postgresql+asyncpg://db_ingestion_worker:pass@remote:5432/db",
            BOOTSTRAP_DATABASE_URL="postgresql+asyncpg://db_bootstrap:pass@remote:5432/db",
            PSEUDONYMIZATION_SALT="prod-secret-salt-99182390",
        )
    assert "FIREBASE_PROJECT_ID must be explicitly provided" in str(exc_info.value)


def test_prohibited_project_id_rejection():
    """Verify travel-mapper project ID is rejected fail-closed."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="staging",
            FIREBASE_PROJECT_ID="travel-mapper-9dffe",
            API_DATABASE_URL="postgresql+asyncpg://db_api_user:pass@remote:5432/db",
            WORKER_DATABASE_URL="postgresql+asyncpg://db_ingestion_worker:pass@remote:5432/db",
            BOOTSTRAP_DATABASE_URL="postgresql+asyncpg://db_bootstrap:pass@remote:5432/db",
            PSEUDONYMIZATION_SALT="prod-secret-salt-99182390",
        )
    assert "Prohibited project ID" in str(exc_info.value)


def test_firebase_app_lifecycle_idempotency():
    """Verify get_or_create_firebase_app returns same named app instance idempotently."""
    app1 = get_or_create_firebase_app("finance-intel-staging-8f2a")
    app2 = get_or_create_firebase_app("finance-intel-staging-8f2a")
    assert app1 is app2
    assert app1.name == "app-finance-intel-staging-8f2a"


def test_verifier_init_with_explicit_project():
    """Verify verifier binds explicitly to configured project."""
    verifier = FirebaseIdentityVerifier(expected_project_id="finance-intel-staging-8f2a")
    assert verifier.expected_project_id == "finance-intel-staging-8f2a"
    assert verifier.app is not None
