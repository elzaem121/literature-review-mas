"""Alembic environment: the database URL comes from settings; migrations run sync."""

from alembic import context
from sqlalchemy import create_engine

from src.db.models import Base
from src.llm.settings import get_settings

target_metadata = Base.metadata


def run_migrations() -> None:
    """Apply migrations to the configured database in one transaction."""
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
