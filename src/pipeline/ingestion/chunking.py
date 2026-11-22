"""Page-aware chunking: fixed-size windows per page, no overlap."""

from collections.abc import Sequence
from dataclasses import dataclass

CHUNK_SIZE = 1200
# Bump when chunking changes; ingestion re-chunks papers stored with another version.
CHUNKER_VERSION = "v1"


@dataclass(frozen=True)
class PageChunk:
    """A text window of one page; `page` is 1-based, `ordinal` counts from 0 within the paper."""

    page: int
    ordinal: int
    text: str


def chunk_pages(pages: Sequence[str]) -> list[PageChunk]:
    """Split each page into `CHUNK_SIZE`-character windows; whitespace-only pages are skipped."""
    chunks: list[PageChunk] = []
    for page_number, text in enumerate(pages, start=1):
        if not text.strip():
            continue
        for start in range(0, len(text), CHUNK_SIZE):
            chunks.append(PageChunk(page_number, len(chunks), text[start : start + CHUNK_SIZE]))
    return chunks
