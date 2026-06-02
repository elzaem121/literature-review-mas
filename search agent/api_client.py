import httpx
import asyncio
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential


class OpenAlexClient:
    def __init__(self, email: str = "agent@example.com"):
        # Utilizing the 'mailto' header grants access to OpenAlex's polite pool,
        # which offers significantly faster response times and higher rate limits.
        self.headers = {"User-Agent": f"AcademicSearchAgent/1.0 (mailto:{email})"}
        self.base_url = "https://api.openalex.org/works"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def search_papers(self, query: str, min_year: int = None) -> List:
        """
        Executes an asynchronous HTTP GET request to fetch papers based on the search query.
        Implements a targeted search strategy using metadata filtering to maximize Precision@10.
        """

        # Base parameters for pagination, sorting, and field selection
        params = {
            "per-page": 50,  # Limit payload to top 20 results per expanded query
            "sort": "relevance_score:desc",  # Native API sorting as a baseline
            # Only request necessary fields to conserve memory and bandwidth
            "select": "id,doi,title,abstract_inverted_index,authorships,publication_year,primary_location"
        }

        # Build deterministic inclusion criteria directly at the API level.
        # Using 'title_and_abstract.search' prevents the API from searching in full-text
        # or references, significantly reducing noise (False Positives).
        # 'type:article' ensures we only retrieve academic research papers, excluding books/datasets.
        filters = [
            f"title_and_abstract.search:{query}",
            "type:article"
        ]

        # Append publication year filter if specified
        if min_year:
            filters.append(f"publication_year:>{min_year}")

        # Combine filters using comma (OpenAlex API syntax for logical AND conditions)
        params["filter"] = ",".join(filters)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    def _reconstruct_abstract(self, inverted_index: Dict) -> str:
        """
        OpenAlex compresses abstracts into an inverted index format.
        This utility function reconstructs the original abstract string.
        """
        if not inverted_index:
            return "No abstract available."

        words = []
        for word, positions in inverted_index.items():
            for pos in positions:
                words.append((pos, word))

        # Sort words based on their original positional indices
        words.sort(key=lambda x: x[0])
        return " ".join([word for _, word in words])

    def parse_results(self, raw_results: List) -> List:
        """
        Transforms complex raw API data into a flat, standardized dictionary format
        suitable for LLM evaluation.
        """
        parsed = []
        for item in raw_results:
            authorships = item.get("authorships") or []
            authors = [a.get("author", {}).get("display_name", "") for a in authorships]

            primary_loc = item.get("primary_location") or {}
            url = primary_loc.get("landing_page_url")

            parsed.append({
                "title": item.get("title") or "Untitled",
                "abstract": self._reconstruct_abstract(item.get("abstract_inverted_index")),
                "year": item.get("publication_year"),
                "authors": authors,
                "doi": item.get("doi"),
                "url": url,
            })
        return parsed