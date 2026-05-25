import asyncio
import json
import sys
from pathlib import Path

import instructor
from openai import AsyncOpenAI

sys.path.append(str(Path(__file__).resolve().parent.parent))

from extraction_schemas import ExtractedPaperInfo


INPUT_FILE = Path("retrieved_chunks.json")
OUTPUT_FILE = Path("rag_extraction_results.json")


client = instructor.patch(
    AsyncOpenAI(
        base_url="http://localhost:11434/v1",
        api_key="local-ollama-key"
    ),
    mode=instructor.Mode.JSON,
)


async def extract_from_retrieved_chunks(paper, research_question: str):
    retrieved_chunks = paper.get("retrieved_chunks", [])

    context = "\n\n--- CHUNK ---\n\n".join(retrieved_chunks)

    system_prompt = """
You are an academic RAG-based extraction agent.

Return ONLY valid JSON.

Use EXACTLY these field names:

{
  "method": "...",
  "dataset": "...",
  "task": "...",
  "main_findings": "...",
  "limitations": "...",
  "relevance_to_research_question": "...",
  "confidence": "medium"
}

Rules:
- ALL fields must be strings.
- Do NOT return lists.
- Do NOT invent new field names.
- Do NOT add explanations.
- Do NOT include markdown.
- Do NOT include thoughts or reasoning.
- Use only the provided retrieved chunks.
- If information is missing, write "not specified".
- confidence must be exactly one of: high, medium, low.
"""

    user_prompt = f"""
Research question:
{research_question}

Paper title:
{paper.get("title")}

Retrieved chunks:
{context}

Extract the following information.

Return JSON with EXACTLY these keys:
method
dataset
task
main_findings
limitations
relevance_to_research_question
confidence

Important:
- Use "method", not "research_method_or_study_type".
- Use "dataset", not "dataset_or_data_source".
- Use "task", not "main_task_or_analytical_focus".
- Use "relevance_to_research_question", not "relevance_to_the_research_question".
- "main_findings" must be one string, not a list.
- "limitations" must be one string, not a list.
- "confidence" must be high, medium, or low.
"""

    result = await client.chat.completions.create(
        model="qwen3:latest",
        response_model=ExtractedPaperInfo,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    return {
        "paper": {
            "title": paper.get("title"),
            "year": paper.get("year"),
            "authors": paper.get("authors"),
            "doi": paper.get("doi"),
            "url": paper.get("url"),
        },
        "rag_extraction": result.model_dump()
    }


async def main():
    research_question = "How does social media shape adolescents' lifeworlds and everyday experiences?"

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    results = []

    for paper in data["papers"]:
        if not paper.get("retrieved_chunks"):
            print(f"[SKIPPED] No retrieved chunks: {paper.get('title')}")
            continue

        print(f"[RAG EXTRACTION] {paper.get('title')}")

        extraction = await extract_from_retrieved_chunks(
            paper=paper,
            research_question=research_question
        )

        results.append(extraction)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump({"rag_extracted_papers": results}, file, indent=2, ensure_ascii=False)

    print(f"\nSaved RAG extraction results to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())