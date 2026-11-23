import asyncio
import inspect
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from eval.gold_build.build_pool import (
    build_pool,
    deduplicate,
    doi_from_url,
    extend_pool,
    is_journal_venue,
    parse_link_list,
    read_link_list_from_git,
    resolve_link_list,
)
from eval.gold_build.freeze_search import freeze_search
from eval.harness.adapters.phase1 import SEARCH_MIN_CITATIONS, SEARCH_TARGET_OUTPUT_COUNT
from eval.harness.gold import (
    PoolPaper,
    load_pool,
    load_search_snapshot,
    resolve_search_set,
)
from src.llm.fake import get_fake_answers, set_fake_answers
from src.pipeline.search.api_client import OpenAlexClient
from src.pipeline.search.new_main import main as search_main
from src.pipeline.search.schemas import AcademicQueryExpansionSchema
from tests.unit.eval.conftest import raw_paper, raw_work, read, write


def pool_paper(key: str, title: str, **overrides: Any) -> PoolPaper:
    return PoolPaper(
        **{
            **raw_paper(key, title),
            "paper_key": key,
            "origin": "search",
            "search_rank": None,
            "aliases": [],
            **overrides,
        }
    )


# --- freeze_search -------------------------------------------------------------------------


def test_the_min_citations_the_snapshot_records_is_the_one_the_search_node_uses():
    default = inspect.signature(search_main).parameters["min_citations"].default

    assert SEARCH_MIN_CITATIONS == default


def test_freeze_search_stores_the_papers_the_query_and_how_they_were_made(
    fake_surface, gold_dir: Path, topics_dir: Path
):
    path = asyncio.run(freeze_search("ta_mini", gold_dir=gold_dir, topics_dir=topics_dir))

    assert path == gold_dir / "ta_mini" / "search.json"
    snapshot = load_search_snapshot(gold_dir, "ta_mini")
    assert snapshot.topic_id == "ta_mini"
    assert snapshot.fallback_used is False
    assert snapshot.synthetic_abstract.startswith("Social media use among adolescents")
    assert snapshot.search_model == "qwen2.5-coder:7b"
    assert snapshot.search_prompt_version == "v1"
    assert snapshot.openalex_params == {
        "target_output_count": SEARCH_TARGET_OUTPUT_COUNT,
        "min_citations": 0,
        "start_year": 2020,
    }
    assert [p["openalex_id"] for p in snapshot.papers][:2] == ["W9000000001", "W9000000002"]
    assert len(snapshot.papers) == 5
    assert snapshot.retrieved_at.endswith("Z")
    assert snapshot.duration_s >= 0


def test_freeze_search_refuses_a_run_that_fell_back_and_writes_nothing(
    fake_surface, gold_dir: Path, topics_dir: Path
):
    def failing(messages: Any) -> Any:
        raise RuntimeError("model down")

    set_fake_answers({**get_fake_answers(), AcademicQueryExpansionSchema: failing})

    with pytest.raises(ValueError, match="fell back to the raw question.*run the step again"):
        asyncio.run(freeze_search("ta_mini", gold_dir=gold_dir, topics_dir=topics_dir))

    assert not (gold_dir / "ta_mini" / "search.json").exists()


def test_freeze_search_never_overwrites_a_frozen_snapshot(
    fake_surface, gold_dir: Path, topics_dir: Path
):
    asyncio.run(freeze_search("ta_mini", gold_dir=gold_dir, topics_dir=topics_dir))
    before = (gold_dir / "ta_mini" / "search.json").read_text("utf-8")

    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(freeze_search("ta_mini", gold_dir=gold_dir, topics_dir=topics_dir))

    assert (gold_dir / "ta_mini" / "search.json").read_text("utf-8") == before


# --- link list -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "doi"),
    [
        ("https://doi.org/10.1177/13591045221092884", "10.1177/13591045221092884"),
        (
            "https://link.springer.com/article/10.1007/s40894-024-00251-1",
            "10.1007/s40894-024-00251-1",
        ),
        (
            "https://link.springer.com/chapter/10.1007/978-981-96-3412-5_17",
            "10.1007/978-981-96-3412-5_17",
        ),
        ("https://doi.org/10.3389/fpsyg.2025.1561581?utm=x", "10.3389/fpsyg.2025.1561581"),
        ("https://www.nature.com/articles/s41599-024-03984-5", None),
        ("https://www.paradigmpress.org/SSSH/article/view/879/754", None),
    ],
)
def test_the_doi_is_read_from_a_doi_link_or_a_publisher_path_that_contains_it(
    url: str, doi: str | None
):
    assert doi_from_url(url) == doi


def test_the_link_list_is_read_as_each_url_once_in_order():
    text = " https://doi.org/10.1/a \n\n https://example.org/b\nhttps://doi.org/10.1/a\n"

    assert parse_link_list(text) == ["https://doi.org/10.1/a", "https://example.org/b"]


def test_a_link_resolves_by_manual_entry_first_then_by_doi_else_it_stays_unresolved():
    asked: list[str] = []
    works = {
        "https://doi.org/10.1000/w1": raw_work("W1", "First Study"),
        "W7": raw_work("W7", "Manual Study"),
        "https://doi.org/10.1000/w3": raw_work("W3", "Overridden Study"),
        "W9": raw_work("W9", "Override Wins"),
    }

    def fetch(reference: str):
        asked.append(reference)
        return works.get(reference)

    urls = [
        "https://doi.org/10.1000/w1",
        "https://www.nature.com/articles/s1",
        "https://doi.org/10.1000/unknown",
        "https://doi.org/10.1000/w3",
        "https://example.org/none",
    ]
    manual = {"https://www.nature.com/articles/s1": "W7", "https://doi.org/10.1000/w3": "W9"}

    entries, found = resolve_link_list(urls, manual, fetch)

    assert [(e.openalex_id, e.resolution) for e in entries] == [
        ("W1", "doi"),
        ("W7", "manual"),
        (None, "unresolved"),
        ("W9", "manual"),
        (None, "unresolved"),
    ]
    assert [work["id"][-2:] for work in found] == ["W1", "W7", "W9"]
    assert "https://doi.org/10.1000/w3" not in asked


def test_a_manual_entry_that_openalex_does_not_know_is_an_error():
    with pytest.raises(ValueError, match="W404 for https://example.org/x is not in OpenAlex"):
        resolve_link_list(
            ["https://example.org/x"], {"https://example.org/x": "W404"}, lambda ref: None
        )


def test_the_link_list_is_read_from_a_git_commit(tmp_path: Path):
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    (tmp_path / "link.md").write_text("https://doi.org/10.1/a\n", encoding="utf-8")
    for command in (["init", "-q"], ["add", "link.md"], ["commit", "-q", "-m", "list"]):
        subprocess.run(["git", *command], cwd=tmp_path, check=True, env={**os.environ, **env})

    assert read_link_list_from_git(tmp_path, "HEAD:link.md") == "https://doi.org/10.1/a\n"
    with pytest.raises(RuntimeError, match="cannot read HEAD:missing.md"):
        read_link_list_from_git(tmp_path, "HEAD:missing.md")


# --- duplicates ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("venue", "journal"),
    [
        ("Journal of Tests", True),
        ("arXiv (Cornell University)", False),
        ("SSRN Electronic Journal", False),
        ("", False),
        (None, False),
    ],
)
def test_a_journal_venue_is_named_and_not_a_preprint_server(venue: str | None, journal: bool):
    assert is_journal_venue(venue) is journal


def test_a_duplicate_keeps_the_journal_version_and_records_the_other_id_as_an_alias():
    preprint = pool_paper("W1", "The Same Study", venue="arXiv (Cornell University)")
    journal = pool_paper("W2", "the same study!", venue="Journal of Tests")
    other = pool_paper("W3", "A Different Study")

    kept = deduplicate([preprint, other, journal])

    assert [(p.paper_key, p.aliases) for p in kept] == [("W2", ["W1"]), ("W3", [])]


def test_without_a_journal_version_the_first_seen_record_is_kept_with_all_aliases():
    first = pool_paper("W1", "Same Title", venue=None)
    second = pool_paper("W2", "Same, Title", venue="arXiv", aliases=["W20"])
    third = pool_paper("W3", "SAME TITLE", venue=None)

    (kept,) = deduplicate([first, second, third])

    assert kept.paper_key == "W1"
    assert kept.aliases == ["W2", "W20", "W3"]


# --- build_pool ----------------------------------------------------------------------------


def write_snapshot(gold_dir: Path, topic_id: str, papers: list[dict[str, Any]]) -> None:
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
            "openalex_params": {"target_output_count": 25, "min_citations": 0, "start_year": 2020},
            "papers": papers,
        },
    )


@pytest.fixture
def snapshots(gold_dir: Path) -> None:
    """ta_mini: 12 search results with a pre-2020 paper and one without abstract in and out of
    the first ten, and a preprint at rank 3. tb_mini: three plain results."""
    papers = [raw_paper(f"WA{rank}", f"Search Study {rank}") for rank in range(1, 13)]
    papers[2] = raw_paper("WA3", "Shared Study", venue="arXiv (Cornell University)")
    papers[4] = raw_paper("WA5", "Old but in the search set", year=2018, abstract="")
    papers[10] = raw_paper("WA11", "Old and outside", year=2018)
    papers[11] = raw_paper("WA12", "No abstract outside", abstract="")
    write_snapshot(gold_dir, "ta_mini", papers)
    write_snapshot(gold_dir, "tb_mini", [raw_paper(f"WB{rank}") for rank in range(1, 4)])


LINK_MD = """
 https://doi.org/10.1000/wl1
 https://doi.org/10.1000/wl2
 https://example.org/unknown
 https://doi.org/10.1000/wl3
"""
LINK_WORKS = {
    "https://doi.org/10.1000/wl1": raw_work("WL1", "Shared Study", venue="Journal of Tests"),
    "https://doi.org/10.1000/wl2": raw_work("WL2", "Link List Study"),
    "https://doi.org/10.1000/wl3": raw_work("WL3", "Link List Too Old", year=2019),
}


def test_the_pool_holds_the_search_output_and_the_link_list_filtered_outside_the_search_set(
    gold_dir: Path, topics_dir: Path, snapshots: None
):
    report = build_pool(
        link_md=LINK_MD,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        link_topic="ta_mini",
        fetch=LINK_WORKS.get,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    pool = {paper.paper_key: paper for paper in load_pool(gold_dir, "ta_mini")}
    assert report.pool_sizes == {"ta_mini": 11, "tb_mini": 3}
    assert report.unresolved_links == ["https://example.org/unknown"]
    # WA11 (old) and WA12 (no abstract) are outside the search set and dropped, and so is WL3
    # (too old). WA5 is in the search set and stays although it is old and has no abstract. WA3
    # and WL1 are one study, kept once as WL1 at the place where the study was first seen.
    assert list(pool) == [
        "WA1", "WA2", "WL1", "WA4", "WA5", "WA6", "WA7", "WA8", "WA9", "WA10", "WL2",
    ]  # fmt: skip
    assert pool["WA5"].year == 2018 and pool["WA5"].abstract == ""
    assert pool["WL2"].origin == "link_list" and pool["WL2"].search_rank is None


def test_a_study_found_twice_keeps_the_journal_version_and_the_search_rank_resolves_to_it(
    gold_dir: Path, topics_dir: Path, snapshots: None
):
    build_pool(
        link_md=LINK_MD,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        link_topic="ta_mini",
        fetch=LINK_WORKS.get,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    pool = load_pool(gold_dir, "ta_mini")
    shared = next(paper for paper in pool if paper.title == "Shared Study")
    assert shared.paper_key == "WL1"
    assert shared.origin == "link_list"
    assert shared.aliases == ["WA3"]
    assert resolve_search_set(load_search_snapshot(gold_dir, "ta_mini"), pool, 10)[2] == "WL1"


def test_the_link_list_is_written_with_its_resolution_and_only_for_its_topic(
    gold_dir: Path, topics_dir: Path, snapshots: None
):
    build_pool(
        link_md=LINK_MD,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        link_topic="ta_mini",
        fetch=LINK_WORKS.get,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    assert read(gold_dir / "ta_mini" / "link_list.json") == [
        {"url": "https://doi.org/10.1000/wl1", "openalex_id": "WL1", "resolution": "doi"},
        {"url": "https://doi.org/10.1000/wl2", "openalex_id": "WL2", "resolution": "doi"},
        {"url": "https://example.org/unknown", "openalex_id": None, "resolution": "unresolved"},
        {"url": "https://doi.org/10.1000/wl3", "openalex_id": "WL3", "resolution": "doi"},
    ]
    assert not (gold_dir / "tb_mini" / "link_list.json").exists()


def test_a_manual_link_list_entry_is_used(gold_dir: Path, topics_dir: Path, snapshots: None):
    write(gold_dir / "ta_mini" / "link_list_manual.json", {"https://example.org/unknown": "WM1"})
    works = {**LINK_WORKS, "WM1": raw_work("WM1", "Hand Resolved Study")}

    build_pool(
        link_md=LINK_MD,
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        link_topic="ta_mini",
        fetch=works.get,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    assert "WM1" in {paper.paper_key for paper in load_pool(gold_dir, "ta_mini")}


def test_an_existing_pool_is_left_alone(gold_dir: Path, topics_dir: Path, snapshots: None):
    write(gold_dir / "tb_mini" / "pool.json", [])

    report = build_pool(
        link_md="",
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        link_topic="none",
        fetch=lambda ref: None,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    assert report.skipped == ["tb_mini"]
    assert read(gold_dir / "tb_mini" / "pool.json") == []
    assert report.pool_sizes == {"ta_mini": 10}


def test_a_topic_without_a_frozen_search_stops_the_build(gold_dir: Path, topics_dir: Path):
    with pytest.raises(FileNotFoundError, match="search.json"):
        build_pool(
            link_md="",
            gold_dir=gold_dir,
            topics_dir=topics_dir,
            link_topic="none",
            fetch=lambda ref: None,
            client=OpenAlexClient(email="tests@example.invalid"),
        )


# --- extend --------------------------------------------------------------------------------


def test_extend_adds_new_results_of_the_frozen_query_as_search_extended(
    gold_dir: Path, topics_dir: Path, add_topic, monkeypatch: pytest.MonkeyPatch
):
    add_topic("ta_mini", ["include"] * 12, prefix="WA", labeled=False)
    calls: list[dict[str, Any]] = []
    results = [
        raw_work("WA3", "Paper WA3"),
        raw_work("WX1", "Fresh One"),
        raw_work("WX2", "Fresh Two", year=2019),
        raw_work("WX3", "Fresh Three"),
        raw_work("WX4", "paper wa4"),
        raw_work("WX5", "Fresh One", venue="arXiv"),
    ]
    results[3]["abstract_inverted_index"] = {}

    def retrieval(
        self: Any, synthetic_abstract: str, limit: int, min_citations: int, start_year: int
    ):
        calls.append(
            {
                "abstract": synthetic_abstract,
                "limit": limit,
                "citations": min_citations,
                "year": start_year,
            }
        )
        return results

    monkeypatch.setattr(OpenAlexClient, "execute_retrieval", retrieval)

    added = extend_pool(
        "ta_mini",
        gold_dir=gold_dir,
        topics_dir=topics_dir,
        client=OpenAlexClient(email="tests@example.invalid"),
    )

    assert calls == [
        {"abstract": "Synthetic abstract for ta_mini.", "limit": 50, "citations": 0, "year": 2020}
    ]
    # WA3 is known, WX2 is too old, WX3 has no abstract, WX5 duplicates WX1, WX4 duplicates WA4.
    assert [(p.paper_key, p.origin, p.search_rank) for p in added] == [
        ("WX1", "search_extended", None)
    ]
    pool = {p.paper_key: p for p in load_pool(gold_dir, "ta_mini")}
    assert len(pool) == 13
    assert pool["WX1"].aliases == ["WX5"]
    assert pool["WA4"].aliases == ["WX4"]
