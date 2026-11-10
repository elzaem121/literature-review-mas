# Multi-Agent Literature Screening System

An automated pipeline for the early stages of a systematic literature review. Given a
research question and inclusion/exclusion criteria, it retrieves candidate papers,
screens them for relevance, downloads the full texts, and extracts structured
information from each included paper.

Built as a Master's team project (Data Science, Hochschule Anhalt) by three students.
All language-model inference runs on self-hosted open-weight models — no external
LLM API is used.

📹 **[Watch the demo (4 min)](https://cloud.hs-anhalt.de/s/49s7N6jTeLAE5BX)** — full
walkthrough of a pipeline run.

---

## The problem

Screening the literature for a systematic review is slow and repetitive. A reviewer
searches an academic database, reads hundreds of titles and abstracts to decide what is
relevant, retrieves the full texts of what survives, and then reads each one to pull out
the same handful of facts — sample size, method, outcome, limitations.

The first three of those steps are mechanical enough to automate, and the fourth is a
structured extraction task that language models handle reasonably well. This system
automates all four as a four-stage agent pipeline.

---

## Architecture

![System architecture](docs/architecture.png)

A Streamlit frontend submits a job to the FastAPI backend, which runs the LangGraph
pipeline as a background task and returns a job ID immediately. The frontend polls for
status while the four agents run in sequence, each reading from and writing to a shared
pipeline state.

**Search agent** — expands the research question into a dense synthetic abstract, then
queries OpenAlex semantic search. Filters for open access, publication year, and
citation count.

**Screening agent** — classifies each paper as included, excluded, or uncertain against
the reviewer's criteria. Runs three papers concurrently.

**Document processing** — resolves and downloads each included paper's PDF, extracts and
chunks the text, embeds it with `all-MiniLM-L6-v2`, and retrieves the most relevant
chunks per extraction field via FAISS. Papers whose PDFs cannot be retrieved are flagged
rather than dropped.

**Extraction agent** — produces one structured record per paper from the retrieved
chunks, using RAG over the chunks rather than the full text.

### Why LangGraph

The pipeline currently runs as a linear sequence, which a plain script could also do.
LangGraph was chosen deliberately for where the system is going: conditional routing
(broaden and retry when a search returns nothing, halt and explain when screening
excludes everything), human-in-the-loop review of uncertain papers, and additional agents
slotted into the graph without rewriting the control flow. The orchestration layer is
built for that; the branching logic is the next step.

---

## Infrastructure

Local Ollama inference was too slow to run the pipeline at a usable pace, so inference
was moved to the university's GPU Kubernetes cluster. This let the agents run full
open-weight models without external API costs or rate limits — and made the cluster's
GPU, rather than a laptop, the constraint on throughput.

| | |
|---|---|
| Deployment | `ollama-deployment` (`ollama/ollama:latest`), 1 replica |
| GPU | `nvidia.com/gpu: 1` (requests = limits) |
| Model | `qwen2.5-coder:7b` |
| Service | ClusterIP on port 11434 |

Ollama is tuned for this workload: `OLLAMA_NUM_PARALLEL=4` matches the screening agent's
concurrency, and `OLLAMA_KEEP_ALIVE=24h` keeps the model resident in VRAM so it is not
reloaded on every run.

The application itself is containerised — one image for the FastAPI backend, one for the
Streamlit frontend, wired together with Docker Compose. See
[`deploy/NOTES.md`](deploy/NOTES.md) for full deployment notes.

---

## Performance

The pipeline is instrumented with LangSmith tracing. Every run produces a single trace,
tagged with the job ID from the API, with a span per stage and per LLM call — so a run in
the UI maps directly to a trace with timings and token counts. Tracing is optional: with
the environment variables unset, the pipeline runs unchanged.

<p align="center">
  <img src="docs/trace-1.png" alt="Trace: search and screening stages" width="420">
  <img src="docs/trace-2.png" alt="Trace: document processing and extraction stages" width="420">
</p>

Measured on a 5-paper run against `qwen2.5-coder:7b` on the GPU cluster:

| Stage | Time | Tokens |
|---|---|---|
| Search | 34s | 675 |
| Screening | 87s | 5.4K |
| Document processing | 29s | — |
| Extraction | 158s | 6.7K |
| **Total** | **~5 min** | **12.8K** |

**Extraction dominates at 51% of runtime.** Screening makes more LLM calls but finishes
in half the time, because it processes three papers concurrently while extraction runs
strictly sequentially at roughly 50 seconds per paper. Applying the same concurrency to
extraction is the single largest available speedup, and would cut total runtime by around
a third.

This is the kind of finding the tracing was added for — the bottleneck is not where call
volume suggests it should be.

---

## Evaluation

All three stages were evaluated manually, each by the team member who built it, across
3 different research topics.

| Stage | Metric | Result |
|---|---|---|
| Search | Mean precision@10 | > 0.85 |
| Screening | Classification accuracy, consistent across repeated runs | 95% |
| Extraction | Manual review of extracted fields | 90% |

Judgements were made by a single annotator per stage on a small sample, so these are
indications of quality rather than benchmark results. A stronger evaluation would use a
labelled dataset, more topics, and a second annotator with an inter-annotator agreement
statistic.

---

## Getting started

**Prerequisites:** Docker, and access to an Ollama instance running `qwen2.5-coder:7b`.

If Ollama runs on a Kubernetes cluster, open a tunnel to it first:

```bash
kubectl port-forward svc/ollama-service 11434:11434 -n mas-project
```

Then start both services:

```bash
docker compose up
```

The UI is at `http://localhost:8501`.

Running a model locally instead, or connecting to the cluster from scratch, is covered in
[`deploy/NOTES.md`](deploy/NOTES.md).

### Configuration

| Variable | Default | Used by |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | backend |
| `BACKEND_URL` | `http://127.0.0.1:8000` | frontend |
| `OPENALEX_EMAIL` | — | backend |
| `LANGSMITH_TRACING` | unset (tracing off) | backend |
| `LANGSMITH_API_KEY` | unset | backend |
| `LANGSMITH_ENDPOINT` | EU instance | backend |
| `LANGSMITH_PROJECT` | — | backend |

Copy `.env.example` to `.env` and fill in the values you need. Inside Compose, the
backend reaches Ollama via `host.docker.internal` (the host end of the port-forward) and
the frontend reaches the backend by service name.

### Running without Docker

```bash
pip install -r requirements.txt
uvicorn Backend.main:app --port 8000
streamlit run ui_app.py
```

---

## Local Interface & Invariants

Source files that live directly in the repository root:

- `ui_app.py` — the Streamlit frontend for the full pipeline (the one `Dockerfile.frontend` runs).
  Submits a `ResearchRequest`-shaped payload to `POST {BACKEND_URL}/start_pipeline`, then polls
  `GET {BACKEND_URL}/status/{job_id}` once per second until `current_step` is `completed` or `error`,
  and renders the screening buckets and extraction table (CSV download). `BACKEND_URL` defaults to
  `http://127.0.0.1:8000`.
- `tracing.py` — optional LangSmith helpers: `tracing_enabled()`, `maybe_wrap_openai(client)`,
  `traceable_stage(name)`, `root_trace(job_id)`.
- `export_graph.py` — script (runs on import) that prints the Mermaid graph and writes `docs/graph.png`.

Invariants:

- The polling loop in `ui_app.py` has no timeout and no retry limit on `requests` calls; it ends only on
  `completed` / `error` or a connection error.
- Tracing is a strict no-op unless `langsmith` imports **and** `LANGSMITH_API_KEY` is set;
  `maybe_wrap_openai` must wrap the raw OpenAI client *before* `instructor` patches it.
- Python modules are imported from the repo root as flat sibling packages (`Backend`, `Orchestration`,
  `search_agent`, `Screening_Agent`, `extract_agent`, plus root-level `tracing`); run commands from the
  repo root (or with it on `PYTHONPATH`), as `Dockerfile.backend` does with `WORKDIR /app`.

Side effects: `export_graph.py` writes `docs/graph.png`; `ui_app.py` makes HTTP calls to the backend.

## Subdirectories & System Boundaries

- Backend: [./Backend/README.md](./Backend/README.md) - FastAPI service: `POST /start_pipeline`,
  `GET /status/{job_id}`, in-memory `JOBS`, runs the graph as a background task.
- Orchestration: [./Orchestration/README.md](./Orchestration/README.md) - LangGraph `PipelineState`,
  `pre_*` status nodes and worker nodes, compiled linear `app`.
- search_agent: [./search_agent/README.md](./search_agent/README.md) - query expansion + OpenAlex semantic
  search; `new_main.main` is the live entry. Contains [archiv](./search_agent/archiv/README.md) (archived,
  non-runnable Streamlit app).
- Screening_Agent: [./Screening_Agent/README.md](./Screening_Agent/README.md) - per-paper
  include/exclude/uncertain classification, schemas, and the only pytest suite.
- extract_agent: [./extract_agent/README.md](./extract_agent/README.md) - PDF download, chunking, FAISS
  retrieval (`document_processing_node`) and LLM extraction (`extraction_node`); also holds legacy CLI
  scripts not used by the graph.
- App_Main: [./App_Main/README.md](./App_Main/README.md) - standalone Streamlit HITL app for search +
  screening only (no backend).
- Non-code directories (no contract): `deploy/` (Kubernetes/Ollama notes in `NOTES.md`), `docs/` (images),
  `pdfs_auto/` (runtime PDF cache), `Screening_Agent/testdaten/` (test fixture).

## Global Invariants

- Papers flow as dicts through `PipelineState`: `raw_papers` (`{"papers": [...]}` entries matching
  `ResearchPaper`) → `screening_results` (four buckets: `included_papers`, `excluded_papers`,
  `uncertain_papers`, `failed_papers`, each item `{"paper", "screening"}`) → `extracted_papers`
  (`{"paper", "rag_extraction"}`). Changing a field name in one stage requires updating the consumers in
  the next stage, `Backend/schemas.py`, and `ui_app.py`.
- All LLM calls go through `instructor` on an OpenAI-SDK client pointed at `OLLAMA_BASE_URL`
  (default `http://localhost:11434/v1`) with a Pydantic `response_model`; there is no cloud LLM provider.
- The default model is `qwen2.5-coder:7b` everywhere it is set explicitly (`SEARCH_MODEL`, `OLLAMA_MODEL`,
  `SCREENING_MODEL` override per stage).
- The pipeline is linear and job state is in-memory only; a backend restart loses all jobs.

## Global Side Effects

- Network: OpenAlex (`api.openalex.org`, search and per-DOI PDF lookup), arbitrary publisher PDF URLs, the
  Ollama endpoint, and optionally LangSmith (`LANGSMITH_*`).
- Disk: `pdfs_auto/` (relative to the working directory; a named Docker volume in `docker-compose.yml`),
  `.mas_runs/` (written by `App_Main` and by `search_agent.new_main` when `save_to_file=True`),
  `Screening_Agent/*.json` run artifacts, `docs/graph.png`.
- Containers: `docker-compose.yml` runs `backend` (port 8000, `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`)
  and `frontend` (port 8501, `BACKEND_URL=http://backend:8000`).
- Environment: `.env.example` lists `OLLAMA_BASE_URL`, `BACKEND_URL`, and the `LANGSMITH_*` variables;
  `OPENALEX_EMAIL` / `OPENALEX_API_KEY` are read by `search_agent/new_main.py`.

## System Verification

- Run: `cd Screening_Agent && PYTHONPATH=.. pytest test_screening.py -q`
- Last observed result (2026-11-10): 8 passed, 3 failed (missing `Screening_Agent/review_config.json`
  fixture and a dual-import class mismatch; details in [Screening_Agent](./Screening_Agent/README.md)).
  No other package has automated tests.
- Graph wiring check (no LLM call): `python -c "from Orchestration.graph import app; print(app.get_graph().draw_mermaid())"`.

---

## Team and contributions

Three-person Master's project.

**Mohamed Elsayed** — LangGraph orchestration layer, FastAPI backend, Streamlit frontend,
search agent, Kubernetes deployment of the LLM inference service, containerisation, and
tracing.

**Jamila Gränzer** — screening agent: per-paper relevance classification against inclusion
and exclusion criteria, with retry handling and structured error reporting.

**Ferass Alrwashdh** — extraction agent: RAG-based structured extraction of predefined
fields from the retrieved document chunks.

---

## Current state and roadmap

The system is a working prototype: the full pipeline runs end to end, on real data, with
self-hosted inference. These are the planned next steps.

**Parallel extraction.** The performance measurement above makes this the clearest
priority — running extraction with the same concurrency as screening would cut roughly a
third off total runtime.

**Conditional routing.** Branching on empty search results and all-excluded screening
passes, plus a broaden-and-retry loop, is what the LangGraph orchestration layer was built
to support.

**Human-in-the-loop review.** Pausing the graph on uncertain screening decisions for
reviewer input, then resuming — a natural fit for a systematic review workflow.

---

## Stack

Python · LangGraph · FastAPI · Streamlit · Ollama · Kubernetes · Docker · LangSmith ·
OpenAlex API · FAISS · sentence-transformers · PyMuPDF
