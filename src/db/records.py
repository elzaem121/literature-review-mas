"""Values and helpers shared by the Postgres and in-memory repositories."""

import re
from dataclasses import dataclass

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
