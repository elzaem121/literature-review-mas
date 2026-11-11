# Research Assistant v2 — Project Plan

> North-star document for v2. Phase-level designs live in `docs/designs/` and must stay consistent with this plan.
> Status: approved direction · Last updated: 2026-11-11

## 1. Goal

A chat-based research assistant that builds a growing library of scientific papers, answers questions with citations, produces evidence tables and state-of-research summaries, is evaluated automatically, and deploys as a full stack on Kubernetes.

**Target users:** Master's and PhD students who need to understand and track the state of research on a topic. Domain-agnostic.

**Paper source:** OpenAlex (open access) only.

## 2. Current state (v1)

- User submits a research question and criteria; after ~5 min receives a table of extracted data per paper.
- Linear LangGraph pipeline: search → screening → PDF processing (RAG) → extraction.
- FastAPI with background jobs, Streamlit with polling, in-memory FAISS, Ollama with a 7B code model, LangSmith tracing, Docker; Kubernetes for Ollama only.
- LLM calls go through raw OpenAI clients + Instructor in several files.

**Known gaps:** every run starts from zero; no persistence (job state lost on restart); no checkpointer; linear graph with no conditional routing; basic RAG (no overlap, no reranking); no automated evaluation; almost no tests; no CI.

## 3. Features

| Feature | Description | Priority |
| --- | --- | --- |
| Chat with memory | Follow-up questions work; conversations survive restarts | Must |
| Router | Each message routes to `context`, `library`, `new_topic`, or `clarify` | Must |
| Persistent library | Each run adds to the library; no duplicates | Must |
| Pipeline with 2 loops | Re-search when too few papers; re-extract empty fields | Must |
| Cited answers | Every claim references a paper | Must |
| Evidence table | Every cell links to its source passage and page | Must |
| Export | CSV/Excel and BibTeX | Must |
| Screening log | Inclusion/exclusion reason per paper (PRISMA-style) | Should |
| Research summary | Trends, gaps, contradictions — generated from the evidence table, with citations | Should |
| Human-in-the-loop | e.g. confirm query, approve re-search (`interrupt()`) | Should |
| Multi-user + auth | Private reviews and chats per user | Later (Phase 4) |

## 4. Non-goals (until v1.0)

Fine-tuning · PDF uploads · paper sources other than OpenAlex · custom extraction fields per review · React frontend · scaling for many concurrent users.

## 5. Architecture

```
Streamlit chat UI
      │
FastAPI (SSE streaming)
      │
LangGraph main graph
  Router ──► Context      (answer from conversation)
         ├─► Library QA   (answer from library, with citations)
         └─► Pipeline     (subgraph: search → screening → retrieval → extraction → store)
      │
LLM layer (get_llm(role))   Postgres + pgvector (library + checkpoints)   OpenAlex API
```

### 5.1 Layers

- **UI:** Streamlit, `st.chat_message`, streamed progress.
- **API:** FastAPI.
  - `POST /chat` — SSE stream of answer tokens and pipeline progress
  - `POST /chat/resume` — user reply after `interrupt()`
  - `GET /reviews/{id}/table`, `GET /reviews/{id}/export?format=csv|bibtex`
  - `GET /health`
- **Agents:** LangGraph main graph; the pipeline is a separate, independently testable subgraph.
- **LLM layer:** single factory `get_llm(role)`; no agent instantiates a provider client directly.
- **Data:** one Postgres instance with pgvector for library data and LangGraph checkpoints.
- **Cross-cutting:** LangSmith tracing and eval experiments, structured JSON logs, configuration via environment variables.

### 5.2 Router

Hybrid: LLM decision + deterministic rules.

1. LLM returns structured output (Pydantic):
   - `route`: `context | library | new_topic | clarify`
   - `rewritten_query`: follow-up rewritten as a standalone question
   - `reason`
2. Rule: for `library`, run retrieval first. If top score is below threshold or too few papers are found, `interrupt()` and ask: "I have little on this. Search for new papers?"

### 5.3 Pipeline loops

**Loop 1 — after screening**
- Condition: included papers < target (default 10).
- Action: rewrite the query using the exclusion reasons from the screening log; exclude `seen_ids`.
- Stop: max 2 iterations or no new papers. Report the actual count honestly.

**Loop 2 — after extraction**
- Each field has a status: `found | not_reported | empty`. Only `empty` triggers the loop.
- Action: targeted re-retrieval for that field only (different phrasing, more chunks, specific sections such as Methods/Results).
- Stop: max 2 iterations, then set status to `not_reported`.

**State:** iteration counter per loop, `seen_ids`, status per field. Both loops are conditional edges.

### 5.4 Repository layout

```
src/
  api/        FastAPI app, endpoints, schemas
  graph/      main graph, router, state
  pipeline/   subgraph: search, screening, retrieval, extraction
  llm/        get_llm, settings, prompts/ (versioned files)
  db/         SQLAlchemy models, Alembic migrations
  ui/         Streamlit app
eval/         datasets, judge prompts, eval scripts
tests/        unit and integration tests
deploy/       Dockerfiles, docker-compose, Kubernetes manifests
docs/         plan_v2.md, designs/
```

Prompts are versioned files in `src/llm/prompts/`, not inline strings.

## 6. Data model

Paper data is shared across users; reviews, screenings, and conversations are private.

| Table | Key columns | Scope |
| --- | --- | --- |
| `users` | `id`, `email` | private |
| `reviews` | `id`, `user_id`, `question`, `criteria` (jsonb) | private |
| `conversations` | `thread_id`, `user_id`, `review_id` | private |
| `screenings` | PK (`review_id`, `paper_id`), `decision`, `reason`, `model`, `prompt_version` | private |
| `papers` | `id`, `openalex_id` (unique), `doi` (unique), `title`, `year`, `pdf_url` | shared |
| `chunks` | `id`, `paper_id`, `page`, `text`, `embedding` (vector), `embedding_model` | shared |
| `extractions` | `id`, `paper_id`, `field`, `value`, `status`, `evidence_chunk_id`, `model`, `prompt_version` | shared |

**Rules**
- Screening is stored per (review, paper): the same paper can be included in one review and excluded in another.
- Upsert papers on `openalex_id` (`ON CONFLICT`); download and chunk each paper once.
- Every extraction references its evidence chunk (traceability).
- Every LLM output stores `model` and `prompt_version` (provenance).
- `user_id` exists in the schema from Phase 1, even before auth.
- LangGraph checkpoint tables are created by `PostgresSaver`; `conversations.thread_id` links to them.
- Tooling: SQLAlchemy (or SQLModel) + Alembic. Add an HNSW index only when chunk volume requires it.
- Future: custom fields per review require `review_id` on `extractions`.

## 7. LLM layer

Models are configured per role:

```yaml
llm:
  router:     { provider: ollama, model: qwen3:8b }          # provisional
  screening:  { provider: ollama, model: qwen3:8b }          # provisional
  extraction: { provider: ollama, model: qwen3:8b }          # provisional
  embedding:  { provider: ollama, model: nomic-embed-text }  # provisional
  summary:    { provider: groq,   model: llama-3.3-70b, fallback: ollama }
  judge:      { provider: groq,   model: llama-3.3-70b }
```

- `get_llm(role)` is the only place that builds clients. All providers use OpenAI-compatible endpoints.
- Settings validated at startup with Pydantic Settings. API keys only in `.env` / Kubernetes Secrets.
- Profiles: `local`, `cloud`, `test` (`test` uses a deterministic fake LLM for unit tests).
- Fallback on errors or rate limits (HTTP 429), e.g. LangChain `with_fallbacks`.
- Model name is recorded in every trace.
- Default local models: general instruct model (not a code model). Phase 1 uses provisional defaults `qwen3:8b` (router, screening, extraction) and `nomic-embed-text` (embeddings). The final choice per role comes from the benchmark at the start of Phase 2; changing the embedding model then means re-embedding stored chunks and migrating the vector column.

### 7.1 Prompt structure and caching (CAG + RAG)

- Order every prompt stable → variable: system prompt → criteria/schema → document → question. This enables prefix/prompt caching.
- **Cache-style context (stable data):** review criteria during screening; full paper text during extraction when it fits the context window; the evidence table for library QA and summaries.
- **Retrieval (growing data):** the library as a whole; OpenAlex.
- Hybrid by length: full paper if it fits, chunks otherwise.
- Never mix data from different users in one cached context.

## 8. Evaluation

| Component | Metric | Method |
| --- | --- | --- |
| Router | Accuracy, confusion matrix | 30–50 labeled messages; no judge |
| Search | precision@10 | Judge: relevant yes/no |
| Screening | Agreement rate | Judge decision vs. system decision |
| Extraction | Faithfulness, share of empty fields | Judge sees value + evidence passage |
| Chat answers, summary | Faithfulness, citation correctness | Judge sees answer + cited sources |
| End-to-end | Latency, tokens per step | LangSmith traces |

**Judge rules**
- Binary or 1–3 scale; reasoning before verdict.
- Judge always sees the source, not only the answer.
- Versioned judge prompt, temperature 0.
- Judge model must be stronger than the system model.
- Calibrate: label 20–30 cases manually; report human–judge agreement before trusting results.

**Process**
- Fixed datasets in `eval/` (versioned in git).
- Results logged as LangSmith experiments.
- CI runs a small subset on every merge (free-tier limits).
- Every change claimed as an improvement must show a metric delta.

## 9. Deployment and operations

- **Local dev:** docker-compose for Postgres, API, UI. Ollama runs natively on macOS (no GPU access inside Docker on Mac).
- **Kubernetes:** local cluster via `kind` or `k3d`. Deployments for UI, API, worker, Postgres. Ollama stays outside the cluster; the API only knows its URL, so it can move to a GPU server without code changes.
- ConfigMap for settings, Secrets for keys.
- Liveness/readiness probes on `/health`.
- Alembic migrations run as a Kubernetes Job before the API starts.
- **Job queue (Phase 4):** Redis + worker for long pipeline runs. Until then, async execution in the API is acceptable because the checkpointer persists state.
- **Auth (Phase 4):** simple authentication; every query filters by `user_id`.
- **CI/CD:** lint → unit tests → eval subset → build images → deploy.

## 10. Phases

Each phase ends with a working system and a git tag. From Phase 2 on, each phase is also measured with the eval harness. Only one phase is active at a time.

### Phase 0 — Baseline · `v0.1` · done
- [x] Fork repository, create branch `v2`
- [x] Bootstrap documentation of the v1 codebase
- Moved to the start of Phase 2: model benchmark, gold dataset v0, eval script (see `docs/eval_notes.md`)

**Exit (revised 2026-11-11):** v1 codebase documented on branch `v2`. Evaluation is deferred to Phase 2; v1 quality is not yet measured.

### Phase 1 — Foundation · `v0.2`
- [ ] New repository layout
- [ ] Settings, `get_llm(role)`, profiles, secrets; provisional models `qwen3:8b` and `nomic-embed-text` (section 7)
- [ ] Postgres + pgvector in docker-compose; SQLAlchemy models; Alembic migrations (incl. `user_id`)
- [ ] Ingestion: paper upsert, chunking, embeddings in pgvector
- [ ] `PostgresSaver` checkpointer with `thread_id`
- [ ] pytest with fake LLM; CI with lint + tests

**Exit:** running the same topic twice creates no duplicates; a restart loses nothing; CI is green.

### Phase 2 — Pipeline · `v0.3`
Evaluation first (moved from Phase 0; input: `docs/eval_notes.md`, draft):
- [ ] Gold dataset v0 for three test topics
- [ ] Eval script measuring the baseline before any Phase 2 pipeline change
- [ ] Benchmark candidate local models on target hardware per role: screening, extraction, embedding (speed, memory, quality). No tool calling; the router is benchmarked in Phase 3.
- [ ] Decision record for the model per role; replace the provisional defaults

Then:
- [ ] Pipeline as subgraph
- [ ] Screening stores decision + reason per (review, paper)
- [ ] Loop 1 with counter and `seen_ids`
- [ ] Extraction with field status and evidence (chunk, page)
- [ ] Loop 2 for `empty` fields only
- [ ] Experiment: full-paper context vs. chunk retrieval for extraction (latency, faithfulness)
- [ ] Chunk overlap; hybrid search or reranking only if metrics improve

**Exit:** eval shows fewer empty fields and measured faithfulness; no unbounded loops.

### Phase 3 — Chat · `v0.4`
- [ ] Router (LLM + rule) with `rewritten_query`
- [ ] Context route and library QA with citations
- [ ] Evidence table, export (CSV, BibTeX), screening log
- [ ] Research summary from the evidence table
- [ ] SSE streaming in API; chat UI in Streamlit
- [ ] `interrupt()` + `/chat/resume`
- [ ] Router test set (30–50 messages) and accuracy

**Exit:** a full demo conversation runs from question to export; router accuracy is measured.

### Phase 4 — Deployment · `v0.5`
- [ ] Local Kubernetes cluster; manifests for all components
- [ ] ConfigMap, Secrets, health probes, migration Job
- [ ] Redis job queue + worker
- [ ] Authentication
- [ ] CI/CD: build images, eval subset, deploy

**Exit:** one command deploys the full stack.

### Phase 5 — Release · `v1.0`
- [ ] README: problem, architecture, key decisions, measured results
- [ ] Design docs complete and drift-free
- [ ] Demo video (~3 min)

**Exit:** every claim in the README is backed by an eval result.

## 11. Constraints

- **Hardware:** MacBook Air M4 (fanless; throttles on long runs), 16 GB RAM.
- **Budget:** free only — local Ollama plus free API tiers. Free-tier limits change; verify before use.

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| Limited local compute | Small test sets, loop limits, judge via free API |
| 7B models unreliable for tool calling | Structured output + rules; model per role swappable |
| Free API limits change | Fallback to Ollama; check limits before use |
| No deadline → scope creep | One phase at a time; exit criteria; backlog for new ideas |
| Long context hurts small models | Hybrid full-paper/chunk strategy; measure before adopting |

## 13. Working rules

1. No big rewrite: the system runs after every step.
2. One phase at a time; finish with a git tag.
3. One EGM cycle per phase or major topic: brainstorm → draft → review → implement → drift report.
4. One agent session per task; each session reads only this plan, the relevant design doc, and the relevant code.
5. Commit after each task with passing tests.
6. Improvements require a metric delta.
7. Ideas outside the current phase go to the backlog, not into code.

## 14. Open questions

- None at plan level. Evaluation design questions are tracked in `docs/eval_notes.md`.
