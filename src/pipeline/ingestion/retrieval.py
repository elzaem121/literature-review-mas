import faiss

from src.llm.client import get_embedder

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


def embed_texts(model, texts: list[str]):
    embeddings = model.encode(texts, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


def perform_faiss_retrieval(chunks: list[str]) -> dict:
    """Runs the SentenceTransformer embedding and FAISS search."""
    if not chunks:
        return {}

    model = get_embedder()
    chunk_embeddings = embed_texts(model, chunks)

    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(chunk_embeddings)

    field_chunks = {}
    for field_name, queries in FIELD_QUERIES.items():
        selected_chunks = []
        query_embeddings = embed_texts(model, queries)
        distances, indices = index.search(query_embeddings, k=5)

        for query_idx, query in enumerate(queries):
            for chunk_idx in indices[query_idx]:
                chunk_text = chunks[int(chunk_idx)]
                if chunk_text not in selected_chunks:
                    selected_chunks.append(chunk_text)

        field_chunks[field_name] = selected_chunks

    return field_chunks
