## phase1_foundation.md

### Architectural divergence

- **The repository is chosen by `REPOSITORY_BACKEND`, not by the profile.** The design (fake-surface table; 2a.4 "`get_repository()` returns the Postgres implementation on the `local` profile and an in-memory fake on `test`"; 2b.1) ties the in-memory repository to `PROFILE=test`. `src/db/repository.py:219-225` switches on a separate `repository_backend` setting (`src/llm/settings.py:22`) that the design never mentions. `PROFILE=test` with the default backend still needs Postgres. This contradicts G4 ("an end-to-end run passes with … no database").
- **`DATABASE_URL` is required only when the backend is postgres.** The design (1a.1) says it is required from 2a onwards. `src/llm/settings.py:28-32` makes it conditional on the undesigned `REPOSITORY_BACKEND`.
- **The `test` profile swaps in only the LLM and the embedder.** The fake-surface table and G4 say the `test` profile replaces OpenAlex and the PDF download "at the same seams". In the code, `get_llm`/`get_embedder` check the profile (`src/llm/client.py:25,36`), but the OpenAlex stub and fixture-PDF fakes are installed only by monkeypatching: the pytest `fake_surface` fixture (`tests/conftest.py:38-48`) and `scripts/fake_run.py:43-46`. A process started with `PROFILE=test` (for example the compose backend) still calls live OpenAlex and live PDF URLs. `.dockerignore` also excludes `tests/`, so `src/llm/fake.py:13` (`FIXTURES_DIR = …/tests/fixtures`) cannot work inside the image.
- **Fake-LLM sentinel handling moved out of `src/llm/fake.py`.** Design 1a.4 puts the canned `include` decision and the `[FAKE:EXCLUDE]` / `[FAKE:UNCERTAIN]` / `[FAKE:FAIL]` handling in `src/llm/fake.py`. They live in `tests/fakes.py:8-28`, and `src/llm/fake.py` only holds an empty registry (commit `ffffe08`). As a result, no fake LLM answers exist outside the test tree, so the compose backend cannot run on the fake surface. That is why the restart check needs the host-side workaround described below.
- **Instructor `max_retries=2` is passed by each caller, not set by `get_llm`.** Design 1a.2 / "LLM layer" places the uniform Instructor retry policy inside `get_llm(role)`. `src/llm/client.py:20-30` sets only the SDK `max_retries=3`. The Instructor value is exported as `INSTRUCTOR_MAX_RETRIES` and must be passed on every `create` call (`src/pipeline/search/agent.py:55`, `src/pipeline/screening/screening_agent.py:181`, `src/pipeline/extraction/node.py:29`). A new call site that omits it silently gets Instructor's default.
- **The LangSmith switch in settings is dead.** The design ("LLM layer", 1a.1) lists the LangSmith switch among the settings. `Settings.langsmith_tracing` (`src/llm/settings.py:25`) is never read. Tracing is enabled by `os.getenv("LANGSMITH_API_KEY")` in `src/llm/tracing.py:25`, and `LANGSMITH_PROJECT` is also read directly (`src/llm/tracing.py:67`).
- **Migrations now run automatically before the API in compose.** Non-Goals say there is "No auto-migration on API start — the migrations-before-API mechanism is a Phase 4 design item; Phase 1 uses `make migrate`". Commit `8402f46` added a one-shot `migrate` service that runs `alembic upgrade head` and gates `backend` on it (`docker-compose.yml:20-30,49-50`). CI's `stack` job and `scripts/restart_check.sh:36` rely on it. This is the deferred Phase 4 mechanism, landed in Phase 1 without a design update.
- **The restart check does not run a fake run through the compose API.** Design 2a.8: "Literal `docker compose restart` of API + Postgres around a fake run". `scripts/restart_check.sh:39-41` creates the run from the host via a new, undesigned `scripts/fake_run.py`. That script runs the whole app in-process with `TestClient` against the compose Postgres and imports `tests.fakes`. The compose API only reads the run back.
- **The `runs.result` column is not "exactly the `GET /status` payload".** The data-model table says `result` is exactly the `GET /status` payload, starting with the provenance envelope. `result` stores `provenance` plus `raw_papers_count`, `screening_results`, `extracted_papers` and `final_analysis` (`src/api/main.py:58-66`, `src/db/repository.py:51`). `GET /status` composes a `ResearchResponse` that has no `provenance` field (`src/api/schemas.py:30-40`). The provenance required by G6 is therefore stored but never returned by the API.

### Logic differing from the design

- **The paper upsert merges more fields than the design's merge rule.** The rule (step 1 of "Ingestion and retrieval") is: "first-seen `openalex_id` wins, `doi` fills in when it first appears". `upsert_paper` also fills in `year`, `venue` and `pdf_url` (`src/db/repository.py:135-137`, mirrored in `src/db/memory_repository.py:125-127`). It never updates `title` or `authors`. When the OpenAlex id and the DOI match two different rows, it picks the lowest id and leaves the DOI unset. The design does not cover that case.
- **The repository API differs from 2a.4.** The design lists a separate "review insertion" function next to `create_run`. The code folds review insertion into `create_run` (`src/db/repository.py:32-55`). It also adds `start_run`, `get_run`, `get_paper`, `set_paper_status` and `is_chunked`, which the design does not name.
- **Configuration is still read outside settings.** The design says configuration goes through settings (the "LLM layer" section; the 1a.1 settings list), but three values are still read directly from the environment:
  - `OPENALEX_API_KEY` via `os.getenv` (`src/pipeline/search/new_main.py:11`)
  - `BACKEND_URL` via `os.getenv` (`src/ui/app.py:13`)
  - the `LANGSMITH_*` variables (see above)

### Naming and file-level drift

- **Migration file name.** Design 2a.3 names `versions/0001_initial.py`; the file is `src/db/migrations/versions/0001_initial_schema.py`.
- **`.dockerignore` still targets the v1 tree.** Design 1b.4 asks for "ignore rules for the new tree". `.dockerignore:7-8,13-14` still list deleted v1 paths (`extract_agent/pdfs`, `App_Main`, `Screening_Agent/*.json`).
- **A second `ResearchPaper` class remains.** `src/pipeline/extraction/schemas.py:13-29` keeps an unused `ResearchPaper` plus `ScreeningAgentOutput`. `ExtractedPaper` and `ExtractionOutput` (lines 56-62) are unused too. The design's stated goal (0.1, Alternative B) was a single `ResearchPaper` identity. 1b.1 says the extraction schemas were moved, not cleaned.

### Code with no counterpart in the design

- **`src/db/records.py`**: shared constants, `NewChunk` and `normalize_doi`. The layout block lists only models, session, repository and migrations under `src/db/`.
- **`src/db/memory_repository.py`**: the design describes the in-memory fake but never names a file or location for it.
- **`scripts/fake_run.py` and `scripts/__init__.py`.** These are production-tree scripts that import from `tests/`.
- **`GET /` root endpoint** (`src/api/main.py:198-201`). The design lists only `POST /start_pipeline`, `GET /status/{job_id}` and `GET /health`.
- **Tests not named in the design:**
  - `tests/unit/test_health.py`
  - `tests/unit/test_llm_client.py`
  - `tests/unit/test_settings.py`
  - `tests/unit/test_prompts.py`
  - `tests/unit/test_run_status.py`
  - `tests/unit/test_ui_polling.py`
  - `tests/unit/test_ingestion_node.py`
  - `tests/unit/test_memory_repository.py`
  - `tests/integration/test_repository.py`
