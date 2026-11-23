"""Gold set files: loading, the search-set lookup and validation. Never imports `src`."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from eval.harness.records import CheckAnswer, GoldDecision, LabelSource, ScoredField
from eval.harness.text import normalize_title, quote_on_page
from eval.harness.topics import TOPICS_DIR, Topic, derive_decision, load_topic

DEFAULT_GOLD_DIR = Path(__file__).resolve().parents[1] / "gold" / "v0"
SEARCH_SET_SIZE = 10
SCREENING_SET_SIZE = 20
MIN_INCLUDES = 8
MAX_INCLUDES = 12
MAX_UNCERTAIN = 4


class AnswerGold(BaseModel):
    """The gold answer to one check, with who gave it and why."""

    answer: CheckAnswer
    source: LabelSource
    reason: str


class ScreeningGold(BaseModel):
    """The gold labels of one pool paper; `decision` is derived from `answers`, never edited."""

    topic_id: str
    paper_key: str
    in_search_set: bool
    in_screening_set: bool
    answers: dict[str, AnswerGold]
    decision: GoldDecision


class ExtractionFieldGold(BaseModel):
    """A field the paper reports, with its value, the 1-based page and a one-sentence quote."""

    field: ScoredField
    value: str = Field(min_length=1)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    source: LabelSource


class ExtractionGold(BaseModel):
    """The extraction gold of one paper, tied to one PDF by its hash."""

    paper_key: str
    topic_id: str
    pdf_url: str
    pdf_sha256: str
    fields: list[ExtractionFieldGold]


class PoolPaper(BaseModel):
    """A paper considered for the gold set, with the metadata the screener sees."""

    paper_key: str
    title: str
    abstract: str
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    openalex_id: str | None = None
    pdf_url: str | None = None
    venue: str | None = None
    origin: Literal["search", "search_extended", "link_list"]
    search_rank: int | None = None
    aliases: list[str] = Field(default_factory=list)


class SearchSnapshot(BaseModel):
    """The frozen output of one baseline search run; `papers` are in rank order."""

    topic_id: str
    retrieved_at: str
    duration_s: float
    search_model: str
    search_prompt_version: str
    synthetic_abstract: str
    fallback_used: bool
    openalex_params: dict[str, Any]
    papers: list[dict[str, Any]]


class GoldProvenance(BaseModel):
    """`provenance.json`; here only `mix_exceptions` is read: topic id -> why it misses the mix."""

    model_config = ConfigDict(extra="allow")

    mix_exceptions: dict[str, Annotated[str, Field(min_length=1)]] = Field(default_factory=dict)


class PageText(BaseModel):
    """PyMuPDF text of one PDF; page n (1-based) is `pages[n - 1]`."""

    paper_key: str
    pymupdf_version: str
    pdf_url: str
    pdf_sha256: str
    pages: list[str]


@dataclass(frozen=True)
class GoldLimits:
    """The set sizes and the include/uncertain mix the validator enforces per topic."""

    search_size: int = SEARCH_SET_SIZE
    screening_size: int = SCREENING_SET_SIZE
    min_includes: int = MIN_INCLUDES
    max_includes: int = MAX_INCLUDES
    max_uncertain: int = MAX_UNCERTAIN


def _read_json(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_screening_gold(gold_dir: Path = DEFAULT_GOLD_DIR) -> list[ScreeningGold]:
    """Load `screening.json`."""
    adapter = TypeAdapter(list[ScreeningGold])
    return adapter.validate_json(_read_json(gold_dir / "screening.json"))


def load_extraction_gold(gold_dir: Path = DEFAULT_GOLD_DIR) -> list[ExtractionGold]:
    """Load `extraction.json`."""
    adapter = TypeAdapter(list[ExtractionGold])
    return adapter.validate_json(_read_json(gold_dir / "extraction.json"))


def load_mix_exceptions(gold_dir: Path = DEFAULT_GOLD_DIR) -> dict[str, str]:
    """The reasons `provenance.json` records for topics that miss the mix; {} without the file."""
    path = gold_dir / "provenance.json"
    if not path.is_file():
        return {}
    return GoldProvenance.model_validate_json(_read_json(path)).mix_exceptions


def load_pool(gold_dir: Path, topic_id: str) -> list[PoolPaper]:
    """Load one topic's `pool.json`."""
    adapter = TypeAdapter(list[PoolPaper])
    return adapter.validate_json(_read_json(gold_dir / topic_id / "pool.json"))


def load_search_snapshot(gold_dir: Path, topic_id: str) -> SearchSnapshot:
    """Load one topic's `search.json`."""
    return SearchSnapshot.model_validate_json(_read_json(gold_dir / topic_id / "search.json"))


def load_page_text(data_dir: Path, paper_key: str) -> PageText:
    """Load `<data_dir>/pages/<paper_key>.json`."""
    return PageText.model_validate_json(_read_json(data_dir / "pages" / f"{paper_key}.json"))


def resolve_search_set(
    snapshot: SearchSnapshot, pool: list[PoolPaper], size: int
) -> list[str | None]:
    """The pool key of each of the first `size` search results, None where it is not in the pool.

    A dropped duplicate resolves to the kept record through its alias, so a study that appears
    twice in the top results yields the same key twice.
    """
    key_by_id = {paper.paper_key: paper.paper_key for paper in pool}
    key_by_id.update({alias: paper.paper_key for paper in pool for alias in paper.aliases})
    return [key_by_id.get(paper.get("openalex_id")) for paper in snapshot.papers[:size]]


@dataclass
class GoldReport:
    """What `validate` found: errors make the gold set invalid, warnings are recorded exceptions."""

    errors: list[str] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)

    def extend(self, other: "GoldReport") -> None:
        """Add another report's errors and warnings to this one."""
        self.errors += other.errors
        self.warnings += other.warnings


def validate(
    gold_dir: Path,
    data_dir: Path | None = None,
    *,
    limits: GoldLimits = GoldLimits(),
    topics_dir: Path = TOPICS_DIR,
) -> GoldReport:
    """Check the whole gold set; no errors means it is valid.

    A topic that misses the include/uncertain mix is only a warning when `provenance.json` records
    why in `mix_exceptions`. With `data_dir`, the extraction quotes are also checked against the
    frozen page text.
    """
    report = GoldReport()
    screening = _load_or_report(report.errors, "screening.json", load_screening_gold, gold_dir)
    extraction = _load_or_report(report.errors, "extraction.json", load_extraction_gold, gold_dir)
    exceptions = _load_or_report(report.errors, "provenance.json", load_mix_exceptions, gold_dir)
    if screening is not None:
        report.errors += _check_unique_keys(screening)
        topic_ids = sorted({record.topic_id for record in screening})
        report.errors += [
            f"provenance.json: mix exception for {topic_id}, which has no gold labels"
            for topic_id in sorted(set(exceptions or {}) - set(topic_ids))
        ]
        for topic_id in topic_ids:
            topic_records = [record for record in screening if record.topic_id == topic_id]
            exception = (exceptions or {}).get(topic_id)
            report.extend(
                _validate_topic(topic_id, topic_records, gold_dir, limits, topics_dir, exception)
            )
    if extraction is not None:
        report.errors += _validate_extraction(extraction, screening, data_dir)
    return report


def _load_or_report[**P, T](
    problems: list[str], label: str, loader: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T | None:
    """Call a loader; on a missing or malformed file, record one problem and return None."""
    try:
        return loader(*args, **kwargs)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        problems.append(f"{label}: {details}")
    except (OSError, ValueError) as exc:
        problems.append(f"{label}: {exc}")
    return None


def _check_unique_keys(screening: list[ScreeningGold]) -> list[str]:
    topics_by_key: dict[str, set[str]] = defaultdict(set)
    problems = []
    seen: set[tuple[str, str]] = set()
    for record in screening:
        identity = (record.topic_id, record.paper_key)
        if identity in seen:
            problems.append(f"{record.topic_id}: paper {record.paper_key} is labeled twice")
        seen.add(identity)
        topics_by_key[record.paper_key].add(record.topic_id)
    for key, topic_ids in sorted(topics_by_key.items()):
        if len(topic_ids) > 1:
            problems.append(
                f"paper {key} is in several topics {sorted(topic_ids)}; scoring needs one"
            )
    return problems


def _validate_topic(
    topic_id: str,
    records: list[ScreeningGold],
    gold_dir: Path,
    limits: GoldLimits,
    topics_dir: Path,
    mix_exception: str | None,
) -> GoldReport:
    problems: list[str] = []
    topic = _load_or_report(problems, f"{topic_id} config", load_topic, topic_id, topics_dir)
    pool = _load_or_report(problems, f"{topic_id}/pool.json", load_pool, gold_dir, topic_id)
    snapshot = _load_or_report(
        problems, f"{topic_id}/search.json", load_search_snapshot, gold_dir, topic_id
    )
    if topic is not None:
        problems += _check_answers(topic, records)
    problems += _check_size(topic_id, records, limits)
    if pool is not None:
        problems += _check_pool(topic_id, records, pool)
    if pool is not None and snapshot is not None:
        problems += _check_search_set(topic_id, records, pool, snapshot, limits.search_size)
    report = GoldReport(errors=problems)
    misses = _check_mix(topic_id, records, limits)
    if mix_exception is None:
        report.errors += misses
    else:
        report.warnings += [f"{miss} (recorded exception: {mix_exception})" for miss in misses]
    return report


def _check_answers(topic: Topic, records: list[ScreeningGold]) -> list[str]:
    problems = []
    check_ids = {check.id for check in topic.checks}
    for record in records:
        where = f"{topic.topic_id} {record.paper_key}"
        if set(record.answers) != check_ids:
            problems.append(
                f"{where}: answers cover {sorted(record.answers)}, "
                f"the topic's checks are {sorted(check_ids)}"
            )
            continue
        derived = derive_decision({cid: answer.answer for cid, answer in record.answers.items()})
        if derived != record.decision:
            problems.append(
                f"{where}: decision is '{record.decision}' but answers give '{derived}'"
            )
    return problems


def _check_size(topic_id: str, records: list[ScreeningGold], limits: GoldLimits) -> list[str]:
    in_set = [record for record in records if record.in_screening_set]
    if len(in_set) == limits.screening_size:
        return []
    return [f"{topic_id}: screening set has {len(in_set)} papers, expected {limits.screening_size}"]


def _check_mix(topic_id: str, records: list[ScreeningGold], limits: GoldLimits) -> list[str]:
    """The ways a topic's screening set misses the include and uncertain counts."""
    in_set = [record for record in records if record.in_screening_set]
    counts = {
        decision: sum(record.decision == decision for record in in_set)
        for decision in ("include", "exclude", "uncertain")
    }
    problems = []
    if not limits.min_includes <= counts["include"] <= limits.max_includes:
        problems.append(
            f"{topic_id}: screening set has {counts['include']} gold includes, "
            f"expected {limits.min_includes} to {limits.max_includes}"
        )
    if counts["uncertain"] > limits.max_uncertain:
        problems.append(
            f"{topic_id}: screening set has {counts['uncertain']} gold uncertain papers, "
            f"at most {limits.max_uncertain} allowed"
        )
    return problems


def _check_pool(topic_id: str, records: list[ScreeningGold], pool: list[PoolPaper]) -> list[str]:
    problems = []
    pool_keys = [paper.paper_key for paper in pool]
    labeled = {record.paper_key for record in records}
    problems += [
        f"{topic_id}: pool paper {key} has no gold labels"
        for key in pool_keys
        if key not in labeled
    ]
    problems += [
        f"{topic_id}: gold labels for {key}, which is not in the pool"
        for key in sorted(labeled - set(pool_keys))
    ]
    papers_by_title: dict[str, list[str]] = defaultdict(list)
    for paper in pool:
        papers_by_title[normalize_title(paper.title)].append(paper.paper_key)
    problems += [
        f"{topic_id}: duplicate study in the pool: {keys}"
        for keys in papers_by_title.values()
        if len(keys) > 1
    ]
    return problems


def _check_search_set(
    topic_id: str,
    records: list[ScreeningGold],
    pool: list[PoolPaper],
    snapshot: SearchSnapshot,
    size: int,
) -> list[str]:
    problems = []
    if len(snapshot.papers) < size:
        problems.append(
            f"{topic_id}: search snapshot has {len(snapshot.papers)} papers, not {size}"
        )
    resolved = resolve_search_set(snapshot, pool, size)
    for rank, key in enumerate(resolved, start=1):
        if key is None:
            problems.append(f"{topic_id}: search result {rank} is not in the pool")
    flagged = {record.paper_key for record in records if record.in_search_set}
    expected = {key for key in resolved if key is not None}
    if flagged != expected:
        problems.append(
            f"{topic_id}: in_search_set marks {sorted(flagged)}, "
            f"the first {size} search results are {sorted(expected)}"
        )
    return problems


def _validate_extraction(
    extraction: list[ExtractionGold], screening: list[ScreeningGold] | None, data_dir: Path | None
) -> list[str]:
    problems: list[str] = []
    screening_by_key = {record.paper_key: record for record in screening or []}
    for paper in extraction:
        where = f"extraction {paper.paper_key}"
        if screening is not None:
            labels = screening_by_key.get(paper.paper_key)
            if labels is None or not labels.in_screening_set or labels.decision != "include":
                problems.append(f"{where}: must be a gold include in the screening set")
            elif labels.topic_id != paper.topic_id:
                problems.append(
                    f"{where}: topic is {paper.topic_id}, screening gold says {labels.topic_id}"
                )
        names = [field.field for field in paper.fields]
        problems += [
            f"{where}: field {name} appears twice"
            for name in sorted(set(names))
            if names.count(name) > 1
        ]
        if data_dir is not None:
            problems += _check_quotes(paper, data_dir)
    return problems


def _check_quotes(paper: ExtractionGold, data_dir: Path) -> list[str]:
    where = f"extraction {paper.paper_key}"
    problems: list[str] = []
    page_text = _load_or_report(
        problems, f"{where} page text", load_page_text, data_dir, paper.paper_key
    )
    if page_text is None:
        return problems
    if page_text.pdf_sha256 != paper.pdf_sha256:
        problems.append(f"{where}: page text is from a PDF with another hash than the gold file")
    for field in paper.fields:
        if field.page > len(page_text.pages):
            problems.append(
                f"{where}: {field.field} cites page {field.page}, PDF has {len(page_text.pages)}"
            )
        elif not quote_on_page(field.quote, page_text.pages[field.page - 1]):
            problems.append(f"{where}: quote of {field.field} is not on page {field.page}")
    return problems
