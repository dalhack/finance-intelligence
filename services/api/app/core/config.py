import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_DEV_SALT = "dev-salt-3918204918239012830129"
DEFAULT_DEV_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/finance_intelligence"
DEFAULT_DEV_API_URL = "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test"
DEFAULT_DEV_WORKER_URL = (
    "postgresql+asyncpg://db_ingestion_worker:dev_worker_pass_123@localhost:5433/finance_intelligence_test"
)
DEFAULT_DEV_BOOTSTRAP_URL = (
    "postgresql+asyncpg://db_bootstrap:dev_bootstrap_pass_123@localhost:5433/finance_intelligence_test"
)
DEFAULT_DEV_MAINTENANCE_URL = (
    "postgresql+asyncpg://db_maintenance_worker:dev_maintenance_pass_123@localhost:5433/finance_intelligence_test"
)
DEFAULT_DEV_MIGRATION_URL = "postgresql+asyncpg://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test"
DEV_PASSWORDS = {
    "dev_api_user_pass_123",
    "dev_worker_pass_123",
    "dev_bootstrap_pass_123",
    "dev_maintenance_pass_123",
    "dev_owner_pass_123",
    "postgres",
    "password",
    "123456",
}


def extract_role_name(url: str | None) -> str | None:
    """Safely extract normalized PostgreSQL username/role using SQLAlchemy make_url without logging passwords."""
    if not url:
        return None
    try:
        parsed = make_url(url)
        return parsed.username.lower() if parsed.username else None
    except (ArgumentError, ValueError):
        return None


class Settings(BaseSettings):
    PROJECT_NAME: str = "Finance Intelligence API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="Options: development, test, staging, production")
    DEBUG: bool = Field(default=False)

    # Database URLs
    DATABASE_URL: str = Field(default=DEFAULT_DEV_DB_URL, description="Fallback Async PostgreSQL Connection String")
    API_DATABASE_URL: str | None = Field(default=None, description="Async PostgreSQL Connection String for db_api_user")
    WORKER_DATABASE_URL: str | None = Field(
        default=None, description="Async PostgreSQL Connection String for db_ingestion_worker"
    )
    BOOTSTRAP_DATABASE_URL: str | None = Field(
        default=None, description="Async PostgreSQL Connection String for db_bootstrap"
    )
    MAINTENANCE_DATABASE_URL: str | None = Field(
        default=None, description="Async PostgreSQL Connection String for db_maintenance_worker"
    )
    MIGRATION_DATABASE_URL: str | None = Field(
        default=None, description="Async PostgreSQL Connection String for db_owner (Migrations only)"
    )

    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Central Parser & Document Resource Limits
    MAX_PDF_PAGES: int = 100
    MAX_PDF_TEXT_CHARS: int = 500000
    MAX_PDF_TABLES: int = 100
    MAX_XLSX_SHEETS: int = 50
    MAX_XLSX_ROWS: int = 100000
    MAX_XLSX_COLS: int = 500
    MAX_CELL_LEN: int = 32767
    MAX_CSV_ROWS: int = 100000
    MAX_CSV_COLS: int = 500
    MAX_EXTRACTED_CHARS: int = 500000

    # ZIP Archive & ZIP Bomb Protection Limits
    MAX_ZIP_ENTRIES: int = 1000
    MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MAX_ZIP_COMPRESSION_RATIO: float = 100.0

    # Pseudonymization Secret (Salt)
    PSEUDONYMIZATION_SALT: str | None = Field(
        default=DEFAULT_DEV_SALT, description="Salt used for log pseudonymization"
    )

    # Object Storage Config ('local' for development, 'gcs' for staging/production)
    STORAGE_BACKEND: str = Field(default="local")
    STORAGE_BUCKET: str | None = Field(default=None, description="GCS bucket name when STORAGE_BACKEND=gcs")

    # Firebase / App Check Config
    FIREBASE_PROJECT_ID: str | None = None
    ENFORCE_APP_CHECK: bool = Field(default=False)
    APP_CHECK_AUDIT_MODE: bool = Field(default=True)
    STRICT_APP_CHECK_ENFORCEMENT: bool = Field(default=False)

    # Anthropic Model Configuration Settings
    ANTHROPIC_BALANCED_MODEL_ID: str | None = Field(
        default=None, description="Anthropic Model ID for finance_analysis_balanced alias"
    )
    ANTHROPIC_FAST_MODEL_ID: str | None = Field(
        default=None, description="Anthropic Model ID for finance_analysis_fast alias"
    )
    ANTHROPIC_API_KEY: str | None = Field(default=None, description="Anthropic API Key or Secret Reference")
    ANTHROPIC_TIMEOUT_SECONDS: float = Field(default=30.0)
    ANTHROPIC_MAX_OUTPUT_TOKENS: int = Field(default=4096)
    ANTHROPIC_PROMPT_CACHE_ENABLED: bool = Field(default=True)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in ("development", "dev", "test")

    @property
    def effective_api_database_url(self) -> str:
        if self.API_DATABASE_URL:
            return self.API_DATABASE_URL
        if os.environ.get("TEST_API_DATABASE_URL"):
            return os.environ["TEST_API_DATABASE_URL"]
        if self.is_development:
            return DEFAULT_DEV_API_URL
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: API_DATABASE_URL must be explicitly configured in production/staging."
        )

    @property
    def effective_worker_database_url(self) -> str:
        if self.WORKER_DATABASE_URL:
            return self.WORKER_DATABASE_URL
        if os.environ.get("TEST_WORKER_DATABASE_URL"):
            return os.environ["TEST_WORKER_DATABASE_URL"]
        if self.is_development:
            return DEFAULT_DEV_WORKER_URL
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: WORKER_DATABASE_URL must be explicitly configured in production/staging."
        )

    @property
    def effective_bootstrap_database_url(self) -> str:
        if self.BOOTSTRAP_DATABASE_URL:
            return self.BOOTSTRAP_DATABASE_URL
        if os.environ.get("TEST_BOOTSTRAP_DATABASE_URL"):
            return os.environ["TEST_BOOTSTRAP_DATABASE_URL"]
        if self.is_development:
            return DEFAULT_DEV_BOOTSTRAP_URL
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: BOOTSTRAP_DATABASE_URL must be explicitly configured in production/staging."
        )

    @property
    def effective_maintenance_database_url(self) -> str:
        if self.MAINTENANCE_DATABASE_URL:
            return self.MAINTENANCE_DATABASE_URL
        if os.environ.get("TEST_MAINTENANCE_DATABASE_URL"):
            return os.environ["TEST_MAINTENANCE_DATABASE_URL"]
        if os.environ.get("TEST_WORKER_DATABASE_URL"):
            return os.environ["TEST_WORKER_DATABASE_URL"]
        if self.is_development:
            return DEFAULT_DEV_MAINTENANCE_URL
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: MAINTENANCE_DATABASE_URL must be explicitly configured in production/staging."
        )

    @property
    def effective_migration_database_url(self) -> str:
        if self.MIGRATION_DATABASE_URL:
            return self.MIGRATION_DATABASE_URL
        if os.environ.get("TEST_OWNER_DATABASE_URL"):
            return os.environ["TEST_OWNER_DATABASE_URL"]
        if self.is_development:
            return DEFAULT_DEV_MIGRATION_URL
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: MIGRATION_DATABASE_URL must be explicitly configured in production/staging."
        )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        env_clean = self.ENVIRONMENT.lower().strip()
        if env_clean in ("production", "staging"):
            if self.DEBUG:
                raise ValueError("CRITICAL SECURITY VIOLATION: DEBUG mode cannot be True in production/staging.")
            if not self.PSEUDONYMIZATION_SALT or self.PSEUDONYMIZATION_SALT == DEFAULT_DEV_SALT:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: PSEUDONYMIZATION_SALT must be configured to a non-default secret in production/staging."
                )
            if not self.FIREBASE_PROJECT_ID or not self.FIREBASE_PROJECT_ID.strip():
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: FIREBASE_PROJECT_ID must be explicitly provided in production/staging."
                )
            if "travel-mapper" in self.FIREBASE_PROJECT_ID.lower():
                raise ValueError("CRITICAL SECURITY VIOLATION: Prohibited project ID cannot be configured.")

            # Strict Production Role Isolation Verification
            if not self.API_DATABASE_URL:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: API_DATABASE_URL must be explicitly provided in production/staging."
                )
            if not self.WORKER_DATABASE_URL:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: WORKER_DATABASE_URL must be explicitly provided in production/staging."
                )
            if not self.BOOTSTRAP_DATABASE_URL:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: BOOTSTRAP_DATABASE_URL must be explicitly provided in production/staging."
                )

            api_url = make_url(self.API_DATABASE_URL)
            worker_url = make_url(self.WORKER_DATABASE_URL)
            bootstrap_url = make_url(self.BOOTSTRAP_DATABASE_URL)

            api_role = api_url.username.lower() if api_url.username else ""
            worker_role = worker_url.username.lower() if worker_url.username else ""
            bootstrap_role = bootstrap_url.username.lower() if bootstrap_url.username else ""

            if api_role != "db_api_user":
                raise ValueError(
                    f"CRITICAL SECURITY VIOLATION: API_DATABASE_URL must use role 'db_api_user', got '{api_role}'."
                )
            if worker_role != "db_ingestion_worker":
                raise ValueError(
                    f"CRITICAL SECURITY VIOLATION: WORKER_DATABASE_URL must use role 'db_ingestion_worker', got '{worker_role}'."
                )
            if bootstrap_role != "db_bootstrap":
                raise ValueError(
                    f"CRITICAL SECURITY VIOLATION: BOOTSTRAP_DATABASE_URL must use role 'db_bootstrap', got '{bootstrap_role}'."
                )

            if len({api_role, worker_role, bootstrap_role}) < 3:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: API_DATABASE_URL, WORKER_DATABASE_URL, and BOOTSTRAP_DATABASE_URL must use distinct PostgreSQL roles in production/staging."
                )

            # Check for localhost in production
            for role_name, u in [("API", api_url), ("WORKER", worker_url), ("BOOTSTRAP", bootstrap_url)]:
                if u.host in ("localhost", "127.0.0.1", "::1"):
                    raise ValueError(
                        f"CRITICAL SECURITY VIOLATION: {role_name}_DATABASE_URL uses localhost in production/staging."
                    )
                if u.password in DEV_PASSWORDS:
                    raise ValueError(
                        f"CRITICAL SECURITY VIOLATION: {role_name}_DATABASE_URL uses default dev password in production/staging."
                    )

            # Check that migration database URL / db_owner is not passed as runtime API/Worker URL
            if "db_owner" in {api_role, worker_role, bootstrap_role}:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: MIGRATION_DATABASE_URL (db_owner) cannot be used as runtime database connection."
                )

        return self


settings = Settings()
