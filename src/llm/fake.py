"""Fake surface for the `test` profile: LLM, embedder, OpenAlex stub and fixture PDFs."""

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Type, Union

import numpy as np
from pydantic import BaseModel

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
EMBEDDING_DIMENSIONS = 384
FAIL_SENTINEL = "[FAKE:FAIL]"
EXCLUDE_SENTINEL = "[FAKE:EXCLUDE]"
UNCERTAIN_SENTINEL = "[FAKE:UNCERTAIN]"

Messages = List[Dict[str, str]]
RegistryValue = Union[BaseModel, Callable[[Messages], BaseModel]]


class FakeLLM:
    """Stands in for an Instructor client: answers `chat.completions.create` from a registry."""

    def __init__(self, registry: Dict[Type[BaseModel], RegistryValue]):
        self._registry = registry
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(
        self, *, response_model: Type[BaseModel], messages: Messages, **_: Any
    ) -> BaseModel:
        if response_model not in self._registry:
            raise KeyError(f"No fake registered for response model {response_model.__name__}")
        value = self._registry[response_model]
        if callable(value):
            return value(messages)
        return value.model_copy(deep=True)


class FakeEmbedder:
    """Deterministic 384-dimensional embedder: no model download, same text gives same vector."""

    def encode(self, texts: Union[str, List[str]], convert_to_numpy: bool = True) -> np.ndarray:
        """Return one L2-normalized float32 vector per text, seeded from its SHA-256."""
        if isinstance(texts, str):
            texts = [texts]
        return np.stack([self._embed(text) for text in texts])

    @staticmethod
    def _embed(text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        vector = np.random.default_rng(seed).standard_normal(EMBEDDING_DIMENSIONS)
        return (vector / np.linalg.norm(vector)).astype("float32")


def default_registry() -> Dict[Type[BaseModel], RegistryValue]:
    """Canned answers for the three wired roles; screening answers via sentinels in the prompt."""
    from extract_agent.extraction_schemas import ExtractedPaperInfo, ExtractionConfidence
    from Screening_Agent.screening_schemas import PaperScreeningResult, ScreeningDecision
    from search_agent.schemas import AcademicQueryExpansionSchema

    def screen(messages: Messages) -> PaperScreeningResult:
        prompt = messages[-1]["content"]
        if FAIL_SENTINEL in prompt:
            raise RuntimeError("Simulated LLM API error")
        if EXCLUDE_SENTINEL in prompt:
            decision, relevance = ScreeningDecision.EXCLUDE, 2
        elif UNCERTAIN_SENTINEL in prompt:
            decision, relevance = ScreeningDecision.UNCERTAIN, 5
        else:
            decision, relevance = ScreeningDecision.INCLUDE, 8
        return PaperScreeningResult(
            decision=decision,
            confidence_score=8,
            relevance_score=relevance,
            reasoning=f"Fake screening decision: {decision.value}.",
        )

    return {
        AcademicQueryExpansionSchema: AcademicQueryExpansionSchema(
            synthetic_abstract=(
                "Social media use among adolescents shapes identity, peer relations and wellbeing."
            ),
            mandatory_entities=["social media", "adolescents", "wellbeing"],
        ),
        PaperScreeningResult: screen,
        ExtractedPaperInfo: ExtractedPaperInfo(
            paper_type="qualitative interview study",
            method="semi-structured interviews",
            dataset="interviews with adolescents",
            task="how adolescents experience social media",
            main_findings="Adolescents use social media to negotiate identity and belonging.",
            limitations="not explicitly specified",
            relevance_to_research_question="Directly addresses the research question.",
            confidence=ExtractionConfidence.MEDIUM,
        ),
    }


def fake_execute_retrieval(
    self: Any,
    synthetic_abstract: str,
    limit: int = 50,
    min_citations: int = 5,
    start_year: int | None = None,
) -> List[Dict[str, Any]]:
    """Replacement for `OpenAlexClient.execute_retrieval`: raw work dicts from the fixture file."""
    works = json.loads((FIXTURES_DIR / "openalex_works.json").read_text(encoding="utf-8"))
    return works[:limit]


def fake_pdf_url(doi: str | None) -> str | None:
    """Replacement for the DOI-to-PDF-URL lookup: a stable fake URL for any DOI."""
    return f"https://fixtures.invalid/doi/{doi}" if doi else None


def fake_download_pdf(url: str, output_path: Path) -> bool:
    """Replacement for the PDF download: copy one of the two fixture PDFs, chosen by file name."""
    index = hashlib.sha256(output_path.name.encode("utf-8")).digest()[0] % 2 + 1
    shutil.copyfile(FIXTURES_DIR / f"paper_small_{index}.pdf", output_path)
    return True
