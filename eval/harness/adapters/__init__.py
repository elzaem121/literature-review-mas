"""Adapters wrap one pipeline version in the harness contract; scoring never sees the pipeline."""

from typing import Any, Protocol

from eval.harness.adapters.phase1 import Phase1Adapter
from eval.harness.records import ExtractionOutput, RetrievedChunk, ScreeningRecord, SearchRecord
from eval.harness.topics import Topic


class Adapter(Protocol):
    """The four calls of the harness contract, plus what a run records about the system."""

    name: str

    async def search(self, topic: Topic) -> SearchRecord:
        """Search for a topic and return the ranked papers with how the query was built."""
        ...

    async def screen(self, papers: list[dict[str, Any]], topic: Topic) -> list[ScreeningRecord]:
        """Screen papers; one record per paper, in input order."""
        ...

    def retrieve(self, paper_key: str, pages: list[str]) -> list[RetrievedChunk]:
        """Retrieve the chunks per scored field from the page text of one paper."""
        ...

    async def extract(
        self, paper: dict[str, Any], chunks: list[RetrievedChunk], topic: Topic
    ) -> ExtractionOutput:
        """Extract the scored fields of one paper from its retrieved chunks."""
        ...

    def provenance(self) -> dict[str, Any]:
        """The models, prompt versions and retrieval settings of this pipeline version."""
        ...


ADAPTERS: dict[str, type[Adapter]] = {Phase1Adapter.name: Phase1Adapter}


def get_adapter(name: str) -> Adapter:
    """Return a new adapter by name; an unknown name lists the known ones."""
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter '{name}'; expected one of {sorted(ADAPTERS)}")
    return ADAPTERS[name]()
