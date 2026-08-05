import requests
import time
from typing import List, Dict, Any, Optional


class OpenAlexClient:
    """
    Handles all external HTTP communication with the OpenAlex semantic search API,
    including pagination, rate limiting, and data reconstruction.
    """

    def __init__(self, email: str, api_key: Optional[str] = None):
        self.email = email
        self.api_key = api_key
        self.base_url = "https://api.openalex.org/works"

    def reconstruct_inverted_abstract(self, inverted_index: Optional[Dict[str, List[int]]]) -> str:
        """
        Reconstructs the original abstract plain-text from the OpenAlex inverted index representation.
        Required to bypass legal and copyright indexation constraints programmatically.
        """
        if not inverted_index:
            return ""

        try:
            # Flatten positions to find correct array size
            all_positions = []
            for positions in inverted_index.values():
                all_positions.extend(positions)

            if not all_positions:
                return ""

            max_pos = max(all_positions)
            abstract_tokens = [""] * (max_pos + 1)

            for word, positions in inverted_index.items():
                for pos in positions:
                    if pos < len(abstract_tokens):
                        abstract_tokens[pos] = word

            return " ".join(abstract_tokens).strip()
        except Exception as e:
            print(f" Failed to reconstruct abstract index: {e}")
            return ""

    def execute_retrieval(
            self,
            synthetic_abstract: str,
            limit: int = 50,
            min_citations: int = 5,
            start_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a semantic search query against the OpenAlex REST API.
        Applies metadata filters locally since Semantic Search API restricts them.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # [FIX]: Only use strictly supported filters by the Semantic API endpoint
        #api_filters = "has_abstract:true,type:journal-article|preprint"
            # [FIX]: Only use strictly supported filters by the Semantic API endpoint
        api_filters = "has_abstract:true,type:journal-article|preprint,is_oa:true"

        params = {
            "search.semantic": synthetic_abstract,
            "filter": api_filters,
            "per_page": 50,  # Fetch max allowed to buffer our local filtering
            "page": 1,
            "mailto": self.email
        }

        retrieved_documents = []

        while len(retrieved_documents) < limit:
            try:
                response = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    timeout=20
                )

                if response.status_code == 429:
                    print(" Rate limit encountered. Sleeping for 2 seconds...")
                    time.sleep(2)
                    continue

                if response.status_code != 200:
                    print(f" OpenAlex returned status code {response.status_code}: {response.text}")
                    break

                payload = response.json()
                results = payload.get("results", [])

                if not results:
                    break

                for doc in results:
                    # [FIX]: Local Programmatic Filtering for Citations and Year
                    pub_year = doc.get("publication_year") or 0
                    citations = doc.get("cited_by_count") or 0

                    primary_loc = doc.get("primary_location") or {}
                    best_oa = doc.get("best_oa_location") or {}

                    pdf_url = primary_loc.get("pdf_url") or best_oa.get("pdf_url")

                    if not pdf_url:
                        continue

                    if start_year and pub_year < start_year:
                        continue
                    if min_citations > 0 and citations < min_citations:
                        continue

                    retrieved_documents.append(doc)
                    if len(retrieved_documents) >= limit:
                        break

                # Use standard page increment
                params["page"] += 1

                # Semantic search maxes out at 50-100 results usually, break if no more pages
                meta = payload.get("meta", {})
                if meta.get("page") * meta.get("per_page") >= meta.get("count"):
                    break

            except requests.exceptions.RequestException as e:
                print(f" Connection to academic API failed: {e}")
                break

        return retrieved_documents