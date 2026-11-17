Read docs/plan_v2.md first. Design docs live in docs/designs/.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A multi-agent system (MAS) that automates a literature review: it searches OpenAlex for papers, screens
them against inclusion/exclusion criteria, downloads and RAG-processes the accepted PDFs, and extracts
structured findings from each paper — all orchestrated as a LangGraph pipeline behind a FastAPI backend
and a Streamlit frontend. All LLM calls go to a **local (or port-forwarded Kubernetes) Ollama endpoint**
via the `instructor` library patched onto the OpenAI SDK client — there is no cloud LLM provider involved.

## Setup & running

```bash
# venv already exists at .venv/ in this repo
source .venv/bin/activate
pip install -r requirements.txt
```

An Ollama-compatible model must be reachable at `http://localhost:11434/v1` before running any agent
(directly, via `ollama serve` + `ollama pull qwen2.5-coder:7b`, or via `kubectl port-forward` to a
cluster-hosted model — see README.md for the full Kubernetes connection steps).

**Full stack (current, FastAPI-backed):**
```bash
# Terminal 1 — backend
uvicorn Backend.main:app --reload

# Terminal 2 — frontend (polls the FastAPI backend)
streamlit run ui_app.py
```

**Standalone in-process HITL UI** (runs search + screening directly, no backend; falls back to local mock
schemas if `Screening_Agent` imports fail — useful for UI work without a live LLM):
```bash
PYTHONPATH="$PWD/Screening_Agent:$PWD/App_Main" python -m streamlit run ./App_Main/streamlit-app.py
```

**Individual pipeline stages**, runnable independently for development (each reads/writes its own JSON
files in its own directory):
```bash
python -m search_agent.new_main                       # search_agent/
python Screening_Agent/screening_main.py               # Screening_Agent/ (run from inside that dir; see below)
python extract_agent/auto_pdf_downloader.py             # extract_agent/ RAG pipeline, step by step:
python extract_agent/add_full_text_from_pdfs.py
python extract_agent/rag_chunker.py
python extract_agent/rag_retriever.py
python extract_agent/rag_extraction_main.py
```

### Tests

The only test suite is `Screening_Agent/test_screening.py`. Its imports (`from screening_agent import ...`)
and fixture paths are relative to the `Screening_Agent/` directory itself, so run it from inside that
directory, not from the repo root:
```bash
cd Screening_Agent
pytest test_screening.py -q
pytest test_screening.py::TestPublicationYearFilter -q   # single test class
```
Note: the test file references `review_config.json` and `search_results.json` directly under
`Screening_Agent/`, but the checked-in fixture actually lives at `Screening_Agent/testdaten/review_config.json`
— check this mismatch before trusting a green/red run.

## Architecture

### Pipeline shape

`Orchestration/graph.py` wires a LangGraph `StateGraph` over a single shared `PipelineState` TypedDict
(`Orchestration/state.py`). Each real stage is preceded by a cheap "pre_*" node
(`Orchestration/nodes.py`) that only sets `current_step`/`status_message` for UI polling, before the
actual worker node runs:

```
pre_search → search_agent → pre_screening → screening_agent
  → pre_document_processing → document_processing_node
  → pre_extraction → extraction_node → END
```

`Backend/main.py` compiles this graph once and, per request, runs it with `workflow_app.astream(...)`
inside a FastAPI `BackgroundTasks` job, streaming state after each node into an **in-memory** `JOBS` dict
keyed by `job_id` (no persistence — restarting the backend loses all job state). `ui_app.py`
polls `GET /status/{job_id}` to drive its progress UI.

### The four stages and their data contracts

1. **Search** (`search_agent/`) — `agent.py`'s `UniversalAcademicSearchAgent` uses the local LLM
   (`instructor` + Pydantic schema `AcademicQueryExpansionSchema`) to turn the user's research question
   into a dense "synthetic abstract" optimized for OpenAlex's semantic search, then `api_client.py`'s
   `OpenAlexClient` queries the OpenAlex Works API and locally filters by year/citations/PDF availability.
   A programmatic keyword "gatekeeping firewall" (`_apply_programmatic_gatekeeping_firewall`) exists but is
   currently **bypassed** in `run_precise_retrieval_cycle` — raw semantic search results pass straight
   through. Output shape: `{"papers": [...]}` (see `search_agent/schemas.py` / `Screening_Agent/screening_schemas.py:ResearchPaper`).
   `new_main.py::main()` is the entry point wired into `Orchestration/nodes.py::search_node` — `search_agent/main.py`
   is an older standalone script, not part of the live pipeline.

2. **Screening** (`Screening_Agent/`) — `AcademicScreeningAgent` first applies a local publication-year
   prefilter (no LLM call), then classifies each remaining paper independently via the LLM into
   include/exclude/uncertain using only title/abstract/year/authors/DOI/URL (explicitly instructed not to
   invent evidence), bounded by an `asyncio.Semaphore` for concurrency. Output is `ScreeningOutput` with
   four buckets: `included_papers` / `excluded_papers` / `uncertain_papers` / `failed_papers`, each entry
   wrapping the original paper plus the screening decision.

3. **Document processing** (`extract_agent/document_processing_node.py`) — mutates
   `screening_results["included_papers"]` in place: resolves a PDF URL via the OpenAlex API, downloads it
   into `pdfs_auto/`, extracts text with PyMuPDF, chunks it, embeds chunks with
   `sentence-transformers/all-MiniLM-L6-v2`, and runs FAISS similarity search per predefined field query
   (`FIELD_QUERIES`: method/dataset/task/findings/limitations) to build `retrieved_chunks_by_field` per
   paper. Papers without a resolvable PDF are flagged via `pdf_status` rather than dropped, so downstream
   counts stay consistent.

4. **Extraction** (`extract_agent/rag_extraction_main.py`) — for each included paper with retrieved
   chunks, calls the LLM once per paper with the field-specific chunk context and a heavily
   anti-hallucination-constrained prompt (must classify `paper_type` first, must write "not specified"
   rather than invent method/dataset/limitations, self-verification step for paper_type/method/dataset
   consistency) to produce `ExtractedPaperInfo` (`extract_agent/extraction_schemas.py`). Final state field:
   `extracted_papers`, a list of `{"paper": {...}, "rag_extraction": {...}}`.

### Legacy / duplicate files — do not confuse with the live pipeline

Several files in `extract_agent/` predate the RAG-based pipeline and are **not** referenced by
`Orchestration/graph.py`: `extract_agent.py`, `extraction_agent.py`, `extraction_main.py`,
`auto_pdf_downloader.py`, `add_full_text_from_pdfs.py`, `rag_chunker.py`, `rag_retriever.py` represent an
earlier step-by-step, file-to-file CLI version of the same pipeline (search_results.json →
papers_with_auto_pdfs.json → papers_with_full_text.json → chunked_papers.json → retrieved_chunks.json →
rag_extraction_results.json, per `extract_agent/README.md`). The version actually wired into the graph is
the all-in-one `document_processing_node.py` + `rag_extraction_main.py`. Likewise, `search_agent/main.py`
and `search_agent/archiv/app.py` are superseded by `search_agent/new_main.py`, and `App_Main/streamlit-app.py`
is a separate standalone in-process HITL Streamlit app (with mock fallback schemas, no FastAPI backend)
distinct from the backend-polling frontend `ui_app.py` at the repo root. When making pipeline changes, confirm which file is actually imported by
`Orchestration/nodes.py` / `Orchestration/graph.py` before editing.

### LLM access pattern

Every agent talks to Ollama through `instructor.from_openai(...)` / `instructor.patch(...)` wrapping an
`openai.OpenAI` or `AsyncOpenAI` client pointed at `http://localhost:11434/v1`, with `response_model=<a
Pydantic schema>` to force structured JSON output — this is the consistent way structured extraction is
enforced everywhere in the codebase (search query expansion, screening decisions, RAG extraction). Default
model is `qwen2.5-coder:7b`; `extract_agent` additionally reads `OLLAMA_BASE_URL`/`OLLAMA_MODEL` env vars.

## Coding standards

- Follow the design; do not add abstractions, layers or options it does not ask for (YAGNI).
- Small functions with one responsibility and clear names; type hints on all public functions; one-line docstrings on public functions.
- Layers: api -> graph/pipeline -> llm/db. Lower layers never import upper ones.
- LLM clients only via `get_llm()`, database only via the repository, configuration only via settings.
- No hardcoded values, no dead or commented-out code, no bare `except`; fail with clear error messages.
- Keep each change inside the current task; no unrelated refactors.
- Code must pass `ruff check` and `ruff format`; new behaviour gets a test.
