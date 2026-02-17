"""
Alembic Migration Environment
Reads settings from app config. Supports both online and offline modes.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add app to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from app.config import settings
from app.models.base import Base

# Import ALL models here so Alembic detects them for autogenerate
from app.models.user import User
from app.models.consent import UserConsent
from app.models.claim import Claim
from app.models.document import Document
from app.models.fraud import FraudAssessment
from app.models.qr import QRAuthorization
from app.models.settlement import Settlement
from app.models.audit import AuditLog
from app.models.access_log import DocumentAccessLog

# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Override sqlalchemy.url with env-variable DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Setup logging from ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL script without connecting to the DB.
    Useful for review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,                   # Detect column type changes
        compare_server_default=True,         # Detect default value changes
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Connects to DB and applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()