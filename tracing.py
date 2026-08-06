"""Optional LangSmith tracing helpers.

Tracing is enabled only when LANGSMITH_API_KEY is set in the environment.
When it is absent (or the langsmith package is unavailable), every helper
here is a no-op / passthrough, so the pipeline behaves exactly as it does
without this module: same call sites, same return values, no added latency,
no import failures.
"""
import os
from contextlib import nullcontext

try:
    from langsmith import traceable as _traceable
    from langsmith.run_helpers import trace as _trace
    from langsmith.wrappers import wrap_openai as _wrap_openai
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False


def tracing_enabled() -> bool:
    """True only when langsmith is importable and LANGSMITH_API_KEY is set."""
    return _LANGSMITH_AVAILABLE and bool(os.getenv("LANGSMITH_API_KEY"))


def maybe_wrap_openai(client):
    """Wrap a raw OpenAI/AsyncOpenAI client for LangSmith tracing, if enabled.

    Must be called on the client BEFORE instructor.from_openai()/patch() wraps
    it, so the traced layer sits below instructor's patching and captures
    every real HTTP call it makes (including instructor's internal retries),
    with latency and token usage read straight off the response.
    """
    if not tracing_enabled():
        return client
    return _wrap_openai(client)


def traceable_stage(name: str):
    """Decorator marking one LangGraph node function as a single stage span.

    Returns the function completely unmodified when tracing is disabled.
    """
    def decorator(fn):
        if not tracing_enabled():
            return fn
        return _traceable(name=name, run_type="chain")(fn)
    return decorator


def root_trace(job_id: str):
    """Context manager (supports both `with` and `async with`) for the
    per-pipeline-run root trace, tagged with the Backend job_id so a run in
    the Streamlit UI maps to a run in LangSmith.

    Falls back to a no-op context manager when tracing is disabled.
    """
    if not tracing_enabled():
        return nullcontext()
    return _trace(
        name="pipeline_run",
        run_type="chain",
        project_name=os.getenv("LANGSMITH_PROJECT"),
        tags=[f"job_id:{job_id}"],
        metadata={"job_id": job_id},
    )
