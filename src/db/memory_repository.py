"""In-memory repository for the unit tests: the same methods as `PostgresRepository`, no database.

Retrieval is brute-force cosine similarity. Payloads go through a JSON round trip, as they do in a
JSONB column, so values that Postgres would reject fail here too.
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np

from src.db.models import INGESTION_STATUSES, Chunk, Paper, Review, Run
from src.db.records import (
    RUN_INITIAL_MESSAGE,
    RUN_INITIAL_STEP,
    UNFINISHED_STATUSES,
    NewChunk,
    normalize_doi,
)


def _json_round_trip(value: Any) -> Any:
    return json.loads(json.dumps(value))


class InMemoryRepository:
    """Run lifecycle and library access held in Python dicts; state lives as long as the object."""

    def __init__(self) -> None:
        self._reviews: dict[int, Review] = {}
        self._runs: dict[uuid.UUID, Run] = {}
        self._papers: dict[int, Paper] = {}
        self._chunks: dict[int, list[Chunk]] = {}

    def create_run(
        self, question: str, criteria: dict[str, Any], provenance: dict[str, Any]
    ) -> uuid.UUID:
        """Store a review and its `pending` run."""
        review_id = len(self._reviews) + 1
        self._reviews[review_id] = Review(
            id=review_id, question=question, criteria=_json_round_trip(criteria)
        )
        run = Run(
            id=uuid.uuid4(),
            review_id=review_id,
            status="pending",
            current_step=RUN_INITIAL_STEP,
            status_message=RUN_INITIAL_MESSAGE,
            result={"provenance": _json_round_trip(provenance)},
        )
        self._runs[run.id] = run
        return run.id

    def start_run(self, run_id: uuid.UUID) -> None:
        """Flip a run from `pending` to `running`."""
        self._runs[run_id].status = "running"

    def update_run_step(
        self, run_id: uuid.UUID, current_step: str, status_message: str, payload: dict[str, Any]
    ) -> None:
        """Store the latest step, message and payload fields; payload keys overwrite in `result`."""
        run = self._runs[run_id]
        run.current_step = current_step
        run.status_message = status_message
        run.result = {**run.result, **_json_round_trip(payload)}

    def finish_run(self, run_id: uuid.UUID, status: str, status_message: str) -> None:
        """Mark a run `completed` or `failed` with its final message."""
        run = self._runs[run_id]
        run.status = status
        run.status_message = status_message
        run.finished_at = datetime.now(UTC)

    def get_run(self, run_id: uuid.UUID) -> Run | None:
        """Return a run by id, or None if it does not exist."""
        return self._runs.get(run_id)

    def mark_unfinished_interrupted(self) -> None:
        """Mark every `pending` or `running` run `interrupted`."""
        for run in self._runs.values():
            if run.status in UNFINISHED_STATUSES:
                run.status = "interrupted"

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
        matches = [
            paper
            for paper in self._papers.values()
            if paper.openalex_id == openalex_id or (normalized_doi and paper.doi == normalized_doi)
        ]
        if not matches:
            paper = Paper(
                id=len(self._papers) + 1,
                openalex_id=openalex_id,
                doi=normalized_doi,
                title=title,
                year=year,
                authors=list(authors),
                venue=venue,
                pdf_url=pdf_url,
                ingestion_status="pending",
            )
            self._papers[paper.id] = paper
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
        return self._papers.get(paper_id)

    def set_paper_status(self, paper_id: int, status: str, last_error: str | None = None) -> None:
        """Set a paper's ingestion status and the error that explains it (None clears it)."""
        if status not in INGESTION_STATUSES:
            raise ValueError(f"Unknown ingestion status '{status}'; expected {INGESTION_STATUSES}")
        paper = self._papers[paper_id]
        paper.ingestion_status = status
        paper.last_error = last_error

    def is_chunked(self, paper_id: int, embedding_model: str, chunker_version: str) -> bool:
        """True if the paper is `chunked` with chunks of this embedding model and chunker."""
        return self._papers[paper_id].ingestion_status == "chunked" and any(
            chunk.embedding_model == embedding_model and chunk.chunker_version == chunker_version
            for chunk in self._chunks.get(paper_id, [])
        )

    def replace_chunks(
        self,
        paper_id: int,
        chunks: Sequence[NewChunk],
        embedding_model: str,
        chunker_version: str,
    ) -> None:
        """Replace a paper's chunks and mark it `chunked`."""
        self._chunks[paper_id] = [
            Chunk(
                paper_id=paper_id,
                page=chunk.page,
                ordinal=chunk.ordinal,
                text=chunk.text,
                embedding=list(chunk.embedding),
                embedding_model=embedding_model,
                chunker_version=chunker_version,
            )
            for chunk in chunks
        ]
        self.set_paper_status(paper_id, "chunked")

    def search_chunks(self, paper_id: int, query_embedding: list[float], limit: int) -> list[str]:
        """Return the texts of a paper's `limit` chunks closest to the query by cosine distance."""
        query = np.asarray(query_embedding, dtype=float)

        def distance(chunk: Chunk) -> float:
            vector = np.asarray(chunk.embedding, dtype=float)
            return 1.0 - float(vector @ query / (np.linalg.norm(vector) * np.linalg.norm(query)))

        ranked = sorted(self._chunks.get(paper_id, []), key=lambda c: (distance(c), c.ordinal))
        return [chunk.text for chunk in ranked[:limit]]
