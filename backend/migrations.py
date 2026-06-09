from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from database import _env_flag_is_enabled, ensure_database_exists, engine, get_database_url, wait_for_database


ROOT_DIR = Path(__file__).resolve().parent.parent
POSTGRES_MIGRATION_LOCK_ID = 384_271_905


def run_migrations() -> None:
    if not _env_flag_is_enabled("AUTO_RUN_MIGRATIONS", default=True):
        return

    ensure_database_exists()
    wait_for_database()

    with engine.connect() as connection:
        is_postgres = connection.dialect.name == "postgresql"

        try:
            if is_postgres:
                connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": POSTGRES_MIGRATION_LOCK_ID})

            config = Config(str(ROOT_DIR / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
            config.set_main_option("sqlalchemy.url", get_database_url())
            command.upgrade(config, "head")
        finally:
            if is_postgres:
                connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": POSTGRES_MIGRATION_LOCK_ID})
