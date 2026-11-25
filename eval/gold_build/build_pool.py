"""Step `build_pool`: the candidate pool per topic, and `--extend` for topics short of includes."""

import re
import subprocess
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from eval.gold_build.files import (
    dump_models,
    load_topics,
    read_json,
    read_provenance,
    update_provenance,
    write_json,
)
from eval.gold_build.openalex import fetch_work, openalex_client
from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    PoolPaper,
    SearchSnapshot,
    load_pool,
    load_search_snapshot,
)
from eval.harness.text import normalize_title
from eval.harness.topics import TOPICS_DIR, Topic
from src.pipeline.search.agent import format_openalex_work
from src.pipeline.search.api_client import OpenAlexClient

LINK_LIST_TOPIC = "t1_social_media"
LINK_LIST_GIT_REF = "dcc06b0^:Testdatensatz/link.md"
LINK_LIST_FILE = "link_list.json"
LINK_LIST_MANUAL_FILE = "link_list_manual.json"
POOL_FILE = "pool.json"
EXTRA_SEARCH_FILE = "search_extra.json"
EXTEND_LIMIT = 50
DOI_RESOLVER = "https://doi.org/"
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s?#]+")
URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]]+")
PREPRINT_VENUE_MARKERS = ("arxiv", "preprint", "ssrn", "research square")
PAPER_FIELDS = (
    "title",
    "abstract",
    "year",
    "authors",
    "doi",
    "url",
    "openalex_id",
    "pdf_url",
    "venue",
)
WorkFetcher = Callable[[str], dict[str, Any] | None]


class LinkEntry(BaseModel):
    """One URL of the v1 link list and the OpenAlex work it was resolved to."""

    url: str
    openalex_id: str | None
    resolution: Literal["doi", "manual", "unresolved"]


@dataclass
class BuildReport:
    """What `build_pool` did per topic: pool sizes, skipped topics and unresolved links."""

    pool_sizes: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    unresolved_links: list[str] = field(default_factory=list)


def read_link_list_from_git(repo_root: Path, ref: str = LINK_LIST_GIT_REF) -> str:
    """The v1 link list text, from the commit before it was removed."""
    result = subprocess.run(
        ["git", "show", ref], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot read {ref}: {result.stderr.strip()}")
    return result.stdout


def parse_link_list(text: str) -> list[str]:
    """The URLs of the link list in order, each once."""
    return list(dict.fromkeys(URL_PATTERN.findall(text)))


def doi_from_url(url: str) -> str | None:
    """The DOI inside a URL (a doi.org link or a publisher path that contains it), if any."""
    match = DOI_PATTERN.search(url)
    return match.group(0).rstrip(".,;") if match else None


def resolve_link_list(
    urls: list[str], manual: dict[str, str], fetch: WorkFetcher
) -> tuple[list[LinkEntry], list[dict[str, Any]]]:
    """Resolve each URL to an OpenAlex work: a manual entry first, then its DOI; else unresolved."""
    entries: list[LinkEntry] = []
    works: list[dict[str, Any]] = []
    for url in urls:
        doi = doi_from_url(url)
        if url in manual:
            work, resolution = fetch(manual[url]), "manual"
            if work is None:
                raise ValueError(
                    f"{LINK_LIST_MANUAL_FILE}: {manual[url]} for {url} is not in OpenAlex"
                )
        elif doi:
            work, resolution = fetch(f"{DOI_RESOLVER}{doi}"), "doi"
        else:
            work, resolution = None, "unresolved"
        if work is None:
            entries.append(LinkEntry(url=url, openalex_id=None, resolution="unresolved"))
            continue
        works.append(work)
        openalex_id = work["id"].removeprefix("https://openalex.org/")
        entries.append(LinkEntry(url=url, openalex_id=openalex_id, resolution=resolution))
    return entries, works


def _pool_paper(paper: dict[str, Any], origin: str, rank: int | None) -> PoolPaper:
    key = paper.get("openalex_id")
    if not key:
        raise ValueError(f"a {origin} paper has no OpenAlex id: {paper.get('title')!r}")
    return PoolPaper(
        paper_key=key,
        origin=origin,
        search_rank=rank,
        **{name: paper.get(name) for name in PAPER_FIELDS},
    )


def is_journal_venue(venue: str | None) -> bool:
    """A venue that is named and is not a preprint server."""
    if not venue:
        return False
    return not any(marker in venue.lower() for marker in PREPRINT_VENUE_MARKERS)


def passes_filters(paper: PoolPaper, topic: Topic) -> bool:
    """Published in the topic's years or later, with an abstract."""
    return bool(paper.year and paper.year >= topic.min_year and paper.abstract.strip())


def deduplicate(papers: list[PoolPaper]) -> list[PoolPaper]:
    """One record per study: the journal version if there is one, else the first seen.

    The dropped records' ids (and their aliases) become aliases of the kept one.
    """
    groups: dict[str, list[PoolPaper]] = defaultdict(list)
    for paper in papers:
        groups[normalize_title(paper.title) or paper.paper_key].append(paper)
    kept: list[PoolPaper] = []
    for group in groups.values():
        keeper = next((p for p in group if is_journal_venue(p.venue)), group[0])
        dropped = [p for p in group if p is not keeper]
        aliases = [*keeper.aliases]
        for paper in dropped:
            aliases += [paper.paper_key, *paper.aliases]
        kept.append(keeper.model_copy(update={"aliases": aliases}))
    return kept


def build_topic_pool(
    topic: Topic, snapshot: SearchSnapshot, link_papers: list[dict[str, Any]]
) -> list[PoolPaper]:
    """The topic's pool: the search output and the link list, filtered outside the search set."""
    candidates = [_pool_paper(p, "search", rank) for rank, p in enumerate(snapshot.papers, start=1)]
    candidates += [_pool_paper(p, "link_list", None) for p in link_papers]
    wanted = [
        paper
        for paper in candidates
        if (paper.search_rank and paper.search_rank <= SEARCH_SET_SIZE)
        or passes_filters(paper, topic)
    ]
    return deduplicate(wanted)


def build_pool(
    *,
    link_md: str,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    link_topic: str = LINK_LIST_TOPIC,
    fetch: WorkFetcher = fetch_work,
    client: OpenAlexClient | None = None,
) -> BuildReport:
    """Write `pool.json` for every topic that has none yet; the link list goes to one topic."""
    client = client or openalex_client()
    report = BuildReport()
    for topic_id, topic in load_topics(topics_dir).items():
        if (gold_dir / topic_id / POOL_FILE).exists():
            report.skipped.append(topic_id)
            continue
        snapshot = load_search_snapshot(gold_dir, topic_id)
        link_papers: list[dict[str, Any]] = []
        if topic_id == link_topic:
            manual_path = gold_dir / topic_id / LINK_LIST_MANUAL_FILE
            manual = read_json(manual_path) if manual_path.is_file() else {}
            entries, works = resolve_link_list(parse_link_list(link_md), manual, fetch)
            write_json(gold_dir / topic_id / LINK_LIST_FILE, dump_models(entries, LinkEntry))
            link_papers = [format_openalex_work(work, client) for work in works]
            report.unresolved_links += [e.url for e in entries if e.resolution == "unresolved"]
        pool = build_topic_pool(topic, snapshot, link_papers)
        write_json(gold_dir / topic_id / POOL_FILE, dump_models(pool, PoolPaper))
        report.pool_sizes[topic_id] = len(pool)
    return report


def _append_search_extended(
    topic_id: str,
    works: list[dict[str, Any]],
    *,
    gold_dir: Path,
    topics_dir: Path,
    client: OpenAlexClient,
) -> list[PoolPaper]:
    """Add the new, filtered works to the topic's pool as `search_extended`; return them."""
    topic = load_topics(topics_dir)[topic_id]
    pool = load_pool(gold_dir, topic_id)
    known_ids = {paper.paper_key for paper in pool} | {a for p in pool for a in p.aliases}
    known_titles = {normalize_title(paper.title): paper for paper in pool}
    fresh = [
        _pool_paper(format_openalex_work(work, client), "search_extended", None) for work in works
    ]
    new_papers = [p for p in fresh if p.paper_key not in known_ids and passes_filters(p, topic)]
    added: list[PoolPaper] = []
    for paper in deduplicate(new_papers):
        twin = known_titles.get(normalize_title(paper.title))
        if twin is None:
            added.append(paper)
        else:
            twin.aliases += [paper.paper_key, *paper.aliases]
    write_json(gold_dir / topic_id / POOL_FILE, dump_models([*pool, *added], PoolPaper))
    return added


def extend_pool(
    topic_id: str,
    *,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    client: OpenAlexClient | None = None,
) -> list[PoolPaper]:
    """Append the next results of the frozen query as `search_extended`; return the new papers."""
    client = client or openalex_client()
    snapshot = load_search_snapshot(gold_dir, topic_id)
    params = snapshot.openalex_params
    works = client.execute_retrieval(
        synthetic_abstract=snapshot.synthetic_abstract,
        limit=EXTEND_LIMIT,
        min_citations=params["min_citations"],
        start_year=params["start_year"],
    )
    return _append_search_extended(
        topic_id, works, gold_dir=gold_dir, topics_dir=topics_dir, client=client
    )


def extend_pool_with_query(
    topic_id: str,
    synthetic_abstract: str,
    *,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    client: OpenAlexClient | None = None,
) -> list[PoolPaper]:
    """Freeze a second, hand-written query as `search_extra.json`, add its papers, record it.

    Used when the baseline query is exhausted: OpenAlex's semantic search returns at most 50
    results, and too few pass the filters. The baseline search and its top-10 stay untouched.
    """
    path = gold_dir / topic_id / EXTRA_SEARCH_FILE
    if path.exists():
        raise ValueError(f"{path} already exists; a frozen query is never overwritten")
    if not synthetic_abstract.strip():
        raise ValueError("the second query's abstract is empty")
    client = client or openalex_client()
    params = load_search_snapshot(gold_dir, topic_id).openalex_params
    works = client.execute_retrieval(
        synthetic_abstract=synthetic_abstract,
        limit=EXTEND_LIMIT,
        min_citations=params["min_citations"],
        start_year=params["start_year"],
    )
    added = _append_search_extended(
        topic_id, works, gold_dir=gold_dir, topics_dir=topics_dir, client=client
    )
    retrieved_at = f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"
    write_json(
        path,
        {
            "topic_id": topic_id,
            "retrieved_at": retrieved_at,
            "written_by": "hand",
            "synthetic_abstract": synthetic_abstract,
            "openalex_params": params,
            "raw_results": len(works),
            "added_keys": [paper.paper_key for paper in added],
        },
    )
    extra_queries = read_provenance(gold_dir).get("extra_queries", {})
    extra_queries[topic_id] = {
        "file": f"{topic_id}/{EXTRA_SEARCH_FILE}",
        "retrieved_at": retrieved_at,
        "papers_added": len(added),
    }
    update_provenance(gold_dir, {"extra_queries": extra_queries})
    return added
