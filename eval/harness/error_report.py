"""The wrong outputs of one run, listed per agent for the error analysis. Never imports `src`."""

from pathlib import Path

from pydantic import TypeAdapter

from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    ExtractionGold,
    ScreeningGold,
    load_extraction_gold,
    load_pool,
    load_screening_gold,
    load_search_snapshot,
    resolve_search_set,
)
from eval.harness.records import ExtractionOutput, RetrievedChunk, ScreeningRecord
from eval.harness.scoring import field_found, retrieval_hit
from eval.harness.text import normalize_ws


def render_errors(
    outputs_dir: Path, gold_dir: Path = DEFAULT_GOLD_DIR, *, search_size: int = SEARCH_SET_SIZE
) -> str:
    """A Markdown list of every wrong output of a run: screening, search, retrieval, extraction."""
    gold = load_screening_gold(gold_dir)
    titles = _titles(gold_dir, gold)
    screening = {
        record.paper_key: record
        for record in TypeAdapter(list[ScreeningRecord]).validate_json(
            (outputs_dir / "screening_1.json").read_text("utf-8")
        )
    }
    sections = [
        f"# Errors of run {outputs_dir.name}",
        *_screening_sections([g for g in gold if g.in_screening_set], screening, titles),
        _search_section(gold_dir, gold, titles, search_size),
        *_extraction_sections(outputs_dir, gold_dir),
    ]
    return "\n\n".join(sections) + "\n"


def _titles(gold_dir: Path, gold: list[ScreeningGold]) -> dict[str, str]:
    return {
        paper.paper_key: paper.title
        for topic_id in sorted({record.topic_id for record in gold})
        for paper in load_pool(gold_dir, topic_id)
    }


def _model_view(record: ScreeningRecord) -> str:
    detail = record.error if record.decision == "failed" else record.reasoning
    return f"model `{record.decision}`: {normalize_ws(detail or '')}"


def _screening_sections(
    gold: list[ScreeningGold], screening: dict[str, ScreeningRecord], titles: dict[str, str]
) -> list[str]:
    include_misses = [
        g for g in gold if g.decision == "include" and screening[g.paper_key].decision != "include"
    ]
    exclude_misses = [
        g for g in gold if g.decision == "exclude" and screening[g.paper_key].decision != "exclude"
    ]
    uncertain = sum(screening[g.paper_key].decision == "uncertain" for g in include_misses)

    def lines(misses: list[ScreeningGold]) -> str:
        if not misses:
            return "None."
        return "\n".join(
            f"- `{g.paper_key}` ({g.topic_id}) {titles[g.paper_key]}\n"
            f"  gold `{g.decision}`, {_model_view(screening[g.paper_key])}"
            for g in misses
        )

    return [
        f"## Screening: gold includes the model did not include\n\n"
        f"{len(include_misses)} papers, {uncertain} of them marked `uncertain` "
        f"(backlog #37).\n\n{lines(include_misses)}",
        f"## Screening: gold excludes the model did not exclude\n\n{lines(exclude_misses)}",
    ]


def _search_section(
    gold_dir: Path, gold: list[ScreeningGold], titles: dict[str, str], size: int
) -> str:
    lines: list[str] = []
    for topic_id in sorted({g.topic_id for g in gold}):
        labels = {g.paper_key: g for g in gold if g.topic_id == topic_id}
        resolved = resolve_search_set(
            load_search_snapshot(gold_dir, topic_id), load_pool(gold_dir, topic_id), size
        )
        seen: set[str] = set()
        for rank, key in enumerate(resolved, start=1):
            if key is None:
                raise ValueError(f"{topic_id}: search result {rank} is not in the gold pool")
            if key in seen:
                lines.append(f"- {topic_id} rank {rank} `{key}`: second copy of a study")
            elif labels[key].decision != "include":
                lines.append(
                    f"- {topic_id} rank {rank} `{key}` {titles[key]}\n"
                    f"  gold `{labels[key].decision}`: {_non_yes_answers(labels[key])}"
                )
            seen.add(key)
    return "## Search: top results that are not gold includes\n\n" + ("\n".join(lines) or "None.")


def _non_yes_answers(label: ScreeningGold) -> str:
    return "; ".join(
        f"{check_id} {answer.answer} ({normalize_ws(answer.reason)})"
        for check_id, answer in label.answers.items()
        if answer.answer != "yes"
    )


def _extraction_sections(outputs_dir: Path, gold_dir: Path) -> list[str]:
    papers = load_extraction_gold(gold_dir)
    retrieval = TypeAdapter(dict[str, list[RetrievedChunk]]).validate_json(
        (outputs_dir / "retrieval.json").read_text("utf-8")
    )
    extraction = TypeAdapter(dict[str, ExtractionOutput]).validate_json(
        (outputs_dir / "extraction.json").read_text("utf-8")
    )
    return [
        "## Retrieval: gold quotes not in the top 5 chunks\n\n"
        + _retrieval_misses(papers, retrieval),
        "## Extraction: gold fields the model reported as not found\n\n"
        + _extraction_misses(papers, extraction),
    ]


def _retrieval_misses(
    papers: list[ExtractionGold], retrieval: dict[str, list[RetrievedChunk]]
) -> str:
    lines = []
    for paper in papers:
        chunks = retrieval[paper.paper_key]
        for field in paper.fields:
            if not retrieval_hit(chunks, field):
                where = ", ".join(
                    f"p{chunk.page}#{chunk.ordinal}"
                    for chunk in sorted(chunks, key=lambda c: c.rank)
                    if chunk.field == field.field
                )
                lines.append(
                    f"- `{paper.paper_key}` {field.field}: quote on page {field.page}, "
                    f"retrieved {where or 'nothing'}"
                )
    return "\n".join(lines) or "None."


def _extraction_misses(
    papers: list[ExtractionGold], extraction: dict[str, ExtractionOutput]
) -> str:
    lines = []
    for paper in papers:
        output = extraction[paper.paper_key]
        for field in paper.fields:
            if not field_found(output, field):
                reported = next((r.value for r in output.fields if r.field == field.field), None)
                lines.append(
                    f"- `{paper.paper_key}` {field.field}: gold `{field.value}`, "
                    f"model value `{reported if reported is not None else output.error}`"
                )
    return "\n".join(lines) or "None."
