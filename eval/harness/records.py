"""Record types of the harness contract: adapters return them and scoring reads them."""

from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

ScoredField = Literal["method", "dataset", "task", "main_findings", "limitations"]
SCORED_FIELDS: tuple[str, ...] = get_args(ScoredField)

CheckAnswer = Literal["yes", "no", "not_stated"]
LabelSource = Literal["model", "model_verified", "human"]
GoldDecision = Literal["include", "exclude", "uncertain"]
ModelDecision = Literal["include", "exclude", "uncertain", "failed"]
FieldStatus = Literal["found", "not_found"]
RunStatus = Literal["complete", "incomplete"]


class SearchRecord(BaseModel):
    """What one search call returned: the ranked papers and how the query was built."""

    papers: list[dict[str, Any]]
    synthetic_abstract: str
    fallback_used: bool


class ScreeningRecord(BaseModel):
    """The screener's decision for one paper; `error` is set only when the call failed."""

    paper_key: str
    decision: ModelDecision
    error: str | None = None
    reasoning: str = ""
    matched_inclusion: list[str] = Field(default_factory=list)
    matched_exclusion: list[str] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    """One chunk retrieved for a field; `rank` and `page` are 1-based, `ordinal` starts at 0."""

    paper_key: str
    field: ScoredField
    rank: int = Field(ge=1)
    page: int = Field(ge=1)
    ordinal: int = Field(ge=0)
    text: str


class FieldRecord(BaseModel):
    """The extractor's answer for one scored field, reduced to a status and its value text."""

    paper_key: str
    field: ScoredField
    status: FieldStatus
    value: str


class ExtractionOutput(BaseModel):
    """Everything one extraction call produced for a paper, kept for later judging."""

    fields: list[FieldRecord] = Field(default_factory=list)
    raw: dict[str, Any] | None = None
    error: str | None = None


class Timings(BaseModel):
    """Wall-clock seconds of one run; screening passes are listed in run order."""

    screening_pass_s: list[float]
    screening_papers: int = Field(gt=0)
    retrieval_s: dict[str, float]
    extraction_s: dict[str, float]


class RunProvenance(BaseModel):
    """What a run was made of; `status` is `incomplete` when an infrastructure error hit the run."""

    status: RunStatus
    incomplete_reason: str | None = None
    adapter: str
    git_commit: str
    started_at: str
    models: dict[str, str]
    ollama_digests: dict[str, str]
    prompt_versions: dict[str, str]
    context_length: int | Literal["ollama_default"]
    embedding_model: str
    chunker_version: str
    retrieval_top_k: int
    concurrency: int
    gold_version: str
    snapshot_retrieved_at: dict[str, str]
