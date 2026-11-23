"""The Phase 1 adapter: wraps the graph's own code in the harness contract.

This is the only harness module that imports the pipeline from `src`.
"""

from typing import Any

import openai
from instructor.core.exceptions import InstructorError

from eval.harness.records import (
    SCORED_FIELDS,
    ExtractionOutput,
    FieldRecord,
    FieldStatus,
    RetrievedChunk,
    ScoredField,
    ScreeningRecord,
    SearchRecord,
)
from eval.harness.topics import Topic, render_screener_input
from src.db.memory_repository import InMemoryRepository
from src.db.records import NewChunk
from src.graph.nodes import screening_node
from src.llm.client import get_llm
from src.llm.prompts import extraction as extraction_prompt
from src.llm.prompts import screening as screening_prompt
from src.llm.prompts import search as search_prompt
from src.llm.settings import get_settings
from src.pipeline.extraction.node import extract_from_retrieved_chunks
from src.pipeline.extraction.schemas import ExtractedPaperInfo
from src.pipeline.ingestion.chunking import CHUNKER_VERSION, PageChunk, chunk_pages
from src.pipeline.ingestion.retrieval import RETRIEVAL_TOP_K, embed_texts, retrieve_field_chunks
from src.pipeline.search.new_main import main as run_search

SEARCH_TARGET_OUTPUT_COUNT = 25
# `screening_node` builds its agent with this limit; the provenance reports it.
SCREENING_CONCURRENCY = 3
RETRIEVAL_FIELDS: dict[str, ScoredField] = {
    "method_chunks": "method",
    "dataset_chunks": "dataset",
    "task_chunks": "task",
    "findings_chunks": "main_findings",
    "limitations_chunks": "limitations",
}
NOT_FOUND_PREFIXES = ("not specified", "not explicitly specified", "not mentioned", "not stated")
NOT_FOUND_VALUES = ("no empirical dataset",)
SCREENING_BUCKETS = {
    "included_papers": "include",
    "excluded_papers": "exclude",
    "uncertain_papers": "uncertain",
}
EXTRACTION_ERRORS = (openai.OpenAIError, InstructorError)


def v1_status(value: str) -> FieldStatus:
    """Read a status out of v1's free text: absence phrases and an empty value are `not_found`."""
    text = value.strip().lower()
    if not text or text.startswith(NOT_FOUND_PREFIXES) or text in NOT_FOUND_VALUES:
        return "not_found"
    return "found"


def extraction_messages(
    paper: dict[str, Any], chunks: list[RetrievedChunk], research_question: str
) -> list[dict[str, str]]:
    """The messages `extract_from_retrieved_chunks` sends for a paper and its retrieved chunks."""
    return [
        {"role": "system", "content": extraction_prompt.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": extraction_prompt.render_user_prompt(
                research_question=research_question,
                title=paper.get("title"),
                retrieved_chunks_by_field=_chunk_texts_by_key(chunks),
            ),
        },
    ]


async def reported_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """The prompt token count Ollama reports for one extraction call (for the truncation check)."""
    _, completion = await get_llm("extraction").chat.completions.create_with_completion(
        model=get_settings().extraction_model,
        response_model=ExtractedPaperInfo,
        messages=messages,
        temperature=0,
    )
    return completion.usage.prompt_tokens


def _chunk_texts_by_key(chunks: list[RetrievedChunk]) -> dict[str, list[str]]:
    """The retrieval node's `retrieved_chunks_by_field`, rebuilt from chunk records."""
    return {
        key: [c.text for c in sorted(chunks, key=lambda c: c.rank) if c.field == name]
        for key, name in RETRIEVAL_FIELDS.items()
    }


class Phase1Adapter:
    """The Phase 1 system behind the four harness calls."""

    name = "phase1"

    async def search(self, topic: Topic) -> SearchRecord:
        """Run the graph's search entry point with the topic's rendered criteria."""
        result = await run_search(
            **render_screener_input(topic), target_output_count=SEARCH_TARGET_OUTPUT_COUNT
        )
        return SearchRecord(
            papers=result["papers"],
            synthetic_abstract=result["synthetic_abstract"],
            fallback_used=result["fallback_used"],
        )

    async def screen(self, papers: list[dict[str, Any]], topic: Topic) -> list[ScreeningRecord]:
        """Screen papers with the graph's screening node; one record per paper, in input order."""
        criteria = render_screener_input(topic)
        state = {
            "raw_papers": papers,
            "research_question": criteria["research_question"],
            "inclusion_criteria": criteria["inclusion_criteria"],
            "exclusion_criteria": criteria["exclusion_criteria"],
            "additional_info": criteria["additional_info"],
        }
        results = (await screening_node(state))["screening_results"]
        by_key = _screening_records(results)
        keys = [paper["openalex_id"] for paper in papers]
        if sorted(by_key) != sorted(keys):
            raise ValueError(
                f"the screening node returned records for {sorted(by_key)}, expected {sorted(keys)}"
            )
        return [by_key[key] for key in keys]

    def retrieve(self, paper_key: str, pages: list[str]) -> list[RetrievedChunk]:
        """Retrieve one paper in memory; map each retrieved text back to its page and ordinal."""
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError(f"paper {paper_key} has no extractable text")
        embeddings = embed_texts([chunk.text for chunk in chunks])
        repository = InMemoryRepository()
        paper_id = repository.upsert_paper(
            openalex_id=paper_key,
            doi=None,
            title=paper_key,
            year=None,
            authors=[],
            venue=None,
            pdf_url=None,
        )
        repository.replace_chunks(
            paper_id,
            [
                NewChunk(chunk.page, chunk.ordinal, chunk.text, embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ],
            get_settings().embedding_model,
            CHUNKER_VERSION,
        )
        first_with_text: dict[str, PageChunk] = {}
        for chunk in chunks:
            first_with_text.setdefault(chunk.text, chunk)
        retrieved = retrieve_field_chunks(repository, paper_id)
        return [
            RetrievedChunk(
                paper_key=paper_key,
                field=RETRIEVAL_FIELDS[key],
                rank=rank,
                page=first_with_text[text].page,
                ordinal=first_with_text[text].ordinal,
                text=text,
            )
            for key, texts in retrieved.items()
            for rank, text in enumerate(texts, start=1)
        ]

    async def extract(
        self, paper: dict[str, Any], chunks: list[RetrievedChunk], topic: Topic
    ) -> ExtractionOutput:
        """Extract with the graph's extraction function; a failed call is kept as an error."""
        paper_key = paper["openalex_id"]
        try:
            result = await extract_from_retrieved_chunks(
                paper={"paper": paper, "retrieved_chunks_by_field": _chunk_texts_by_key(chunks)},
                research_question=topic.research_question,
            )
        except EXTRACTION_ERRORS as exc:
            return ExtractionOutput(error=f"{type(exc).__name__}: {exc}")
        raw = result["rag_extraction"]
        fields = [
            FieldRecord(
                paper_key=paper_key, field=name, status=v1_status(raw[name]), value=raw[name]
            )
            for name in SCORED_FIELDS
        ]
        return ExtractionOutput(fields=fields, raw=raw)

    def provenance(self) -> dict[str, Any]:
        """The model, prompt, embedding, chunking and retrieval settings of this system."""
        settings = get_settings()
        return {
            "models": {
                "search": settings.search_model,
                "screening": settings.screening_model,
                "extraction": settings.extraction_model,
            },
            "prompt_versions": {
                "search": search_prompt.PROMPT_VERSION,
                "screening": screening_prompt.PROMPT_VERSION,
                "extraction": extraction_prompt.PROMPT_VERSION,
            },
            "embedding_model": settings.embedding_model,
            "chunker_version": CHUNKER_VERSION,
            "retrieval_top_k": RETRIEVAL_TOP_K,
            "concurrency": SCREENING_CONCURRENCY,
        }


def _screening_records(results: dict[str, list[dict[str, Any]]]) -> dict[str, ScreeningRecord]:
    """Map the node's four buckets to records keyed by OpenAlex id."""
    records: dict[str, ScreeningRecord] = {}
    for bucket, decision in SCREENING_BUCKETS.items():
        for item in results[bucket]:
            screening = item["screening"]
            records[item["paper"]["openalex_id"]] = ScreeningRecord(
                paper_key=item["paper"]["openalex_id"],
                decision=decision,
                reasoning=screening["reasoning"],
                matched_inclusion=screening["matched_inclusion_criteria"],
                matched_exclusion=screening["matched_exclusion_criteria"],
            )
    for item in results["failed_papers"]:
        key = item["paper"]["openalex_id"]
        records[key] = ScreeningRecord(paper_key=key, decision="failed", error=item["error"])
    return records
