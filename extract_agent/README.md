# extract_agent

## Overview

Third and fourth pipeline stages, both wired into the LangGraph graph:

1. **Document processing** (`document_processing_node.py`) — for each screening-included paper, resolves
   an open-access PDF URL through OpenAlex, downloads it, extracts text with PyMuPDF, splits it into
   fixed-size chunks, embeds them with `sentence-transformers/all-MiniLM-L6-v2`, and retrieves the top
   chunks per field with a FAISS inner-product index.
2. **Extraction** (`rag_extraction_main.py`) — one LLM call per paper over the retrieved chunks, forced
   into `ExtractedPaperInfo` by `instructor`, with a prompt that prefers `"not specified"` over guessing.

Four other scripts (`auto_pdf_downloader.py`, `add_full_text_from_pdfs.py`, `rag_chunker.py`,
`rag_retriever.py`) are an earlier file-to-file CLI version of the same flow and are **not** used by
the graph (see Invariants). Upstream/downstream contracts:
[Screening_Agent](../Screening_Agent/README.md), [Orchestration](../Orchestration/README.md).

## Interface

Live (imported by `Orchestration/`):

- `document_processing_node.py:document_processing_node(state)` — async LangGraph node; returns
  `{"screening_results", "current_step": "document_processing", "status_message"}`. Helpers:
  `safe_filename`, `get_openalex_pdf_url(doi)`, `download_pdf(url, output_path)`,
  `extract_text_from_pdf(pdf_path)`, `chunk_text(text, chunk_size)`, `embed_texts(model, texts)`,
  `perform_faiss_retrieval(chunks)`, `get_embedding_model()`. Constants: `PDF_DIR=Path("pdfs_auto")`,
  `CHUNK_SIZE=1200`, `MODEL_NAME`, `FIELD_QUERIES` (`method_chunks`, `dataset_chunks`, `task_chunks`,
  `findings_chunks`, `limitations_chunks`).
- `rag_extraction_main.py:extraction_node(state)` — async LangGraph node; returns
  `{"extracted_papers", "current_step": "completed", "status_message"}`.
  `extract_from_retrieved_chunks(paper, research_question)` does the per-paper LLM call and returns
  `{"paper": {title, year, authors, doi, url}, "rag_extraction": {...ExtractedPaperInfo fields}}`.
  Config: `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (default `qwen2.5-coder:7b`).
- `extraction_schemas.py:ExtractedPaperInfo` — fields `paper_type`, `method`, `dataset`, `task`,
  `main_findings`, `limitations`, `relevance_to_research_question` (all `str`) and `confidence`
  (`ExtractionConfidence`: `high|medium|low`). Only this model is used by the live code; `ResearchPaper`,
  `ScreeningAgentOutput`, `ExtractedPaper` and `ExtractionOutput` in the same file are unreferenced.

Legacy CLI scripts (each reads one JSON file and writes the next, relative to the current directory):

| Script | Reads | Writes |
|---|---|---|
| `auto_pdf_downloader.py` | `search_results.json` | `papers_with_auto_pdfs.json`, `pdfs_auto/` |
| `add_full_text_from_pdfs.py` | `papers_with_auto_pdfs.json` | `papers_with_full_text.json` |
| `rag_chunker.py` | `papers_with_full_text.json` | `chunked_papers.json` |
| `rag_retriever.py` | `chunked_papers.json` | `retrieved_chunks.json` |

## Invariants

- Papers are never dropped from `screening_results["included_papers"]`: a paper without a usable PDF gets
  `pdf_status` of `"Not Available"`, `"Download Failed"` or `"Extraction Failed"`; success sets
  `"Downloaded"`, `pdf_path`, and `retrieved_chunks_by_field` (written both on the item and on its nested
  `paper` dict, because the item may or may not be wrapped).
- `extraction_node` only processes included papers that have a `pdf_path` and non-empty
  `retrieved_chunks_by_field`; others are skipped, so `extracted_papers` can be shorter than
  `included_papers`. Extraction is sequential (one `await` per paper).
- Each field retrieves `k=5` chunks; chunks are fixed 1200-character slices with no overlap and no
  sentence awareness (`chunk_text`).
- The extraction prompt must keep its anti-hallucination rules: use only retrieved chunks, classify
  `paper_type` first, return `"not specified"`, `"no empirical dataset"` or `"not explicitly specified"`
  instead of guessing, and keep `paper_type`/`method`/`dataset` mutually consistent.
- `extract_from_retrieved_chunks` is called without a try/except; an LLM/validation error propagates out of
  `extraction_node` and fails the whole pipeline run (the Backend reports `error`).
- `chunk_text`, `FIELD_QUERIES`, `embed_texts`, `MODEL_NAME` and `safe_filename` are duplicated between the
  live node and the legacy scripts; change both or remove the legacy copies together.
- Legacy scripts execute at import time (`add_full_text_from_pdfs.py`, `rag_chunker.py`,
  `rag_retriever.py` have no `main()`), so never import them.
- `rag_extraction_main.py` no longer has a script entry point (its `INPUT_FILE`/`OUTPUT_FILE` lines are
  commented out), so `python rag_extraction_main.py` only prints configuration.

## Side Effects

- `document_processing_node.py` creates `pdfs_auto/` **relative to the current working directory** at import
  time, and writes one PDF per included paper into it (named by `safe_filename(title)`).
- Network: `GET https://api.openalex.org/works/https://doi.org/<doi>` (20 s timeout) and the PDF URL
  (30 s timeout, `User-Agent: Mozilla/5.0`, follows redirects); the first call to
  `get_embedding_model()` loads/downloads the SentenceTransformer weights (cached in a module global).
- CPU-bound work (download, PyMuPDF, embedding/FAISS) is pushed to threads with `asyncio.to_thread`.
- `rag_extraction_main.py` creates a module-level `instructor`-patched `AsyncOpenAI` client and prints the
  Ollama URL/model when imported; each paper triggers one LLM request (traced when LangSmith is enabled).
- Both nodes `print` progress lines.

## Verification

- No automated tests. Manual end-to-end check: run the whole pipeline (`uvicorn Backend.main:app` +
  `streamlit run ui_app.py`) or call `Orchestration.graph.app.ainvoke(...)` with a research question.

---

## Original notes (preserved)

> **Stale in places:** the original text below describes the earlier CLI flow and names "Qwen3"; the live
> code defaults to `qwen2.5-coder:7b`, and `python rag_extraction_main.py` is no longer a runnable step.
> The listed `*.json` data files are run artifacts (only `search_results.json` is present in this
> directory, and it is gitignored).

# RAG-Based Extraction Agent

## Overview

This project implements a RAG-based Extraction Agent for a multi-agent literature-review system.

The agent processes scientific papers and extracts structured academic information using semantic retrieval and LLM-based analysis.

The system is designed to avoid hardcoded rules and instead uses:

* semantic search
* embeddings
* generic query-based retrieval
* field-specific retrieval
* LLM prompting
* self-verification rules to reduce hallucinations

---

## Pipeline

1. Search
2. Screening
3. Automatic PDF download
4. PDF storage
5. Full-text extraction
6. Chunking
7. Embedding generation
8. Semantic retrieval
9. Field-specific chunk retrieval
10. RAG-based extraction with Qwen3
11. Structured JSON output

---

## Technologies

* Python
* Ollama
* Qwen3
* Instructor
* FAISS
* SentenceTransformers
* PyMuPDF
* Pydantic

---

## Files

### Core Files

* `auto_pdf_downloader.py`
* `add_full_text_from_pdfs.py`
* `extraction_schemas.py`
* `rag_chunker.py`
* `rag_retriever.py`
* `rag_extraction_main.py`

### Data Files

* `search_results.json`
* `papers_with_auto_pdfs.json`
* `papers_with_full_text.json`
* `chunked_papers.json`
* `retrieved_chunks.json`
* `rag_extraction_results.json`

---

## RAG Workflow

Search Results  
→ Automatic PDF Download  
→ PDF Storage  
→ Full-text Extraction  
→ Chunking  
→ Embeddings  
→ Semantic Retrieval  
→ Field-specific Relevant Chunks  
→ Qwen3  
→ Structured Extraction

---

## Usage

Run the pipeline step by step:

```bash
python auto_pdf_downloader.py
python add_full_text_from_pdfs.py
python rag_chunker.py
python rag_retriever.py
python rag_extraction_main.py
```
