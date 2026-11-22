"""All database access of the application; SQL lives here and nowhere else."""

import uuid
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from sqlalchemy import cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker

from src.db.memory_repository import InMemoryRepository
from src.db.models import Chunk, Paper, Review, Run, User
from src.db.records import (
    LOCAL_USER_EMAIL,
    RUN_INITIAL_MESSAGE,
    RUN_INITIAL_STEP,
    UNFINISHED_STATUSES,
    NewChunk,
    normalize_doi,
)
from src.db.session import create_session_factory
from src.llm.settings import get_settings


class PostgresRepository:
    """Run lifecycle and library access on Postgres; every method is blocking (sync engine)."""

    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def create_run(
        self, question: str, criteria: dict[str, Any], provenance: dict[str, Any]
    ) -> uuid.UUID:
        """Insert a review and its `pending` run for the local user in one transaction."""
        with self._sessions.begin() as session:
            user_id = session.scalar(select(User.id).where(User.email == LOCAL_USER_EMAIL))
            if user_id is None:
                raise RuntimeError(
                    f"User '{LOCAL_USER_EMAIL}' is missing; run the migrations (`make migrate`)."
                )
            review = Review(user_id=user_id, question=question, criteria=criteria)
            session.add(review)
            session.flush()
            run = Run(
                user_id=user_id,
                review_id=review.id,
                status="pending",
                current_step=RUN_INITIAL_STEP,
                status_message=RUN_INITIAL_MESSAGE,
                result={"provenance": provenance},
            )
            session.add(run)
            session.flush()
            return run.id

    def start_run(self, run_id: uuid.UUID) -> None:
        """Flip a run from `pending` to `running`."""
        with self._sessions.begin() as session:
            session.execute(update(Run).where(Run.id == run_id).values(status="running"))

    def update_run_step(
        self, run_id: uuid.UUID, current_step: str, status_message: str, payload: dict[str, Any]
    ) -> None:
        """Store the latest step, message and payload fields; payload keys overwrite in `result`."""
        with self._sessions.begin() as session:
            session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(
                    current_step=current_step,
                    status_message=status_message,
                    result=Run.result.op("||")(cast(payload, JSONB)),
                )
            )

    def finish_run(self, run_id: uuid.UUID, status: str, status_message: str) -> None:
        """Mark a run `completed` or `failed` with its final message."""
        with self._sessions.begin() as session:
            session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(status=status, status_message=status_message, finished_at=func.now())
            )

    def get_run(self, run_id: uuid.UUID) -> Run | None:
        """Return a run by id, or None if it does not exist."""
        with self._sessions() as session:
            return session.get(Run, run_id)

    def mark_unfinished_interrupted(self) -> None:
        """Mark every `pending` or `running` run `interrupted` (called once at API start)."""
        with self._sessions.begin() as session:
            session.execute(
                update(Run).where(Run.status.in_(UNFINISHED_STATUSES)).values(status="interrupted")
            )

    def upsert_paper(
        self,
        *,
        openalex_id: str,
        doi: str | None,
        title: str,
        year: int | None,
        authors: list[str],
        venue: str | None,
        pdf_url: str | None,
    ) -> int:
        """Insert a paper or merge it into the one with the same OpenAlex id or DOI; return its id.

        The first-seen `openalex_id` wins; DOI, year, venue and PDF URL fill in when first known.
        """
        normalized_doi = normalize_doi(doi)
        keys = [Paper.openalex_id == openalex_id]
        if normalized_doi:
            keys.append(Paper.doi == normalized_doi)
        with self._sessions.begin() as session:
            matches = session.scalars(select(Paper).where(or_(*keys)).order_by(Paper.id)).all()
            if not matches:
                paper = Paper(
                    openalex_id=openalex_id,
                    doi=normalized_doi,
                    title=title,
                    year=year,
                    authors=authors,
                    venue=venue,
                    pdf_url=pdf_url,
                )
                session.add(paper)
                session.flush()
                return paper.id
            paper = matches[0]
            if paper.doi is None and len(matches) == 1:
                paper.doi = normalized_doi
            paper.year = paper.year if paper.year is not None else year
            paper.venue = paper.venue or venue
            paper.pdf_url = paper.pdf_url or pdf_url
            return paper.id

    def get_paper(self, paper_id: int) -> Paper | None:
        """Return a paper by id, or None if it does not exist."""
        with self._sessions() as session:
            return session.get(Paper, paper_id)

    def set_paper_status(self, paper_id: int, status: str, last_error: str | None = None) -> None:
        """Set a paper's ingestion status and the error that explains it (None clears it)."""
        with self._sessions.begin() as session:
            session.execute(
                update(Paper)
                .where(Paper.id == paper_id)
                .values(ingestion_status=status, last_error=last_error)
            )

    def is_chunked(self, paper_id: int, embedding_model: str, chunker_version: str) -> bool:
        """True if the paper is `chunked` with chunks of this embedding model and chunker version.

        Chunks are replaced as a set, so one chunk row speaks for all of them.
        """
        with self._sessions() as session:
            return (
                session.scalar(
                    select(Chunk.id)
                    .join(Paper, Paper.id == Chunk.paper_id)
                    .where(
                        Chunk.paper_id == paper_id,
                        Paper.ingestion_status == "chunked",
                        Chunk.embedding_model == embedding_model,
                        Chunk.chunker_version == chunker_version,
                    )
                    .limit(1)
                )
                is not None
            )

    def replace_chunks(
        self,
        paper_id: int,
        chunks: Sequence[NewChunk],
        embedding_model: str,
        chunker_version: str,
    ) -> None:
        """Replace a paper's chunks and mark it `chunked` in one transaction."""
        with self._sessions.begin() as session:
            session.execute(delete(Chunk).where(Chunk.paper_id == paper_id))
            session.add_all(
                Chunk(
                    paper_id=paper_id,
                    page=chunk.page,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    embedding=chunk.embedding,
                    embedding_model=embedding_model,
                    chunker_version=chunker_version,
                )
                for chunk in chunks
            )
            session.execute(
                update(Paper)
                .where(Paper.id == paper_id)
                .values(ingestion_status="chunked", last_error=None)
            )

    def search_chunks(self, paper_id: int, query_embedding: list[float], limit: int) -> list[str]:
        """Return the texts of a paper's `limit` chunks closest to the query by cosine distance."""
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(Chunk.text)
                    .where(Chunk.paper_id == paper_id)
                    .order_by(Chunk.embedding.cosine_distance(query_embedding), Chunk.ordinal)
                    .limit(limit)
                )
            )


Repository = PostgresRepository | InMemoryRepository


@lru_cache
def get_repository() -> Repository:
    """Return the repository chosen by `REPOSITORY_BACKEND` (the single data-access seam)."""
    settings = get_settings()
    if settings.repository_backend == "memory":
        return InMemoryRepository()
    return PostgresRepository(create_session_factory(settings.database_url))
