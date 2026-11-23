import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from eval.harness.gold import (
    GoldLimits,
    GoldReport,
    load_extraction_gold,
    load_pool,
    load_screening_gold,
    load_search_snapshot,
    resolve_search_set,
    validate,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
MINI_LIMITS = GoldLimits(
    search_size=3, screening_size=5, min_includes=2, max_includes=3, max_uncertain=1
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A writable copy of the fixture gold set, page text and topics."""
    shutil.copytree(FIXTURES, tmp_path / "fx", ignore=shutil.ignore_patterns("runs"))
    return tmp_path / "fx"


def report(workspace: Path, with_data: bool = True) -> GoldReport:
    return validate(
        workspace / "gold",
        workspace / "data" if with_data else None,
        limits=MINI_LIMITS,
        topics_dir=workspace / "topics",
    )


def check(workspace: Path, with_data: bool = True) -> list[str]:
    return report(workspace, with_data).errors


def edit(path: Path, change: Callable[[Any], None]) -> None:
    data = json.loads(path.read_text("utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def record(screening: list[dict], key: str) -> dict:
    return next(item for item in screening if item["paper_key"] == key)


def test_the_fixture_gold_set_is_valid(workspace: Path):
    assert check(workspace) == []


def test_loaders_return_typed_records():
    gold_dir = FIXTURES / "gold"

    screening = load_screening_gold(gold_dir)
    assert len(screening) == 12
    assert screening[0].answers["c1"].source in ("model", "model_verified", "human")
    assert load_extraction_gold(gold_dir)[0].fields[0].field == "method"
    assert [paper.paper_key for paper in load_pool(gold_dir, "ta_mini")][:2] == ["WA1", "WA2"]
    assert load_search_snapshot(gold_dir, "ta_mini").fallback_used is False


def test_the_default_limits_report_the_real_set_sizes(workspace: Path):
    problems = validate(workspace / "gold", None, topics_dir=workspace / "topics").errors

    assert "ta_mini: screening set has 5 papers, expected 20" in problems
    assert "ta_mini: screening set has 3 gold includes, expected 8 to 12" in problems
    assert any("search snapshot has 4 papers, not 10" in problem for problem in problems)


def test_the_mix_limits_report_too_many_uncertain_papers(workspace: Path):
    def make_uncertain(screening: list[dict]) -> None:
        for key in ("WA1", "WA2"):
            item = record(screening, key)
            item["answers"]["c2"]["answer"] = "not_stated"
            item["decision"] = "uncertain"

    edit(workspace / "gold/screening.json", make_uncertain)

    problems = check(workspace)

    assert "ta_mini: screening set has 3 gold uncertain papers, at most 1 allowed" in problems
    assert "ta_mini: screening set has 1 gold includes, expected 2 to 3" in problems


def make_two_uncertain(screening: list[dict]) -> None:
    for key in ("WA2", "WA6"):
        item = record(screening, key)
        item["answers"]["c2"]["answer"] = "not_stated"
        item["decision"] = "uncertain"


def write_provenance(workspace: Path, mix_exceptions: dict[str, str]) -> None:
    (workspace / "gold/provenance.json").write_text(
        json.dumps({"labeling_model": "m", "mix_exceptions": mix_exceptions}), encoding="utf-8"
    )


def test_a_recorded_mix_exception_turns_the_mix_errors_into_warnings(workspace: Path):
    edit(workspace / "gold/screening.json", make_two_uncertain)
    write_provenance(workspace, {"ta_mini": "only 4 of its papers are about teenagers"})

    result = report(workspace)

    assert result.errors == []
    assert result.warnings == [
        "ta_mini: screening set has 1 gold includes, expected 2 to 3 "
        "(recorded exception: only 4 of its papers are about teenagers)",
        "ta_mini: screening set has 3 gold uncertain papers, at most 1 allowed "
        "(recorded exception: only 4 of its papers are about teenagers)",
    ]


def test_a_mix_exception_for_another_topic_does_not_excuse_a_topic(workspace: Path):
    edit(workspace / "gold/screening.json", make_two_uncertain)
    write_provenance(workspace, {"tb_mini": "a reason for the wrong topic"})

    result = report(workspace)

    assert "ta_mini: screening set has 1 gold includes, expected 2 to 3" in result.errors
    assert result.warnings == []


def test_a_mix_exception_does_not_excuse_a_wrong_set_size(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: record(screening, "WA6").update(in_screening_set=False),
    )
    write_provenance(workspace, {"ta_mini": "a reason"})

    assert "ta_mini: screening set has 4 papers, expected 5" in report(workspace).errors


def test_a_mix_exception_without_a_reason_or_for_an_unknown_topic_is_an_error(workspace: Path):
    write_provenance(workspace, {"ta_mini": "", "tx_unknown": "typo"})

    errors = check(workspace)

    assert any(p.startswith("provenance.json:") and "ta_mini" in p for p in errors)
    write_provenance(workspace, {"tx_unknown": "typo"})
    assert "provenance.json: mix exception for tx_unknown, which has no gold labels" in check(
        workspace
    )


def test_a_gold_set_without_provenance_has_no_mix_exceptions(workspace: Path):
    assert not (workspace / "gold/provenance.json").exists()
    assert report(workspace).warnings == []


def test_a_decision_that_does_not_follow_from_its_answers_is_reported(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: record(screening, "WA4").update(decision="include"),
    )

    assert "ta_mini WA4: decision is 'include' but answers give 'exclude'" in check(workspace)


def test_answers_that_do_not_cover_the_topic_checks_are_reported(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: record(screening, "WA4")["answers"].pop("c2"),
    )

    assert any("WA4: answers cover ['c1']" in problem for problem in check(workspace))


def test_an_answer_without_a_source_is_reported(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: record(screening, "WA4")["answers"]["c1"].pop("source"),
    )

    problems = check(workspace)

    assert any(p.startswith("screening.json:") and "source: Field required" in p for p in problems)


def test_an_unlabeled_pool_paper_and_a_label_without_a_pool_paper_are_reported(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: screening.remove(record(screening, "WA7")),
    )
    edit(
        workspace / "gold/tb_mini/pool.json",
        lambda pool: pool.remove(next(p for p in pool if p["paper_key"] == "WB6")),
    )

    problems = check(workspace)

    assert "ta_mini: pool paper WA7 has no gold labels" in problems
    assert "tb_mini: gold labels for WB6, which is not in the pool" in problems


def test_two_pool_papers_with_the_same_normalized_title_are_a_duplicate(workspace: Path):
    def retitle(pool: list[dict]) -> None:
        next(p for p in pool if p["paper_key"] == "WA4")["title"] = "study TWO on group-chats."

    edit(workspace / "gold/ta_mini/pool.json", retitle)

    assert "ta_mini: duplicate study in the pool: ['WA2', 'WA4']" in check(workspace)


def test_a_paper_labeled_in_two_topics_is_reported(workspace: Path):
    def copy_to_other_topic(screening: list[dict]) -> None:
        screening.append(dict(record(screening, "WA7"), topic_id="tb_mini"))

    edit(workspace / "gold/screening.json", copy_to_other_topic)

    assert any(
        "paper WA7 is in several topics ['ta_mini', 'tb_mini']" in p for p in check(workspace)
    )


def test_the_search_set_flags_must_match_the_first_search_results(workspace: Path):
    edit(
        workspace / "gold/screening.json",
        lambda screening: record(screening, "WA1").update(in_search_set=False),
    )

    assert any(p.startswith("ta_mini: in_search_set marks ['WA2']") for p in check(workspace))


def test_a_search_result_missing_from_the_pool_is_reported(workspace: Path):
    def drop_alias(pool: list[dict]) -> None:
        next(p for p in pool if p["paper_key"] == "WA2")["aliases"] = []

    edit(workspace / "gold/ta_mini/pool.json", drop_alias)

    assert "ta_mini: search result 3 is not in the pool" in check(workspace)


def test_a_missing_file_is_a_problem_not_a_crash(workspace: Path):
    (workspace / "gold/tb_mini/search.json").unlink()

    problems = check(workspace)

    assert any(p.startswith("tb_mini/search.json:") and "No such file" in p for p in problems)


def test_an_extraction_paper_must_be_a_gold_include_of_its_topic(workspace: Path):
    def make_exclude(screening: list[dict]) -> None:
        item = record(screening, "WB1")
        item["answers"]["c1"]["answer"] = "no"
        item["decision"] = "exclude"

    edit(workspace / "gold/screening.json", make_exclude)

    assert "extraction WB1: must be a gold include in the screening set" in check(workspace)


def test_a_field_listed_twice_for_one_paper_is_reported(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[0]["fields"].append(extraction[0]["fields"][0]),
    )

    assert "extraction WA1: field method appears twice" in check(workspace)


def test_a_field_outside_the_scored_set_is_reported(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[0]["fields"][0].update(field="funding"),
    )

    assert any(p.startswith("extraction.json:") and "fields.0.field" in p for p in check(workspace))


def test_a_quote_that_is_not_on_its_page_is_reported(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[0]["fields"][0].update(page=3),
    )

    assert "extraction WA1: quote of method is not on page 3" in check(workspace)


def test_a_page_beyond_the_pdf_is_reported(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[1]["fields"][0].update(page=9),
    )

    assert "extraction WB1: task cites page 9, PDF has 2" in check(workspace)


def test_a_page_file_from_another_pdf_is_a_hash_mismatch(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[0].update(pdf_sha256="0" * 64),
    )

    problems = check(workspace)

    assert (
        "extraction WA1: page text is from a PDF with another hash than the gold file" in problems
    )


def test_quotes_are_only_checked_when_a_data_folder_is_given(workspace: Path):
    edit(
        workspace / "gold/extraction.json",
        lambda extraction: extraction[0]["fields"][0].update(quote="Not in the paper."),
    )

    assert check(workspace, with_data=False) == []
    assert "extraction WA1: quote of method is not on page 2" in check(workspace)


def test_a_missing_page_text_file_is_reported(workspace: Path):
    (workspace / "data/pages/WB1.json").unlink()

    assert any("extraction WB1 page text:" in p for p in check(workspace))


def test_resolve_search_set_maps_aliases_and_marks_unknown_papers():
    gold_dir = FIXTURES / "gold"
    snapshot = load_search_snapshot(gold_dir, "ta_mini")
    pool = load_pool(gold_dir, "ta_mini")

    assert resolve_search_set(snapshot, pool, 3) == ["WA1", "WA2", "WA2"]
    assert resolve_search_set(snapshot, pool, 4) == ["WA1", "WA2", "WA2", None]
