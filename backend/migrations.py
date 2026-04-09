from pathlib import Path

from alembic import command
from alembic.config import Config

from database import ensure_database_exists, get_database_url, wait_for_database


ROOT_DIR = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    ensure_database_exists()
    wait_for_database()
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", get_database_url())
    command.upgrade(config, "head")
