# Screening_Agent

## Overview

Second pipeline stage. `AcademicScreeningAgent` classifies each paper from the search stage as
`include`, `exclude`, or `uncertain` against a research question and inclusion/exclusion criteria,
using only title, abstract, year, authors, DOI and URL. Decisions come from the local Ollama model via
`instructor` (structured output into a Pydantic schema), bounded by an `asyncio.Semaphore`. The agent
is used in-process by `Orchestration/nodes.py:screening_node` and by the Streamlit HITL app, and can
also run standalone against JSON files.

## Interface

- `screening_agent.py:AcademicScreeningAgent(model_name="llama3.1:8b", base_url=$OLLAMA_BASE_URL or
  http://localhost:11434/v1, api_key, max_concurrent_tasks=3, max_retries=2)`
  - `screen_papers(papers, research_question, inclusion_criteria, exclusion_criteria,
    additional_instructions=None, pre_excluded=None) -> ScreeningOutput` — async, concurrency-limited.
  - `screen_single_paper(...) -> ScreenedPaper` — one LLM call at `temperature=0`, retried up to
    `max_retries` with `0.5 * (attempt + 1)` s back-off.
  - `screen_file(...)` / `screen_file_with_protocol(input_path, output_path, protocol)` — read search
    JSON, screen, write `ScreeningOutput` JSON; the protocol variant applies the year pre-filter first.
  - Static helpers: `load_search_results`, `load_review_protocol`, `apply_publication_year_filter`,
    `build_screening_output`.
- `screening_schemas.py` — `ScreeningDecision` (enum `include|exclude|uncertain`),
  `PublicationYearFilter`, `ReviewProtocol` (with `format_inclusion_criteria` /
  `format_exclusion_criteria`), `ResearchPaper`, `SearchAgentOutput`, `PaperScreeningResult`
  (`confidence_score` and `relevance_score` constrained to 1–10), `ScreenedPaper`, `ScreeningError`,
  `ScreeningOutput` (buckets `included_papers`, `excluded_papers`, `uncertain_papers`,
  `failed_papers`), `format_criteria_list`.
- `screening_main.py:main()` — development entry point: reads `review_config_Evaluation.json` and
  `search_results.json` from the current directory, writes `screening_results.json`
  (model `qwen2.5-coder:7b`).
- `test_screening.py` — pytest suite (classes `TestSchemaLoading`, `TestProtocolFormatting`,
  `TestPublicationYearFilter`, `TestBuildScreeningOutput`, `TestMainEntryContract`).
- Data files: `review_config_Evaluation.json`, `search_results.json`, `screening_results.json`
  (the latter two are gitignored run artifacts) and the fixture directory `testdaten/`
  (`testdaten/review_config.json`).

## Invariants

- Per-paper failures never abort a batch: `screen_papers` uses `gather(..., return_exceptions=True)` and
  records each failure as a `ScreeningError` in `failed_papers`.
- `build_screening_output` sorts every bucket by `(relevance_score, confidence_score)` descending, and
  puts year-filtered papers into `excluded_papers` with `confidence_score=10`, `relevance_score=1`.
- `apply_publication_year_filter` keeps papers whose `year` is `None`; only papers with a year outside
  `[min_year, max_year]` are excluded.
- The system prompt tells the model to be conservative ("uncertain is better than wrongly excluding"),
  not to invent information, and to treat paper metadata as untrusted data.
- The pipeline must import this package as `Screening_Agent.screening_schemas`
  (`screening_agent.py` uses that absolute path), so the repo root has to be on `sys.path`. Importing
  the same schemas via the flat module name `screening_schemas` creates a second, distinct set of
  classes, and Pydantic then rejects them (`ScreenedPaper` validation error in
  `test_screening.py::TestBuildScreeningOutput`).
- The default `model_name` of `AcademicScreeningAgent` is `llama3.1:8b`; every real caller
  (`screening_node`, `screening_main.py`, the Streamlit app) passes `qwen2.5-coder:7b` explicitly.

## Side Effects

- HTTP calls to the Ollama-compatible endpoint (`OLLAMA_BASE_URL`); the client is wrapped by
  `tracing.maybe_wrap_openai`, so calls are traced when LangSmith is enabled.
- `screen_file*` read and overwrite JSON files at caller-supplied paths; `screening_main.py` writes
  `screening_results.json` into the current working directory.
- Logs through `logging` (`logger.warning` per failed attempt, `logger.error` per failed paper,
  `logger.info` summary counts).

## Verification

- Run: `cd Screening_Agent && PYTHONPATH=.. pytest test_screening.py -q`
- Current result (checked 2026-11-10): 8 passed, 3 failed. Without `PYTHONPATH=..` collection fails with
  `ModuleNotFoundError: No module named 'Screening_Agent'`. Two failures are `FileNotFoundError` for
  `Screening_Agent/review_config.json` (the tests expect it there, the checked-in copy is
  `testdaten/review_config.json`); the third is the dual-import class mismatch described above.
