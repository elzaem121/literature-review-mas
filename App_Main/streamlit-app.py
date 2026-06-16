from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol

import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Optional project imports
# -----------------------------------------------------------------------------
# In your project repository, keep this file next to:
# - screening_agent.py
# - screening_schemas.py
# - your Search Agent module exposing a main(...) function
# If these imports fail, the app falls back to local mock schemas/agents so the UI
# can be tested independently.

try:
    from Screening_Agent.screening_agent import AcademicScreeningAgent  # type: ignore
    from Screening_Agent.screening_schemas import (  # type: ignore
        PaperScreeningResult,
        PublicationYearFilter,
        ResearchPaper,
        ReviewProtocol,
        ScreenedPaper,
        ScreeningDecision,
        ScreeningError,
        ScreeningOutput,
        SearchAgentOutput,
    )
    REAL_SCREENING_AVAILABLE = True
except Exception:
    REAL_SCREENING_AVAILABLE = False

    class ScreeningDecision(str, Enum):
        INCLUDE = "include"
        EXCLUDE = "exclude"
        UNCERTAIN = "uncertain"

    class PublicationYearFilter(BaseModel):
        min_year: Optional[int] = None
        max_year: Optional[int] = None

    class ReviewProtocol(BaseModel):
        research_question: str
        inclusion_criteria: list[str] = Field(default_factory=list)
        exclusion_criteria: list[str] = Field(default_factory=list)
        publication_year: PublicationYearFilter = Field(default_factory=PublicationYearFilter)
        additional_instructions: Optional[str] = None

        def format_inclusion_criteria(self) -> str:
            return "\n".join(f"- {item}" for item in self.inclusion_criteria) or "None specified."

        def format_exclusion_criteria(self) -> str:
            return "\n".join(f"- {item}" for item in self.exclusion_criteria) or "None specified."

    class ResearchPaper(BaseModel):
        title: str
        abstract: str = "No abstract available."
        year: Optional[int] = None
        authors: list[str] = Field(default_factory=list)
        doi: Optional[str] = None
        url: Optional[str] = None
        relevance_score: Optional[int] = None

    class SearchAgentOutput(BaseModel):
        papers: list[ResearchPaper] = Field(default_factory=list)

    class PaperScreeningResult(BaseModel):
        decision: ScreeningDecision
        confidence_score: int = Field(ge=1, le=10)
        relevance_score: int = Field(ge=1, le=10)
        matched_inclusion_criteria: list[str] = Field(default_factory=list)
        matched_exclusion_criteria: list[str] = Field(default_factory=list)
        reasoning: str

    class ScreenedPaper(BaseModel):
        paper: ResearchPaper
        screening: PaperScreeningResult

    class ScreeningError(BaseModel):
        paper: ResearchPaper
        error: str

    class ScreeningOutput(BaseModel):
        included_papers: list[ScreenedPaper] = Field(default_factory=list)
        excluded_papers: list[ScreenedPaper] = Field(default_factory=list)
        uncertain_papers: list[ScreenedPaper] = Field(default_factory=list)
        failed_papers: list[ScreeningError] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

APP_TITLE = "Literature Review MAS · HITL Orchestrator"
HITL_TIMEOUT_SECONDS = int(os.getenv("HITL_TIMEOUT_SECONDS", "60"))
DEFAULT_SEARCH_ENTRYPOINT = os.getenv("SEARCH_AGENT_ENTRYPOINT", "search_agent.new_main:main")
DEFAULT_SCREENING_MODEL = os.getenv("SCREENING_MODEL", "qwen2.5-coder:7b")
OUTPUT_DIR = Path(os.getenv("MAS_OUTPUT_DIR", ".mas_runs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_INCLUSION_OPTIONS = [
    "Focus on multi-agent systems, agentic workflows, or collaborative AI environments",
    "Investigates safety evaluation, benchmarking frameworks, or vulnerability assessments",
    "Addresses alignment, adversarial robustness, hallucination containment, or secure tool use",
]


# -----------------------------------------------------------------------------
# State machine
# -----------------------------------------------------------------------------

class AppState(str, Enum):
    IDLE = "idle"
    SEARCH_RUNNING = "search_running"
    SCREENING_RUNNING = "screening_running"
    HITL_REVIEW = "hitl_review"
    HITL_SUBMITTED = "hitl_submitted"
    READY_FOR_NEXT_PHASE = "ready_for_next_phase"
    DONE = "done"
    ERROR = "error"


class HitlSubmitSource(str, Enum):
    USER = "user_confirmed"
    TIMEOUT = "timeout_original_selection"


@dataclass(frozen=True)
class UiInput:
    research_question: str
    exclusion_criteria: str
    additional_info: str
    min_year: int
    inclusion_criteria: list[str]

    def to_review_protocol(self) -> ReviewProtocol:
        return ReviewProtocol(
            research_question=self.research_question,
            inclusion_criteria=self.inclusion_criteria,
            exclusion_criteria=split_criteria(self.exclusion_criteria),
            publication_year=PublicationYearFilter(min_year=self.min_year),
            additional_instructions=self.additional_info or None,
        )


@dataclass(frozen=True)
class HitlPhaseConfig:
    phase_key: str
    title: str
    timeout_seconds: int


SCREENING_HITL = HitlPhaseConfig(
    phase_key="screening",
    title="HITL Screening",
    timeout_seconds=HITL_TIMEOUT_SECONDS,
)


# -----------------------------------------------------------------------------
# Agent contracts
# -----------------------------------------------------------------------------

class SearchAgentMain(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Existing Search Agent main(...) contract."""


class SearchAgentAdapter:
    """
    Adapter for an existing Search Agent.

    Supported real signatures:
    1) main(research_question=..., min_year=..., inclusion_criteria=..., exclusion_criteria=..., additional_info=...)
    2) main(user_query=..., min_year=..., criteria=...)
    3) main(research_question, min_year, inclusion_criteria, exclusion_criteria, additional_info)

    Expected return formats:
    - SearchAgentOutput
    - dict: {"papers": [...]}
    - JSON string: {"papers": [...]}
    - list[dict] or list[ResearchPaper]
    """

    def __init__(self, entrypoint: str = DEFAULT_SEARCH_ENTRYPOINT):
        self.entrypoint = entrypoint.strip()

    def run(
            self,
            ui_input: UiInput,
            status_callback: Optional[Callable[[str], None]] = None,
    ) -> SearchAgentOutput:
        if not self.entrypoint:
            if status_callback:
                status_callback("Mock Search Agent läuft...")
            return mock_search_agent_main(ui_input)

        fn = import_callable(self.entrypoint)
        result = self._call_flexible(fn, ui_input, status_callback=status_callback)
        return normalize_search_output(result)

    def _call_flexible(
            self,
            fn: Callable[..., Any],
            ui_input: UiInput,
            status_callback: Optional[Callable[[str], None]] = None,
    ) -> Any:
        inclusion_as_text = "\n".join(ui_input.inclusion_criteria)

        call_attempts: list[dict[str, Any] | tuple[Any, ...]] = [
            {
                "research_question": ui_input.research_question,
                "min_year": ui_input.min_year,
                "inclusion_criteria": ui_input.inclusion_criteria,
                "exclusion_criteria": ui_input.exclusion_criteria,
                "additional_info": ui_input.additional_info,
                "progress_callback": status_callback,
            },
            {
                "user_query": ui_input.research_question,
                "min_year": ui_input.min_year,
                "criteria": inclusion_as_text,
                "progress_callback": status_callback,
            },
            (
                ui_input.research_question,
                ui_input.min_year,
                ui_input.inclusion_criteria,
                ui_input.exclusion_criteria,
                ui_input.additional_info,
            ),
        ]

        last_error: Optional[Exception] = None
        for attempt in call_attempts:
            try:
                if isinstance(attempt, dict):
                    return await_if_needed(fn(**attempt))
                return await_if_needed(fn(*attempt))
            except TypeError as error:
                last_error = error
                continue

        raise RuntimeError(f"Search Agent main(...) could not be called. Last error: {last_error}")


class ScreeningAgentAdapter:
    """
    Adapter for the existing AcademicScreeningAgent.

    Uses the in-memory `screen_papers(...)` contract because the Streamlit app already
    has SearchAgentOutput in session_state. This avoids temp JSON files between phases.
    """

    def __init__(self, model_name: str = DEFAULT_SCREENING_MODEL):
        self.model_name = model_name

    def run(
        self,
        search_output: SearchAgentOutput,
        protocol: ReviewProtocol,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> ScreeningOutput:
        if status_callback:
            status_callback("Daten erhalten, führe Screening aus...")

        if not REAL_SCREENING_AVAILABLE:
            return mock_screening_agent_main(search_output=search_output, protocol=protocol)

        agent = AcademicScreeningAgent(model_name=self.model_name, max_concurrent_tasks=3)  # type: ignore[name-defined]
        eligible, pre_excluded = AcademicScreeningAgent.apply_publication_year_filter(  # type: ignore[name-defined]
            search_output.papers,
            protocol,
        )
        return await_if_needed(
            agent.screen_papers(
                papers=eligible,
                research_question=protocol.research_question,
                inclusion_criteria=protocol.format_inclusion_criteria(),
                exclusion_criteria=protocol.format_exclusion_criteria(),
                additional_instructions=protocol.additional_instructions,
                pre_excluded=pre_excluded,
            )
        )


# -----------------------------------------------------------------------------
# Mock interfaces
# -----------------------------------------------------------------------------

def mock_search_agent_main(ui_input: UiInput) -> SearchAgentOutput:
    """
    Mock replacement for your Search Agent main(...).
    Remove this after setting SEARCH_AGENT_ENTRYPOINT, e.g.:
    export SEARCH_AGENT_ENTRYPOINT="search_main:main"
    """
    papers = [
        ResearchPaper(
            title="Scalable Evaluation of Multi-Agent Reinforcement Learning with Melting Pot",
            abstract=(
                "Evaluation suite for multi-agent reinforcement learning measuring "
                "generalization in novel social and collaborative scenarios."
            ),
            year=max(ui_input.min_year, 2021),
            authors=["DeepMind Research Team"],
            doi="10.48550/arXiv.2107.06857",
            url="https://arxiv.org/abs/2107.06857",
            relevance_score=10,
        ),
        ResearchPaper(
            title="Benchmarking Secure Tool Use in Agentic Workflows",
            abstract=(
                "A benchmark for evaluating tool-use safety, prompt injection exposure, "
                "and adversarial robustness in collaborative AI systems."
            ),
            year=max(ui_input.min_year, 2024),
            authors=["Example Author"],
            doi=None,
            url="https://example.org/paper",
            relevance_score=9,
        ),
        ResearchPaper(
            title="Single-Agent Prompt Optimization for Cost Reduction",
            abstract="Cost-only prompt optimization for standalone large language models.",
            year=max(ui_input.min_year, 2023),
            authors=["Example Author"],
            doi=None,
            url=None,
            relevance_score=4,
        ),
    ]
    return SearchAgentOutput(papers=papers)


def mock_screening_agent_main(search_output: SearchAgentOutput, protocol: ReviewProtocol) -> ScreeningOutput:
    output = ScreeningOutput()
    min_year = protocol.publication_year.min_year

    for paper in search_output.papers:
        if min_year is not None and paper.year is not None and paper.year < min_year:
            decision = ScreeningDecision.EXCLUDE
            confidence = 10
            relevance = 1
            reasoning = f"Publication year {paper.year} is below minimum {min_year}."
        elif "single-agent" in paper.title.lower() or "cost" in paper.abstract.lower():
            decision = ScreeningDecision.EXCLUDE
            confidence = 8
            relevance = 3
            reasoning = "The paper appears to focus on single-agent or cost-only optimization."
        elif "multi-agent" in (paper.title + " " + paper.abstract).lower() or "agentic" in paper.abstract.lower():
            decision = ScreeningDecision.INCLUDE
            confidence = 8
            relevance = 8
            reasoning = "The paper matches the MAS / agentic workflow focus."
        else:
            decision = ScreeningDecision.UNCERTAIN
            confidence = 5
            relevance = 5
            reasoning = "Metadata is insufficient for a safe final decision."

        screened = ScreenedPaper(
            paper=paper,
            screening=PaperScreeningResult(
                decision=decision,
                confidence_score=confidence,
                relevance_score=relevance,
                reasoning=reasoning,
            ),
        )
        if decision == ScreeningDecision.INCLUDE:
            output.included_papers.append(screened)
        elif decision == ScreeningDecision.EXCLUDE:
            output.excluded_papers.append(screened)
        else:
            output.uncertain_papers.append(screened)

    return output


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def split_criteria(raw: str) -> list[str]:
    return [line.strip(" -\t") for line in raw.splitlines() if line.strip(" -\t")]


def import_callable(path: str) -> Callable[..., Any]:
    if ":" not in path:
        raise ValueError("Entrypoint must use 'module:function', e.g. 'search_main:main'.")
    module_name, attr_name = path.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, attr_name)
    if not callable(fn):
        raise TypeError(f"{path} is not callable.")
    return fn


def await_if_needed(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    # Streamlit normally has no running event loop in the script thread, but this
    # fallback prevents nested-loop failures if the app is embedded differently.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(value))
        return future.result()


def normalize_search_output(raw: Any) -> SearchAgentOutput:
    if isinstance(raw, SearchAgentOutput):
        return raw
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, list):
        raw = {"papers": [item.model_dump() if hasattr(item, "model_dump") else item for item in raw]}
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    if not isinstance(raw, dict):
        raise TypeError(f"Unsupported Search Agent output type: {type(raw)!r}")
    return SearchAgentOutput.model_validate(raw)


def model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    raise TypeError(f"Cannot serialize type {type(value)!r}")


def model_to_json(value: Any) -> str:
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)
    return json.dumps(value, indent=2, ensure_ascii=False)


def stable_uid(paper: ResearchPaper) -> str:
    raw = "|".join([paper.doi or "", paper.url or "", paper.title or "", str(paper.year or "")])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def rows_hash(rows: Iterable[dict[str, Any]]) -> str:
    relevant = [
        {"uid": row.get("uid"), "decision": row.get("decision")}
        for row in rows
    ]
    payload = json.dumps(relevant, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def flatten_screening_output(output: ScreeningOutput) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    item_map: dict[str, dict[str, Any]] = {}

    buckets = [
        (ScreeningDecision.INCLUDE.value, output.included_papers),
        (ScreeningDecision.EXCLUDE.value, output.excluded_papers),
        (ScreeningDecision.UNCERTAIN.value, output.uncertain_papers),
    ]

    for decision, items in buckets:
        for item in items:
            uid = stable_uid(item.paper)
            rows.append(
                {
                    "uid": uid,
                    "decision": decision,
                    "agent_decision": decision,
                    "title": item.paper.title,
                    "year": item.paper.year,
                    "authors": ", ".join(item.paper.authors or []),
                    "confidence_score": item.screening.confidence_score,
                    "relevance_score": item.screening.relevance_score,
                    "reasoning": item.screening.reasoning,
                    "doi": item.paper.doi,
                    "url": item.paper.url,
                }
            )
            item_map[uid] = model_to_dict(item)

    return rows, item_map


def rebuild_screening_output_from_rows(
    rows: list[dict[str, Any]],
    item_map: dict[str, dict[str, Any]],
    failed_papers: list[dict[str, Any]],
) -> ScreeningOutput:
    output = ScreeningOutput()

    for failed in failed_papers:
        output.failed_papers.append(ScreeningError.model_validate(failed))

    for row in rows:
        uid = row["uid"]
        base_item = ScreenedPaper.model_validate(item_map[uid])
        decision = ScreeningDecision(row["decision"])
        original_decision = ScreeningDecision(row.get("agent_decision", row["decision"]))

        reasoning = base_item.screening.reasoning
        if decision != original_decision and "Human override" not in reasoning:
            reasoning = f"{reasoning} [Human override: {original_decision.value} -> {decision.value}]"

        updated_screening = base_item.screening.model_copy(
            update={"decision": decision, "reasoning": reasoning}
        )
        updated_item = base_item.model_copy(update={"screening": updated_screening})

        if decision == ScreeningDecision.INCLUDE:
            output.included_papers.append(updated_item)
        elif decision == ScreeningDecision.EXCLUDE:
            output.excluded_papers.append(updated_item)
        else:
            output.uncertain_papers.append(updated_item)

    return output


# -----------------------------------------------------------------------------
# Session state operations
# -----------------------------------------------------------------------------

def init_state() -> None:
    defaults = {
        "app_state": AppState.IDLE.value,
        "ui_input": None,
        "search_output": None,
        "screening_output": None,
        "validated_screening_output": None,
        "active_hitl": None,
        "last_error": None,
        "phase_run_id": 0,
        "pipeline_log": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def set_state(state: AppState) -> None:
    st.session_state.app_state = state.value


def log_event(message: str) -> None:
    st.session_state.pipeline_log.append(
        {"ts": time.strftime("%H:%M:%S"), "message": message}
    )


def start_hitl_phase(config: HitlPhaseConfig, screening_output: ScreeningOutput) -> None:
    rows, item_map = flatten_screening_output(screening_output)
    now = time.time()
    st.session_state.phase_run_id += 1
    st.session_state.active_hitl = {
        "phase_key": config.phase_key,
        "title": config.title,
        "timeout_seconds": config.timeout_seconds,
        "started_at": now,
        "last_activity_at": now,
        "submitted_at": None,
        "submit_source": None,
        "original_rows": rows,
        "edited_rows": rows,
        "item_map": item_map,
        "failed_papers": [model_to_dict(item) for item in screening_output.failed_papers],
        "last_editor_hash": rows_hash(rows),
        "editor_key": f"screening_editor_{st.session_state.phase_run_id}",
    }
    set_state(AppState.HITL_REVIEW)
    log_event("Screening results rendered. HITL countdown started.")


def submit_current_hitl(source: HitlSubmitSource, use_original: bool) -> None:
    hitl = st.session_state.active_hitl
    if not hitl or hitl.get("submitted_at"):
        return

    rows = hitl["original_rows"] if use_original else hitl["edited_rows"]
    output = rebuild_screening_output_from_rows(
        rows=rows,
        item_map=hitl["item_map"],
        failed_papers=hitl["failed_papers"],
    )

    hitl["submitted_at"] = time.time()
    hitl["submit_source"] = source.value
    st.session_state.validated_screening_output = model_to_dict(output)
    persist_json("validated_screening_results.json", output)
    set_state(AppState.HITL_SUBMITTED)
    log_event(f"HITL submitted via {source.value}.")


def persist_json(filename: str, value: Any) -> Path:
    path = OUTPUT_DIR / filename
    path.write_text(model_to_json(value), encoding="utf-8")
    return path


def reset_pipeline() -> None:
    keys = [
        "ui_input",
        "search_output",
        "screening_output",
        "validated_screening_output",
        "active_hitl",
        "last_error",
        "pipeline_log",
    ]
    for key in keys:
        st.session_state[key] = [] if key == "pipeline_log" else None
    set_state(AppState.IDLE)


# -----------------------------------------------------------------------------
# UI components
# -----------------------------------------------------------------------------

def render_sidebar_input() -> None:
    st.sidebar.header("Review-Protokoll")

    with st.sidebar.form("protocol_form", clear_on_submit=False):
        research_question = st.text_area(
            "Forschungsfrage",
            placeholder="z. B. How to evaluate multi-agent systems efficiently?",
            height=100,
        )
        exclusion_criteria = st.text_area(
            "Ausschlusskriterien",
            placeholder="Eine Zeile pro Kriterium",
            height=120,
        )
        additional_info = st.text_area(
            "Zusatzinfos / Instructions",
            placeholder="z. B. Be conservative when excluding papers.",
            height=90,
        )
        min_year = st.number_input(
            "Minimales Jahr",
            min_value=1900,
            max_value=2100,
            value=2020,
            step=1,
        )
        inclusion_criteria = render_tags_input(
            "Einschlusskriterien",
            DEFAULT_INCLUSION_OPTIONS,
        )

        submitted = st.form_submit_button("Suche starten", use_container_width=True, type="primary")

    if submitted:
        if not research_question.strip():
            st.sidebar.error("Forschungsfrage fehlt.")
            return
        ui_input = UiInput(
            research_question=research_question.strip(),
            exclusion_criteria=exclusion_criteria.strip(),
            additional_info=additional_info.strip(),
            min_year=int(min_year),
            inclusion_criteria=list(inclusion_criteria),
        )
        st.session_state.ui_input = ui_input.__dict__
        st.session_state.pipeline_log = []
        set_state(AppState.SEARCH_RUNNING)
        log_event("Search started by user.")
        st.rerun()

    if st.sidebar.button("Pipeline zurücksetzen", use_container_width=True):
        reset_pipeline()
        st.rerun()


def render_tags_input(label: str, default_options: list[str]) -> list[str]:
    """
    Uses Streamlit's multiselect as dynamic tag input when supported.
    Falls back to newline text input on older Streamlit versions.
    """
    try:
        return st.multiselect(
            label,
            options=default_options,
            default=default_options[:1],
            accept_new_options=True,
            help="Bestehende Kriterien auswählen oder neue Kriterien eintippen.",
        )
    except TypeError:
        raw = st.text_area(
            f"{label} (eine Zeile pro Kriterium)",
            value="\n".join(default_options[:1]),
            height=120,
        )
        return split_criteria(raw)


def render_pipeline_log() -> None:
    with st.expander("Pipeline Log", expanded=False):
        for item in st.session_state.pipeline_log or []:
            st.write(f"`{item['ts']}` {item['message']}")


def render_idle() -> None:
    st.info("Review-Protokoll links ausfüllen und Suche starten.")


def render_search_running() -> None:
    ui_input = UiInput(**st.session_state.ui_input)
    adapter = SearchAgentAdapter()

    with st.status("Search Agent läuft...", expanded=True) as status:
        try:
            #logging für den Nutzer
            def search_status(message: str) -> None:
                st.write(message)
                log_event(message)

            search_status("UI-Daten an Search Agent main(...) übergeben.")
            search_output = adapter.run(ui_input, status_callback=search_status)
            st.session_state.search_output = model_to_dict(search_output)
            persist_json("search_results.json", search_output)
            log_event(f"Search complete: {len(search_output.papers)} papers retrieved.")
            status.update(label="Search Agent abgeschlossen", state="complete")
            set_state(AppState.SCREENING_RUNNING)
            st.rerun()
        except Exception as error:
            st.session_state.last_error = str(error)
            log_event(f"Search failed: {error}")
            status.update(label="Search Agent fehlgeschlagen", state="error")
            set_state(AppState.ERROR)


def render_screening_running() -> None:
    ui_input = UiInput(**st.session_state.ui_input)
    search_output = SearchAgentOutput.model_validate(st.session_state.search_output)
    protocol = ui_input.to_review_protocol()
    adapter = ScreeningAgentAdapter()

    with st.status("Screening Agent läuft...", expanded=True) as status:
        try:
            def status_callback(message: str) -> None:
                st.write(message)
                log_event(message)

            output = adapter.run(search_output, protocol, status_callback=status_callback)
            st.session_state.screening_output = model_to_dict(output)
            persist_json("screening_results_agent_raw.json", output)
            log_event(
                "Screening complete: "
                f"included={len(output.included_papers)}, "
                f"excluded={len(output.excluded_papers)}, "
                f"uncertain={len(output.uncertain_papers)}, "
                f"failed={len(output.failed_papers)}."
            )
            status.update(label="Screening Agent abgeschlossen", state="complete")
            start_hitl_phase(SCREENING_HITL, output)
            st.rerun()
        except Exception as error:
            st.session_state.last_error = str(error)
            log_event(f"Screening failed: {error}")
            status.update(label="Screening Agent fehlgeschlagen", state="error")
            set_state(AppState.ERROR)


def render_hitl_review() -> None:
    hitl = st.session_state.active_hitl
    if not hitl:
        st.error("HITL state missing.")
        set_state(AppState.ERROR)
        return

    st.subheader(hitl["title"])
    st.caption(
        "Ändere in der Spalte `decision` einzelne Paper. "
        "Ohne Bestätigung wird nach Timeout die ursprüngliche Agenten-Auswahl verwendet."
    )

    render_timer_fragment()

    rows = hitl["edited_rows"]
    df = pd.DataFrame(rows)

    edited_df = st.data_editor(
        df,
        key=hitl["editor_key"],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=[
            "uid",
            "agent_decision",
            "title",
            "year",
            "authors",
            "confidence_score",
            "relevance_score",
            "reasoning",
            "doi",
            "url",
        ],
        column_config={
            "decision": st.column_config.SelectboxColumn(
                "decision",
                options=[decision.value for decision in ScreeningDecision],
                required=True,
            ),
            "uid": None,
            "url": st.column_config.LinkColumn("url"),
            "doi": st.column_config.TextColumn("doi"),
            "reasoning": st.column_config.TextColumn("reasoning", width="large"),
            "title": st.column_config.TextColumn("title", width="large"),
        },
    )

    edited_rows = edited_df.to_dict("records")
    current_hash = rows_hash(edited_rows)
    if current_hash != hitl["last_editor_hash"]:
        hitl["edited_rows"] = edited_rows
        hitl["last_editor_hash"] = current_hash
        hitl["last_activity_at"] = time.time()
        log_event("HITL selection changed by user; inactivity timer reset.")

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        if st.button("Auswahl bestätigen", type="primary", use_container_width=True):
            hitl["edited_rows"] = edited_rows
            submit_current_hitl(HitlSubmitSource.USER, use_original=False)
            st.rerun()
    with col_b:
        if st.button("Agenten-Auswahl übernehmen", use_container_width=True):
            submit_current_hitl(HitlSubmitSource.USER, use_original=True)
            st.rerun()

    render_screening_summary_from_rows(edited_rows)


def _timer_body() -> None:
    hitl = st.session_state.get("active_hitl")
    if not hitl or st.session_state.get("app_state") != AppState.HITL_REVIEW.value:
        return

    timeout = int(hitl["timeout_seconds"])
    elapsed = int(time.time() - float(hitl["last_activity_at"]))
    remaining = max(0, timeout - elapsed)

    progress = 1.0 - (remaining / timeout if timeout else 1.0)
    st.progress(min(max(progress, 0.0), 1.0), text=f"Auto-Submit in {remaining}s bei Inaktivität")

    if remaining <= 0:
        submit_current_hitl(HitlSubmitSource.TIMEOUT, use_original=True)
        st.rerun()


if hasattr(st, "fragment"):
    render_timer_fragment = st.fragment(run_every=1)(_timer_body)  # type: ignore[attr-defined]
else:
    def render_timer_fragment() -> None:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=1000, key="hitl_autorefresh")
        except Exception:
            st.warning("Installiere `streamlit-autorefresh` oder nutze Streamlit mit `st.fragment`.")
        _timer_body()


def render_screening_summary_from_rows(rows: list[dict[str, Any]]) -> None:
    counts = pd.Series([row["decision"] for row in rows]).value_counts().to_dict()
    col1, col2, col3 = st.columns(3)
    col1.metric("Included", counts.get(ScreeningDecision.INCLUDE.value, 0))
    col2.metric("Excluded", counts.get(ScreeningDecision.EXCLUDE.value, 0))
    col3.metric("Uncertain", counts.get(ScreeningDecision.UNCERTAIN.value, 0))


def render_after_hitl() -> None:
    hitl = st.session_state.active_hitl or {}
    validated = ScreeningOutput.model_validate(st.session_state.validated_screening_output)

    st.success(f"HITL abgeschlossen: {hitl.get('submit_source')}.")
    render_screening_summary(validated)

    # Extension point: call Extract Agent here using the same pattern:
    # 1) run extract agent
    # 2) start_hitl_phase(EXTRACTION_HITL, extraction_output)
    # 3) auto-submit original extraction output after timeout if no user confirmation
    set_state(AppState.READY_FOR_NEXT_PHASE)

    st.download_button(
        "Validated Screening JSON herunterladen",
        data=model_to_json(validated),
        file_name="validated_screening_results.json",
        mime="application/json",
        use_container_width=True,
    )


def render_ready_for_next_phase() -> None:
    validated = ScreeningOutput.model_validate(st.session_state.validated_screening_output)
    st.success("Validated Screening Output liegt vor. Nächste Phase kann gestartet werden.")
    render_screening_summary(validated)

    with st.expander("Extension Point: Extract Agent", expanded=True):
        st.code(
            """\
# Pattern für spätere Phasen:
# extraction_output = ExtractAgentAdapter().run(validated_screening_output)
# start_hitl_phase(EXTRACTION_HITL, extraction_output)
# -> gleiche State Machine, gleicher Timer, gleiche Submit-Policy
""",
            language="python",
        )

    st.download_button(
        "Validated Screening JSON herunterladen",
        data=model_to_json(validated),
        file_name="validated_screening_results.json",
        mime="application/json",
        use_container_width=True,
    )


def render_screening_summary(output: ScreeningOutput) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Included", len(output.included_papers))
    col2.metric("Excluded", len(output.excluded_papers))
    col3.metric("Uncertain", len(output.uncertain_papers))
    col4.metric("Failed", len(output.failed_papers))

    tabs = st.tabs(["Included", "Excluded", "Uncertain", "Failed"])
    for tab, label, items in [
        (tabs[0], "Included", output.included_papers),
        (tabs[1], "Excluded", output.excluded_papers),
        (tabs[2], "Uncertain", output.uncertain_papers),
    ]:
        with tab:
            st.dataframe(pd.DataFrame([screened_to_row(item) for item in items]), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(pd.DataFrame([model_to_dict(item) for item in output.failed_papers]), use_container_width=True, hide_index=True)


def screened_to_row(item: ScreenedPaper) -> dict[str, Any]:
    return {
        "title": item.paper.title,
        "year": item.paper.year,
        "authors": ", ".join(item.paper.authors or []),
        "decision": item.screening.decision.value,
        "confidence_score": item.screening.confidence_score,
        "relevance_score": item.screening.relevance_score,
        "reasoning": item.screening.reasoning,
        "doi": item.paper.doi,
        "url": item.paper.url,
    }


def render_error() -> None:
    st.error(st.session_state.last_error or "Unknown error")


# -----------------------------------------------------------------------------
# Main app
# -----------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.title(APP_TITLE)
    render_sidebar_input()
    render_pipeline_log()

    state = AppState(st.session_state.app_state)

    if state == AppState.IDLE:
        render_idle()
    elif state == AppState.SEARCH_RUNNING:
        render_search_running()
    elif state == AppState.SCREENING_RUNNING:
        render_screening_running()
    elif state == AppState.HITL_REVIEW:
        render_hitl_review()
    elif state == AppState.HITL_SUBMITTED:
        render_after_hitl()
    elif state == AppState.READY_FOR_NEXT_PHASE:
        render_ready_for_next_phase()
    elif state == AppState.DONE:
        st.success("Pipeline abgeschlossen.")
    elif state == AppState.ERROR:
        render_error()


if __name__ == "__main__":
    main()