import subprocess
from pathlib import Path

import pytest

from eval.harness import sync as sync_module
from eval.harness.data_dir import data_dir, outputs_dir
from eval.harness.sync import sync
from src.llm.settings import get_settings

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Eval Test",
    "GIT_AUTHOR_EMAIL": "eval@example.invalid",
    "GIT_COMMITTER_NAME": "Eval Test",
    "GIT_COMMITTER_EMAIL": "eval@example.invalid",
}


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout


@pytest.fixture(autouse=True)
def git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in GIT_IDENTITY.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def backup(tmp_path: Path) -> tuple[Path, Path]:
    """A bare 'private repository' and a clone of it, as the eval data folder is set up."""
    remote = tmp_path / "remote.git"
    clone = tmp_path / "eval-data"
    git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    git(tmp_path, "clone", str(remote), str(clone))
    git(clone, "checkout", "-B", "main")
    git(clone, "config", "push.autoSetupRemote", "true")
    return remote, clone


def set_data_dir(monkeypatch: pytest.MonkeyPatch, value: Path | None) -> None:
    if value is None:
        monkeypatch.delenv("EVAL_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("EVAL_DATA_DIR", str(value))
    get_settings.cache_clear()


def test_data_dir_reads_the_setting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    set_data_dir(monkeypatch, tmp_path)

    assert data_dir() == tmp_path


def test_a_missing_setting_names_what_to_do(monkeypatch: pytest.MonkeyPatch):
    set_data_dir(monkeypatch, None)

    with pytest.raises(RuntimeError) as error:
        data_dir()

    assert str(error.value) == (
        "EVAL_DATA_DIR is not set; point it at the local eval data folder "
        "(a clone of the private backup repository)"
    )


def test_a_setting_that_is_not_a_folder_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    missing = tmp_path / "nowhere"
    set_data_dir(monkeypatch, missing)

    with pytest.raises(RuntimeError, match=f"EVAL_DATA_DIR {missing} is not a folder"):
        data_dir()


def test_the_outputs_of_a_run_live_under_outputs_and_its_id(tmp_path: Path):
    assert outputs_dir(tmp_path, "r1") == tmp_path / "outputs" / "r1"


def test_sync_commits_everything_and_pushes_it_to_the_backup(backup: tuple[Path, Path]):
    remote, clone = backup
    (clone / "outputs" / "r1").mkdir(parents=True)
    (clone / "outputs" / "r1" / "screening_1.json").write_text("[]", encoding="utf-8")

    committed = sync(clone)

    assert committed is True
    assert git(remote, "log", "--format=%s", "main").startswith("sync 20")
    assert "outputs/r1/screening_1.json" in git(remote, "ls-tree", "-r", "--name-only", "main")


def test_sync_with_nothing_new_makes_no_commit_but_still_pushes(backup: tuple[Path, Path]):
    remote, clone = backup
    (clone / "a.txt").write_text("a", encoding="utf-8")
    sync(clone)
    (clone / "b.txt").write_text("b", encoding="utf-8")
    git(clone, "add", "-A")
    git(clone, "commit", "-m", "committed by hand, not yet pushed")

    committed = sync(clone)

    assert committed is False
    assert git(remote, "log", "--format=%s", "main").splitlines()[0] == (
        "committed by hand, not yet pushed"
    )


def test_a_failing_git_command_raises_with_gits_message(tmp_path: Path):
    with pytest.raises(RuntimeError, match=r"git add -A failed: .*not a git repository"):
        sync(tmp_path)


def test_the_command_prints_the_git_error_and_exits_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    set_data_dir(monkeypatch, tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        sync_module.main()

    assert str(exit_info.value).startswith("error: git add -A failed:")
