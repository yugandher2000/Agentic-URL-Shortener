"""
Requirement Agent
─────────────────
Parses raw requirement text into a structured engineering spec.

Handles three scenario types:
  greenfield  — new system, full pipeline
  brownfield  — enhancement to existing code
  ambiguous   — unclear intent; flags unknowns and documents assumptions
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agents.base_agent import make_llm, now_iso, timed_stage, invoke_structured
from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry

# ── Structured output schema ──────────────────────────────────────────────────

class _EndpointOut(BaseModel):
    method: str
    path: str
    description: str

class _ColumnOut(BaseModel):
    name: str
    sql_type: str
    nullable: bool
    primary_key: bool

class _DataModelOut(BaseModel):
    table_name: str
    columns: list[_ColumnOut]

class RequirementOutput(BaseModel):
    feature_name: str
    scenario_type: str = Field(description="greenfield | brownfield | ambiguous")
    description: str
    endpoints: list[_EndpointOut]
    data_model: _DataModelOut
    caching_strategy: str
    ambiguities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]


_SYSTEM_PROMPT = """\
You are a senior requirements engineer for a URL shortener service built with
Spring Boot (Java 21), MySQL, and Redis.

Analyse the given requirement and classify it as one of:
  • greenfield  — building from scratch
  • brownfield  — modifying existing code
  • ambiguous   — unclear intent

For ambiguous requirements, list open questions in `ambiguities` and document
your best-guess assumptions in `assumptions`.

Return a JSON object matching the RequirementOutput schema exactly.
"""

# ── Node function ─────────────────────────────────────────────────────────────

def requirement_agent_node(state: SDLCState) -> dict:
    llm = make_llm()

    with timed_stage("parse_requirements") as timing:
        result: RequirementOutput = invoke_structured(
            llm, RequirementOutput, _SYSTEM_PROMPT,
            f"Requirement:\n{state['requirement']}",
        )

    parsed = result.model_dump()

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="parse_requirements",
        event="completed",
        details={
            "scenario_type": parsed["scenario_type"],
            "endpoints_found": len(parsed["endpoints"]),
            "ambiguities_found": len(parsed["ambiguities"]),
            "elapsed_s": timing["elapsed"],
        },
    )

    return {
        "parsed_requirements": parsed,
        "current_stage": "requirements_complete",
        "audit_log": [entry],
        "stage_timings": {"parse_requirements": timing["elapsed"]},
    }
