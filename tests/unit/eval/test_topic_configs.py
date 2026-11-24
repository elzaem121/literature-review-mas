import pytest

from eval.gold_build.blind_sample import DECISIVE_CHECKS
from eval.gold_build.build_pool import LINK_LIST_TOPIC
from eval.harness.topics import (
    TOPICS_DIR,
    load_topic,
    render_labeling_prompt,
    render_screener_input,
)

CHECK_COUNTS = {"t1_social_media": 5, "t2_llm_mas_eval": 4, "t3_mobile_money": 5}


def test_the_topics_folder_holds_exactly_the_three_test_topics():
    assert sorted(path.stem for path in TOPICS_DIR.glob("*.json")) == sorted(CHECK_COUNTS)


@pytest.mark.parametrize(("topic_id", "count"), CHECK_COUNTS.items())
def test_each_topic_config_loads_with_its_accepted_number_of_checks(topic_id, count):
    topic = load_topic(topic_id)

    assert [check.id for check in topic.checks] == [f"c{n}" for n in range(1, count + 1)]
    assert topic.min_year == 2020


@pytest.mark.parametrize("topic_id", CHECK_COUNTS)
def test_every_check_has_distinct_yes_and_no_statements(topic_id):
    for check in load_topic(topic_id).checks:
        assert check.yes != check.no


@pytest.mark.parametrize("topic_id", CHECK_COUNTS)
def test_the_screener_gets_one_inclusion_and_one_exclusion_line_per_check(topic_id):
    topic = load_topic(topic_id)

    rendered = render_screener_input(topic)

    assert rendered["inclusion_criteria"] == [check.yes for check in topic.checks]
    assert rendered["exclusion_criteria"] == [check.no for check in topic.checks]
    assert rendered["additional_info"] is None


@pytest.mark.parametrize("topic_id", CHECK_COUNTS)
def test_the_labeling_prompt_names_every_check_and_the_question(topic_id):
    topic = load_topic(topic_id)

    prompt = render_labeling_prompt(topic)

    assert topic.research_question in prompt
    assert all(f"{check.id}. {check.question}" in prompt for check in topic.checks)


def test_the_wellbeing_boundary_is_written_into_topic_1_check_3():
    check = load_topic("t1_social_media").checks[2]

    assert "depressive and anxiety symptoms" in check.yes
    assert "Depressive and anxiety symptoms" in check.question


def test_the_decisive_check_of_topic_2_is_the_evaluation_check():
    check_id = DECISIVE_CHECKS["t2_llm_mas_eval"]
    check = next(c for c in load_topic("t2_llm_mas_eval").checks if c.id == check_id)

    assert "main contribution" in check.question


def test_the_link_list_topic_is_a_real_topic_config():
    assert load_topic(LINK_LIST_TOPIC).topic_id == "t1_social_media"


def check_of(topic_id: str, check_id: str):
    return next(c for c in load_topic(topic_id).checks if c.id == check_id)


def test_topic_1_check_4_is_yes_unless_clinical_or_treatment_and_outcomes_do_not_count():
    check = check_of("t1_social_media", "c4")

    assert 'Answer "yes" unless' in check.question
    assert "selected because of a diagnosis" in check.question
    assert "measured as an outcome does not make a sample clinical" in check.question
    assert "measured as an outcome does not make a sample clinical" in check.yes
    assert "selected because of a diagnosis" in check.no


def test_topic_2_check_3_counts_a_system_paper_that_releases_a_reusable_benchmark():
    check = check_of("t2_llm_mas_eval", "c3")

    assert "also releases a new benchmark or dataset that others can reuse" in check.question
    assert "releases a reusable new benchmark or dataset" in check.yes
    assert "without releasing a reusable new benchmark or dataset" in check.no


def test_topic_3_check_1_accepts_digital_finance_only_when_mobile_money_is_measured():
    check = check_of("t3_mobile_money", "c1")

    assert "only if mobile money is part of what is measured" in check.question
    assert 'online banking alone is "no"' in check.question
    assert "only if mobile money is part of what is measured" in check.yes
    assert "online banking alone" in check.no
