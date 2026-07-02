"""
Architecture Agent
──────────────────
Translates parsed requirements into concrete architectural decisions:
  • SQL DDL schema
  • OpenAPI 3.0 contract
  • Component list
  • (For brownfield) impacted files list
"""
from __future__ import annotations

import json
from pydantic import BaseModel, Field

from agents.base_agent import make_llm, timed_stage
from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry
import config


class ArchitectureOutput(BaseModel):
    components: list[str]
    sql_schema: str = Field(description="MySQL DDL CREATE TABLE statement(s)")
    openapi_spec: dict = Field(description="OpenAPI 3.0 spec as a JSON-serialisable dict")
    impacted_files: list[str] = Field(
        default_factory=list,
        description="Filled only for brownfield — relative paths of files to modify",
    )
    design_notes: str


_SYSTEM_PROMPT = f"""\
You are a senior software architect.  The tech stack is fixed:
  • Spring Boot {config.JAVA_PACKAGE} (Java 21)
  • MySQL 8 — schema name: {config.DB_SCHEMA_NAME}
  • Redis 7 (master + replica via Docker Compose)
  • Base62 encoding for short codes (6 chars)

Given the parsed requirements JSON, produce:
1. A list of software components (e.g. "UrlMappingEntity", "UrlShortenerService")
2. MySQL DDL for all required tables
3. A minimal OpenAPI 3.0 spec covering every endpoint
4. (brownfield only) which existing files are impacted
5. Concise design notes explaining key decisions

Return a JSON object matching the ArchitectureOutput schema exactly.
"""


def architecture_agent_node(state: SDLCState) -> dict:
    llm = make_llm()
    structured = llm.with_structured_output(ArchitectureOutput)

    req_json = json.dumps(state["parsed_requirements"], indent=2)

    with timed_stage("design_architecture") as timing:
        result: ArchitectureOutput = structured.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Parsed requirements:\n{req_json}"},
            ]
        )

    arch = result.model_dump()

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="design_architecture",
        event="completed",
        details={
            "components": arch["components"],
            "impacted_files": arch["impacted_files"],
            "elapsed_s": timing["elapsed"],
        },
    )

    return {
        "architecture": arch,
        "current_stage": "architecture_complete",
        "audit_log": [entry],
        "stage_timings": {"design_architecture": timing["elapsed"]},
    }
