"""Alembic environment: the database URL comes from settings; migrations run sync."""

from alembic import context
from sqlalchemy import create_engine

from src.db.models import Base
from src.llm.settings import get_settings

target_metadata = Base.metadata


def run_migrations() -> None:
    """Apply migrations to the configured database in one transaction."""
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to run the migrations.")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
