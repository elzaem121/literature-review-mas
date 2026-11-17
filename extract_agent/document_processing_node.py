import re
import requests
import fitz  # PyMuPDF
import asyncio
import faiss
import numpy as np
from pathlib import Path
from typing import Dict, Any
from sentence_transformers import SentenceTransformer

from tracing import traceable_stage

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
PDF_DIR = Path("pdfs_auto")
PDF_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 1200
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

FIELD_QUERIES = {
    "method_chunks": [
        "research method methodology study design approach qualitative quantitative mixed methods theoretical conceptual literature review"
    ],
    "dataset_chunks": [
        "data dataset data source participants sample corpus interviews survey observation experiment field data documents research population"
    ],
    "task_chunks": [
        "research objective aim purpose research question analytical focus task contribution"
    ],
    "findings_chunks": ["main findings results conclusions key outcomes implications contribution"],
    "limitations_chunks": ["limitations weaknesses constraints future work study limitations"],
}

# Lazy-loaded global model to prevent reloading for every paper
_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[INIT] Loading SentenceTransformer model...")
        _embedding_model = SentenceTransformer(MODEL_NAME)
    return _embedding_model


# ==========================================
# HELPER FUNCTIONS (PDF Download & Text)
# ==========================================
def safe_filename(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", "_", title)
    title = title.strip("_")
    return title[:80] + ".pdf"


def get_openalex_pdf_url(doi: str) -> str | None:
    if not doi:
        return None
    doi_clean = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    openalex_url = f"https://api.openalex.org/works/https://doi.org/{doi_clean}"

    try:
        response = requests.get(openalex_url, timeout=20)
        if response.status_code != 200:
            return None

        work = response.json()
        open_access = work.get("open_access") or {}
        locations = work.get("locations") or []

        candidates = []
        if open_access.get("oa_url"):
            candidates.append(open_access["oa_url"])

        for loc in locations:
            pdf_url = loc.get("pdf_url")
            landing_page_url = loc.get("landing_page_url")
            if pdf_url:
                candidates.append(pdf_url)
            if landing_page_url and landing_page_url.endswith(".pdf"):
                candidates.append(landing_page_url)

        for url in candidates:
            if url and (".pdf" in url.lower() or "download" in url.lower() or "pdf" in url.lower()):
                return url

        return candidates[0] if candidates else None
    except Exception as e:
        print(f"[API ERROR] OpenAlex fetch failed: {e}")
        return None


def download_pdf(url: str, output_path: Path) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if response.status_code != 200:
            return False
        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            return False
        output_path.write_bytes(response.content)
        return True
    except Exception:
        return False


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        return "".join([page.get_text() for page in doc])
    except Exception:
        return ""


def chunk_text(text: str, chunk_size: int) -> list:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


# ==========================================
# HELPER FUNCTIONS (FAISS Retrieval)
# ==========================================
def embed_texts(model, texts: list[str]):
    embeddings = model.encode(texts, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


def perform_faiss_retrieval(chunks: list[str]) -> dict:
    """Runs the SentenceTransformer embedding and FAISS search."""
    if not chunks:
        return {}

    model = get_embedding_model()
    chunk_embeddings = embed_texts(model, chunks)

    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(chunk_embeddings)

    field_chunks = {}
    for field_name, queries in FIELD_QUERIES.items():
        selected_chunks = []
        query_embeddings = embed_texts(model, queries)
        distances, indices = index.search(query_embeddings, k=5)

        for query_idx, query in enumerate(queries):
            for chunk_idx in indices[query_idx]:
                chunk_text = chunks[int(chunk_idx)]
                if chunk_text not in selected_chunks:
                    selected_chunks.append(chunk_text)

        field_chunks[field_name] = selected_chunks

    return field_chunks


# ==========================================
# LANGGRAPH NODE
# ==========================================
@traceable_stage("document_processing")
async def document_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Downloads PDFs, extracts text, chunks it, and retrieves relevant chunks via FAISS.
    Keeps all papers in the state to ensure accurate tracking, but flags missing PDFs.
    """
    print("--- RUNNING DOCUMENT PROCESSING & RAG RETRIEVAL ---")

    # 1. Create a shallow copy of the screening results to preserve all data (included, excluded, etc.)
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

    # 3. Update the copied dictionary with the modified list (which still contains all initial papers)
    current_screening["included_papers"] = included_papers

    # 4. Return the updated screening dictionary back to the LangGraph state
    return {
        "screening_results": current_screening,
        "current_step": "document_processing",
        "status_message": f"Document processing complete: {processed_count} out of {len(included_papers)} PDFs ready for extraction.",
    }
