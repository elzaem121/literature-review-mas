"""Paths in the local eval data folder, which lives outside this repository."""

from pathlib import Path

from src.llm.settings import get_settings


def data_dir() -> Path:
    """The local eval data folder named by `EVAL_DATA_DIR`; fails clearly if it is unusable."""
    path = get_settings().eval_data_dir
    if path is None:
        raise RuntimeError(
            "EVAL_DATA_DIR is not set; point it at the local eval data folder "
            "(a clone of the private backup repository)"
        )
    if not path.is_dir():
        raise RuntimeError(f"EVAL_DATA_DIR {path} is not a folder; clone the private backup there")
    return path


def outputs_dir(root: Path, run_id: str) -> Path:
    """The folder that holds the saved records of one run."""
    return root / "outputs" / run_id
