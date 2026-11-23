"""Topic configs: one source for the labeler's prompt and the screener's criteria."""

import json
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, Field, model_validator

from eval.harness.records import CheckAnswer, GoldDecision

TOPICS_DIR = Path(__file__).resolve().parents[1] / "topics"
CHECK_ID_PATTERN = r"^c[0-9]+$"
ANSWERS: tuple[str, ...] = get_args(CheckAnswer)


class Check(BaseModel):
    """One yes/no/not_stated question about a paper, with the statement for each outcome."""

    id: str = Field(pattern=CHECK_ID_PATTERN)
    question: str = Field(min_length=1)
    yes: str = Field(min_length=1)
    no: str = Field(min_length=1)


class Topic(BaseModel):
    """A test topic: the research question, the earliest year and the checks."""

    topic_id: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    min_year: int
    checks: list[Check] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_ids_are_unique(self) -> "Topic":
        ids = [check.id for check in self.checks]
        if len(set(ids)) != len(ids):
            raise ValueError(f"topic {self.topic_id} has duplicate check ids: {ids}")
        return self


def load_topic(topic_id: str, topics_dir: Path = TOPICS_DIR) -> Topic:
    """Load and validate `<topics_dir>/<topic_id>.json`; the file's own topic id must match."""
    topic = Topic.model_validate(json.loads((topics_dir / f"{topic_id}.json").read_text("utf-8")))
    if topic.topic_id != topic_id:
        raise ValueError(f"{topic_id}.json declares topic_id '{topic.topic_id}'")
    return topic


def derive_decision(answers: dict[str, str]) -> GoldDecision:
    """Any `no` excludes, all `yes` includes, anything else is uncertain."""
    if not answers:
        raise ValueError("cannot derive a decision from no check answers")
    unknown = sorted(set(answers.values()) - set(ANSWERS))
    if unknown:
        raise ValueError(f"unknown check answers {unknown}; expected one of {list(ANSWERS)}")
    values = set(answers.values())
    if "no" in values:
        return "exclude"
    if values == {"yes"}:
        return "include"
    return "uncertain"


def decided_by(answers: dict[str, str], check_id: str) -> bool:
    """Whether changing the answer of this one check could change the decision."""
    if check_id not in answers:
        raise ValueError(f"check '{check_id}' has no answer; answered checks: {sorted(answers)}")
    current = derive_decision(answers)
    return any(
        derive_decision({**answers, check_id: other}) != current
        for other in ANSWERS
        if other != answers[check_id]
    )


def render_screener_input(topic: Topic) -> dict[str, Any]:
    """The criteria the unchanged screening prompt receives: one line per check and outcome."""
    return {
        "research_question": topic.research_question,
        "inclusion_criteria": [check.yes for check in topic.checks],
        "exclusion_criteria": [check.no for check in topic.checks],
        "additional_info": None,
        "min_year": topic.min_year,
    }


def render_labeling_prompt(topic: Topic) -> str:
    """The system prompt for labeling one paper from its title and abstract alone."""
    checks = "\n\n".join(
        f"{check.id}. {check.question}\n   yes: {check.yes}\n   no: {check.no}"
        for check in topic.checks
    )
    return (
        "You label one scientific paper for a literature review. You see only its title and "
        "abstract. Judge nothing else: use no outside knowledge about the paper.\n\n"
        f"Research question: {topic.research_question}\n\n"
        f"Checks:\n\n{checks}\n\n"
        "Answer every check exactly once with one of:\n"
        '- "yes": the title or abstract clearly satisfies the "yes" statement.\n'
        '- "no": the title or abstract clearly satisfies the "no" statement.\n'
        '- "not_stated": the title and abstract do not say enough to decide. Do not guess.\n'
        "Give a one-line reason for each answer, based on the text you were given."
    )


def labeling_json_schema(topic: Topic) -> dict[str, Any]:
    """The JSON schema of the labeler's answer: exactly one answer per check, ids from the topic."""
    count = len(topic.checks)
    answer = {
        "type": "object",
        "properties": {
            "check": {"type": "string", "enum": [check.id for check in topic.checks]},
            "answer": {"type": "string", "enum": list(ANSWERS)},
            "reason": {"type": "string"},
        },
        "required": ["check", "answer", "reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "answers": {"type": "array", "items": answer, "minItems": count, "maxItems": count}
        },
        "required": ["answers"],
        "additionalProperties": False,
    }
