# Phase 1 — explanations

Plain-language notes after each core task.

## Batch 0 — Safety net

Before moving any code, Batch 0 makes sure we can tell when something breaks. The three failing
screening tests were not real bugs: one test looked for a config file in the wrong folder, and one
imported the same class under two different names, so Python treated them as two different classes.
Now the tests load the config from where it really is, import with the full package name, and read
their paper data from a small committed fixture (`tests/fixtures/`) instead of a gitignored file that
would not exist on GitHub. `pyproject.toml` tells pytest to start from the repo root and skip
database tests by default, and holds the ruff settings. We ran `ruff format` once over every file in
its own commit, so later diffs show only real changes. The CI workflow, the Makefile and the frozen
v1 search results in `eval/snapshots/v1/` are the remaining pieces; the Phase 2a baseline needs those
search results to stay unchanged.

## Commit 1a — Seam (LLM layer and settings)

Before 1a, three different files each built their own connection to the model, with the model name and
your email typed directly into the code. Now there is one place for that: `src/llm/settings.py` reads
every setting from the environment (and `.env`) and stops the app at startup if the OpenAlex email is
missing. `src/llm/client.py` has `get_llm(role)` and `get_embedder()`, the only functions that create
model clients; swapping a model for one role later means changing one setting. The prompts moved out of
the agents into `src/llm/prompts/` unchanged (checked byte for byte), each with a version label, so a
stored result can later say which prompt produced it. The `test` profile swaps in fakes at the same
seams: a fake model that answers from a small table, a fake embedder, a fake OpenAlex and two tiny
fixture PDFs. That is what lets the whole pipeline run in a test with no network and no model. The
"golden transcript" is that run's final output saved to a file; any later commit that changes the
output by accident now fails a test. Also in 1a: search became `async`, and the screening agent's own
retry loop is gone (the OpenAI client retries 3 times and Instructor 2 times, and nothing else).

## Commit 1b — Move into `src/`

1b only moves code; it does not change what the code does, and the golden transcript test proves it:
the fake end-to-end run produces exactly the output it produced before the move. Everything now lives
under `src/` by job: `api` (FastAPI), `graph` (the LangGraph pipeline), `pipeline` (search, screening,
ingestion, extraction), `llm`, and `ui`. Files were moved with `git mv`, so their history follows them,
and every import now starts with `src.`. The old document-processing file was split by function into
`pdf.py` (download and read PDFs), `chunking.py`, `retrieval.py` (still FAISS until 2b) and `node.py`
(the graph node that ties them together). The API gained `GET /health`, a plain "I am alive" answer
that the CI compose check will call. The Dockerfiles, `.dockerignore` and CI were pointed at the new
paths, and CI now also runs ruff. One layering fix from 1a: `src/llm/fake.py` used to import the
pipeline's schemas to build its default answers, which made the lower layer depend on the upper one.
Now the fake only holds a registry that tests fill (`tests/fakes.py`, registered in `tests/conftest.py`),
so `src/llm` imports nothing from `src/pipeline`.

## Commit 1c — Delete and correct docs

1c removes everything the pipeline no longer uses, so there is one place for each thing. Gone are the old
step-by-step command-line scripts for PDF download and chunking (the graph does that now inside
`src/pipeline/ingestion/`), the older standalone Streamlit app `App_Main/`, the archived search app, the
`screening_main.py` script, `export_graph.py`, the per-folder READMEs and the five emptied top-level
folders (`Backend`, `Orchestration`, `search_agent`, `Screening_Agent`, `extract_agent`). Local-only
leftovers that git never tracked (old result files, `.mas_runs/`, empty `testdaten/`) were deleted by hand;
the two search-result files were first checked byte for byte against the copies in `eval/snapshots/v1/`.
`CLAUDE.md` and `README.md` now describe the `src/` layout, the new run and test commands and the settings
file, and no longer mention the deleted code or the old "3 tests fail" note. Nothing in `src/` changed, so
the tests and the golden transcript stay exactly as green as before.
