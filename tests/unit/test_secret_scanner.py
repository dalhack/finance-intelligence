import pytest

from scripts.verify_boundary import scan_content


@pytest.mark.unit
def test_unknown_hardcoded_db_password_fails():
    content = 'DATABASE_URL = "postgresql://prod_user:unapproved_secret_pass_888@localhost:5432/finance_db"'
    findings, _fixtures = scan_content("/path/to/tests/unit/test_config.py", content, "tests/unit/test_config.py")
    assert len(findings) == 1
    assert "Unapproved hardcoded DB password 'unapproved_secret_pass_888'" in findings[0]
    assert len(_fixtures) == 0


@pytest.mark.unit
def test_approved_ci_test_fixture_in_allowed_path_passes():
    content = (
        "TEST_OWNER_DATABASE_URL ="
        ' "postgresql+asyncpg://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test"'
    )
    findings, fixtures = scan_content(
        "/path/to/tests/integration/test_rls_postgres.py", content, "tests/integration/test_rls_postgres.py"
    )
    assert len(findings) == 0
    assert len(fixtures) == 1
    assert fixtures[0][0] == "dev_owner_pass_123"
    assert fixtures[0][2] == 1


@pytest.mark.unit
def test_approved_fixture_in_production_source_fails():
    content = 'DATABASE_URL = "postgresql://prod_user:dev_owner_pass_123@localhost:5432/prod_db"'
    findings, _fixtures = scan_content("/path/to/services/api/app/main.py", content, "services/api/app/main.py")
    assert len(findings) == 1
    assert "leaked into production path: services/api/app/main.py" in findings[0]


@pytest.mark.unit
def test_private_key_header_fails():
    content = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC..."
    findings, _fixtures = scan_content("/path/to/keys/server.key", content, "keys/server.key")
    assert len(findings) == 1
    assert "Hardcoded Private Key in keys/server.key" in findings[0]


@pytest.mark.unit
def test_firebase_provider_key_fails():
    content = 'FIREBASE_KEY = "AIzaSyD' + "123456789012345678901234567890123" + '"'
    findings, _fixtures = scan_content("/path/to/config.py", content, "config.py")
    assert len(findings) == 1
    assert "Hardcoded Firebase Key" in findings[0]


@pytest.mark.unit
def test_anthropic_provider_key_fails():
    content = 'ANTHROPIC_KEY = "sk-ant-api03-' + "123456789012345678901234567890123" + '"'
    findings, _fixtures = scan_content("/path/to/config.py", content, "config.py")
    assert len(findings) == 1
    assert "Hardcoded Anthropic Key" in findings[0]


@pytest.mark.unit
def test_clean_source_file_passes():
    content = """
def calculate_sum(a: int, b: int) -> int:
    return a + b
"""
    findings, fixtures = scan_content("/path/to/services/api/app/utils.py", content, "services/api/app/utils.py")
    assert len(findings) == 0
    assert len(fixtures) == 0
