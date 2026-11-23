"""Text helpers shared by gold validation and scoring."""

from eval.harness.records import RetrievedChunk


def normalize_ws(text: str) -> str:
    """Collapse all whitespace to single spaces and trim."""
    return " ".join(text.split())


def normalize_title(title: str) -> str:
    """Lowercase a title and drop everything that is not a letter or a digit."""
    return "".join(char for char in title.lower() if char.isalnum())


def quote_on_page(quote: str, page_text: str) -> bool:
    """Whether the quote is in the text after whitespace normalization; an empty quote never is."""
    normalized = normalize_ws(quote)
    return bool(normalized) and normalized in normalize_ws(page_text)


def joined_runs(chunks: list[RetrievedChunk]) -> list[str]:
    """Join chunks of one page with consecutive ordinals into one text per run, in reading order.

    The chunker cuts at fixed offsets without overlap, so neighbouring chunks are joined with no
    separator; a run never crosses a page.
    """
    unique = {(chunk.page, chunk.ordinal): chunk for chunk in chunks}
    runs: list[list[RetrievedChunk]] = []
    for key in sorted(unique):
        chunk = unique[key]
        previous = runs[-1][-1] if runs else None
        if previous and previous.page == chunk.page and previous.ordinal + 1 == chunk.ordinal:
            runs[-1].append(chunk)
        else:
            runs.append([chunk])
    return ["".join(chunk.text for chunk in run) for run in runs]
