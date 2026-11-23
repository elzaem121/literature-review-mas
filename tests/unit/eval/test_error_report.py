import json
import shutil
from pathlib import Path

import pytest

from eval.harness import score as score_module
from eval.harness.error_report import render_errors
from src.llm.settings import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
GOLD_DIR = FIXTURES / "gold"
SEARCH_SIZE = 3


@pytest.fixture(scope="module")
def errors() -> str:
    return render_errors(FIXTURES / "runs" / "complete", GOLD_DIR, search_size=SEARCH_SIZE)


def section(errors: str, heading: str) -> str:
    """The text of one `## heading` section, without the heading."""
    body = errors.split(f"## {heading}\n", 1)[1]
    return body.split("\n## ", 1)[0].strip()


def test_the_report_names_the_run(errors: str):
    assert errors.startswith("# Errors of run complete\n")


def test_missed_gold_includes_are_listed_with_the_models_view_and_the_uncertain_count(errors: str):
    body = section(errors, "Screening: gold includes the model did not include")

    assert body.startswith("3 papers, 1 of them marked `uncertain` (backlog #37).")
    assert (
        "- `WA2` (ta_mini) Study Two on Group Chats\n  gold `include`, model `uncertain`: " in body
    )
    assert "gold `include`, model `failed`: Validation failed after retries" in body
    assert "- `WB4` (tb_mini) Study Four on Support\n  gold `include`, model `exclude`" in body
    assert "WB1" not in body


def test_missed_gold_excludes_are_listed(errors: str):
    body = section(errors, "Screening: gold excludes the model did not exclude")

    assert body.splitlines()[0] == "- `WB2` (tb_mini) Study Two on Moderation"
    assert body.count("\n- ") == 0


def test_search_results_that_are_not_gold_includes_show_the_failing_checks(errors: str):
    body = section(errors, "Search: top results that are not gold includes")

    assert "- ta_mini rank 3 `WA2`: second copy of a study" in body
    assert (
        "- tb_mini rank 3 `WB3` Study Three on Trust\n  gold `exclude`: c1 no (WB3 c1: no.)" in body
    )
    assert "`WA1`" not in body


def test_retrieval_misses_show_the_gold_page_and_what_was_retrieved(errors: str):
    body = section(errors, "Retrieval: gold quotes not in the top 5 chunks")

    assert body.splitlines() == [
        "- `WA1` dataset: quote on page 2, retrieved p3#3",
        "- `WB1` main_findings: quote on page 2, retrieved p1#0",
        "- `WB1` limitations: quote on page 2, retrieved nothing",
    ]


def test_found_fields_the_model_called_not_found_show_both_values(errors: str):
    body = section(errors, "Extraction: gold fields the model reported as not found")

    assert body.splitlines() == [
        "- `WA1` limitations: gold `Two schools, self-reported accounts`, "
        "model value `Not mentioned`",
        "- `WB1` limitations: gold `The framework is untested`, model value `Not stated`",
    ]


def test_a_run_that_matches_the_gold_has_no_screening_errors(tmp_path: Path):
    run_dir = tmp_path / "perfect"
    shutil.copytree(FIXTURES / "runs" / "complete", run_dir)
    gold = {
        record["paper_key"]: record["decision"]
        for record in json.loads((GOLD_DIR / "screening.json").read_text("utf-8"))
    }
    records = json.loads((run_dir / "screening_1.json").read_text("utf-8"))
    for record in records:
        record.update(decision=gold[record["paper_key"]], error=None)
    (run_dir / "screening_1.json").write_text(json.dumps(records), encoding="utf-8")

    errors = render_errors(run_dir, GOLD_DIR, search_size=SEARCH_SIZE)

    assert section(errors, "Screening: gold includes the model did not include").endswith("None.")
    assert section(errors, "Screening: gold excludes the model did not exclude") == "None."


def test_the_score_command_scores_a_run_in_the_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    shutil.copytree(FIXTURES / "runs" / "complete", tmp_path / "outputs" / "r1")
    monkeypatch.setenv("EVAL_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    scored: list[Path] = []

    def spy(run_dir: Path) -> Path:
        scored.append(run_dir)
        return Path("results/r1.json")

    monkeypatch.setattr(score_module, "score_run", spy)

    assert score_module.main(["r1"]) == 0
    assert scored == [tmp_path / "outputs" / "r1"]


def test_the_score_command_refuses_an_incomplete_run_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    shutil.copytree(FIXTURES / "runs" / "incomplete", tmp_path / "outputs" / "r2")
    monkeypatch.setenv("EVAL_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(SystemExit) as exit_info:
        score_module.main(["r2"])

    assert "run r2 is incomplete" in str(exit_info.value)
