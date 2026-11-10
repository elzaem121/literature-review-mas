# search_agent

## Overview

First pipeline stage. `UniversalAcademicSearchAgent` turns the user's research question into a dense
"synthetic abstract" with the local LLM (`instructor` + `AcademicQueryExpansionSchema`), then
`OpenAlexClient` runs OpenAlex semantic search with it and filters the hits locally. The live entry
point is `new_main.main`, called by `Orchestration/nodes.py:search_node`; `main.py` and
[archiv](./archiv/README.md) are superseded.

## Interface

- `new_main.py:main(research_question=None, min_year=None, inclusion_criteria=None,
  exclusion_criteria=None, additional_info=None, user_query=None, criteria=None,
  target_output_count=25, min_citations=0, save_to_file=False,
  output_path=".mas_runs/search_results.json", progress_callback=None) -> {"papers": [...]}` —
  builds the query text, instantiates the agent, runs the retrieval cycle, optionally writes JSON.
  Module config: `OPENALEX_EMAIL`, `OPENALEX_API_KEY`, `SEARCH_MODEL` (default `qwen2.5-coder:7b`).
- `agent.py:UniversalAcademicSearchAgent(openalex_email, openalex_api_key=None,
  model_name="qwen2.5-coder:7b")`
  - `run_precise_retrieval_cycle(user_query, target_output_count=20, min_citations=10, start_year=None,
    progress_callback=None)` — expand query, retrieve, format.
  - `_generate_academic_search_strategy(raw_user_query)` — LLM call; on any exception falls back to
    `{"synthetic_abstract": raw_user_query, "mandatory_entities": [words longer than 4 chars]}`.
  - `_apply_programmatic_gatekeeping_firewall(papers, mandatory_entities)` — keyword filter, kept but
    **not called** by `run_precise_retrieval_cycle`.
- `api_client.py:OpenAlexClient(email, api_key=None)` — `execute_retrieval(synthetic_abstract, limit=50,
  min_citations=5, start_year=None)` and `reconstruct_inverted_abstract(inverted_index)`.
- `schemas.py:AcademicQueryExpansionSchema` — `synthetic_abstract: str`, `mandatory_entities: List[str]`.
- `main.py:main()` — legacy standalone script (flat `from agent import ...`, writes
  `../Screening_Agent/search_results.json`); not part of the pipeline.
- Subdirectory: [archiv](./archiv/README.md) — archived Streamlit app, broken import.

## Invariants

- Output shape is `{"papers": [{"title", "abstract", "year", "authors", "doi", "url",
  "relevance_score"}]}`, matching `Screening_Agent.screening_schemas.ResearchPaper`. `relevance_score` is
  always `0`, and `url` is the OpenAlex id (falling back to the DOI), not a PDF link.
- Results are truncated to `target_output_count`.
- `OpenAlexClient.execute_retrieval` sends the fixed filter `has_abstract:true,type:journal-article|preprint,
  is_oa:true`, and locally drops any hit without a `pdf_url` (primary or best OA location), below
  `start_year`, or below `min_citations`. `new_main.main` defaults `min_citations=0`.
- Exclusion criteria are deliberately **not** added to the query (left to the screening stage); only
  inclusion criteria, `criteria`, and `additional_info` are appended.
- `new_main.py` must work both as a package import and as a script: when `__package__` is empty it
  prepends the repo root to `sys.path` and imports `search_agent.agent`; otherwise it uses the relative
  import.
- `agent.py` and `api_client.py` use package-relative imports (`from .schemas`, `from .api_client`), so
  `python search_agent/agent.py` does not work; use `python -m search_agent.new_main`.
- `new_main.OPENALEX_EMAIL` falls back to a hard-coded default address when the env var is unset; set
  `OPENALEX_EMAIL` for any shared deployment.

## Side Effects

- LLM call to `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`), traced through
  `tracing.maybe_wrap_openai`.
- HTTPS GET requests to `https://api.openalex.org/works` with a 20 s timeout; sleeps 2 s and retries on
  HTTP 429, stops on other non-200 statuses or on `requests` exceptions.
- `print` output of progress; optional `progress_callback` invocation.
- With `save_to_file=True`, creates the parent directory and writes `output_path`
  (default `.mas_runs/search_results.json`).

## Verification

- No tests exist for this stage. Manual run (needs Ollama and network): `python -m search_agent.new_main`
  from the repo root; it runs one hard-coded healthcare query and saves `.mas_runs/search_results.json`.

---

## Legacy notes (preserved from the original README)

> **Stale:** `app.py` no longer lives here (it moved to `archiv/`) and is not runnable; use the commands
> in the repository root README instead.

## 🚀 Installation & Start

Folge diesen 3 einfachen Schritten, um den Agenten lokal zu starten:

### 1. Abhängigkeiten installieren
Öffne das Terminal im Projektverzeichnis und installiere die benötigten Pakete:
```bash
pip install -r requirements.txt
```

### 2. Lokales LLM starten
Lade und starte das KI-Modell über Ollama (dies muss im Hintergrund laufen):
```bash
ollama run qwen2.5-coder:7b
```

### 3. Streamlit-UI starten
Öffne ein **neues** Terminal-Fenster und starte die Web-Oberfläche:
```bash
streamlit run app.py
```
*(Die App öffnet sich danach automatisch in deinem Browser).*
