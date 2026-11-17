"""Fixtures for tests against the docker-compose Postgres (`make up` and `make migrate` first)."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from src.db.repository import PostgresRepository, get_repository
from src.db.session import create_session_factory
from src.llm.settings import get_settings

COMPOSE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
TEST_DATABASE_NAME = "literature_review_test"
ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"
LIBRARY_TABLES = "chunks, papers, runs, reviews"

# Read before any fixture overrides DATABASE_URL for a test.
SERVER_DATABASE_URL = os.environ.get("DATABASE_URL", COMPOSE_DATABASE_URL)


def _recreate_database(server_url: str) -> str:
    """Drop and create the dedicated test database on the server; return its URL.

    A separate database keeps `make integration` away from the development library.
    """
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
    admin.dispose()
    return make_url(server_url).set(database=TEST_DATABASE_NAME).render_as_string(False)


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL of a freshly created and migrated test database."""
    url = _recreate_database(SERVER_DATABASE_URL)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", url)
        patch.setenv("OPENALEX_EMAIL", "tests@example.invalid")
        get_settings.cache_clear()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        get_settings.cache_clear()
    return url


@pytest.fixture
def sessions(database_url: str, monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    """Session factory on the test database, emptied of library rows (the seeded user stays)."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    get_repository.cache_clear()
    factory = create_session_factory(database_url)
    with factory.begin() as session:
        session.execute(text(f"TRUNCATE {LIBRARY_TABLES} RESTART IDENTITY CASCADE"))
    yield factory
    get_repository.cache_clear()


@pytest.fixture
def repository(sessions: sessionmaker[Session]) -> PostgresRepository:
    """The application's repository (`get_repository()`), pointed at the test database."""
    return get_repository()
