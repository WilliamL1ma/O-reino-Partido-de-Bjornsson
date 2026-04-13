import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "bjornsson")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
    future=True,
)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def remove_session() -> None:
    SessionLocal.remove()


def _is_local_postgres_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _tcp_port_is_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_database_host_and_port() -> tuple[str, int] | None:
    url = make_url(get_database_url())
    if not url.drivername.startswith("postgresql"):
        return None

    host = url.host or os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = url.port or int(os.getenv("POSTGRES_PORT", "5432"))
    return host, port


def _run_docker_compose(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


def _compose_service_has_container(service: str) -> bool:
    try:
        result = _run_docker_compose(["ps", "-a", "-q", service])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    return bool(result.stdout.strip())


def _start_compose_service(service: str) -> None:
    try:
        _run_docker_compose(["up", "-d", service])
    except FileNotFoundError:
        return
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip()
        stdout = error.stdout.strip()
        details = stderr or stdout or f"Falha ao subir o container do servico {service}."
        raise RuntimeError(details) from error


def ensure_local_postgres_container() -> None:
    database_endpoint = _get_database_host_and_port()
    if database_endpoint is None:
        return

    host, port = database_endpoint
    if not _is_local_postgres_host(host):
        return

    compose_file = ROOT_DIR / "docker-compose.yml"
    if not compose_file.exists():
        return

    if _compose_service_has_container("db"):
        _start_compose_service("db")
        return

    if _tcp_port_is_open(host, port):
        return

    _start_compose_service("db")


def _quote_postgres_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def ensure_database_exists() -> None:
    ensure_local_postgres_container()
    database_url = get_database_url()
    url = make_url(database_url)

    if not url.drivername.startswith("postgresql"):
        return

    target_database = url.database
    if not target_database:
        return

    maintenance_database = os.getenv("POSTGRES_MAINTENANCE_DB", "postgres")
    admin_engine = create_engine(
        url.set(database=maintenance_database),
        pool_pre_ping=True,
        future=True,
        isolation_level="AUTOCOMMIT",
    )

    try:
        with admin_engine.connect() as connection:
            database_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": target_database},
            ).scalar()

            if database_exists:
                return

            quoted_database_name = _quote_postgres_identifier(target_database)
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_database_name}")
    finally:
        admin_engine.dispose()


def wait_for_database() -> None:
    retries = int(os.getenv("DB_CONNECT_RETRIES", "20"))
    delay_seconds = float(os.getenv("DB_CONNECT_DELAY", "1.5"))
    last_error = None

    for _ in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as error:
            last_error = error
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error
