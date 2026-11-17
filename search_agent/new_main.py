from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from src.llm.settings import get_settings

from .agent import UniversalAcademicSearchAgent

OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY") or None


async def main(
    research_question=None,
    min_year=None,
    inclusion_criteria=None,
    exclusion_criteria=None,
    additional_info=None,
    user_query=None,
    criteria=None,
    target_output_count=25,
    min_citations=0,
    save_to_file=False,
    output_path=".mas_runs/search_results.json",
    progress_callback=None,
) -> dict:
    """
    Search-Agent EntryPoint für die Streamlit-HITL-App.

    Gibt ein Dict im Format {"papers": [...]} zurück.
    Keine direkte Kopplung an den Screening-Agent-Pfad.
    """

    query = research_question or user_query
    if not query:
        raise ValueError("research_question oder user_query fehlt.")

    query_parts = [query]

    # Positive Einschlusskriterien dürfen die Suche verbessern.
    # Ausschlusskriterien lieber NICHT in die Suche geben, sondern dem Screening Agent überlassen.
    if inclusion_criteria:
        query_parts.append("Relevant inclusion focus:")
        query_parts.extend(inclusion_criteria)

    if criteria:
        query_parts.append("Relevant criteria:")
        query_parts.append(criteria)

    if additional_info:
        query_parts.append("Additional context:")
        query_parts.append(additional_info)

    expanded_query = "\n".join(query_parts)

    settings = get_settings()
    search_agent = UniversalAcademicSearchAgent(
        openalex_email=settings.openalex_email,
        openalex_api_key=OPENALEX_API_KEY,
        model_name=settings.search_model,
    )
    if progress_callback:
        progress_callback("Search Agent initialisiert.")
    results = await search_agent.run_precise_retrieval_cycle(
        user_query=expanded_query,
        target_output_count=target_output_count,
        min_citations=min_citations,
        start_year=min_year,
        progress_callback=progress_callback,
    )

    if save_to_file:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    return results


if __name__ == "__main__":
    result = asyncio.run(
        main(
            research_question="What are the risks when AI systems that plan and act on their own are deployed in healthcare, and how are these risks currently managed?",
            min_year=2018,
            target_output_count=20,
            min_citations=0,
            save_to_file=True,
        )
    )
    print(f"[SUCCESS] Retrieved {len(result.get('papers', []))} papers.")
