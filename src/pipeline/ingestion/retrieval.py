"""Per-field retrieval of a paper's chunks by embedding similarity (pgvector cosine)."""

from src.db.repository import Repository
from src.llm.client import get_embedder

RETRIEVAL_TOP_K = 5

FIELD_QUERIES = {
    "method_chunks": [
        (
            "research method methodology study design approach qualitative quantitative "
            "mixed methods theoretical conceptual literature review"
        )
    ],
    "dataset_chunks": [
        (
            "data dataset data source participants sample corpus interviews survey "
            "observation experiment field data documents research population"
        )
    ],
    "task_chunks": [
        "research objective aim purpose research question analytical focus task contribution"
    ],
    "findings_chunks": ["main findings results conclusions key outcomes implications contribution"],
    "limitations_chunks": ["limitations weaknesses constraints future work study limitations"],
}


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the configured embedder (blocking)."""
    return get_embedder().encode(texts, convert_to_numpy=True).tolist()


def retrieve_field_chunks(repository: Repository, paper_id: int) -> dict[str, list[str]]:
    """Return the closest chunks of one paper per extraction field (blocking)."""
    field_chunks: dict[str, list[str]] = {}
    for field_name, queries in FIELD_QUERIES.items():
        selected: list[str] = []
        for query_embedding in embed_texts(queries):
            for text in repository.search_chunks(paper_id, query_embedding, RETRIEVAL_TOP_K):
                if text not in selected:
                    selected.append(text)
        field_chunks[field_name] = selected
    return field_chunks
