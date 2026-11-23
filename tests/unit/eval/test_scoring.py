import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from eval.harness.scoring import ratio, score

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
GOLD_DIR = FIXTURES / "gold"
SEARCH_SIZE = 3


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A writable copy of the recorded complete run."""
    shutil.copytree(FIXTURES / "runs" / "complete", tmp_path / "complete")
    return tmp_path / "complete"


def edit(path: Path, change: Callable[[Any], None]) -> None:
    data = json.loads(path.read_text("utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def scored(run_dir: Path) -> dict[str, Any]:
    return score(run_dir, GOLD_DIR, search_size=SEARCH_SIZE)


def kn(value: dict[str, Any]) -> tuple[int, int]:
    return value["k"], value["n"]


def test_ratio_reports_counts_with_the_rate_and_no_rate_for_an_empty_total():
    assert ratio(1, 4) == {"k": 1, "n": 4, "rate": 0.25}
    assert ratio(0, 0) == {"k": 0, "n": 0, "rate": None}


def test_the_results_file_names_the_run_and_copies_its_provenance():
    results = score(FIXTURES / "runs" / "complete", GOLD_DIR, search_size=SEARCH_SIZE)

    assert results["run_id"] == "complete"
    assert results["status"] == "complete"
    assert results["provenance"]["adapter"] == "phase1"
    assert results["provenance"]["context_length"] == "ollama_default"


def test_the_gold_by_model_table_per_topic_and_pooled(run_dir: Path):
    screening = scored(run_dir)["screening"]

    assert screening["topics"]["ta_mini"]["table"] == {
        "include": {"include": 1, "exclude": 0, "uncertain": 1, "failed": 1},
        "exclude": {"include": 0, "exclude": 1, "uncertain": 0, "failed": 0},
        "uncertain": {"include": 1, "exclude": 0, "uncertain": 0, "failed": 0},
    }
    assert screening["topics"]["tb_mini"]["table"] == {
        "include": {"include": 2, "exclude": 1, "uncertain": 0, "failed": 0},
        "exclude": {"include": 1, "exclude": 1, "uncertain": 0, "failed": 0},
        "uncertain": {"include": 0, "exclude": 0, "uncertain": 0, "failed": 0},
    }
    assert screening["pooled"]["table"] == {
        "include": {"include": 3, "exclude": 1, "uncertain": 1, "failed": 1},
        "exclude": {"include": 1, "exclude": 2, "uncertain": 0, "failed": 0},
        "uncertain": {"include": 1, "exclude": 0, "uncertain": 0, "failed": 0},
    }


def test_an_uncertain_or_failed_call_is_an_include_miss(run_dir: Path):
    topic = scored(run_dir)["screening"]["topics"]["ta_mini"]

    # gold includes WA1, WA2, WA6; the model said include, uncertain, failed
    assert kn(topic["include_recall"]) == (1, 3)
    assert topic["failed"] == 1


def test_exclude_recall_hard_errors_and_gold_uncertain_outcomes(run_dir: Path):
    screening = scored(run_dir)["screening"]

    assert kn(screening["topics"]["ta_mini"]["exclude_recall"]) == (1, 1)
    assert kn(screening["topics"]["ta_mini"]["hard_errors"]) == (0, 4)
    assert kn(screening["topics"]["tb_mini"]["exclude_recall"]) == (1, 2)
    # WB4 gold include -> exclude and WB2 gold exclude -> include
    assert kn(screening["topics"]["tb_mini"]["hard_errors"]) == (2, 5)
    assert kn(screening["pooled"]["include_recall"]) == (3, 6)
    assert kn(screening["pooled"]["exclude_recall"]) == (2, 3)
    assert kn(screening["pooled"]["hard_errors"]) == (2, 9)
    assert screening["pooled"]["gold_uncertain_outcomes"] == {
        "include": 1,
        "exclude": 0,
        "uncertain": 0,
        "failed": 0,
    }


def test_only_the_screening_set_is_scored(run_dir: Path):
    pooled = scored(run_dir)["screening"]["pooled"]

    # 12 labeled papers, 10 of them in a screening set
    assert sum(sum(row.values()) for row in pooled["table"].values()) == 10


def test_flips_between_the_two_screening_runs_in_total_and_among_gold_includes(run_dir: Path):
    # WA2, WA5, WA6 and WB2 changed; WA2 and WA6 are gold includes
    assert scored(run_dir)["noise"] == {"flips_total": 4, "flips_gold_include": 2}


def test_precision_at_k_counts_gold_includes_and_a_second_copy_as_not_relevant(run_dir: Path):
    search = scored(run_dir)["search"]["precision_at_10"]

    # topic A top 3: WA1 include, WA2 include, WA2D = second copy of WA2
    assert kn(search["topics"]["ta_mini"]) == (2, 3)
    # topic B top 3: WB1 include, WB2 exclude, WB3 exclude
    assert kn(search["topics"]["tb_mini"]) == (1, 3)
    assert kn(search["pooled"]) == (3, 6)


def test_precision_stops_at_the_search_set_size(run_dir: Path):
    # the fourth snapshot result is not in the pool, so a size of 4 cannot be scored
    with pytest.raises(ValueError, match="ta_mini: search result 4 is not in the gold pool"):
        score(run_dir, GOLD_DIR, search_size=4)


def test_retrieval_recall_per_field_including_a_quote_split_over_two_chunks(run_dir: Path):
    recall = scored(run_dir)["retrieval"]["recall_at_5"]

    # WA1: method hit, dataset miss, findings hit, limitations hit only by joining chunks 3+4
    # WB1: task hit, findings miss (wrong chunk), limitations miss (nothing retrieved)
    assert {field: kn(value) for field, value in recall["fields"].items()} == {
        "method": (1, 1),
        "dataset": (0, 1),
        "task": (1, 1),
        "main_findings": (1, 2),
        "limitations": (1, 2),
    }
    assert kn(recall["pooled"]) == (4, 7)


def test_a_chunk_below_the_recall_cutoff_does_not_count(run_dir: Path):
    def push_down(retrieval: dict) -> None:
        retrieval["WA1"][0]["rank"] = 6

    edit(run_dir / "retrieval.json", push_down)

    recall = scored(run_dir)["retrieval"]["recall_at_5"]

    assert kn(recall["fields"]["method"]) == (0, 1)


def test_extraction_field_status_per_field_and_pooled(run_dir: Path):
    found = scored(run_dir)["extraction"]["found"]

    assert {field: kn(value) for field, value in found["fields"].items()} == {
        "method": (1, 1),
        "dataset": (1, 1),
        "task": (1, 1),
        "main_findings": (2, 2),
        "limitations": (0, 2),
    }
    assert kn(found["pooled"]) == (5, 7)


def test_a_failed_extraction_misses_its_gold_fields_and_is_counted(run_dir: Path):
    def fail_wa1(extraction: dict) -> None:
        extraction["WA1"] = {"fields": [], "raw": None, "error": "Validation failed"}

    edit(run_dir / "extraction.json", fail_wa1)

    results = scored(run_dir)

    assert kn(results["extraction"]["found"]["pooled"]) == (2, 7)
    assert results["failures"] == {"screening_1": 1, "screening_2": 0, "extraction": 1}


def test_timings_and_the_latency_budget(run_dir: Path):
    results = scored(run_dir)

    # screening: (30 / 10 + 20 / 10) / 2 = 2.5 s per paper
    # retrieval 2.0 + extraction 8.0 = 10.0 s per paper
    # search: mean of 20 s and 40 s = 30 s
    assert results["timings"] == {
        "screening_pass_s": [30.0, 20.0],
        "screening_per_paper_s": 2.5,
        "retrieval_per_paper_s": 2.0,
        "extraction_per_paper_s": 8.0,
        "retrieval_extraction_per_paper_s": 10.0,
    }
    assert results["latency_budget_s"] == 30 + 25 * 2.5 + 10 * 10.0


def test_scoring_twice_gives_the_same_results(run_dir: Path):
    assert scored(run_dir) == scored(run_dir)


def test_an_incomplete_run_is_refused():
    with pytest.raises(ValueError, match="run incomplete is incomplete .*Ollama is not reachable"):
        score(FIXTURES / "runs" / "incomplete", GOLD_DIR, search_size=SEARCH_SIZE)


def test_a_screening_run_that_misses_a_gold_paper_is_an_error(run_dir: Path):
    edit(
        run_dir / "screening_1.json",
        lambda records: records.remove(next(r for r in records if r["paper_key"] == "WB5")),
    )

    with pytest.raises(ValueError, match="screening_1.json has no screening record for paper WB5"):
        scored(run_dir)


def test_a_run_without_retrieval_for_a_gold_paper_is_an_error(run_dir: Path):
    edit(run_dir / "retrieval.json", lambda retrieval: retrieval.pop("WB1"))

    with pytest.raises(ValueError, match="retrieval.json has no entry for.*WB1"):
        scored(run_dir)
