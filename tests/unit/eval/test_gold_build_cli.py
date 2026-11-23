from pathlib import Path

import pytest

from eval.gold_build import __main__ as cli
from eval.gold_build.__main__ import build_parser, main
from src.llm.settings import get_settings
from tests.unit.eval.conftest import AddTopic


def set_data_dir(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv("EVAL_DATA_DIR", str(path))
    get_settings.cache_clear()


def test_every_step_is_a_subcommand_with_its_options():
    parse = build_parser().parse_args

    assert parse(["freeze_search", "--topic", "t1"]).topic == "t1"
    assert parse(["build_pool"]).extend is None
    assert parse(["build_pool", "--extend", "t3"]).extend == "t3"
    assert parse(["label_run", "--model", "claude-opus-5-5"]).model == "claude-opus-5-5"
    args = parse(["select_sets", "--seed", "7", "--needs-extension"])
    assert (args.seed, args.needs_extension) == (7, True)
    assert parse(["select_sets"]).seed == 2026
    assert parse(["blind_sample"]).seed == 2026
    args = parse(["extraction_prepare", "--model", "m", "--paper", "W1", "--paper", "W2"])
    assert args.paper == ["W1", "W2"]
    assert parse(["extraction_verify"]).import_sheet is False
    assert parse(["extraction_verify", "--import"]).import_sheet is True
    for step in (
        "label_prepare",
        "label_import",
        "compare",
        "escalation_import",
        "validate",
    ):
        assert parse([step]).handler


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["unknown_step"],
        ["freeze_search"],
        ["label_run"],
        ["extraction_prepare", "--model", "m"],
    ],
)
def test_a_missing_step_or_required_option_is_a_usage_error(argv: list[str]):
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(argv)

    assert error.value.code == 2


def test_a_failing_step_ends_with_a_one_line_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    set_data_dir(monkeypatch, tmp_path)

    def failing(**kwargs: object) -> int:
        raise ValueError("labels are missing")

    monkeypatch.setattr(cli, "prepare_labeling", failing)

    with pytest.raises(SystemExit, match="error: labels are missing"):
        main(["label_prepare"])


def test_the_steps_that_write_the_data_folder_remind_about_the_sync(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "prepare_labeling", lambda **kwargs: 3)

    assert main(["label_prepare"]) == 0

    assert (
        capsys.readouterr().out
        == "wrote 3 labeling inputs\nNow back up the data folder: make eval-sync\n"
    )


def test_the_extension_report_names_the_topics_that_are_short(
    add_topic: AddTopic,
    gold_dir: Path,
    topics_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    add_topic("ta_mini", ["include"] * 8 + ["exclude"] * 12, prefix="WA")
    add_topic("tb_mini", ["include"] * 7 + ["exclude"] * 13, prefix="WB")
    monkeypatch.setattr(cli, "DEFAULT_GOLD_DIR", gold_dir)
    monkeypatch.setattr(cli, "TOPICS_DIR", topics_dir)

    assert main(["select_sets", "--needs-extension"]) == 0

    assert capsys.readouterr().out == "topics below the minimum of gold includes: tb_mini\n"


def test_validate_prints_the_problems_and_exits_non_zero(
    add_topic: AddTopic,
    gold_dir: Path,
    topics_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    add_topic("ta_mini", ["include"] * 4, prefix="WA")
    (gold_dir / "extraction.json").write_text("[]", encoding="utf-8")
    set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_GOLD_DIR", gold_dir)
    monkeypatch.setattr(cli, "TOPICS_DIR", topics_dir)

    assert main(["validate"]) == 1

    output = capsys.readouterr().out
    assert "error: ta_mini: screening set has 0 papers, expected 20" in output
    assert output.endswith("problems\n")
