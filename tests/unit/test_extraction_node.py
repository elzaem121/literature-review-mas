import asyncio

from src.pipeline.extraction.node import extraction_node
from src.pipeline.extraction.schemas import ExtractedPaperInfo
from tests.fakes import default_registry

CHUNKS = {"method_chunks": ["We interviewed twenty adolescents."]}


def _included(title: str, **extra) -> dict:
    return {
        "paper": {"title": title, "year": 2023, "authors": ["A"], "doi": "10.1/x", "url": "u"},
        "screening": {},
        **extra,
    }


def test_canned_extraction_round_trips_into_the_state_shape():
    state = {
        "research_question": "RQ",
        "screening_results": {
            "included_papers": [
                _included("With PDF", pdf_path="a.pdf", retrieved_chunks_by_field=CHUNKS)
            ]
        },
    }

    result = asyncio.run(extraction_node(state))

    canned = default_registry()[ExtractedPaperInfo].model_dump()
    assert result["current_step"] == "completed"
    assert result["extracted_papers"] == [
        {
            "paper": {
                "title": "With PDF",
                "year": 2023,
                "authors": ["A"],
                "doi": "10.1/x",
                "url": "u",
            },
            "rag_extraction": canned,
        }
    ]


def test_papers_without_pdf_or_chunks_are_skipped():
    state = {
        "research_question": "RQ",
        "screening_results": {
            "included_papers": [
                _included("No PDF"),
                _included("No chunks", pdf_path="b.pdf"),
            ]
        },
    }

    assert asyncio.run(extraction_node(state))["extracted_papers"] == []
