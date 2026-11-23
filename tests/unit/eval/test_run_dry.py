"""The whole eval run on the fixture gold set, with the fake LLM, fake embedder and a temp folder.

Every expected number was worked out by hand from the fixture gold (tests/fixtures/eval/gold),
the scripted screening answers below, and the fake extraction answer (limitations "not specified").
"""

import asyncio
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest

from eval.harness import run as run_module
from eval.harness.ollama_check import OllamaCheckError
from eval.harness.run import RunSummary, run_eval
from eval.harness.score import score_run
from src.llm.fake import Messages, get_fake_answers, set_fake_answers
from src.llm.settings import get_settings
from src.pipeline.screening.screening_schemas import PaperScreeningResult, ScreeningDecision

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
SEARCH_SIZE = 3
FAIL = "fail"
# Each title's screening answer in the first and the second pass over the screening set.
SCRIPT: dict[str, tuple[str, str]] = {
    "Social Media Use and Everyday Identity Work Among Teenagers": ("include", "include"),
    "Study Two on Group Chats": ("uncertain", "include"),
    "Study Four on Gaming": ("include", "include"),
    "Study Five on Streaming": ("exclude", "exclude"),
    "Study Six on Messaging": (FAIL, FAIL),
    "Online Communities and Young Adults": ("include", "include"),
    "Study Two on Moderation": ("exclude", "exclude"),
    "Study Three on Trust": ("include", "exclude"),
    "Study Four on Support": ("exclude", "exclude"),
    "Study Five on Reputation": ("include", "include"),
}


def script_screening(script: dict[str, tuple[str, str]], failure: Exception | None = None):
    """A fake screener that answers each title as scripted, by how often it was asked before."""
    calls: Counter[str] = Counter()

    def screen(messages: Messages) -> PaperScreeningResult:
        prompt = messages[-1]["content"]
        title = next(title for title in script if f"Title: {title}\n" in prompt)
        answer = script[title][calls[title]]
        calls[title] += 1
        if answer == FAIL:
            raise failure or RuntimeError("Simulated LLM API error")
        return PaperScreeningResult(
            decision=ScreeningDecision(answer),
            confidence_score=8,
            relevance_score=5,
            reasoning=f"Scripted {answer} for {title}.",
        )

    return screen


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURES, tmp_path / "fx", ignore=shutil.ignore_patterns("runs"))
    return tmp_path / "fx"


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """A reachable Ollama that serves every model; the list records what each check asked for."""
    asked: list[list[str]] = []

    def check_models(models: list[str], base_url: str) -> dict[str, str]:
        asked.append(list(models))
        return {model: "sha256:fixture" for model in models}

    monkeypatch.setattr(run_module, "check_models", check_models)
    return asked


@pytest.fixture(autouse=True)
def scripted_screener() -> None:
    set_fake_answers({**get_fake_answers(), PaperScreeningResult: script_screening(SCRIPT)})


def run(workspace: Path) -> RunSummary:
    return asyncio.run(
        run_eval(
            "phase1",
            workspace / "data",
            gold_dir=workspace / "gold",
            topics_dir=workspace / "topics",
            results_dir=workspace / "results",
            search_size=SEARCH_SIZE,
        )
    )


def read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def test_a_complete_run_saves_its_outputs_and_the_scored_results(
    workspace: Path, ollama: list[list[str]]
):
    summary = run(workspace)

    assert summary.status == "complete"
    assert re.fullmatch(r"\d{8}T\d{6}-phase1-[0-9a-f]{7,}", summary.run_id)
    run_dir = workspace / "data" / "outputs" / summary.run_id
    assert sorted(path.name for path in run_dir.iterdir()) == [
        "errors.md",
        "extraction.json",
        "provenance.json",
        "retrieval.json",
        "screening_1.json",
        "screening_2.json",
        "timings.json",
    ]
    assert summary.results_path == workspace / "results" / f"{summary.run_id}.json"
    assert read(summary.results_path)["run_id"] == summary.run_id


def test_the_provenance_records_the_system_and_the_frozen_inputs(
    workspace: Path, ollama: list[list[str]]
):
    summary = run(workspace)

    provenance = read(workspace / "data" / "outputs" / summary.run_id / "provenance.json")
    assert provenance["status"] == "complete"
    assert provenance["incomplete_reason"] is None
    assert provenance["adapter"] == "phase1"
    assert provenance["models"] == {
        "search": "qwen2.5-coder:7b",
        "screening": "qwen2.5-coder:7b",
        "extraction": "qwen2.5-coder:7b",
    }
    assert provenance["ollama_digests"] == {"qwen2.5-coder:7b": "sha256:fixture"}
    assert provenance["context_length"] == "ollama_default"
    assert provenance["gold_version"] == "gold"
    assert provenance["snapshot_retrieved_at"] == {
        "ta_mini": "2026-11-23T10:00:00Z",
        "tb_mini": "2026-11-23T10:00:00Z",
    }
    assert provenance["git_commit"] == summary.run_id.rsplit("-", 1)[1]
    assert (provenance["chunker_version"], provenance["retrieval_top_k"]) == ("v1", 5)


def test_the_models_are_checked_once_before_and_once_after_the_run(
    workspace: Path, ollama: list[list[str]]
):
    run(workspace)

    assert ollama == [["qwen2.5-coder:7b"], ["qwen2.5-coder:7b"]]


def test_the_screening_numbers_match_the_hand_computed_expectation(
    workspace: Path, ollama: list[list[str]]
):
    results = read(run(workspace).results_path)

    ta = results["screening"]["topics"]["ta_mini"]
    assert ta["table"] == {
        "include": {"include": 1, "exclude": 0, "uncertain": 1, "failed": 1},
        "exclude": {"include": 1, "exclude": 0, "uncertain": 0, "failed": 0},
        "uncertain": {"include": 0, "exclude": 1, "uncertain": 0, "failed": 0},
    }
    assert ta["include_recall"] == {"k": 1, "n": 3, "rate": 1 / 3}
    assert ta["hard_errors"] == {"k": 1, "n": 4, "rate": 0.25}
    assert ta["failed"] == 1
    tb = results["screening"]["topics"]["tb_mini"]
    assert tb["include_recall"]["k"] == 2
    assert tb["exclude_recall"] == {"k": 1, "n": 2, "rate": 0.5}
    assert tb["hard_errors"] == {"k": 2, "n": 5, "rate": 0.4}
    pooled = results["screening"]["pooled"]
    assert pooled["include_recall"] == {"k": 3, "n": 6, "rate": 0.5}
    assert pooled["exclude_recall"] == {"k": 1, "n": 3, "rate": 1 / 3}
    assert pooled["hard_errors"] == {"k": 3, "n": 9, "rate": 1 / 3}
    assert pooled["failed"] == 1
    assert pooled["gold_uncertain_outcomes"] == {
        "include": 0,
        "exclude": 1,
        "uncertain": 0,
        "failed": 0,
    }


def test_the_second_screening_pass_gives_the_noise_and_a_failed_call_is_counted(
    workspace: Path, ollama: list[list[str]]
):
    results = read(run(workspace).results_path)

    assert results["noise"] == {"flips_total": 2, "flips_gold_include": 1}
    assert results["failures"] == {"screening_1": 1, "screening_2": 1, "extraction": 0}


def test_search_retrieval_and_extraction_are_scored_on_the_gold_papers(
    workspace: Path, ollama: list[list[str]]
):
    results = read(run(workspace).results_path)

    assert results["search"]["precision_at_10"]["topics"]["ta_mini"] == {
        "k": 2,
        "n": 3,
        "rate": 2 / 3,
    }
    assert results["search"]["precision_at_10"]["topics"]["tb_mini"]["k"] == 1
    # Both papers have at most 5 chunks, so every chunk is retrieved for every field.
    assert results["retrieval"]["recall_at_5"]["pooled"] == {"k": 7, "n": 7, "rate": 1.0}
    found = results["extraction"]["found"]
    assert {name: (v["k"], v["n"]) for name, v in found["fields"].items()} == {
        "method": (1, 1),
        "dataset": (1, 1),
        "task": (1, 1),
        "main_findings": (2, 2),
        "limitations": (0, 2),
    }
    assert found["pooled"] == {"k": 5, "n": 7, "rate": 5 / 7}


def test_the_saved_records_hold_the_chunks_and_the_raw_extraction_output(
    workspace: Path, ollama: list[list[str]]
):
    summary = run(workspace)

    run_dir = workspace / "data" / "outputs" / summary.run_id
    retrieval = read(run_dir / "retrieval.json")
    assert sorted(retrieval) == ["WA1", "WB1"]
    assert {chunk["field"] for chunk in retrieval["WA1"]} == {
        "method",
        "dataset",
        "task",
        "main_findings",
        "limitations",
    }
    extraction = read(run_dir / "extraction.json")
    assert extraction["WA1"]["raw"]["paper_type"] == "qualitative interview study"
    assert len(read(run_dir / "screening_1.json")) == 10
    timings = read(run_dir / "timings.json")
    assert timings["screening_papers"] == 10
    assert len(timings["screening_pass_s"]) == 2
    assert sorted(timings["retrieval_s"]) == sorted(timings["extraction_s"]) == ["WA1", "WB1"]


def test_rescoring_the_saved_outputs_reproduces_the_results_file(
    workspace: Path, ollama: list[list[str]]
):
    summary = run(workspace)
    first = summary.results_path.read_bytes()

    score_run(
        workspace / "data" / "outputs" / summary.run_id,
        workspace / "gold",
        workspace / "results",
        search_size=SEARCH_SIZE,
    )

    assert summary.results_path.read_bytes() == first


def test_errors_md_lists_the_wrong_outputs_with_the_models_reasoning(
    workspace: Path, ollama: list[list[str]]
):
    summary = run(workspace)

    errors = (workspace / "data" / "outputs" / summary.run_id / "errors.md").read_text("utf-8")
    assert "Scripted uncertain for Study Two on Group Chats." in errors
    assert "`WA6` (ta_mini) Study Six on Messaging\n  gold `include`, model `failed`" in errors
    assert "`WA4` (ta_mini) Study Four on Gaming\n  gold `exclude`, model `include`" in errors


def test_a_connection_error_during_the_run_makes_it_incomplete_and_unscored(
    workspace: Path, ollama: list[list[str]]
):
    refused = openai.APIConnectionError(request=httpx.Request("POST", "http://localhost/v1"))
    script = {**SCRIPT, "Study Six on Messaging": (FAIL, FAIL)}
    set_fake_answers(
        {**get_fake_answers(), PaperScreeningResult: script_screening(script, refused)}
    )

    summary = run(workspace)

    assert summary.status == "incomplete"
    assert summary.results_path is None
    assert "calls failed on the infrastructure" in summary.incomplete_reason
    assert not (workspace / "results").exists()
    provenance = read(workspace / "data" / "outputs" / summary.run_id / "provenance.json")
    assert provenance["status"] == "incomplete"
    assert provenance["incomplete_reason"] == summary.incomplete_reason


def test_ollama_failing_after_the_run_makes_it_incomplete(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    checks = []

    def check_models(models: list[str], base_url: str) -> dict[str, str]:
        checks.append(models)
        if len(checks) == 2:
            raise OllamaCheckError("Ollama is not reachable at http://localhost:11434")
        return dict.fromkeys(models, "sha256:fixture")

    monkeypatch.setattr(run_module, "check_models", check_models)

    summary = run(workspace)

    assert summary.status == "incomplete"
    assert summary.incomplete_reason == (
        "the check after the run failed: Ollama is not reachable at http://localhost:11434"
    )
    assert summary.results_path is None


def test_an_unreachable_model_before_the_run_stops_it_without_saving_anything(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    def check_models(models: list[str], base_url: str) -> dict[str, str]:
        raise OllamaCheckError("Ollama model 'qwen2.5-coder:7b' is not pulled")

    monkeypatch.setattr(run_module, "check_models", check_models)

    with pytest.raises(OllamaCheckError, match="not pulled"):
        run(workspace)

    assert not (workspace / "data" / "outputs").exists()


def test_the_run_refuses_to_touch_the_library(
    workspace: Path, ollama: list[list[str]], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("REPOSITORY_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/unused")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="needs REPOSITORY_BACKEND=memory"):
        run(workspace)

    assert ollama == []


def test_page_text_from_another_pdf_than_the_gold_file_stops_the_run(
    workspace: Path, ollama: list[list[str]]
):
    page_file = workspace / "data" / "pages" / "WA1.json"
    data = read(page_file)
    data["pdf_sha256"] = "0" * 64
    page_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="page text of WA1 is from another PDF"):
        run(workspace)
