"""All database access of the application; SQL lives here and nowhere else."""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Chunk, Paper, Review, Run, User
from src.db.session import create_session_factory
from src.llm.settings import get_settings

LOCAL_USER_EMAIL = "local@localhost"
RUN_INITIAL_STEP = "initialized"
RUN_INITIAL_MESSAGE = "Pipeline initialized, adding to background tasks..."
UNFINISHED_STATUSES = ("pending", "running")
DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/")


@dataclass(frozen=True)
class NewChunk:
    """A chunk to store: one text window of a page with its embedding."""

    page: int
    ordinal: int
    text: str
    embedding: list[float]


def normalize_doi(doi: str | None) -> str | None:
    """Lowercase a DOI and strip its resolver URL prefix; empty values become None."""
    if not doi:
        return None
    return DOI_PREFIX.sub("", doi.strip().lower()) or None


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


@lru_cache
def get_repository() -> PostgresRepository:
    """Return the repository on the database from settings (the single data-access seam)."""
    return PostgresRepository(create_session_factory(get_settings().database_url))
