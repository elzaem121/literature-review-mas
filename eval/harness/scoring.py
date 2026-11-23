"""Metrics: reads the saved outputs of one run and the gold set. Never calls a model or `src`."""

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from statistics import mean
from typing import Any, get_args

from pydantic import TypeAdapter

from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    ExtractionFieldGold,
    ExtractionGold,
    ScreeningGold,
    SearchSnapshot,
    load_extraction_gold,
    load_pool,
    load_screening_gold,
    load_search_snapshot,
    resolve_search_set,
)
from eval.harness.records import (
    SCORED_FIELDS,
    ExtractionOutput,
    GoldDecision,
    ModelDecision,
    RetrievedChunk,
    RunProvenance,
    ScreeningRecord,
    Timings,
)
from eval.harness.text import joined_runs, quote_on_page

RECALL_K = 5
BUDGET_SCREENING_PAPERS = 25
BUDGET_EXTRACTION_PAPERS = 10
GOLD_DECISIONS: tuple[str, ...] = get_args(GoldDecision)
MODEL_DECISIONS: tuple[str, ...] = get_args(ModelDecision)


def score(
    outputs_dir: Path, gold_dir: Path = DEFAULT_GOLD_DIR, *, search_size: int = SEARCH_SET_SIZE
) -> dict[str, Any]:
    """Score one run's saved outputs against the gold set; refuses a run marked incomplete."""
    provenance = RunProvenance.model_validate_json(_read(outputs_dir / "provenance.json"))
    if provenance.status != "complete":
        raise ValueError(
            f"run {outputs_dir.name} is incomplete ({provenance.incomplete_reason}); not scored"
        )
    all_gold = load_screening_gold(gold_dir)
    screening_gold = [r for r in all_gold if r.in_screening_set]
    extraction_gold = load_extraction_gold(gold_dir)
    first = _load_screening_run(outputs_dir / "screening_1.json")
    second = _load_screening_run(outputs_dir / "screening_2.json")
    retrieval = TypeAdapter(dict[str, list[RetrievedChunk]]).validate_json(
        _read(outputs_dir / "retrieval.json")
    )
    extraction = TypeAdapter(dict[str, ExtractionOutput]).validate_json(
        _read(outputs_dir / "extraction.json")
    )
    timings = Timings.model_validate_json(_read(outputs_dir / "timings.json"))
    snapshots = {
        topic_id: load_search_snapshot(gold_dir, topic_id)
        for topic_id in sorted({r.topic_id for r in all_gold})
    }
    return {
        "run_id": outputs_dir.name,
        "status": provenance.status,
        "provenance": provenance.model_dump(),
        "screening": _screening_section(screening_gold, first),
        "noise": _noise(screening_gold, first, second),
        "search": _search_section(gold_dir, all_gold, snapshots, search_size),
        "retrieval": _retrieval_section(extraction_gold, retrieval),
        "extraction": _extraction_section(extraction_gold, extraction),
        "failures": {
            "screening_1": _count_failed(first),
            "screening_2": _count_failed(second),
            "extraction": sum(1 for output in extraction.values() if output.error),
        },
        "timings": _timings_section(timings, extraction_gold),
        "latency_budget_s": _latency_budget(timings, extraction_gold, snapshots),
    }


def ratio(k: int, n: int) -> dict[str, Any]:
    """A count out of a total, with its rate; the rate is None when the total is zero."""
    return {"k": k, "n": n, "rate": k / n if n else None}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_screening_run(path: Path) -> dict[str, ScreeningRecord]:
    records = TypeAdapter(list[ScreeningRecord]).validate_json(_read(path))
    return {record.paper_key: record for record in records}


def _model_decision(run: dict[str, ScreeningRecord], paper_key: str, run_name: str) -> str:
    if paper_key not in run:
        raise ValueError(f"{run_name} has no screening record for paper {paper_key}")
    return run[paper_key].decision


def _count_failed(run: dict[str, ScreeningRecord]) -> int:
    return sum(1 for record in run.values() if record.decision == "failed")


def _by_topic(records: list[ScreeningGold]) -> dict[str, list[ScreeningGold]]:
    grouped: dict[str, list[ScreeningGold]] = defaultdict(list)
    for record in records:
        grouped[record.topic_id].append(record)
    return dict(sorted(grouped.items()))


def _screening_section(
    gold: list[ScreeningGold], run: dict[str, ScreeningRecord]
) -> dict[str, Any]:
    return {
        "topics": {
            topic_id: _screening_metrics(records, run)
            for topic_id, records in _by_topic(gold).items()
        },
        "pooled": _screening_metrics(gold, run),
    }


def _screening_metrics(
    gold: list[ScreeningGold], run: dict[str, ScreeningRecord]
) -> dict[str, Any]:
    table = {g: dict.fromkeys(MODEL_DECISIONS, 0) for g in GOLD_DECISIONS}
    for record in gold:
        table[record.decision][_model_decision(run, record.paper_key, "screening_1.json")] += 1
    n_include = sum(table["include"].values())
    n_exclude = sum(table["exclude"].values())
    return {
        "table": table,
        "include_recall": ratio(table["include"]["include"], n_include),
        "exclude_recall": ratio(table["exclude"]["exclude"], n_exclude),
        "hard_errors": ratio(
            table["include"]["exclude"] + table["exclude"]["include"], n_include + n_exclude
        ),
        "failed": sum(row["failed"] for row in table.values()),
        "gold_uncertain_outcomes": dict(table["uncertain"]),
    }


def _noise(
    gold: list[ScreeningGold],
    first: dict[str, ScreeningRecord],
    second: dict[str, ScreeningRecord],
) -> dict[str, int]:
    flipped = [
        record
        for record in gold
        if _model_decision(first, record.paper_key, "screening_1.json")
        != _model_decision(second, record.paper_key, "screening_2.json")
    ]
    return {
        "flips_total": len(flipped),
        "flips_gold_include": sum(1 for record in flipped if record.decision == "include"),
    }


def _search_section(
    gold_dir: Path, gold: list[ScreeningGold], snapshots: dict[str, SearchSnapshot], size: int
) -> dict[str, Any]:
    topics = {
        topic_id: _precision(
            {r.paper_key: r.decision for r in gold if r.topic_id == topic_id},
            resolve_search_set(snapshot, load_pool(gold_dir, topic_id), size),
            size,
            topic_id,
        )
        for topic_id, snapshot in snapshots.items()
    }
    pooled = ratio(sum(t["k"] for t in topics.values()), sum(t["n"] for t in topics.values()))
    return {"precision_at_10": {"topics": topics, "pooled": pooled}}


def _precision(
    decisions: dict[str, str], resolved: list[str | None], size: int, topic_id: str
) -> dict[str, Any]:
    """Gold includes among the search results; a second copy of a study is not relevant."""
    seen: set[str] = set()
    relevant = 0
    for rank, key in enumerate(resolved, start=1):
        if key is None:
            raise ValueError(f"{topic_id}: search result {rank} is not in the gold pool")
        if key not in seen and decisions[key] == "include":
            relevant += 1
        seen.add(key)
    return ratio(relevant, size)


def _retrieval_section(
    gold: list[ExtractionGold], retrieval: dict[str, list[RetrievedChunk]]
) -> dict[str, Any]:
    def hit(paper: ExtractionGold, field: ExtractionFieldGold) -> bool:
        chunks = [
            chunk
            for chunk in _for_paper(retrieval, paper.paper_key, "retrieval.json")
            if chunk.field == field.field and chunk.rank <= RECALL_K
        ]
        return any(quote_on_page(field.quote, text) for text in joined_runs(chunks))

    return {"recall_at_5": _field_ratios(gold, hit)}


def _extraction_section(
    gold: list[ExtractionGold], extraction: dict[str, ExtractionOutput]
) -> dict[str, Any]:
    def found(paper: ExtractionGold, field: ExtractionFieldGold) -> bool:
        output = _for_paper(extraction, paper.paper_key, "extraction.json")
        return any(r.field == field.field and r.status == "found" for r in output.fields)

    return {"found": _field_ratios(gold, found)}


def _for_paper[T](by_paper: dict[str, T], paper_key: str, file_name: str) -> T:
    if paper_key not in by_paper:
        raise ValueError(f"{file_name} has no entry for extraction-gold paper {paper_key}")
    return by_paper[paper_key]


def _field_ratios(
    gold: list[ExtractionGold], is_hit: Callable[[ExtractionGold, ExtractionFieldGold], bool]
) -> dict[str, Any]:
    """Count the gold fields for which `is_hit(paper, field)` holds, per field and pooled."""
    hits = dict.fromkeys(SCORED_FIELDS, 0)
    totals = dict.fromkeys(SCORED_FIELDS, 0)
    for paper in gold:
        for field in paper.fields:
            totals[field.field] += 1
            hits[field.field] += is_hit(paper, field)
    return {
        "fields": {name: ratio(hits[name], totals[name]) for name in SCORED_FIELDS},
        "pooled": ratio(sum(hits.values()), sum(totals.values())),
    }


def _timings_section(timings: Timings, gold: list[ExtractionGold]) -> dict[str, Any]:
    keys = [paper.paper_key for paper in gold]
    return {
        "screening_pass_s": timings.screening_pass_s,
        "screening_per_paper_s": _screening_per_paper(timings),
        "retrieval_per_paper_s": mean(timings.retrieval_s[key] for key in keys),
        "extraction_per_paper_s": mean(timings.extraction_s[key] for key in keys),
        "retrieval_extraction_per_paper_s": _extraction_per_paper(timings, keys),
    }


def _screening_per_paper(timings: Timings) -> float:
    return mean(seconds / timings.screening_papers for seconds in timings.screening_pass_s)


def _extraction_per_paper(timings: Timings, keys: list[str]) -> float:
    return mean(timings.retrieval_s[key] + timings.extraction_s[key] for key in keys)


def _latency_budget(
    timings: Timings, gold: list[ExtractionGold], snapshots: dict[str, SearchSnapshot]
) -> float:
    """Search time (mean over the topics' snapshot runs) plus the per-paper agent times."""
    search_s = mean(snapshot.duration_s for snapshot in snapshots.values())
    keys = [paper.paper_key for paper in gold]
    return (
        search_s
        + BUDGET_SCREENING_PAPERS * _screening_per_paper(timings)
        + BUDGET_EXTRACTION_PAPERS * _extraction_per_paper(timings, keys)
    )
