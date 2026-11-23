from eval.harness.records import RetrievedChunk
from eval.harness.text import joined_runs, normalize_title, normalize_ws, quote_on_page


def chunk(page: int, ordinal: int, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        paper_key="W1", field="method", rank=1, page=page, ordinal=ordinal, text=text
    )


def test_normalize_ws_collapses_every_kind_of_whitespace_and_trims():
    assert normalize_ws("  a\n b\t\tc \r\n") == "a b c"


def test_normalize_title_keeps_only_lowercase_letters_and_digits():
    assert normalize_title("Study Two: On Group-Chats (2nd ed.)!") == "studytwoongroupchats2nded"
    assert normalize_title("Über Soziale Medien") == "übersozialemedien"


def test_quote_on_page_ignores_line_breaks_and_spacing():
    page = "The study is limited to two schools and relies on self-reported\naccounts, so it."

    assert quote_on_page("relies on  self-reported accounts, so it.", page)
    assert not quote_on_page("relies on interviews", page)


def test_quote_on_page_never_matches_an_empty_quote():
    assert not quote_on_page("   ", "any page text")


def test_joined_runs_joins_a_quote_split_over_two_consecutive_chunks():
    runs = joined_runs([chunk(2, 5, "relies on self-"), chunk(2, 4, "The study ")])

    assert runs == ["The study relies on self-"]
    assert quote_on_page("The study relies on self-", runs[0])


def test_joined_runs_does_not_join_across_pages_or_across_a_gap():
    runs = joined_runs([chunk(1, 3, "end of page one "), chunk(2, 4, "start of page two")])
    assert runs == ["end of page one ", "start of page two"]

    runs = joined_runs([chunk(1, 1, "first"), chunk(1, 3, "third")])
    assert runs == ["first", "third"]


def test_joined_runs_ignores_a_chunk_listed_twice_and_handles_no_chunks():
    runs = joined_runs([chunk(1, 1, "a"), chunk(1, 1, "a"), chunk(1, 2, "b")])

    assert runs == ["ab"]
    assert joined_runs([]) == []
