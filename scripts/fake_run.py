"""Run one pipeline on the fake surface against the database in DATABASE_URL; print its job id.

Needs REPOSITORY_BACKEND=postgres: on the memory backend the run would vanish with this process.

Used by scripts/restart_check.sh: the compose backend has no fake LLM (the fake answers live in
tests/), so the finished run is created from the host and then read back through the API.
"""

import os
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.fake import (
    fake_download_pdf,
    fake_execute_retrieval,
    fake_pdf_url,
    set_fake_answers,
)
from tests.fakes import default_registry

REQUEST = {
    "research_question": "How do teenagers use social media?",
    "min_year": 2020,
    "inclusion_criteria": ["Studies adolescents"],
    "exclusion_criteria": [],
    "target_output_count": 5,
}


def main() -> None:
    """Start a run through the API app and print its job id once the run has finished."""
    with tempfile.TemporaryDirectory() as pdf_dir, patch.dict(os.environ, {"PDF_DIR": pdf_dir}):
        from src.api.main import app
        from src.llm.settings import get_settings
        from src.pipeline.ingestion import node as ingestion_node
        from src.pipeline.search.api_client import OpenAlexClient

        if get_settings().repository_backend != "postgres":
            raise SystemExit("scripts.fake_run needs REPOSITORY_BACKEND=postgres")
        set_fake_answers(default_registry())
        with (
            patch.object(OpenAlexClient, "execute_retrieval", fake_execute_retrieval),
            patch.object(ingestion_node, "get_openalex_pdf_url", fake_pdf_url),
            patch.object(ingestion_node, "download_pdf", fake_download_pdf),
            TestClient(app) as client,
        ):
            response = client.post("/start_pipeline", json=REQUEST)
            response.raise_for_status()
            print(response.json()["job_id"])


if __name__ == "__main__":
    main()
