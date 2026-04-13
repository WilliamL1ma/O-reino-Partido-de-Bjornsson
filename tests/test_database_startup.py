import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database


class LocalPostgresStartupTests(unittest.TestCase):
    def test_starts_compose_db_when_local_port_is_closed_and_container_is_missing(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "POSTGRES_HOST": "127.0.0.1",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "bjornsson",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                },
                clear=True,
            ),
            patch.object(database, "_compose_service_has_container", return_value=False),
            patch.object(database, "_tcp_port_is_open", return_value=False),
            patch.object(database, "_start_compose_service") as start_compose_service,
        ):
            database.ensure_local_postgres_container()

        start_compose_service.assert_called_once_with("db")

    def test_starts_existing_compose_db_container_without_checking_the_port(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "POSTGRES_HOST": "127.0.0.1",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "bjornsson",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                },
                clear=True,
            ),
            patch.object(database, "_compose_service_has_container", return_value=True),
            patch.object(database, "_tcp_port_is_open") as tcp_port_is_open,
            patch.object(database, "_start_compose_service") as start_compose_service,
        ):
            database.ensure_local_postgres_container()

        start_compose_service.assert_called_once_with("db")
        tcp_port_is_open.assert_not_called()

    def test_keeps_external_local_postgres_when_port_is_open_and_container_is_missing(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "POSTGRES_HOST": "127.0.0.1",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "bjornsson",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                },
                clear=True,
            ),
            patch.object(database, "_compose_service_has_container", return_value=False),
            patch.object(database, "_tcp_port_is_open", return_value=True),
            patch.object(database, "_start_compose_service") as start_compose_service,
        ):
            database.ensure_local_postgres_container()

        start_compose_service.assert_not_called()

    def test_does_not_start_local_container_for_remote_database_url(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "DATABASE_URL": "postgresql+psycopg2://postgres:postgres@db.example.com:5432/bjornsson",
                },
                clear=True,
            ),
            patch.object(database, "_compose_service_has_container") as compose_service_has_container,
            patch.object(database, "_start_compose_service") as start_compose_service,
        ):
            database.ensure_local_postgres_container()

        compose_service_has_container.assert_not_called()
        start_compose_service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
