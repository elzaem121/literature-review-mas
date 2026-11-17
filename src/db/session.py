"""Sync SQLAlchemy engine and session factory; async callers go through `asyncio.to_thread`."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Build a session factory on a pooled sync engine for the given database URL."""
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)
