# Orchestration

## Overview

Defines the LangGraph pipeline that chains the four agents (search, screening, document processing,
extraction) over one shared state dictionary. Each worker node is preceded by a cheap `pre_*` node
whose only job is to publish `current_step` / `status_message` so the UI can show live progress. The
compiled graph is consumed by [Backend](../Backend/README.md).

## Interface

- `Orchestration/graph.py:app` — compiled `StateGraph(PipelineState)`. Entry point `pre_search`; linear
  edges:
  `pre_search → search_agent → pre_screening → screening_agent → pre_document_processing →
  document_processing_node → pre_extraction → extraction_node → END`.
- `Orchestration/graph.py:workflow` — the uncompiled `StateGraph`.
- `Orchestration/state.py:PipelineState` — `TypedDict` with inputs (`research_question`, `min_year`,
  `inclusion_criteria`, `exclusion_criteria`, `additional_info`, `target_output_count`), outputs
  (`raw_papers`, `screening_results`, `extracted_papers`) and UI tracking (`current_step`,
  `status_message`).
- `Orchestration/nodes.py`:
  - Status nodes: `pre_search_node`, `pre_screening_node`, `pre_document_processing_node`,
    `pre_extraction_node` (set `current_step` to `search`, `screening`, `document_processing`,
    `extraction`).
  - Worker nodes: `search_node` (sync, wraps `search_agent.new_main.main`) and `screening_node` (async,
    wraps `AcademicScreeningAgent`, model `qwen2.5-coder:7b`, `max_concurrent_tasks=3`).
  - Re-exported/used from elsewhere: `extraction_node` is imported from
    `extract_agent.rag_extraction_main`, and `document_processing_node` from
    `extract_agent.document_processing_node` (imported in `graph.py`, not `nodes.py`).

## Invariants

- Only the nodes wired in `graph.py` are live. Node registration names (`search_agent`,
  `screening_agent`, `document_processing_node`, `extraction_node`) are what `Backend/main.py` receives as
  `step_result` keys.
- `search_node` and `screening_node` return the mutated full state; `document_processing_node` and
  `extraction_node` return partial updates (`screening_results` / `extracted_papers` plus
  `current_step` and `status_message`). Every worker must leave `screening_results` with the four keys
  `included_papers`, `excluded_papers`, `uncertain_papers`, `failed_papers`.
- `screening_node` converts `raw_papers` into `ResearchPaper` objects, so search output must conform to
  that schema, and it serialises results with `model_dump()` so state stays JSON-compatible.
- The terminal `current_step == "completed"` is set only by `extraction_node`; `PipelineState` documents
  `"completed"` but the status nodes never set it.
- `screening_node` always passes `pre_excluded=[]`; the year pre-filter used by the standalone screening
  CLI is not applied in this pipeline (the search stage filters by `min_year` instead).
- Linear graph: there is no conditional routing, retry loop, or human-in-the-loop interrupt.
- `search_node` and `screening_node` are decorated with `tracing.traceable_stage`, which is a passthrough
  when tracing is disabled.

## Side Effects

- Importing `Orchestration.graph` imports the agents, which at import time: create a module-level
  `AsyncOpenAI`/instructor client and print the Ollama URL and model
  (`extract_agent/rag_extraction_main.py`), and create the `pdfs_auto/` directory relative to the current
  working directory (`extract_agent/document_processing_node.py:PDF_DIR`).
- Running the graph performs the network, LLM, and disk effects of each stage; see the stage contracts:
  [search_agent](../search_agent/README.md), [Screening_Agent](../Screening_Agent/README.md),
  [extract_agent](../extract_agent/README.md).

## Verification

- No tests exist for this package. Smoke test: `python -c "from Orchestration.graph import app; print(app.get_graph().draw_mermaid())"`
  from the repo root (needs the pinned requirements installed; no LLM call is made).
- [export_graph.py](../export_graph.py) prints the Mermaid source and writes `docs/graph.png`.
