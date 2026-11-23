import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from eval.gold_build import claude_cli, label_run
from eval.gold_build.claude_cli import ClaudeError, claude_version, run_claude
from eval.gold_build.label_import import import_labels
from eval.gold_build.label_prepare import inputs_dir, prepare_labeling
from eval.gold_build.label_run import answer_path, run_labeling
from eval.harness.gold import load_screening_gold
from eval.harness.topics import labeling_json_schema, load_topic, render_labeling_prompt
from tests.unit.eval.conftest import read, write

MODEL = "claude-opus-5-5"
SCHEMA = {"type": "object"}


def completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def claude_output(**overrides: Any) -> dict[str, Any]:
    return {
        "is_error": False,
        "result": "{}",
        "structured_output": {"answers": []},
        "modelUsage": {MODEL: {"inputTokens": 1}},
        **overrides,
    }


@pytest.fixture
def called(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Make `claude -p` succeed with a valid output and record how it was started."""
    calls: list[dict[str, Any]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        calls.append({"command": command, **kwargs})
        return completed(json.dumps(claude_output()))

    monkeypatch.setattr(claude_cli.subprocess, "run", run)
    return calls


# --- the headless call ---------------------------------------------------------------------


def test_a_headless_call_passes_the_pinned_model_no_tools_and_the_paper_on_stdin(
    called: list[dict[str, Any]], tmp_path: Path
):
    output = run_claude(
        model=MODEL, system_prompt="Label it.", schema=SCHEMA, text="Title: T", cwd=tmp_path
    )

    assert output["structured_output"] == {"answers": []}
    (call,) = called
    assert call["command"] == [
        "claude",
        "-p",
        "--model",
        MODEL,
        "--tools",
        "",
        "--system-prompt",
        "Label it.",
        "--json-schema",
        '{"type": "object"}',
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    assert call["input"] == "Title: T"
    assert call["cwd"] == tmp_path


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (completed("", returncode=1, stderr="not logged in"), "exited with 1: not logged in"),
        (completed("not json"), "did not print JSON"),
        (completed(json.dumps(claude_output(is_error=True, result="overloaded"))), "overloaded"),
        (
            completed(json.dumps(claude_output(modelUsage={"claude-haiku-5-5": {}}))),
            r"were \['claude-haiku-5-5'\], the pinned model is 'claude-opus-5-5'",
        ),
        (
            completed(json.dumps(claude_output(modelUsage={MODEL: {}, "claude-haiku-5-5": {}}))),
            "models that answered were",
        ),
        (completed(json.dumps(claude_output(modelUsage={}))), "models that answered were"),
        (completed(json.dumps(claude_output(structured_output=None))), "no structured output"),
    ],
)
def test_a_failed_call_or_the_wrong_model_stops_with_a_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: subprocess.CompletedProcess,
    message: str,
):
    monkeypatch.setattr(claude_cli.subprocess, "run", lambda command, **kwargs: result)

    with pytest.raises(ClaudeError, match=message):
        run_claude(model=MODEL, system_prompt="p", schema=SCHEMA, text="t", cwd=tmp_path)


def test_a_call_that_takes_too_long_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(claude_cli.subprocess, "run", run)

    with pytest.raises(ClaudeError, match="did not answer within 600 s"):
        run_claude(model=MODEL, system_prompt="p", schema=SCHEMA, text="t", cwd=tmp_path)


def test_the_claude_code_version_is_read_from_the_cli(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        claude_cli.subprocess, "run", lambda command, **kwargs: completed("2.1.322 (Claude Code)\n")
    )

    assert claude_version() == "2.1.322 (Claude Code)"


# --- prepare -------------------------------------------------------------------------------


@pytest.fixture
def pools(add_topic) -> None:
    add_topic("ta_mini", ["include"] * 12, prefix="WA", labeled=False)
    add_topic("tb_mini", ["include"] * 12, prefix="WB", labeled=False)


def test_prepare_writes_title_and_abstract_only_plus_the_prompt_and_schema_per_topic(
    pools: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    count = prepare_labeling(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    folder = inputs_dir(data_root, "ta_mini")
    topic = load_topic("ta_mini", topics_dir)
    assert count == 24
    assert (folder / "WA1.txt").read_text(
        "utf-8"
    ) == "Title: Paper WA1\n\nAbstract: Abstract of WA1.\n"
    assert len(list(folder.glob("*.txt"))) == 12
    assert (folder / "prompt.md").read_text("utf-8") == render_labeling_prompt(topic) + "\n"
    assert read(folder / "schema.json") == labeling_json_schema(topic)


def test_prepare_commits_one_prompt_file_that_holds_every_topics_prompt(
    pools: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    prepare_labeling(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    text = (gold_dir / "labeling_prompt.md").read_text("utf-8")
    for topic_id in ("ta_mini", "tb_mini"):
        assert (
            f"## {topic_id}\n\n{render_labeling_prompt(load_topic(topic_id, topics_dir))}" in text
        )


# --- run -----------------------------------------------------------------------------------


def labeling_output(topic_id: str, answers: dict[str, str]) -> dict[str, Any]:
    return claude_output(
        structured_output={
            "answers": [
                {"check": check, "answer": answer, "reason": f"{topic_id} {check}"}
                for check, answer in answers.items()
            ]
        }
    )


@pytest.fixture
def prepared(pools: None, gold_dir: Path, data_root: Path, topics_dir: Path) -> None:
    prepare_labeling(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)


@pytest.fixture
def recording_runner() -> list[dict[str, Any]]:
    return []


def make_runner(calls: list[dict[str, Any]], answers: dict[str, str] | None = None):
    def runner(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return labeling_output("t", answers or {"c1": "yes", "c2": "yes"})

    return runner


def test_every_input_is_labeled_in_its_own_folder_with_its_topics_prompt_and_schema(
    prepared: None,
    gold_dir: Path,
    data_root: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_runner: list[dict[str, Any]],
):
    monkeypatch.setattr(label_run.claude_cli, "claude_version", lambda: "2.1.322 (Claude Code)")

    count = run_labeling(
        MODEL,
        data_root=data_root,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        runner=make_runner(recording_runner),
    )

    assert count == 24
    first = recording_runner[0]
    folder = inputs_dir(data_root, "ta_mini")
    assert first["model"] == MODEL
    assert first["cwd"] == folder
    assert first["text"] == "Title: Paper WA1\n\nAbstract: Abstract of WA1.\n"
    assert first["system_prompt"] == (folder / "prompt.md").read_text("utf-8")
    assert first["schema"] == read(folder / "schema.json")
    assert (data_root / "labeling" / "answers" / "ta_mini" / "WA1.json").is_file()
    assert Path(__file__).resolve().parents[3] not in first["cwd"].parents


def test_papers_with_an_answer_are_not_asked_again(
    prepared: None,
    gold_dir: Path,
    data_root: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_runner: list[dict[str, Any]],
):
    monkeypatch.setattr(label_run.claude_cli, "claude_version", lambda: "v")
    write(answer_path(data_root, "ta_mini", "WA1"), labeling_output("ta_mini", {}))

    count = run_labeling(
        MODEL,
        data_root=data_root,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        runner=make_runner(recording_runner),
    )

    assert count == 23
    assert not any(call["text"].startswith("Title: Paper WA1\n") for call in recording_runner)


def test_the_model_version_and_prompt_hash_go_into_the_provenance(
    prepared: None,
    gold_dir: Path,
    data_root: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_runner: list[dict[str, Any]],
):
    monkeypatch.setattr(label_run.claude_cli, "claude_version", lambda: "2.1.322 (Claude Code)")

    run_labeling(
        MODEL,
        data_root=data_root,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        runner=make_runner(recording_runner),
    )

    provenance = read(gold_dir / "provenance.json")
    assert provenance["labeling_model"] == MODEL
    assert provenance["claude_code_version"] == "2.1.322 (Claude Code)"
    assert (
        provenance["labeling_prompt_sha256"]
        == hashlib.sha256((gold_dir / "labeling_prompt.md").read_bytes()).hexdigest()
    )
    assert provenance["dates"]["labeling"]


def test_labeling_with_another_model_than_the_one_already_used_is_refused(
    prepared: None,
    gold_dir: Path,
    data_root: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_runner: list[dict[str, Any]],
):
    monkeypatch.setattr(label_run.claude_cli, "claude_version", lambda: "v")
    write(gold_dir / "provenance.json", {"labeling_model": "claude-sonnet-5-5"})

    with pytest.raises(ValueError, match="made with 'claude-sonnet-5-5'; keep that model"):
        run_labeling(
            MODEL,
            data_root=data_root,
            gold_dir=gold_dir,
            topics_dir=topics_dir,
            runner=make_runner(recording_runner),
        )

    assert recording_runner == []


def test_labeling_needs_the_prepared_inputs(
    pools: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    with pytest.raises(ValueError, match="run label_prepare first"):
        run_labeling(MODEL, data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)


def test_a_run_that_stops_midway_keeps_its_answers_and_can_continue(
    prepared: None,
    gold_dir: Path,
    data_root: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(label_run.claude_cli, "claude_version", lambda: "v")
    calls: list[dict[str, Any]] = []

    def failing_third(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if len(calls) == 3:
            raise ClaudeError("overloaded")
        return labeling_output("t", {"c1": "yes", "c2": "yes"})

    with pytest.raises(ClaudeError, match="overloaded"):
        run_labeling(
            MODEL,
            data_root=data_root,
            gold_dir=gold_dir,
            topics_dir=topics_dir,
            runner=failing_third,
        )
    resumed: list[dict[str, Any]] = []

    count = run_labeling(
        MODEL,
        data_root=data_root,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        runner=make_runner(resumed),
    )

    assert count == 22


# --- import --------------------------------------------------------------------------------


def label_everything(
    data_root: Path, answers_by_key: dict[str, dict[str, str]], topic_ids: tuple[str, ...]
) -> None:
    for topic_id in topic_ids:
        for path in sorted(inputs_dir(data_root, topic_id).glob("*.txt")):
            answers = answers_by_key.get(path.stem, {"c1": "yes", "c2": "yes"})
            write(answer_path(data_root, topic_id, path.stem), labeling_output(topic_id, answers))


def test_import_writes_model_sourced_records_with_derived_decisions_and_the_search_set(
    prepared: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    label_everything(
        data_root,
        {"WA2": {"c1": "no", "c2": "yes"}, "WA3": {"c1": "yes", "c2": "not_stated"}},
        ("ta_mini", "tb_mini"),
    )

    added = import_labels(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    records = {(r.topic_id, r.paper_key): r for r in load_screening_gold(gold_dir)}
    assert added == 24 and len(records) == 24
    assert records["ta_mini", "WA1"].decision == "include"
    assert records["ta_mini", "WA2"].decision == "exclude"
    assert records["ta_mini", "WA3"].decision == "uncertain"
    assert records["ta_mini", "WA3"].answers["c2"].answer == "not_stated"
    assert records["ta_mini", "WA3"].answers["c2"].reason == "ta_mini c2"
    assert {a.source for r in records.values() for a in r.answers.values()} == {"model"}
    assert records["ta_mini", "WA10"].in_search_set and not records["ta_mini", "WA11"].in_search_set
    assert not any(r.in_screening_set for r in records.values())


def test_a_second_import_adds_only_new_papers_and_never_touches_existing_labels(
    prepared: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    label_everything(data_root, {}, ("ta_mini", "tb_mini"))
    import_labels(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)
    labels = read(gold_dir / "screening.json")
    labels[0]["answers"]["c1"]["source"] = "human"
    labels[0]["in_screening_set"] = True
    write(gold_dir / "screening.json", labels)
    pool = read(gold_dir / "ta_mini" / "pool.json")
    write(
        gold_dir / "ta_mini" / "pool.json",
        [*pool, {**pool[0], "paper_key": "WA99", "openalex_id": "WA99", "title": "New One"}],
    )
    write(
        answer_path(data_root, "ta_mini", "WA99"),
        labeling_output("ta_mini", {"c1": "no", "c2": "yes"}),
    )

    added = import_labels(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    assert added == 1
    after = read(gold_dir / "screening.json")
    assert after[0] == labels[0]
    assert after[-1]["paper_key"] == "WA99" and after[-1]["decision"] == "exclude"


def test_a_pool_paper_without_an_answer_is_named(
    prepared: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    label_everything(data_root, {}, ("ta_mini", "tb_mini"))
    answer_path(data_root, "tb_mini", "WB5").unlink()

    with pytest.raises(ValueError, match="no labeling answer for WB5.*run label_run"):
        import_labels(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)


def test_answers_that_do_not_cover_the_topics_checks_are_refused(
    prepared: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    label_everything(data_root, {"WA1": {"c1": "yes"}}, ("ta_mini", "tb_mini"))

    with pytest.raises(
        ValueError, match=r"ta_mini WA1: answers cover \['c1'\], the checks are \['c1', 'c2'\]"
    ):
        import_labels(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)
