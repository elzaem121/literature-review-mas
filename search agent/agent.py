import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
import instructor  # Added to support structured outputs on local Ollama

# Internal local imports
from schemas import AcademicQueryExpansionSchema
from api_client import OpenAlexClient


class UniversalAcademicSearchAgent:
    """
    High-Precision Academic Retrieval Agent designed strictly for first-stage retrieval.
    Leverages OpenAlex semantic search with local CPU-side programmatic gatekeeping.
    """

    def __init__(
            self,
            openalex_email: str,
            openalex_api_key: Optional[str] = None,
            model_name: str = "qwen2.5-coder:7b"
    ):
        """
        Initialize the agent with academic database client and local Ollama credentials.
        """
        self.model_name = model_name

        # Patching the standard OpenAI client with Instructor to enforce JSON schema on local models
        self.llm_client = instructor.from_openai(
            OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="local-ollama-key"
            ),
            mode=instructor.Mode.JSON
        )

        self.openalex_client = OpenAlexClient(email=openalex_email, api_key=openalex_api_key)

    def _generate_academic_search_strategy(self, raw_user_query: str) -> Dict[str, Any]:
        """
        Transforms raw, colloquial user input into a dense scientific pseudo-abstract
        and extracts strict programmatic gatekeeping entities using Structured Outputs.
        """
        system_instruction = (
            "You are an expert AI Systems Architect interacting with a dense Vector Embeddings Database (like SPECTER/OpenAlex). "
            "Your objective is to translate the user's natural language question into a 'synthetic_abstract' (150-200 words) "
            "that represents the ideal paper answering this query.\n\n"
            "CRITICAL RULES FOR VECTOR SEARCH OPTIMIZATION:\n"
            "1. IMPLICIT IMRaD STRUCTURE: The paragraph must seamlessly flow from context/background, to methodology, to precise findings.\n"
            "2. MAXIMIZE NOUN DENSITY: Pack the text with exact scientific jargon, methodologies, and technical noun-chunks. Minimize generic verbs.\n"
            "3. POSITIVE FRAMING ONLY: Vector databases struggle with negation. Never use 'without', 'not', or 'avoids'. "
            "Frame concepts positively (e.g., use 'high safety profile' instead of 'without side effects').\n"
            "4. NO FILLER PHRASES: Omit conversational text like 'This paper demonstrates...'. Jump directly into the scientific context."
        )

        try:
            # Using Instructor's overridden create method to directly return the Pydantic model
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": raw_user_query}
                ],
                response_model=AcademicQueryExpansionSchema,
                temperature=0.1
            )
            # Response is already parsed as AcademicQueryExpansionSchema
            return response.model_dump()

        except Exception as e:
            # Safe programmatic fallback in case of local LLM timeout/failure
            print(f" [!] Query expansion failed: {e}. Falling back to tokenized query.")
            fallback_terms = [word for word in raw_user_query.split() if len(word) > 4]
            return {
                "synthetic_abstract": raw_user_query,
                "mandatory_entities": fallback_terms
            }

    # The gatekeeper function is kept in the code for future use, but bypassed in the run cycle
    def _apply_programmatic_gatekeeping_firewall(
            self,
            papers: List[Dict[str, Any]],
            mandatory_entities: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Applies local, highly fast programmatic filters to secure high precision.
        Performs exact case-insensitive match check of LLM extracted keywords.
        """
        validated_papers = []

        for paper in papers:
            title = paper.get("title", "") or ""
            inverted_abstract = paper.get("abstract_inverted_index", {})
            reconstructed_abstract = self.openalex_client.reconstruct_inverted_abstract(inverted_abstract)
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

                validated_papers.append({
                    "openalex_id": paper.get("id"),
                    "doi": paper.get("doi"),
                    "title": title,
                    "abstract": reconstructed_abstract,
                    "publication_year": paper.get("publication_year"),
                    "cited_by_count": paper.get("cited_by_count"),
                    "matched_gatekeeping_entities": matched_entities,
                    "journal": journal_name
                })

        return validated_papers

    def run_precise_retrieval_cycle(
            self,
            user_query: str,
            target_output_count: int = 20,  # Default changed to 20
            min_citations: int = 10,
            start_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes the high-precision retrieval cycle.
        GATEKEEPER IS CURRENTLY BYPASSED for raw semantic search testing.
        """
        print(f"[INFO] Initializing retrieval cycle for query: '{user_query}'")

        # Step 1: Query understanding and pseudo-abstract generation
        strategy = self._generate_academic_search_strategy(user_query)
        print(f"[INFO] Formulated Synthetic Abstract:\n---\n{strategy['synthetic_abstract']}\n---")

        # Step 2: Fetch exactly the target count directly from semantic search
        print(f"[INFO] Querying OpenAlex Semantic Endpoint (Target limit: {target_output_count})...")
        candidate_pool = self.openalex_client.execute_retrieval(
            synthetic_abstract=strategy["synthetic_abstract"],
            limit=target_output_count,  # Fetch exactly 20
            min_citations=min_citations,
            start_year=start_year
        )
        print(f"[INFO] Retrieved {len(candidate_pool)} raw semantic candidate papers.")

        # Step 3: BYPASS GATEKEEPER
        print("[INFO] Gatekeeper is DISABLED. Formatting raw results directly...")

        # Format the raw output slightly to match expected structure
        final_results = []
        for paper in candidate_pool:
            title = paper.get("title", "") or ""
            inverted_abstract = paper.get("abstract_inverted_index", {})
            reconstructed_abstract = self.openalex_client.reconstruct_inverted_abstract(inverted_abstract)

            primary_loc = paper.get("primary_location") or {}
            source = primary_loc.get("source") or {}
            journal_name = source.get("display_name") or "Unknown Venue"

            final_results.append({
                "openalex_id": paper.get("id"),
                "doi": paper.get("doi"),
                "title": title,
                "abstract": reconstructed_abstract,
                "publication_year": paper.get("publication_year"),
                "cited_by_count": paper.get("cited_by_count"),
                "matched_gatekeeping_entities": ["GATEKEEPER_DISABLED"],
                "journal": journal_name
            })

        return final_results[:target_output_count]