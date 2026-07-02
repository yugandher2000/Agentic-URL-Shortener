"""
Shared utilities for all agents.

Every agent:
  1. Creates an LLM with `make_llm()`
  2. Logs entry/exit via `make_audit_entry()`
  3. Records timing via `timed_stage()`
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from langchain_groq import ChatGroq

import config
from tools.audit_logger import make_audit_entry  # noqa: F401  (re-exported)


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
