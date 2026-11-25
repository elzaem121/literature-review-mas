import csv
from pathlib import Path

import pytest

from eval.gold_build import blind_sample as blind_module
from eval.gold_build.blind_sample import blind_sample, is_borderline, sample_topic
from eval.gold_build.compare import compare, papers_in_scope
from eval.gold_build.escalation_import import import_escalation
from eval.gold_build.select_sets import select_sets, topics_below_min_includes
from eval.harness.gold import AnswerGold, GoldLimits, ScreeningGold, load_screening_gold
from tests.unit.eval.conftest import AddTopic, read, read_sheet, write

INCLUDE, EXCLUDE, UNCERTAIN = "include", "exclude", "uncertain"
# Search set: 5 includes, 3 excludes, 2 uncertain. Outside it: 12 includes, 6 excludes, 2 uncertain.
MIXED = (
    [INCLUDE] * 5
    + [EXCLUDE] * 3
    + [UNCERTAIN] * 2
    + [INCLUDE] * 12
    + [EXCLUDE] * 6
    + [UNCERTAIN] * 2
)


def two_topics(add_topic: AddTopic, decisions: list[str] = MIXED) -> None:
    add_topic("ta_mini", decisions, prefix="WA")
    add_topic("tb_mini", decisions, prefix="WB")


def screening_set(gold_dir: Path, topic_id: str) -> list[ScreeningGold]:
    return [
        r for r in load_screening_gold(gold_dir) if r.topic_id == topic_id and r.in_screening_set
    ]


def gold_record(topic_id: str, **answers: str) -> ScreeningGold:
    from eval.harness.topics import derive_decision

    return ScreeningGold(
        topic_id=topic_id,
        paper_key="W",
        in_search_set=True,
        in_screening_set=False,
        answers={c: AnswerGold(answer=a, source="model", reason="r") for c, a in answers.items()},
        decision=derive_decision(answers),
    )


# --- select_sets ---------------------------------------------------------------------------


def test_each_topics_set_has_20_papers_with_8_to_12_includes_and_at_most_4_uncertain(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    two_topics(add_topic)

    select_sets(gold_dir=gold_dir, topics_dir=topics_dir)

    for topic_id in ("ta_mini", "tb_mini"):
        chosen = screening_set(gold_dir, topic_id)
        decisions = [r.decision for r in chosen]
        assert len(chosen) == 20
        assert 8 <= decisions.count(INCLUDE) <= 12
        assert decisions.count(UNCERTAIN) <= 4
        search_set = {
            r.paper_key
            for r in load_screening_gold(gold_dir)
            if r.in_search_set and r.topic_id == topic_id
        }
        assert search_set <= {r.paper_key for r in chosen}


def test_the_selection_is_the_same_for_the_same_seed_and_differs_between_seeds(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    two_topics(add_topic)

    def selection(seed: int) -> tuple[frozenset[str], ...]:
        chosen = select_sets(seed=seed, gold_dir=gold_dir, topics_dir=topics_dir)
        return tuple(frozenset(chosen[topic_id]) for topic_id in sorted(chosen))

    assert selection(7) == selection(7)
    assert len({selection(seed) for seed in range(6)}) > 1


def test_the_seed_and_the_date_are_recorded_and_the_labels_file_keeps_its_other_fields(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    two_topics(add_topic)
    before = read(gold_dir / "screening.json")

    select_sets(seed=11, gold_dir=gold_dir, topics_dir=topics_dir)

    provenance = read(gold_dir / "provenance.json")
    assert provenance["selection_seed"] == 11
    assert provenance["skipped_papers"] == []
    assert provenance["dates"]["selection"]
    after = read(gold_dir / "screening.json")
    assert [r["paper_key"] for r in after] == [r["paper_key"] for r in before]
    assert all(
        {k: v for k, v in a.items() if k != "in_screening_set"}
        == {k: v for k, v in b.items() if k != "in_screening_set"}
        for a, b in zip(after, before)
    )


def test_search_set_uncertain_papers_beyond_the_cap_are_skipped_and_recorded(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    decisions = [UNCERTAIN] * 6 + [INCLUDE] * 14 + [EXCLUDE] * 10
    two_topics(add_topic, decisions)

    select_sets(gold_dir=gold_dir, topics_dir=topics_dir)

    chosen = {r.paper_key for r in screening_set(gold_dir, "ta_mini")}
    assert {"WA1", "WA2", "WA3", "WA4"} <= chosen
    assert not {"WA5", "WA6"} & chosen
    skipped = read(gold_dir / "provenance.json")["skipped_papers"]
    assert {
        "topic_id": "ta_mini",
        "paper_key": "WA5",
        "reason": "gold-uncertain cap reached",
    } in skipped
    assert len(skipped) == 4
    flags = {
        r.paper_key: r.in_search_set
        for r in load_screening_gold(gold_dir)
        if r.topic_id == "ta_mini"
    }
    assert flags["WA5"] is True
    assert sum(r.decision == UNCERTAIN for r in screening_set(gold_dir, "ta_mini")) == 4


def test_a_topic_that_cannot_reach_the_minimum_includes_stops_the_selection_and_writes_nothing(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    add_topic("ta_mini", MIXED, prefix="WA")
    add_topic("tb_mini", [INCLUDE] * 7 + [EXCLUDE] * 23, prefix="WB")
    before = (gold_dir / "screening.json").read_text("utf-8")

    with pytest.raises(ValueError, match="tb_mini: cannot reach 8 gold includes.*extend the pool"):
        select_sets(gold_dir=gold_dir, topics_dir=topics_dir)

    assert (gold_dir / "screening.json").read_text("utf-8") == before
    assert not (gold_dir / "provenance.json").exists()
    assert topics_below_min_includes(gold_dir, topics_dir) == ["tb_mini"]


def test_a_topic_with_a_recorded_mix_exception_is_selected_with_the_includes_it_has(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    add_topic("ta_mini", MIXED, prefix="WA")
    add_topic("tb_mini", [INCLUDE] * 2 + [EXCLUDE] * 28, prefix="WB")
    write(gold_dir / "provenance.json", {"mix_exceptions": {"tb_mini": "only 2 includes found"}})

    select_sets(gold_dir=gold_dir, topics_dir=topics_dir)

    chosen = screening_set(gold_dir, "tb_mini")
    assert len(chosen) == 20
    assert sum(r.decision == INCLUDE for r in chosen) == 2
    assert read(gold_dir / "provenance.json")["mix_exceptions"] == {
        "tb_mini": "only 2 includes found"
    }


def test_the_extension_report_lists_no_topic_when_every_topic_has_enough_includes(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    two_topics(add_topic)

    assert topics_below_min_includes(gold_dir, topics_dir) == []


def test_a_pool_too_small_for_20_papers_is_reported(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    add_topic("ta_mini", MIXED, prefix="WA")
    add_topic("tb_mini", [INCLUDE] * 10 + [EXCLUDE] * 8, prefix="WB")

    with pytest.raises(ValueError, match="tb_mini: the pool has only 18 papers that fit"):
        select_sets(gold_dir=gold_dir, topics_dir=topics_dir)


def test_a_pool_paper_without_labels_asks_for_the_import(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path
):
    add_topic("ta_mini", MIXED, prefix="WA")
    add_topic("tb_mini", MIXED, prefix="WB", labeled=False)

    with pytest.raises(ValueError, match="tb_mini: no labels for .*run label_import"):
        select_sets(gold_dir=gold_dir, topics_dir=topics_dir)


def test_smaller_limits_are_respected(add_topic: AddTopic, gold_dir: Path, topics_dir: Path):
    two_topics(add_topic)
    limits = GoldLimits(screening_size=12, min_includes=4, max_includes=6, max_uncertain=1)

    select_sets(gold_dir=gold_dir, topics_dir=topics_dir, limits=limits)

    chosen = screening_set(gold_dir, "ta_mini")
    assert len(chosen) == 12
    assert 5 <= sum(r.decision == INCLUDE for r in chosen) <= 6  # the 5 search-set includes
    assert sum(r.decision == UNCERTAIN for r in chosen) <= 1


# --- blind_sample --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answers", "borderline"),
    [
        ({"c1": "yes", "c2": "yes"}, False),
        ({"c1": "yes", "c2": "not_stated"}, True),
        ({"c1": "no", "c2": "yes"}, True),
        ({"c1": "no", "c2": "no"}, False),
        ({"c1": "no", "c2": "not_stated"}, True),
    ],
)
def test_borderline_means_a_not_stated_answer_or_an_exclude_that_rests_on_one_no(
    answers: dict[str, str], borderline: bool
):
    assert is_borderline(gold_record("ta_mini", **answers)) is borderline


def test_the_decisive_check_of_a_topic_makes_every_paper_hanging_on_it_borderline(
    monkeypatch: pytest.MonkeyPatch,
):
    record = gold_record("ta_mini", c1="yes", c2="yes")
    assert not is_borderline(record)

    monkeypatch.setattr(blind_module, "DECISIVE_CHECKS", {"ta_mini": "c1"})

    assert is_borderline(record)
    assert not is_borderline(gold_record("tb_mini", c1="yes", c2="yes"))


def test_the_sheet_has_7_papers_per_topic_3_borderline_from_either_set_and_the_rest_from_search(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path, data_root: Path
):
    # Search set: 10 includes. Papers 11-15 are excludes in the screening set; the rest includes.
    decisions = [INCLUDE] * 10 + [EXCLUDE] * 5 + [INCLUDE] * 15
    two_topics(add_topic, decisions)
    labels = read(gold_dir / "screening.json")
    for record in labels:
        record["in_screening_set"] = record["decision"] == EXCLUDE
    write(gold_dir / "screening.json", labels)

    path = blind_sample(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    assert path == data_root / "labeling" / "blind_sheet.csv"
    rows = read_sheet(path)
    assert len(rows) == 14
    assert list(rows[0]) == ["topic_id", "paper_key", "title", "abstract", "c1", "c2"]
    for topic_id, prefix in (("ta_mini", "WA"), ("tb_mini", "WB")):
        keys = [r["paper_key"] for r in rows if r["topic_id"] == topic_id]
        numbers = sorted(int(key.removeprefix(prefix)) for key in keys)
        assert len(set(keys)) == 7
        assert sum(11 <= number <= 15 for number in numbers) == 3
        assert sum(number <= 10 for number in numbers) == 4
    assert all(r["c1"] == "" and r["c2"] == "" for r in rows)
    assert {r["title"] for r in rows if r["paper_key"] == rows[0]["paper_key"]} == {
        f"Paper {rows[0]['paper_key']}"
    }
    assert [(r["topic_id"], r["paper_key"]) for r in rows] != sorted(
        (r["topic_id"], r["paper_key"]) for r in rows
    )


def test_the_same_seed_gives_the_same_sheet_and_the_sheet_never_shows_model_answers(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path, tmp_path: Path
):
    two_topics(add_topic)
    first = blind_sample(
        data_root=tmp_path / "one", gold_dir=gold_dir, topics_dir=topics_dir, seed=5
    )
    second = blind_sample(
        data_root=tmp_path / "two", gold_dir=gold_dir, topics_dir=topics_dir, seed=5
    )
    other = blind_sample(
        data_root=tmp_path / "three", gold_dir=gold_dir, topics_dir=topics_dir, seed=6
    )

    assert first.read_text("utf-8") == second.read_text("utf-8")
    assert first.read_text("utf-8") != other.read_text("utf-8")
    assert "not_stated" not in first.read_text("utf-8")


def test_an_existing_sheet_is_never_overwritten(
    add_topic: AddTopic, gold_dir: Path, topics_dir: Path, data_root: Path
):
    two_topics(add_topic)
    path = blind_sample(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)
    path.write_text("my answers", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists and may hold answers"):
        blind_sample(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    assert path.read_text("utf-8") == "my answers"


def test_a_search_set_too_small_for_the_random_part_is_reported():
    records = [
        ScreeningGold(
            **{**gold_record("ta_mini", c1="yes", c2="yes").model_dump(), "paper_key": f"W{n}"}
        )
        for n in range(3)
    ]

    with pytest.raises(ValueError, match="ta_mini: the search set has 3 papers left.*7 are needed"):
        sample_topic("ta_mini", records, seed=1)


# --- compare -------------------------------------------------------------------------------

# ta_mini: 1-4 include, 5-7 exclude (no, yes), 8-10 uncertain (yes, not_stated), 11-20 include.
COMPARE_WORLD = [INCLUDE] * 4 + [EXCLUDE] * 3 + [UNCERTAIN] * 3 + [INCLUDE] * 10
HUMAN = {
    ("ta_mini", "WA1"): ("yes", "yes"),
    ("ta_mini", "WA2"): ("yes", "no"),
    ("ta_mini", "WA3"): ("yes", "not_stated"),
    ("ta_mini", "WA5"): ("no", "yes"),
    ("ta_mini", "WA8"): ("no", "not_stated"),
    ("tb_mini", "WB1"): ("yes", "yes"),
}
SHEET_COLUMNS = ["topic_id", "paper_key", "title", "abstract", "c1", "c2"]


def write_blind_sheet(data_root: Path, human: dict[tuple[str, str], tuple[str, str]]) -> None:
    path = data_root / "labeling" / "blind_sheet.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for (topic_id, key), (c1, c2) in human.items():
            writer.writerow(
                {
                    "topic_id": topic_id,
                    "paper_key": key,
                    "title": "t",
                    "abstract": "a",
                    "c1": c1,
                    "c2": c2,
                }
            )


@pytest.fixture
def compare_world(add_topic: AddTopic, gold_dir: Path, data_root: Path) -> None:
    add_topic("ta_mini", COMPARE_WORLD, prefix="WA")
    add_topic("tb_mini", COMPARE_WORLD, prefix="WB")
    labels = read(gold_dir / "screening.json")
    for record in labels:
        record["in_screening_set"] = record["paper_key"] == "WA15"
    write(gold_dir / "screening.json", labels)
    write_blind_sheet(data_root, HUMAN)


def test_agreement_is_counted_per_topic_and_check(
    compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path
):
    compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    provenance = read(gold_dir / "provenance.json")
    assert provenance["agreement"] == {
        "ta_mini": {"c1": {"agree": 4, "disagree": 1}, "c2": {"agree": 3, "disagree": 2}},
        "tb_mini": {"c1": {"agree": 1, "disagree": 0}, "c2": {"agree": 1, "disagree": 0}},
    }
    assert provenance["dates"]["comparison"]


def test_two_disagreements_on_one_check_trigger_an_escalation_of_the_papers_it_decides(
    compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path
):
    triggers = compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    assert triggers == [("ta_mini", "c2")]
    rows = read_sheet(data_root / "labeling" / "escalation_sheet.csv")
    assert list(rows[0]) == [
        "topic_id",
        "paper_key",
        "check",
        "question",
        "title",
        "abstract",
        "answer",
    ]
    # Includes and uncertain papers hang on c2; excludes (no, yes) do not. Papers outside both
    # sets (WA11-14, WA16-20) are not in scope; WA15 is, through the screening set.
    assert [r["paper_key"] for r in rows] == [
        "WA1", "WA10", "WA15", "WA2", "WA3", "WA4", "WA8", "WA9",
    ]  # fmt: skip
    assert {r["check"] for r in rows} == {"c2"}
    assert {r["question"] for r in rows} == {"Does the study report empirical or conceptual work?"}
    assert {r["answer"] for r in rows} == {""}
    assert rows[0]["title"] == "Paper WA1"


def test_scope_uses_decided_by_so_a_single_no_exclude_hangs_on_its_no_check_only(
    compare_world: None, gold_dir: Path
):
    labels = load_screening_gold(gold_dir)

    assert "WA5" not in papers_in_scope(labels, "ta_mini", "c2")
    assert "WA5" in papers_in_scope(labels, "ta_mini", "c1")


def test_one_disagreement_triggers_nothing_and_writes_no_sheet(
    compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path
):
    write_blind_sheet(data_root, {**HUMAN, ("ta_mini", "WA3"): ("yes", "yes")})

    assert compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir) == []
    assert not (data_root / "labeling" / "escalation_sheet.csv").exists()


def test_an_unanswered_cell_or_an_unknown_paper_is_named(
    compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path
):
    write_blind_sheet(data_root, {("ta_mini", "WA1"): ("yes", "")})
    with pytest.raises(ValueError, match="blind_sheet.csv row 2 c2: '' is not one of"):
        compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    write_blind_sheet(data_root, {("ta_mini", "WA99"): ("yes", "yes")})
    with pytest.raises(ValueError, match="row 2: no gold labels for ta_mini WA99"):
        compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)


def test_a_sheet_the_human_is_filling_is_not_overwritten_by_a_second_comparison(
    compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path
):
    compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)

    with pytest.raises(ValueError, match="escalation_sheet.csv already exists"):
        compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)


# --- escalation_import ---------------------------------------------------------------------

ESCALATION_ANSWERS = {
    "WA1": "yes",
    "WA2": "no",
    "WA3": "not_stated",
    "WA4": "",
    "WA8": "not stated",
    "WA9": "yes",
    "WA10": "",
    "WA15": "Yes",
}


def fill_escalation_sheet(data_root: Path, answers: dict[str, str]) -> None:
    path = data_root / "labeling" / "escalation_sheet.csv"
    rows = read_sheet(path)
    for row in rows:
        row["answer"] = answers.get(row["paper_key"], row["answer"])
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def escalation(compare_world: None, gold_dir: Path, topics_dir: Path, data_root: Path) -> None:
    compare(data_root=data_root, gold_dir=gold_dir, topics_dir=topics_dir)
    fill_escalation_sheet(data_root, ESCALATION_ANSWERS)


def c2_of(gold_dir: Path) -> dict[str, tuple[str, str, str]]:
    return {
        r.paper_key: (r.answers["c2"].answer, r.answers["c2"].source, r.decision)
        for r in load_screening_gold(gold_dir)
        if r.topic_id == "ta_mini"
    }


def test_confirmed_answers_become_verified_changed_ones_human_and_decisions_are_rederived(
    escalation: None, gold_dir: Path, data_root: Path
):
    import_escalation(data_root=data_root, gold_dir=gold_dir)

    c2 = c2_of(gold_dir)
    assert c2["WA1"] == ("yes", "model_verified", "include")
    assert c2["WA2"] == ("no", "human", "exclude")
    assert c2["WA3"] == ("not_stated", "human", "uncertain")
    assert c2["WA8"] == ("not_stated", "model_verified", "uncertain")
    assert c2["WA9"] == ("yes", "human", "include")
    assert c2["WA15"] == ("yes", "model_verified", "include")
    assert c2["WA4"] == ("yes", "model", "include")
    assert c2["WA10"] == ("not_stated", "model", "uncertain")
    reason = (
        next(r for r in load_screening_gold(gold_dir) if r.paper_key == "WA2").answers["c2"].reason
    )
    assert reason == "Changed by the human on escalation; the model answered 'yes'."
    untouched = next(r for r in load_screening_gold(gold_dir) if r.paper_key == "WA5")
    assert {a.source for a in untouched.answers.values()} == {"model"}


def test_the_escalation_log_counts_scope_reviewed_and_changed(
    escalation: None, gold_dir: Path, data_root: Path
):
    log = import_escalation(data_root=data_root, gold_dir=gold_dir)

    expected = {
        "topic_id": "ta_mini",
        "check": "c2",
        "papers_in_scope": ["WA1", "WA10", "WA15", "WA2", "WA3", "WA4", "WA8", "WA9"],
        "papers_reviewed": ["WA1", "WA15", "WA2", "WA3", "WA8", "WA9"],
        "answers_changed": ["WA2", "WA3", "WA9"],
    }
    assert log == [expected]
    provenance = read(gold_dir / "provenance.json")
    assert provenance["escalation"] == [expected]
    assert provenance["dates"]["escalation"]


def test_importing_the_same_sheet_again_changes_nothing_and_a_later_answer_is_added(
    escalation: None, gold_dir: Path, data_root: Path
):
    first = import_escalation(data_root=data_root, gold_dir=gold_dir)
    after_first = (gold_dir / "screening.json").read_text("utf-8")

    assert import_escalation(data_root=data_root, gold_dir=gold_dir) == first
    assert (gold_dir / "screening.json").read_text("utf-8") == after_first

    fill_escalation_sheet(data_root, {"WA4": "no"})
    log = import_escalation(data_root=data_root, gold_dir=gold_dir)

    assert c2_of(gold_dir)["WA4"] == ("no", "human", "exclude")
    assert log[0]["papers_reviewed"] == ["WA1", "WA15", "WA2", "WA3", "WA4", "WA8", "WA9"]
    assert log[0]["answers_changed"] == ["WA2", "WA3", "WA4", "WA9"]
    assert c2_of(gold_dir)["WA2"] == ("no", "human", "exclude")


def test_an_invalid_answer_names_its_row_and_changes_nothing(
    escalation: None, gold_dir: Path, data_root: Path
):
    fill_escalation_sheet(data_root, {"WA9": "maybe"})
    before = (gold_dir / "screening.json").read_text("utf-8")

    with pytest.raises(ValueError, match="escalation_sheet.csv row 9: 'maybe' is not one of"):
        import_escalation(data_root=data_root, gold_dir=gold_dir)

    assert (gold_dir / "screening.json").read_text("utf-8") == before


def test_importing_without_a_sheet_says_so(gold_dir: Path, data_root: Path, add_topic: AddTopic):
    add_topic("ta_mini", MIXED, prefix="WA")

    with pytest.raises(ValueError, match="escalation_sheet.csv does not exist"):
        import_escalation(data_root=data_root, gold_dir=gold_dir)
