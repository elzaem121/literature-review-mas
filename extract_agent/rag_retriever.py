import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


INPUT_FILE = Path("chunked_papers.json")
OUTPUT_FILE = Path("retrieved_chunks.json")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

FIELD_QUERIES = {
    "method_chunks": [
        "research method methodology study design approach qualitative quantitative mixed methods theoretical conceptual literature review"
    ],
    "dataset_chunks": [
        "data dataset data source participants sample corpus interviews survey observation experiment field data documents research population"
    ],
    "task_chunks": [
        "research objective aim purpose research question analytical focus task contribution"
    ],
    "findings_chunks": [
        "main findings results conclusions key outcomes implications contribution"
    ],
    "limitations_chunks": [
        "limitations weaknesses constraints future work study limitations"
    ],
}
def embed_texts(model, texts):
    embeddings = model.encode(texts, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)


for paper in data["papers"]:
    chunks = paper.get("chunks", [])

    if not chunks:
        print(f"[SKIPPED] No chunks: {paper.get('title')}")
        continue

    print(f"\n[PROCESSING] {paper.get('title')}")
    print(f"Chunks: {len(chunks)}")

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

    paper["retrieved_chunks_by_field"] = field_chunks

    all_chunks = []
    for chunks_list in field_chunks.values():
        for chunk in chunks_list:
            if chunk not in all_chunks:
                all_chunks.append(chunk)

    paper["retrieved_chunks"] = all_chunks


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)


print(f"\nSaved retrieved chunks to: {OUTPUT_FILE}")