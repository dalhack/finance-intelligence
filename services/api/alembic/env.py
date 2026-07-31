import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from services.api.app.core.config import settings
from services.api.app.db.base import Base

# Import all models to register with Base metadata
from services.api.app.models.audit_event import AuditEvent  # noqa: F401
from services.api.app.models.membership import Membership  # noqa: F401
from services.api.app.models.organization import Organization  # noqa: F401
from services.api.app.models.role import MembershipRole, Role  # noqa: F401
from services.api.app.models.user import User  # noqa: F401

config = context.config

x_args = context.get_x_argument(as_dictionary=True)
raw_url = (
    os.environ.get("ALEMBIC_TARGET_URL")
    or x_args.get("sqlalchemy.url")
    or os.environ.get("TEST_OWNER_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
    or settings.DATABASE_URL
)


assert raw_url is not None
sync_url: str = raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
