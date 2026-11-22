import asyncio
from pathlib import Path
from typing import Any, Dict

from src.db.records import NewChunk
from src.db.repository import Repository, get_repository
from src.llm.settings import get_settings
from src.llm.tracing import traceable_stage
from src.pipeline.ingestion.chunking import CHUNKER_VERSION, chunk_pages
from src.pipeline.ingestion.pdf import (
    download_pdf,
    extract_pages_from_pdf,
    get_openalex_pdf_url,
    is_cached_pdf,
    pdf_path_for,
)
from src.pipeline.ingestion.retrieval import embed_texts, retrieve_field_chunks

# The `pdf_status` values of the v1 state contract.
DOWNLOADED = "Downloaded"
NOT_AVAILABLE = "Not Available"
DOWNLOAD_FAILED = "Download Failed"
EXTRACTION_FAILED = "Extraction Failed"


def paper_fields(paper_info: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the library fields of a screened paper; a paper without an OpenAlex id is an error."""
    title = paper_info.get("title", "unknown")
    if not paper_info.get("openalex_id"):
        raise ValueError(f"Paper '{title}' has no openalex_id, so the library cannot store it.")
    return {
        "openalex_id": paper_info["openalex_id"],
        "doi": paper_info.get("doi"),
        "title": title,
        "year": paper_info.get("year"),
        "authors": paper_info.get("authors") or [],
        "venue": paper_info.get("venue"),
        "pdf_url": paper_info.get("pdf_url"),
    }


async def fetch_pdf(repository: Repository, paper_id: int, path: Path) -> str:
    """Make the paper's PDF available at `path`: cached file, stored URL, then the DOI lookup."""
    if await asyncio.to_thread(is_cached_pdf, path):
        return DOWNLOADED
    paper = await asyncio.to_thread(repository.get_paper, paper_id)
    tried: list[str] = []
    if paper.pdf_url:
        tried.append(paper.pdf_url)
        if await asyncio.to_thread(download_pdf, paper.pdf_url, path):
            return DOWNLOADED
    fallback_url = await asyncio.to_thread(get_openalex_pdf_url, paper.doi)
    if fallback_url and fallback_url not in tried:
        tried.append(fallback_url)
        if await asyncio.to_thread(download_pdf, fallback_url, path):
            return DOWNLOADED
    if tried:
        status, error = DOWNLOAD_FAILED, f"PDF download failed for: {', '.join(tried)}"
    else:
        status, error = NOT_AVAILABLE, "No PDF URL found for this paper"
    await asyncio.to_thread(repository.set_paper_status, paper_id, "pdf_unavailable", error)
    return status


async def chunk_pdf(repository: Repository, paper_id: int, path: Path) -> str:
    """Extract, chunk and embed the PDF and store the chunks; return the v1 `pdf_status`."""
    await asyncio.to_thread(repository.set_paper_status, paper_id, "downloaded")
    try:
        pages = await asyncio.to_thread(extract_pages_from_pdf, path)
    except RuntimeError as error:
        await asyncio.to_thread(
            repository.set_paper_status, paper_id, "failed", f"Text extraction failed: {error}"
        )
        return EXTRACTION_FAILED
    chunks = chunk_pages(pages)
    if not chunks:
        await asyncio.to_thread(
            repository.set_paper_status, paper_id, "failed", "The PDF has no extractable text"
        )
        return EXTRACTION_FAILED
    embeddings = await asyncio.to_thread(embed_texts, [chunk.text for chunk in chunks])
    new_chunks = [
        NewChunk(chunk.page, chunk.ordinal, chunk.text, embedding)
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    await asyncio.to_thread(
        repository.replace_chunks,
        paper_id,
        new_chunks,
        get_settings().embedding_model,
        CHUNKER_VERSION,
    )
    return DOWNLOADED


async def ingest_paper(repository: Repository, paper_id: int) -> str:
    """Download and chunk a paper unless that is already done; return the v1 `pdf_status`."""
    already_chunked = await asyncio.to_thread(
        repository.is_chunked, paper_id, get_settings().embedding_model, CHUNKER_VERSION
    )
    if already_chunked:
        return DOWNLOADED
    path = pdf_path_for(paper_id)
    status = await fetch_pdf(repository, paper_id, path)
    if status != DOWNLOADED:
        return status
    return await chunk_pdf(repository, paper_id, path)


@traceable_stage("document_processing")
async def document_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stores each included paper in the library, downloads and chunks its PDF unless that is already
    done, and retrieves the most relevant chunks per field via pgvector.
    Keeps all papers in the state to ensure accurate tracking, but flags missing PDFs.
    """
    print("--- RUNNING DOCUMENT PROCESSING & RAG RETRIEVAL ---")

    repository = get_repository()

    # 1. Shallow-copy the screening results to preserve all data (included, excluded, etc.)
    current_screening = state.get("screening_results", {}).copy()
    included_papers = current_screening.get("included_papers", [])

    processed_count = 0

    # 2. Iterate over the included papers without removing any from the list
    for paper in included_papers:
        # Handle potential nesting depending on how Screening Agent dumped the data
        paper_info = paper.get("paper", paper)

        print(f"[PROCESSING] {paper_info.get('title', 'unknown')}")

        # Step A: Store the paper (merged by OpenAlex id or DOI), then download and chunk it
        paper_id = await asyncio.to_thread(repository.upsert_paper, **paper_fields(paper_info))
        pdf_status = await ingest_paper(repository, paper_id)

        if pdf_status != DOWNLOADED:
            print(f"[SKIPPED] {pdf_status}.")
            paper["pdf_status"] = pdf_status  # Flag for the extraction node to skip
            continue

        # Step B: Retrieve the chunks per field
        retrieved_fields = await asyncio.to_thread(retrieve_field_chunks, repository, paper_id)

        # Step C: Store results safely in the paper dictionary
        # Adding to both levels guarantees compatibility with your extraction_node logic
        pdf_path = str(pdf_path_for(paper_id))
        paper_info["retrieved_chunks_by_field"] = retrieved_fields
        paper_info["pdf_path"] = pdf_path
        paper_info["pdf_status"] = DOWNLOADED

        paper["retrieved_chunks_by_field"] = retrieved_fields
        paper["pdf_path"] = pdf_path

        processed_count += 1
        print("[SUCCESS] Retrieval complete.")

    # 3. Update the copied dictionary with the modified list (still holds all initial papers)
    current_screening["included_papers"] = included_papers

    # 4. Return the updated screening dictionary back to the LangGraph state
    return {
        "screening_results": current_screening,
        "current_step": "document_processing",
        "status_message": (
            f"Document processing complete: {processed_count} out of {len(included_papers)} "
            "PDFs ready for extraction."
        ),
    }
