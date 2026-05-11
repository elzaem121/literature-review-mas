import asyncio
import instructor
from openai import AsyncOpenAI
from typing import List, Dict

from schemas import SearchQuery, ScreenedPapers, ResearchPaper
from api_client import OpenAlexClient


class AcademicSearchAgent:
    def __init__(self, model_name: str = "qwen2.5-coder:7b"):
        self.model_name = model_name

        # Patch the OpenAI-compatible client to strictly output JSON matching Pydantic schemas.
        # Ensure Ollama is running locally on port 11434.
        self.client = instructor.patch(
            AsyncOpenAI(
                base_url="http://localhost:11434/v1",
                api_key="local-ollama-key"
            ),
            mode=instructor.Mode.JSON
        )
        self.api = OpenAlexClient()

    async def expand_query(self, user_query: str) -> List[str]:
        """
        Executes multi-query expansion to overcome vocabulary mismatch.
        """
        prompt = f"""
        You are a highly skilled academic research assistant. 
        The user intends to research the following topic: "{user_query}"

        Your task is to generate 3 to 5 distinct, high-quality search queries. 
        Include academic synonyms, formal terminology, and related concepts to 
        maximize the retrieval recall of relevant research papers.
        """

        response = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=SearchQuery,
            messages=[{"role": "system", "content": prompt}]
        )
        return response.queries

    def deduplicate_papers(self, papers: List) -> List:
        """
        Simplified filtering to eliminate duplicate entries using exact match via DOI.
        """
        unique_papers = []
        seen_dois = set()

        for paper in papers:
            doi = paper.get("doi")
            if doi:
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)

            unique_papers.append(paper)

        return unique_papers

    async def run_pipeline(self, user_query: str, min_year: int, criteria: str) -> str:
        """
        The simplified orchestrator method for the MVP.
        Returns a strict JSON string ready for consumption by the Screening Agent.
        """
        print(" Initiating Intelligent Query Expansion...")
        expanded_queries = await self.expand_query(user_query)
        expanded_queries.append(user_query)
        print(f" Executing searches for: {expanded_queries}")

        print(" Fetching data concurrently from OpenAlex API...")
        fetch_tasks = [self.api.search_papers(q, min_year) for q in expanded_queries]
        raw_results_nested = await asyncio.gather(*fetch_tasks)

        all_parsed_papers = []
        for raw_batch in raw_results_nested:
            # Ensure the batch contains data before parsing
            if raw_batch:
                all_parsed_papers.extend(self.api.parse_results(raw_batch))

        print(f" Deduplicating {len(all_parsed_papers)} retrieved papers...")
        unique_papers = self.deduplicate_papers(all_parsed_papers)
        print(f" Deduplication complete. {len(unique_papers)} unique papers remain.")

        print(" Bypassing LLM Evaluation for MVP. Selecting top 10 papers...")

        # Select top 10 papers and assign a mock relevance score to satisfy Pydantic schema requirements
        top_10_papers = unique_papers[:10]
        for paper in top_10_papers:
            paper['relevance_score'] = 10

            # Serialize the validated Pydantic model back to a JSON string
        output_schema = ScreenedPapers(papers=top_10_papers)
        return output_schema.model_dump_json(indent=2)