"""Fixtures for the gold-build tests: a small labeled gold set built from decision lists."""

import csv
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from eval.harness.gold import SEARCH_SET_SIZE

FIXTURE_TOPICS = Path(__file__).resolve().parents[2] / "fixtures" / "eval" / "topics"
ANSWERS_BY_DECISION = {
    "include": ("yes", "yes"),
    "exclude": ("no", "yes"),
    "uncertain": ("yes", "not_stated"),
}
SEARCH_SIZE_IN_SNAPSHOT = 25
AddTopic = Callable[..., list[str]]


def read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def read_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


@pytest.fixture
def topics_dir(tmp_path: Path) -> Path:
    """A writable copy of the two fixture topics (`ta_mini`, `tb_mini`, two checks each)."""
    shutil.copytree(FIXTURE_TOPICS, tmp_path / "topics")
    return tmp_path / "topics"


@pytest.fixture
def gold_dir(tmp_path: Path) -> Path:
    return tmp_path / "gold"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    return tmp_path / "data"


def raw_paper(key: str, title: str | None = None, **overrides: Any) -> dict[str, Any]:
    """A paper dict as the search node returns it."""
    return {
        "title": title or f"Paper {key}",
        "abstract": f"Abstract of {key}.",
        "year": 2023,
        "authors": ["Alice Example"],
        "doi": f"https://doi.org/10.1000/{key.lower()}",
        "url": f"https://openalex.org/{key}",
        "relevance_score": 0,
        "openalex_id": key,
        "pdf_url": f"https://fixtures.invalid/{key}.pdf",
        "venue": "Journal of Fixture Studies",
        **overrides,
    }


def raw_work(key: str, title: str, year: int = 2023, venue: str | None = "Journal of Tests"):
    """A raw OpenAlex work of the shape `format_openalex_work` reads."""
    return {
        "id": f"https://openalex.org/{key}",
        "doi": f"https://doi.org/10.1000/{key.lower()}",
        "title": title,
        "publication_year": year,
        "abstract_inverted_index": {"Words": [0], "about": [1], title.split()[0]: [2]},
        "authorships": [{"author": {"display_name": "Bob Sample"}}],
        "primary_location": {
            "pdf_url": f"https://fixtures.invalid/{key}.pdf",
            "source": {"display_name": venue} if venue else None,
        },
    }


@pytest.fixture
def add_topic(gold_dir: Path) -> AddTopic:
    """Write search.json, pool.json and screening records for a topic from a decision list.

    Paper i (1-based) is `<prefix><i>`; the first 10 are the search set, the rest were
    `search_extended`. Each decision has the answers in `ANSWERS_BY_DECISION`.
    """

    def add(topic_id: str, decisions: list[str], *, prefix: str, labeled: bool = True) -> list[str]:
        keys = [f"{prefix}{number}" for number in range(1, len(decisions) + 1)]
        papers = [raw_paper(key) for key in keys]
        search = papers[:SEARCH_SIZE_IN_SNAPSHOT]
        write(
            gold_dir / topic_id / "search.json",
            {
                "topic_id": topic_id,
                "retrieved_at": "2026-11-23T10:00:00Z",
                "duration_s": 5.0,
                "search_model": "qwen2.5-coder:7b",
                "search_prompt_version": "v1",
                "synthetic_abstract": f"Synthetic abstract for {topic_id}.",
                "fallback_used": False,
                "openalex_params": {
                    "target_output_count": 25,
                    "min_citations": 0,
                    "start_year": 2020,
                },
                "papers": [{"openalex_id": p["openalex_id"], "title": p["title"]} for p in search],
            },
        )
        write(
            gold_dir / topic_id / "pool.json",
            [
                {
                    **{k: v for k, v in paper.items() if k != "relevance_score"},
                    "paper_key": paper["openalex_id"],
                    "origin": "search" if number <= SEARCH_SET_SIZE else "search_extended",
                    "search_rank": number if number <= SEARCH_SET_SIZE else None,
                    "aliases": [],
                }
                for number, paper in enumerate(papers, start=1)
            ],
        )
        if labeled:
            screening_path = gold_dir / "screening.json"
            existing = read(screening_path) if screening_path.is_file() else []
            write(
                screening_path,
                existing
                + [
                    {
                        "topic_id": topic_id,
                        "paper_key": key,
                        "in_search_set": number <= SEARCH_SET_SIZE,
                        "in_screening_set": False,
                        "answers": {
                            check: {"answer": answer, "source": "model", "reason": f"{key} {check}"}
                            for check, answer in zip(("c1", "c2"), ANSWERS_BY_DECISION[decision])
                        },
                        "decision": decision,
                    }
                    for number, (key, decision) in enumerate(zip(keys, decisions), start=1)
                ],
            )
        return keys

    return add
