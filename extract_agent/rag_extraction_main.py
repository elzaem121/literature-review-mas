import os
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


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:latest")

print(f"Using Ollama API at: {OLLAMA_BASE_URL}")
print(f"Using Ollama model: {OLLAMA_MODEL}")


client = instructor.patch(
    AsyncOpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="local-ollama-key",
    ),
    mode=instructor.Mode.JSON,
)


async def extract_from_retrieved_chunks(paper, research_question: str):
    retrieved_chunks_by_field = paper.get("retrieved_chunks_by_field", {})

    method_context = "\n\n--- METHOD CHUNK ---\n\n".join(
        retrieved_chunks_by_field.get("method_chunks", [])
    )

    dataset_context = "\n\n--- DATASET CHUNK ---\n\n".join(
        retrieved_chunks_by_field.get("dataset_chunks", [])
    )

    task_context = "\n\n--- TASK CHUNK ---\n\n".join(
        retrieved_chunks_by_field.get("task_chunks", [])
    )

    findings_context = "\n\n--- FINDINGS CHUNK ---\n\n".join(
        retrieved_chunks_by_field.get("findings_chunks", [])
    )

    limitations_context = "\n\n--- LIMITATIONS CHUNK ---\n\n".join(
        retrieved_chunks_by_field.get("limitations_chunks", [])
    )

    all_context = "\n\n".join([
        method_context,
        dataset_context,
        task_context,
        findings_context,
        limitations_context,
    ])

    system_prompt = """
You are an academic RAG-based extraction agent.

Your task is to extract structured scientific information from retrieved chunks of one research paper.

Use ONLY the provided retrieved chunks.
Do NOT invent missing information.
Do NOT infer methods, datasets, findings, or limitations if they are not explicitly supported by the chunks.

Important rules:
0. Paper Type
- First classify the paper type.
- Determine the paper type based on its content and methodology.
- Use the most appropriate scientific category (e.g. empirical study, literature review, conceptual paper, theoretical discussion, case study, mixed-methods study, or another suitable category if justified by the text).
- Identify the actual research method or study type.
- Examples: empirical study, qualitative interview study, quantitative study, mixed-methods study, literature review, conceptual paper, theoretical discussion.
- If the method is not explicitly clear, write "not specified".
- If the paper is conceptual, theoretical, or a literature review, state that clearly.

2. Dataset
- Identify the actual dataset, participants, corpus, documents, or data source.
- If the paper does not use an empirical dataset, write "no empirical dataset".
- Do not invent participants, sample sizes, interviews, surveys, or datasets.

3. Task
- Identify the main analytical focus of the paper.
- Keep it concise and based only on the chunks.

4. Main Findings
- Extract only findings explicitly supported by the retrieved chunks.
- Do not summarize beyond the provided evidence.
- Do not add findings from general knowledge.

5. Limitations
- Only mention limitations explicitly stated in the chunks.
- If no limitations are explicitly stated, write "not explicitly specified".

6. Relevance to research question
- Briefly explain how the paper is relevant or not relevant to the research question.
- Do not overstate the relevance.

7. Confidence
- Must be exactly one of: high, medium, low.
8. Self-verification
Before returning the final JSON, internally check your extraction for contradictions.

Check especially:
- If the paper_type is conceptual paper, theoretical discussion, or literature review, do not invent empirical datasets.
- If the extracted method implies empirical data collection, verify that the dataset is supported by the retrieved chunks. If no supporting evidence exists, return "not specified" instead of inventing a dataset.
- If dataset is "no empirical dataset", make sure the method is not an empirical method.
- If limitations are not explicitly stated, write "not explicitly specified".
- If the evidence in the chunks is weak or missing, write "not specified".
IMPORTANT:
- Never infer participant numbers, ages, locations, or datasets.
- Never invent limitations.
- Never invent findings that are not explicitly supported by the retrieved chunks.
- If a value cannot be directly extracted from the provided text, return "not specified".
- It is better to return "not specified" than to guess.
Before returning the final answer, verify every extracted field against the retrieved chunks.
If a statement cannot be directly supported by the provided text, replace it with "not specified" instead of guessing.

Return ONLY valid JSON.
Do not return markdown.
Do not return explanations.
Do not return lists.
All fields must be strings.
"""

    user_prompt = f"""
Research question:
{research_question}

Paper title:
{paper.get("title")}

Field-specific retrieved chunks:

Method-related chunks:
{method_context}

Dataset-related chunks:
{dataset_context}

Task-related chunks:
{task_context}

Findings-related chunks:
{findings_context}

Limitations-related chunks:
{limitations_context}

Return JSON with EXACTLY these fields:

{{
  "paper_type": "...",
  "method": "...",
  "dataset": "...",
  "task": "...",
  "main_findings": "...",
  "limitations": "...",
  "relevance_to_research_question": "...",
  "confidence": "medium"
}}

Rules:
- Use "method", not "research_method_or_study_type".
- Use "dataset", not "dataset_or_data_source".
- Use "task", not "main_task_or_analytical_focus".
- Use "relevance_to_research_question", not "relevance_to_the_research_question".
- "main_findings" must be one string, not a list.
- "limitations" must be one string, not a list.
- All fields must be strings.
- Use only the provided retrieved chunks.
- If information is missing, write "not specified".
- If the paper has no empirical dataset, write "no empirical dataset".
- If limitations are not explicitly stated, write "not explicitly specified".
- Confidence must be high, medium, or low.
- Use "paper_type" to classify the paper before extracting method and dataset.
- If paper_type is conceptual paper, theoretical discussion, or literature review, do not invent an empirical dataset.
- Before returning the JSON, check whether paper_type, method, and dataset are logically consistent.
- Correct contradictions before producing the final answer.
- Do not classify a paper as conceptual if the chunks mention participants, interviews, observation, survey, experiment, field data, research population, or empirical data collection.
- Do not write "no empirical dataset" if the chunks mention participants, interviews, surveys, observations, documents, corpus, or field data.
- For limitations, use only the limitations-related chunks.
- Do not infer typical study limitations such as small sample size, self-report bias, single-location focus, cultural bias, or limited generalizability unless they are explicitly stated as limitations in the chunks.
- If no explicit limitation is stated in the limitations-related chunks, write "not explicitly specified".
"""

    result = await client.chat.completions.create(
        model=OLLAMA_MODEL,
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
        "rag_extraction": result.model_dump(),
    }


async def main():
    research_question = "How does social media shape adolescents' lifeworlds and everyday experiences?"

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    results = []

    for paper in data["papers"]:
        if not paper.get("retrieved_chunks_by_field"):
            print(f"[SKIPPED] No retrieved chunks: {paper.get('title')}")
            continue

        print(f"[RAG EXTRACTION] {paper.get('title')}")

        extraction = await extract_from_retrieved_chunks(
            paper=paper,
            research_question=research_question,
        )

        results.append(extraction)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            {"rag_extracted_papers": results},
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved RAG extraction results to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())