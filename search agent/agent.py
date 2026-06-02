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
        Prompts the LLM to analyze the research topic, infer the core academic discipline,
        and generate highly precise keyword strings while automatically excluding
        irrelevant fields to maximize search precision.
        """
        prompt = f"""
        You are an elite Information Retrieval System Architect 
        specializing in Systematic Literature Reviews.

        Research Topic: "{user_query}"

        Step 1: Identify the academic discipline.

        Step 2: Choose the appropriate framework:
        - Medical/Clinical → PICO (Population, Intervention, Comparison, Outcome)
        - CS/Engineering   → PECO (Problem, Environment, Comparison, Outcome)
        - Social Science   → PCC  (Population, Concept, Context)
        - Humanities/Philosophy/History → FREE KEYWORDS (no framework)

        Step 3: For each element generate 2-3 synonyms/acronyms.

        Step 4: Generate exactly 8 Boolean queries:
        - Queries 1-6: HIGH PRECISION (strict AND between all elements, quoted phrases)
        - Queries 7-8: BROADER RECALL (use OR more liberally, fewer constraints)
          These last 2 queries act as a safety net to capture important papers 
          that might use different terminology.

        RULES:
- CRITICAL SYNTAX: You must use ESCAPED double quotes for multi-word phrases inside the JSON (e.g., \"social media\"). 
- NEVER use single quotes ('').
- NEVER enclose the entire query string in quotes. Only quote the specific multi-word phrases.
- CRITICAL LOGIC RULE: Always use parentheses () to group OR conditions. Example: (\"term1\" OR \"term2\") AND \"term3\".
- Use NOT sparingly — only for clearly unrelated disciplines.
- Output valid JSON only, no markdown formatting.

OUTPUT FORMAT:
{{
    "framework_used": "PICO/PECO/PCC/FREE",
    "analysis": {{
        "population": ["term1", "term2"],
        "intervention": ["term3"],
        "comparison": [],
        "outcome": ["term4", "term5"]
    }},
    "queries": [
        "\"term1\" AND \"term3\" AND \"term4\"",
        "\"term2\" AND \"term3\" AND \"term5\"",
        "strict query 3",
        "strict query 4",
        "strict query 5",
        "strict query 6",
        "(\"term1\" OR \"term2\") AND \"term3\" AND (\"term4\" OR \"term5\")",
        "broader query 8"
    ]
}}
        """

        response = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=SearchQuery,
            temperature=0.0,
            max_retries=3,
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

    async def run_pipeline(self, user_query: str, min_year: int, max_results: int = 20) -> str:
        """
        The main search orchestrator.
        Note: Specific criteria have been removed to broaden the search,
        and the initial relevance score is set to 0 for downstream evaluation.
        """
        print(" Initiating Intelligent Query Expansion...")
        expanded_queries = await self.expand_query(user_query)
        print(f" Executing API keyword searches for: {expanded_queries}")

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

        print(" Preparing candidate batch for the Screening Agent...")

        # Select the top N papers and assign a relevance score of 0
        # This acts as a flag for the downstream Screening Agent to evaluate them later
        top_papers = unique_papers[:max_results]
        for paper in top_papers:
            paper['relevance_score'] = 0

            # Serialize the validated Pydantic model back to a JSON string
        output_schema = ScreenedPapers(papers=top_papers)
        return output_schema.model_dump_json(indent=2)