import asyncio
from typing import Any, Dict

from src.llm.tracing import traceable_stage
from src.pipeline.ingestion.chunking import CHUNK_SIZE, chunk_text
from src.pipeline.ingestion.pdf import (
    PDF_DIR,
    download_pdf,
    extract_text_from_pdf,
    get_openalex_pdf_url,
    safe_filename,
)
from src.pipeline.ingestion.retrieval import perform_faiss_retrieval


@traceable_stage("document_processing")
async def document_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Downloads PDFs, extracts text, chunks it, and retrieves relevant chunks via FAISS.
    Keeps all papers in the state to ensure accurate tracking, but flags missing PDFs.
    """
    print("--- RUNNING DOCUMENT PROCESSING & RAG RETRIEVAL ---")

    # 1. Shallow-copy the screening results to preserve all data (included, excluded, etc.)
    current_screening = state.get("screening_results", {}).copy()
    included_papers = current_screening.get("included_papers", [])

    processed_count = 0

    # 2. Iterate over the included papers without removing any from the list
    for paper in included_papers:
        # Handle potential nesting depending on how Screening Agent dumped the data
        paper_info = paper.get("paper", paper)
        title = paper_info.get("title", "unknown")
        doi = paper_info.get("doi")

        print(f"[PROCESSING] {title}")

        # Step A: Fetch PDF URL
        pdf_url = get_openalex_pdf_url(doi)
        if not pdf_url:
            print("[SKIPPED] No PDF found.")
            paper["pdf_status"] = "Not Available"  # Flag for the extraction node to skip
            continue

        # Step B: Download PDF
        filename = safe_filename(title)
        output_path = PDF_DIR / filename
        success = await asyncio.to_thread(download_pdf, pdf_url, output_path)

        if success:
            # Step C: Extract Text
            full_text = await asyncio.to_thread(extract_text_from_pdf, str(output_path))
            if full_text:
                # Step D: Chunk Text and Retrieve FAISS chunks
                chunks = chunk_text(full_text, CHUNK_SIZE)
                retrieved_fields = await asyncio.to_thread(perform_faiss_retrieval, chunks)

                # Step E: Store results safely in the paper dictionary
                # Adding to both levels guarantees compatibility with your extraction_node logic
                paper_info["retrieved_chunks_by_field"] = retrieved_fields
                paper_info["pdf_path"] = str(output_path)
                paper_info["pdf_status"] = "Downloaded"

                paper["retrieved_chunks_by_field"] = retrieved_fields
                paper["pdf_path"] = str(output_path)

                processed_count += 1
                print(f"[SUCCESS] FAISS Retrieval complete ({len(chunks)} chunks).")
            else:
                print("[FAILED] Could not extract text from PDF.")
                paper["pdf_status"] = "Extraction Failed"
        else:
            print("[FAILED] PDF download failed.")
            paper["pdf_status"] = "Download Failed"

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
