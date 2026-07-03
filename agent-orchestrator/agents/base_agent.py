"""
Shared utilities for all agents.

Every agent:
  1. Creates an LLM with `make_llm()`
  2. Logs entry/exit via `make_audit_entry()`
  3. Records timing via `timed_stage()`
"""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Type, TypeVar

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

import config
from tools.audit_logger import make_audit_entry  # noqa: F401  (re-exported)

T = TypeVar("T", bound=BaseModel)


def make_llm(temperature: float = 0.0) -> ChatGroq:
    """Return a configured Groq LLM instance."""
    if not config.GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.  Copy .env.example → .env and add your key."
        )
    return ChatGroq(
        model=config.LLM_MODEL,
        temperature=temperature,
        api_key=config.GROQ_API_KEY,
    )


def invoke_structured(
    llm: ChatGroq,
    schema: Type[T],
    system_prompt: str,
    user_content: str,
) -> T:
    """
    Call the LLM and parse its response as a Pydantic model.
    Embeds the JSON schema in the prompt so function-calling is not needed.
    Works with any Groq model regardless of tool-call support.
    """
    schema_str = json.dumps(schema.model_json_schema(), indent=2)
    augmented_system = (
        f"{system_prompt}\n\n"
        "=== OUTPUT FORMAT ===\n"
        "Respond with ONLY a valid JSON object (no markdown, no explanation) "
        "matching this JSON Schema exactly:\n"
        f"{schema_str}"
    )
    response = llm.invoke([
        SystemMessage(content=augmented_system),
        HumanMessage(content=user_content),
    ])
    raw = response.content.strip()
    # Strip optional markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    parsed = json.loads(match.group() if match else raw, strict=False)
    return schema.model_validate(parsed)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def timed_stage(stage_name: str) -> Generator[dict, None, None]:
    """
    Context manager that measures wall-clock time for a stage.

    Usage:
        with timed_stage("generate_code") as timing:
            ...do work...
        # timing["elapsed"] is available after the block
    """
    timing: dict = {}
    start = time.perf_counter()
    try:
        yield timing
    finally:
        timing["elapsed"] = round(time.perf_counter() - start, 2)
        timing["stage"] = stage_name
