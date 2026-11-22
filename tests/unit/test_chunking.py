"""Chunking is page-aware and, while Phase 1 has no overlap, a partition of each page's text."""

from pathlib import Path

import pytest

from src.pipeline.ingestion.chunking import CHUNK_SIZE, chunk_pages
from src.pipeline.ingestion.pdf import extract_pages_from_pdf

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _by_page(chunks) -> dict[int, str]:
    pages: dict[int, str] = {}
    for chunk in chunks:
        pages[chunk.page] = pages.get(chunk.page, "") + chunk.text
    return pages


def test_concatenating_a_pages_chunks_reproduces_the_page():
    # Phase-1-only invariant: it is retired when chunk overlap arrives (Phase 2b).
    pages = ["a" * (CHUNK_SIZE * 2 + 17), "short page", "b" * CHUNK_SIZE]

    chunks = chunk_pages(pages)

    assert _by_page(chunks) == {1: pages[0], 2: pages[1], 3: pages[2]}


@pytest.mark.parametrize("pdf", ["paper_small_1.pdf", "paper_small_2.pdf"])
def test_the_partition_invariant_holds_for_real_pdf_pages(pdf: str):
    pages = extract_pages_from_pdf(FIXTURES / pdf)

    chunks = chunk_pages(pages)

    assert _by_page(chunks) == {n: text for n, text in enumerate(pages, 1) if text.strip()}


def test_pages_are_one_based_and_ordinals_count_from_zero_across_pages():
    chunks = chunk_pages(["x" * (CHUNK_SIZE + 1), "y"])

    assert [(c.page, c.ordinal, len(c.text)) for c in chunks] == [
        (1, 0, CHUNK_SIZE),
        (1, 1, 1),
        (2, 2, 1),
    ]


def test_whitespace_only_pages_are_skipped_but_keep_their_page_numbers():
    chunks = chunk_pages(["first", " \n\t ", "third"])

    assert [(c.page, c.ordinal, c.text) for c in chunks] == [(1, 0, "first"), (3, 1, "third")]


def test_no_pages_or_only_blank_pages_give_no_chunks():
    assert chunk_pages([]) == []
    assert chunk_pages(["", "  "]) == []
