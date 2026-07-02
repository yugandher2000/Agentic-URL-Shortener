"""
Central configuration — loaded once at import time.
All agents and tools import from here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
_ORCHESTRATOR_ROOT = Path(__file__).parent
_PROJECT_ROOT = _ORCHESTRATOR_ROOT.parent

_spring_raw = os.getenv("SPRING_PROJECT_PATH", str(_PROJECT_ROOT))
SPRING_PROJECT_PATH: Path = Path(_spring_raw)

SPRING_SRC_PATH: Path = (
    SPRING_PROJECT_PATH
    / "src" / "main" / "java"
    / "com" / "yugandher" / "urlShortener"
)
SPRING_RESOURCES_PATH: Path = SPRING_PROJECT_PATH / "src" / "main" / "resources"
SPRING_TEST_PATH: Path = (
    SPRING_PROJECT_PATH
    / "src" / "test" / "java"
    / "com" / "yugandher" / "urlShortener"
)

# ── LLM (Groq) ────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

# ── Orchestrator ──────────────────────────────────────────────────────────────
MAX_CODING_RETRIES: int = int(os.getenv("MAX_CODING_RETRIES", "3"))
DB_SCHEMA_NAME: str = os.getenv("DB_SCHEMA_NAME", "url_shortener")
JAVA_PACKAGE: str = "com.yugandher.urlShortener"

# ── Audit ─────────────────────────────────────────────────────────────────────
AUDIT_LOG_DIR: Path = _ORCHESTRATOR_ROOT / "audit"
AUDIT_LOG_DIR.mkdir(exist_ok=True)
AUDIT_LOG_PATH: Path = AUDIT_LOG_DIR / "audit.log"
