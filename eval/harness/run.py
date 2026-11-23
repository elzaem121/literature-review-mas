"""The eval run: `python -m eval.harness.run --adapter phase1`.

Checks the models, screens the screening set twice, retrieves and extracts the extraction-gold
papers, saves every record to the data folder, and scores a complete run.
"""

import argparse
import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from eval.harness.adapters import Adapter, get_adapter
from eval.harness.data_dir import data_dir, outputs_dir
from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    ExtractionGold,
    PoolPaper,
    ScreeningGold,
    load_extraction_gold,
    load_page_text,
    load_pool,
    load_screening_gold,
    load_search_snapshot,
)
from eval.harness.ollama_check import OllamaCheckError, check_models, is_infrastructure_error
from eval.harness.records import (
    ExtractionOutput,
    RetrievedChunk,
    RunProvenance,
    RunStatus,
    ScreeningRecord,
    Timings,
)
from eval.harness.score import score_run
from eval.harness.scoring import RESULTS_DIR
from eval.harness.topics import TOPICS_DIR, Topic, load_topic
from src.llm.settings import get_settings

SCREENING_PASSES = 2
CONTEXT_LENGTH = "ollama_default"
POOL_ONLY_FIELDS = {"paper_key", "origin", "search_rank", "aliases"}
REPO_ROOT = Path(__file__).resolve().parents[2]


class RunSummary(BaseModel):
    """What a finished run reports to the command line."""

    run_id: str
    status: RunStatus
    incomplete_reason: str | None = None
    results_path: Path | None = None


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot read the git commit: {result.stderr.strip()}")
    return result.stdout.strip()


def paper_info(paper: PoolPaper) -> dict[str, Any]:
    """The pool paper as the dict the screener and the extractor receive."""
    return {**paper.model_dump(exclude=POOL_ONLY_FIELDS), "openalex_id": paper.paper_key}


def _screening_inputs(
    gold: list[ScreeningGold], pools: dict[str, list[PoolPaper]]
) -> dict[str, list[dict[str, Any]]]:
    """The screening-set papers per topic, as the dicts the screener receives."""
    inputs: dict[str, list[dict[str, Any]]] = {}
    for record in gold:
        if not record.in_screening_set:
            continue
        paper = next(p for p in pools[record.topic_id] if p.paper_key == record.paper_key)
        inputs.setdefault(record.topic_id, []).append(paper_info(paper))
    return inputs


async def _screen_everything(
    adapter: Adapter, inputs: dict[str, list[dict[str, Any]]], topics: dict[str, Topic]
) -> tuple[list[ScreeningRecord], float]:
    """One screening pass over every topic's set; returns the records and the wall-clock seconds."""
    started = time.perf_counter()
    records: list[ScreeningRecord] = []
    for topic_id, papers in inputs.items():
        records += await adapter.screen(papers, topics[topic_id])
    return records, time.perf_counter() - started


def verified_pages(data_root: Path, paper: ExtractionGold) -> list[str]:
    """The paper's frozen page text, checked against the PDF hash in the gold file."""
    page_text = load_page_text(data_root, paper.paper_key)
    if page_text.pdf_sha256 != paper.pdf_sha256:
        raise ValueError(f"page text of {paper.paper_key} is from another PDF than the gold file")
    return page_text.pages


@dataclass
class ExtractionRun:
    """The retrieval and extraction records of the extraction-gold papers, with their timings."""

    retrieval: dict[str, list[RetrievedChunk]] = field(default_factory=dict)
    extraction: dict[str, ExtractionOutput] = field(default_factory=dict)
    retrieval_s: dict[str, float] = field(default_factory=dict)
    extraction_s: dict[str, float] = field(default_factory=dict)


async def _extract_gold_papers(
    adapter: Adapter,
    data_root: Path,
    papers: list[ExtractionGold],
    pools: dict[str, list[PoolPaper]],
    topics: dict[str, Topic],
) -> ExtractionRun:
    """Retrieve and extract every extraction-gold paper, whatever the screener decided."""
    run = ExtractionRun()
    for paper in papers:
        key = paper.paper_key
        pool_paper = next(p for p in pools[paper.topic_id] if p.paper_key == key)
        pages = verified_pages(data_root, paper)
        started = time.perf_counter()
        run.retrieval[key] = adapter.retrieve(key, pages)
        run.retrieval_s[key] = time.perf_counter() - started
        started = time.perf_counter()
        info = {**pool_paper.model_dump(exclude=POOL_ONLY_FIELDS), "openalex_id": key}
        run.extraction[key] = await adapter.extract(
            info, run.retrieval[key], topics[paper.topic_id]
        )
        run.extraction_s[key] = time.perf_counter() - started
    return run


def _incomplete_reason(
    models: list[str],
    base_url: str,
    screening_runs: list[list[ScreeningRecord]],
    extraction: dict[str, ExtractionOutput],
) -> str | None:
    """Why a run cannot be scored: Ollama failed after the run, or a call hit the infrastructure."""
    try:
        check_models(models, base_url)
    except OllamaCheckError as exc:
        return f"the check after the run failed: {exc}"
    errors = [r.error for run in screening_runs for r in run if r.error]
    errors += [output.error for output in extraction.values() if output.error]
    infrastructure = [error for error in errors if is_infrastructure_error(error)]
    if infrastructure:
        return f"{len(infrastructure)} calls failed on the infrastructure, e.g. {infrastructure[0]}"
    return None


def _save(run_dir: Path, name: str, value: Any, value_type: Any) -> None:
    payload = TypeAdapter(value_type).dump_json(value, indent=2)
    (run_dir / name).write_bytes(payload + b"\n")


def _save_outputs(
    run_dir: Path,
    provenance: RunProvenance,
    screening_runs: list[list[ScreeningRecord]],
    extraction_run: ExtractionRun,
    timings: Timings,
) -> None:
    run_dir.mkdir(parents=True)
    _save(run_dir, "provenance.json", provenance, RunProvenance)
    for number, records in enumerate(screening_runs, start=1):
        _save(run_dir, f"screening_{number}.json", records, list[ScreeningRecord])
    _save(run_dir, "retrieval.json", extraction_run.retrieval, dict[str, list[RetrievedChunk]])
    _save(run_dir, "extraction.json", extraction_run.extraction, dict[str, ExtractionOutput])
    _save(run_dir, "timings.json", timings, Timings)


async def run_eval(
    adapter_name: str,
    data_root: Path,
    *,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    results_dir: Path = RESULTS_DIR,
    search_size: int = SEARCH_SET_SIZE,
) -> RunSummary:
    """Run the whole eval for one adapter and the configured models; score it if it is complete."""
    settings = get_settings()
    if settings.repository_backend != "memory":
        raise RuntimeError(
            "the eval run needs REPOSITORY_BACKEND=memory, so that it never touches the library"
        )
    adapter = get_adapter(adapter_name)
    system = adapter.provenance()
    models = sorted(set(system["models"].values()))
    digests = check_models(models, settings.ollama_base_url)
    started_at = datetime.now(UTC)
    git_commit = _git_commit()

    gold = load_screening_gold(gold_dir)
    topic_ids = sorted({record.topic_id for record in gold})
    topics = {topic_id: load_topic(topic_id, topics_dir) for topic_id in topic_ids}
    pools = {topic_id: load_pool(gold_dir, topic_id) for topic_id in topic_ids}
    inputs = _screening_inputs(gold, pools)

    passes = [await _screen_everything(adapter, inputs, topics) for _ in range(SCREENING_PASSES)]
    screening_runs = [records for records, _ in passes]
    extraction_run = await _extract_gold_papers(
        adapter, data_root, load_extraction_gold(gold_dir), pools, topics
    )
    timings = Timings(
        screening_pass_s=[seconds for _, seconds in passes],
        screening_papers=sum(len(papers) for papers in inputs.values()),
        retrieval_s=extraction_run.retrieval_s,
        extraction_s=extraction_run.extraction_s,
    )
    reason = _incomplete_reason(
        models, settings.ollama_base_url, screening_runs, extraction_run.extraction
    )
    status: RunStatus = "incomplete" if reason else "complete"
    provenance = RunProvenance(
        status=status,
        incomplete_reason=reason,
        adapter=adapter.name,
        git_commit=git_commit,
        started_at=f"{started_at:%Y-%m-%dT%H:%M:%SZ}",
        ollama_digests=digests,
        context_length=CONTEXT_LENGTH,
        gold_version=gold_dir.name,
        snapshot_retrieved_at={
            topic_id: load_search_snapshot(gold_dir, topic_id).retrieved_at
            for topic_id in topic_ids
        },
        **system,
    )
    run_id = f"{started_at:%Y%m%dT%H%M%S}-{adapter.name}-{git_commit}"
    run_dir = outputs_dir(data_root, run_id)
    _save_outputs(run_dir, provenance, screening_runs, extraction_run, timings)
    results_path = None
    if status == "complete":
        results_path = score_run(run_dir, gold_dir, results_dir, search_size=search_size)
    return RunSummary(
        run_id=run_id, status=status, incomplete_reason=reason, results_path=results_path
    )


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description="Run the eval for one pipeline adapter.")
    parser.add_argument("--adapter", default="phase1")
    args = parser.parse_args(argv)
    try:
        summary = asyncio.run(run_eval(args.adapter, data_dir()))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(f"run {summary.run_id}: {summary.status}")
    if summary.incomplete_reason:
        print(f"not scored: {summary.incomplete_reason}")
    if summary.results_path:
        print(f"results: {summary.results_path}")
    print("Now back up the data folder: make eval-sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
