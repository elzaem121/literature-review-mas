Read docs/plan_v2.md first. Design docs live in docs/designs/.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A multi-agent system (MAS) that automates a literature review: it searches OpenAlex for papers, screens
them against inclusion/exclusion criteria, downloads and RAG-processes the accepted PDFs, and extracts
structured findings from each paper — all orchestrated as a LangGraph pipeline behind a FastAPI backend
and a Streamlit frontend. All LLM calls go to a **local (or port-forwarded Kubernetes) Ollama endpoint**
via the `instructor` library patched onto the OpenAI SDK client — there is no cloud LLM provider involved.

This is the v2 rewrite (branch `v2`). Phase 1 is in progress: the code has moved into `src/` and goes
through one LLM seam; Postgres-backed state and ingestion land in commits 2a/2b (see
`docs/designs/phase1_foundation.md`). Until then, job state is in memory and retrieval is FAISS.

## Setup & running

```bash
# venv already exists at .venv/ in this repo
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # OPENALEX_EMAIL is required; the app refuses to start without it
```

An Ollama-compatible model must be reachable at `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`)
before running the real pipeline (directly, via `ollama serve` + `ollama pull qwen2.5-coder:7b`, or via
`kubectl port-forward` to a cluster-hosted model — see `README.md` and `deploy/NOTES.md`).

All commands run from the repo root; `src` is a plain package (no editable install).

```bash
# Terminal 1 — backend
uvicorn src.api.main:app --reload

# Terminal 2 — frontend (polls the FastAPI backend)
streamlit run src/ui/app.py

# Or the whole stack in containers
make up        # docker compose up -d --build
```

### Tests and lint

```bash
make test                      # pytest from the repo root; unit + fake end-to-end, no network, no model
pytest tests/unit/test_screening.py -q
ruff check src tests
ruff format --check src tests
```

`make test` runs with the `test` profile's fake surface (fake LLM, fake embedder, stubbed OpenAlex,
fixture PDFs from `tests/fixtures/`). Tests marked `integration` are excluded by default and need the
compose Postgres (`make integration`, from 2a on). The golden-transcript test
(`tests/e2e/test_golden_transcript.py`) diffs the fake end-to-end run against
`tests/fixtures/golden_run.json`; regenerate that file only as a deliberate, reviewed step.

## Architecture

### Layout

```text
src/
  api/        FastAPI app: POST /start_pipeline, GET /status/{job_id}, GET /health
  graph/      LangGraph graph (graph.py), shared PipelineState (state.py), nodes (nodes.py)
  pipeline/
    search/     OpenAlex query expansion + retrieval
    screening/  per-paper include/exclude/uncertain classification
    ingestion/  PDF download (pdf.py), chunking, retrieval, and the graph node (node.py)
    extraction/ RAG-based structured extraction (node.py, schemas.py)
  llm/        settings.py, client.py (get_llm / get_embedder), tracing.py, fake.py, prompts/
  ui/         Streamlit frontend (app.py)
tests/        unit/, e2e/, fixtures/ (golden_run.json, OpenAlex works, PDFs, review config)
eval/snapshots/v1/   frozen v1 search results (inputs for the Phase 2a baseline)
```

Imports are `from src.pipeline.search import ...`. Layering: api -> graph/pipeline -> llm/db; `src/llm`
imports nothing from `src/pipeline` (the fake LLM is a registry that tests fill in `tests/fakes.py`).

### Pipeline shape

`src/graph/graph.py` wires a LangGraph `StateGraph` over a single shared `PipelineState` TypedDict
(`src/graph/state.py`). Each real stage is preceded by a cheap "pre_*" node (`src/graph/nodes.py`) that
only sets `current_step`/`status_message` for UI polling, before the actual worker node runs:

```
pre_search → search_agent → pre_screening → screening_agent
  → pre_document_processing → document_processing_node
  → pre_extraction → extraction_node → END
```

`src/api/main.py` compiles this graph once and, per request, runs it with `workflow_app.astream(...)`
inside a FastAPI `BackgroundTasks` job, streaming state after each node into an **in-memory** `JOBS` dict
keyed by `job_id` (no persistence yet — restarting the backend loses all job state; this changes in 2a).
`src/ui/app.py` polls `GET /status/{job_id}` to drive its progress UI.

### The four stages and their data contracts

1. **Search** (`src/pipeline/search/`) — `agent.py`'s `UniversalAcademicSearchAgent` uses the LLM
   (`get_llm("search")`, Pydantic schema `AcademicQueryExpansionSchema`) to turn the research question into
   a dense "synthetic abstract" optimized for OpenAlex's semantic search, then `api_client.py`'s
   `OpenAlexClient` queries the OpenAlex Works API (blocking `requests`, called via `asyncio.to_thread`) and
   locally filters by year/citations/PDF availability. A programmatic keyword "gatekeeping firewall"
   (`_apply_programmatic_gatekeeping_firewall`) exists but is currently **bypassed** in
   `run_precise_retrieval_cycle`. Output shape: `{"papers": [...]}` (`ResearchPaper` in
   `src/pipeline/screening/screening_schemas.py`). `new_main.py::main()` is the entry point wired into
   `src/graph/nodes.py::search_node`.

2. **Screening** (`src/pipeline/screening/`) — `AcademicScreeningAgent` first applies a local
   publication-year prefilter (no LLM call), then classifies each remaining paper independently via
   `get_llm("screening")` into include/exclude/uncertain using only title/abstract/year/authors/DOI/URL
   (explicitly instructed not to invent evidence), bounded by an `asyncio.Semaphore`. Retries come only from
   the client policy (SDK `max_retries=3`, Instructor `max_retries=2`). Output is `ScreeningOutput` with
   four buckets: `included_papers` / `excluded_papers` / `uncertain_papers` / `failed_papers`.

3. **Document processing** (`src/pipeline/ingestion/`) — `node.py` mutates
   `screening_results["included_papers"]` in place: resolves a PDF URL via the OpenAlex API (`pdf.py`),
   downloads it into `settings.pdf_dir` (`pdfs_auto/`), extracts text with PyMuPDF, chunks it
   (`chunking.py`), embeds chunks with `get_embedder()`, and runs FAISS similarity search per field query
   (`FIELD_QUERIES`: method/dataset/task/findings/limitations, in `retrieval.py`) to build
   `retrieved_chunks_by_field` per paper. Papers without a resolvable PDF are flagged via `pdf_status`
   rather than dropped, so downstream counts stay consistent.

4. **Extraction** (`src/pipeline/extraction/`) — for each included paper with retrieved chunks, calls
   `get_llm("extraction")` once per paper with the field-specific chunk context and a heavily
   anti-hallucination-constrained prompt (must classify `paper_type` first, must write "not specified"
   rather than invent method/dataset/limitations, self-verification step) to produce `ExtractedPaperInfo`
   (`schemas.py`). Final state field: `extracted_papers`, a list of `{"paper": {...}, "rag_extraction": {...}}`.

### LLM access pattern

`src/llm/client.py` is the only place that builds LLM and embedding clients: `get_llm(role)` for roles
`search`, `screening`, `extraction` (other roles raise) returns an Instructor-patched `AsyncOpenAI` pointed
at Ollama, wrapped for LangSmith tracing (`src/llm/tracing.py`); `get_embedder()` returns the embedder.
Every call passes `response_model=<a Pydantic schema>` to force structured JSON output. Prompts live in
`src/llm/prompts/<role>.py`, each with a `PROMPT_VERSION`. With `PROFILE=test`, both seams return fakes.

### Configuration

All configuration is `src/llm/settings.py` (pydantic-settings, validated at startup, read from the
environment and `.env`): `PROFILE`, `OLLAMA_BASE_URL`, `SEARCH_MODEL` / `SCREENING_MODEL` /
`EXTRACTION_MODEL` (default `qwen2.5-coder:7b`), `EMBEDDING_MODEL` (default
`sentence-transformers/all-MiniLM-L6-v2`), `DATABASE_URL` (optional until 2a), `OPENALEX_EMAIL`
(required), `LANGSMITH_TRACING`, `PDF_DIR`. `.env.example` documents each one. The frontend also reads
`BACKEND_URL`; `src/pipeline/search/new_main.py` still reads the optional `OPENALEX_API_KEY` and
`src/llm/tracing.py` the `LANGSMITH_*` variables directly. New configuration goes through settings.

## Coding standards

- Follow the design; do not add abstractions, layers or options it does not ask for (YAGNI).
- Small functions with one responsibility and clear names; type hints on all public functions; one-line docstrings on public functions.
- Layers: api -> graph/pipeline -> llm/db. Lower layers never import upper ones.
- LLM clients only via `get_llm()`, database only via the repository, configuration only via settings.
- No hardcoded values, no dead or commented-out code, no bare `except`; fail with clear error messages.
- Keep each change inside the current task; no unrelated refactors.
- Code must pass `ruff check` and `ruff format`; new behaviour gets a test.
