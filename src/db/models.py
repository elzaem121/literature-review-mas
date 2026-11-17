"""SQLAlchemy models for the library (users, reviews, runs, papers, chunks)."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSIONS = 384
RUN_STATUSES = ("pending", "running", "completed", "failed", "interrupted")
INGESTION_STATUSES = ("pending", "downloaded", "chunked", "pdf_unavailable", "failed")


def _in_list_check(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    """Declarative base of all library tables."""


class User(Base):
    """A library user; one seeded `local` user until authentication exists."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)


class Review(Base):
    """A research question with its criteria."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    question: Mapped[str] = mapped_column(Text)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Run(Base):
    """One pipeline run; `id` is the job id returned to the UI."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(_in_list_check("status", RUN_STATUSES), name="ck_runs_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(Text)
    current_step: Mapped[str] = mapped_column(Text)
    status_message: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Paper(Base):
    """A paper, stored once and shared across reviews."""

    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(
            _in_list_check("ingestion_status", INGESTION_STATUSES),
            name="ck_papers_ingestion_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    openalex_id: Mapped[str] = mapped_column(Text, unique=True)
    doi: Mapped[str | None] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    authors: Mapped[list[str]] = mapped_column(JSONB)
    venue: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    ingestion_status: Mapped[str] = mapped_column(Text, server_default="pending")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    """A page-aware text chunk of a paper with its embedding."""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("paper_id", "ordinal", name="uq_chunks_paper_id_ordinal"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str] = mapped_column(Text)
    chunker_version: Mapped[str] = mapped_column(Text)
