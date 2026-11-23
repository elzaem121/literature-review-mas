import asyncio
import re
from typing import Any, Dict, List, Optional

from src.llm.client import get_llm
from src.llm.prompts.search import SYSTEM_PROMPT
from src.pipeline.search.api_client import OpenAlexClient

# Internal local imports
from src.pipeline.search.schemas import AcademicQueryExpansionSchema

OPENALEX_ID_PREFIX = "https://openalex.org/"


def _emit(self, message: str, progress_callback=None) -> None:
    print(message)
    if progress_callback:
        progress_callback(message)


def format_openalex_work(work: Dict[str, Any], client: OpenAlexClient) -> Dict[str, Any]:
    """Turn one raw OpenAlex work into the paper dict the search node returns."""
    inverted_abstract = work.get("abstract_inverted_index", {})
    authors = []
    for authorship in work.get("authorships", []):
        author_name = authorship.get("author", {}).get("display_name")
        if author_name:
            authors.append(author_name)

    primary_loc = work.get("primary_location") or {}
    best_oa = work.get("best_oa_location") or {}
    openalex_id = work.get("id")

    return {
        "title": work.get("title", "") or "",
        "abstract": client.reconstruct_inverted_abstract(inverted_abstract),
        "year": work.get("publication_year"),
        "authors": authors,
        "doi": work.get("doi"),
        "url": work.get("id") or work.get("doi"),
        "relevance_score": 0,
        "openalex_id": openalex_id.removeprefix(OPENALEX_ID_PREFIX) if openalex_id else None,
        "pdf_url": primary_loc.get("pdf_url") or best_oa.get("pdf_url"),
        "venue": (primary_loc.get("source") or {}).get("display_name"),
    }


class UniversalAcademicSearchAgent:
    """
    High-Precision Academic Retrieval Agent designed strictly for first-stage retrieval.
    Leverages OpenAlex semantic search with local CPU-side programmatic gatekeeping.
    """

    def __init__(
        self,
        openalex_email: str,
        model_name: str,
        openalex_api_key: Optional[str] = None,
    ):
        """
        Initialize the agent with academic database client and the search-role LLM.
        """
        self.model_name = model_name
        self.llm_client = get_llm("search")
        self.openalex_client = OpenAlexClient(email=openalex_email, api_key=openalex_api_key)

    async def _generate_academic_search_strategy(self, raw_user_query: str) -> Dict[str, Any]:
        """
        Transforms raw, colloquial user input into a dense scientific pseudo-abstract
        and extracts strict programmatic gatekeeping entities using Structured Outputs.
        """
        try:
            # Using Instructor's overridden create method to directly return the Pydantic model
            response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw_user_query},
                ],
                response_model=AcademicQueryExpansionSchema,
                temperature=0.1,
            )
            # Response is already parsed as AcademicQueryExpansionSchema
            return {**response.model_dump(), "fallback_used": False}

        except Exception as e:
            # Safe programmatic fallback in case of local LLM timeout/failure
            print(f" [!] Query expansion failed: {e}. Falling back to tokenized query.")
            fallback_terms = [word for word in raw_user_query.split() if len(word) > 4]
            return {
                "synthetic_abstract": raw_user_query,
                "mandatory_entities": fallback_terms,
                "fallback_used": True,
            }

    # The gatekeeper function is kept in the code for future use, but bypassed in the run cycle
    def _apply_programmatic_gatekeeping_firewall(
        self, papers: List[Dict[str, Any]], mandatory_entities: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Applies local, highly fast programmatic filters to secure high precision.
        Performs exact case-insensitive match check of LLM extracted keywords.
        """
        validated_papers = []

        for paper in papers:
            title = paper.get("title", "") or ""
            inverted_abstract = paper.get("abstract_inverted_index", {})
            reconstructed_abstract = self.openalex_client.reconstruct_inverted_abstract(
                inverted_abstract
            )
            search_corpus = f"{title} {reconstructed_abstract}".lower()

            matched_entities = []
            for entity in mandatory_entities:
                cleaned_entity = entity.lower().strip()
                pattern = re.compile(rf"\b{re.escape(cleaned_entity)}\b")

                if pattern.search(search_corpus) or cleaned_entity in search_corpus:
                    matched_entities.append(entity)

            if len(matched_entities) >= 1:
                primary_loc = paper.get("primary_location") or {}
                source = primary_loc.get("source") or {}
                journal_name = source.get("display_name") or "Unknown Venue"

                validated_papers.append(
                    {
                        "openalex_id": paper.get("id"),
                        "doi": paper.get("doi"),
                        "title": title,
                        "abstract": reconstructed_abstract,
                        "publication_year": paper.get("publication_year"),
                        "cited_by_count": paper.get("cited_by_count"),
                        "matched_gatekeeping_entities": matched_entities,
                        "journal": journal_name,
                    }
                )

        return validated_papers

    async def run_precise_retrieval_cycle(
        self,
        user_query: str,
        target_output_count: int = 20,
        min_citations: int = 10,
        start_year: Optional[int] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Executes the high-precision retrieval cycle.
        GATEKEEPER IS CURRENTLY BYPASSED for raw semantic search testing.
        """
        print(f"[INFO] Initializing retrieval cycle for query: '{user_query}'")

        # Step 1: Query understanding and pseudo-abstract generation
        strategy = await self._generate_academic_search_strategy(user_query)
        print(f"[INFO] Formulated Synthetic Abstract:\n---\n{strategy['synthetic_abstract']}\n---")

        # Step 2: Fetch exactly the target count directly from semantic search
        print(
            f"[INFO] Querying OpenAlex Semantic Endpoint (Target limit: {target_output_count})..."
        )
        candidate_pool = await asyncio.to_thread(
            self.openalex_client.execute_retrieval,
            synthetic_abstract=strategy["synthetic_abstract"],
            limit=target_output_count,  # Fetch exactly 20
            min_citations=min_citations,
            start_year=start_year,
        )
        print(f"[INFO] Retrieved {len(candidate_pool)} raw semantic candidate papers.")
        # Step 3: BYPASS GATEKEEPER
        print("[INFO] Gatekeeper is DISABLED. Formatting raw results directly...")

        papers = [format_openalex_work(work, self.openalex_client) for work in candidate_pool]

        # Prune the results to match the exact target output count
        return {
            "papers": papers[:target_output_count],
            "synthetic_abstract": strategy["synthetic_abstract"],
            "fallback_used": strategy["fallback_used"],
        }
