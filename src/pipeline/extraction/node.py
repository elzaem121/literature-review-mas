from src.llm.client import get_llm
from src.llm.prompts.extraction import SYSTEM_PROMPT, render_user_prompt
from src.llm.settings import get_settings
from src.llm.tracing import traceable_stage
from src.pipeline.extraction.schemas import ExtractedPaperInfo


async def extract_from_retrieved_chunks(paper, research_question: str):
    paper_info = paper.get("paper", paper)
    retrieved_chunks_by_field = (
        paper.get("retrieved_chunks_by_field") or paper_info.get("retrieved_chunks_by_field") or {}
    )

    result = await get_llm("extraction").chat.completions.create(
        model=get_settings().extraction_model,
        response_model=ExtractedPaperInfo,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": render_user_prompt(
                    research_question=research_question,
                    title=paper_info.get("title"),
                    retrieved_chunks_by_field=retrieved_chunks_by_field,
                ),
            },
        ],
        temperature=0,
    )

    return {
        "paper": {
            "title": paper_info.get("title"),
            "year": paper_info.get("year"),
            "authors": paper_info.get("authors"),
            "doi": paper_info.get("doi"),
            "url": paper_info.get("url"),
        },
        "rag_extraction": result.model_dump(),
    }


@traceable_stage("extraction")
async def extraction_node(state: dict) -> dict:
    """
    LangGraph Node: Extracts structured information from the screened papers.
    """
    print("--- RUNNING EXTRACTION AGENT ---")

    research_question = state.get("research_question", "")

    # 1. Retrieve only the papers accepted from the Screening phase
    screening_results = state.get("screening_results", {})

    included_papers = screening_results.get("included_papers", [])

    results = []

    # 2. Iterate through the accepted papers and extract data
    for paper in included_papers:
        paper_info = paper.get("paper", paper)

        if "pdf_path" not in paper and "pdf_path" not in paper_info:
            print(f"[SKIPPED] No PDF available for extraction: {paper_info.get('title')}")
            continue

        retrieved_chunks_by_field = paper.get("retrieved_chunks_by_field") or paper_info.get(
            "retrieved_chunks_by_field"
        )

        if not retrieved_chunks_by_field:
            print(f"[SKIPPED] No retrieved chunks: {paper_info.get('title')}")
            continue

        print(f"[RAG EXTRACTION] {paper_info.get('title')}")

        extraction = await extract_from_retrieved_chunks(
            paper=paper,
            research_question=research_question,
        )

        results.append(extraction)

    # 3. Return the results to update the PipelineState and UI tracking
    return {
        "extracted_papers": results,
        "current_step": "completed",
        "status_message": "Extraktion abgeschlossen! (Daten sind bereit)",
    }
