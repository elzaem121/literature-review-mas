from pathlib import Path

import pytest

from eval.harness.topics import (
    decided_by,
    derive_decision,
    labeling_json_schema,
    load_topic,
    render_labeling_prompt,
    render_screener_input,
)

TOPICS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "eval" / "topics"

TWO_CHECK_DECISIONS = [
    (("yes", "yes"), "include"),
    (("yes", "no"), "exclude"),
    (("no", "yes"), "exclude"),
    (("no", "no"), "exclude"),
    (("no", "not_stated"), "exclude"),
    (("not_stated", "no"), "exclude"),
    (("yes", "not_stated"), "uncertain"),
    (("not_stated", "yes"), "uncertain"),
    (("not_stated", "not_stated"), "uncertain"),
]


@pytest.mark.parametrize(("answers", "expected"), TWO_CHECK_DECISIONS)
def test_derive_decision_covers_every_answer_combination(answers, expected):
    assert derive_decision({"c1": answers[0], "c2": answers[1]}) == expected


def test_derive_decision_rejects_no_answers_and_unknown_answers():
    with pytest.raises(ValueError, match="no check answers"):
        derive_decision({})
    with pytest.raises(ValueError, match="unknown check answers.*maybe"):
        derive_decision({"c1": "maybe"})


def test_decided_by_for_an_include_is_true_for_every_check():
    answers = {"c1": "yes", "c2": "yes", "c3": "yes"}

    assert [decided_by(answers, check) for check in answers] == [True, True, True]


def test_decided_by_for_a_single_no_exclude_is_true_only_for_the_no_check():
    answers = {"c1": "no", "c2": "yes", "c3": "yes"}

    assert [decided_by(answers, check) for check in answers] == [True, False, False]


def test_decided_by_for_a_single_no_next_to_a_not_stated_still_depends_on_the_no():
    answers = {"c1": "no", "c2": "not_stated", "c3": "yes"}

    assert [decided_by(answers, check) for check in answers] == [True, False, False]


def test_decided_by_for_a_multi_no_exclude_is_false_for_every_check():
    answers = {"c1": "no", "c2": "no", "c3": "yes"}

    assert [decided_by(answers, check) for check in answers] == [False, False, False]


def test_decided_by_for_an_uncertain_is_true_for_every_check():
    answers = {"c1": "yes", "c2": "not_stated", "c3": "not_stated"}

    assert [decided_by(answers, check) for check in answers] == [True, True, True]


def test_decided_by_rejects_a_check_without_an_answer():
    with pytest.raises(ValueError, match="check 'c9' has no answer"):
        decided_by({"c1": "yes"}, "c9")


def test_load_topic_reads_and_validates_the_config():
    topic = load_topic("ta_mini", TOPICS_DIR)

    assert topic.research_question == "How do teenagers use social media?"
    assert [check.id for check in topic.checks] == ["c1", "c2"]
    assert topic.min_year == 2020


def test_load_topic_rejects_a_file_declaring_another_topic_id(tmp_path: Path):
    (tmp_path / "tx.json").write_text((TOPICS_DIR / "ta_mini.json").read_text("utf-8"))

    with pytest.raises(ValueError, match="declares topic_id 'ta_mini'"):
        load_topic("tx", tmp_path)


def test_load_topic_rejects_duplicate_and_malformed_check_ids(tmp_path: Path):
    text = (TOPICS_DIR / "ta_mini.json").read_text("utf-8")
    (tmp_path / "ta_mini.json").write_text(text.replace('"c2"', '"c1"'))
    with pytest.raises(ValueError, match="duplicate check ids"):
        load_topic("ta_mini", tmp_path)

    (tmp_path / "ta_mini.json").write_text(text.replace('"c2"', '"second"'))
    with pytest.raises(ValueError, match="string_pattern_mismatch"):
        load_topic("ta_mini", tmp_path)


def test_screener_input_has_one_line_per_check_and_no_additional_info():
    rendered = render_screener_input(load_topic("ta_mini", TOPICS_DIR))

    assert rendered == {
        "research_question": "How do teenagers use social media?",
        "inclusion_criteria": [
            "The study is about young people.",
            "The study reports empirical or conceptual work.",
        ],
        "exclusion_criteria": [
            "The study is not about young people.",
            "The study is only an editorial or news item.",
        ],
        "additional_info": None,
        "min_year": 2020,
    }


def test_labeling_prompt_holds_the_question_the_checks_and_the_answer_rules():
    prompt = render_labeling_prompt(load_topic("ta_mini", TOPICS_DIR))

    assert "How do teenagers use social media?" in prompt
    assert "c1. Is the study about young people?" in prompt
    assert "yes: The study is about young people." in prompt
    assert "no: The study is only an editorial or news item." in prompt
    assert "not_stated" in prompt
    assert "title and abstract" in prompt


def test_labeling_schema_requires_exactly_one_answer_per_check_with_enum_ids():
    schema = labeling_json_schema(load_topic("ta_mini", TOPICS_DIR))

    answers = schema["properties"]["answers"]
    assert schema["required"] == ["answers"]
    assert answers["minItems"] == answers["maxItems"] == 2
    assert answers["items"]["properties"]["check"]["enum"] == ["c1", "c2"]
    assert answers["items"]["properties"]["answer"]["enum"] == ["yes", "no", "not_stated"]
    assert answers["items"]["required"] == ["check", "answer", "reason"]
