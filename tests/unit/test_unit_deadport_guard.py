import os

from app.core.config import settings


def test_unit_deadport_guard_configuration_and_isolation():
    """Permanent unit dead-port guard assertion test.

    Proves that all effective settings database URLs point to sentinel port 1
    (127.0.0.1:1/unit_guard_forbidden) and that dev port 5433 is completely invisible.
    """
    # 1. Assert host is 127.0.0.1
    assert "127.0.0.1" in settings.effective_api_database_url
    assert "127.0.0.1" in settings.effective_worker_database_url
    assert "127.0.0.1" in settings.effective_bootstrap_database_url
    assert "127.0.0.1" in settings.effective_maintenance_database_url
    assert "127.0.0.1" in settings.effective_migration_database_url

    # 2. Assert port is 1
    assert ":1/" in settings.effective_api_database_url
    assert ":1/" in settings.effective_worker_database_url
    assert ":1/" in settings.effective_bootstrap_database_url
    assert ":1/" in settings.effective_maintenance_database_url
    assert ":1/" in settings.effective_migration_database_url

    # 3. Assert database name is unit_guard_forbidden
    assert "unit_guard_forbidden" in settings.effective_api_database_url
    assert "unit_guard_forbidden" in settings.effective_worker_database_url

    # 4. Assert forbidden dev port 5433 is invisible in unit settings
    assert ":5433" not in settings.effective_api_database_url
    assert ":5433" not in settings.effective_worker_database_url
    assert ":5433" not in settings.effective_bootstrap_database_url
    assert ":5433" not in settings.effective_maintenance_database_url
    assert ":5433" not in settings.effective_migration_database_url

    # 5. Assert all canonical env keys are set to dead-port URL
    for env_key in [
        "TEST_API_DATABASE_URL",
        "TEST_WORKER_DATABASE_URL",
        "TEST_BOOTSTRAP_DATABASE_URL",
        "TEST_MAINTENANCE_DATABASE_URL",
        "TEST_OWNER_DATABASE_URL",
        "API_DATABASE_URL",
        "WORKER_DATABASE_URL",
    ]:
        assert os.environ.get(env_key) == "postgresql+asyncpg://unit_guard:unit_guard@127.0.0.1:1/unit_guard_forbidden"
