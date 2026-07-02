"""
Documentation Agent
───────────────────
Generates:
  • README.md content
  • OpenAPI YAML (from architecture spec)
  • Setup instructions (local + Docker)

Runs in PARALLEL with Security Agent after human approval.
"""
from __future__ import annotations

import json
from pydantic import BaseModel

from agents.base_agent import make_llm, timed_stage
from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry
import config


class DocsOutput(BaseModel):
    readme_content: str
    api_docs_yaml: str
    setup_instructions: str


_SYSTEM_PROMPT = f"""\
You are a technical writer for a software engineering team.

Generate documentation for a URL shortener service:
1. README.md  — include: project overview, architecture diagram (ASCII),
   API endpoints table, quick-start, environment variables, and caveats.
2. api-docs.yaml — a complete OpenAPI 3.0 YAML document derived from the
   OpenAPI spec in the architecture JSON.
3. setup.md  — step-by-step local dev setup:
   MySQL (localhost:3306, user root/root, schema url_shortener),
   Redis via Docker Compose, mvn spring-boot:run.

Base URL: {config.SPRING_PROJECT_PATH} (local dev)
Java package: {config.JAVA_PACKAGE}

Be concise but complete.  Return a JSON object matching DocsOutput.
"""


def documentation_agent_node(state: SDLCState) -> dict:
    llm = make_llm(temperature=0.2)
    structured = llm.with_structured_output(DocsOutput)

    context = {
        "parsed_requirements": state.get("parsed_requirements"),
        "architecture":        state.get("architecture"),
        "generated_files":     [f["path"] for f in (state.get("generated_files") or [])],
        "test_results":        state.get("test_results"),
    }

    with timed_stage("generate_docs") as timing:
        result: DocsOutput = structured.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Context:\n{json.dumps(context, indent=2)}"},
            ]
        )

    docs = result.model_dump()

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="generate_docs",
        event="completed",
        details={"elapsed_s": timing["elapsed"]},
    )

    return {
        "documentation":  docs,
        "current_stage":  "docs_complete",
        "audit_log":      [entry],
        "stage_timings":  {"generate_docs": timing["elapsed"]},
    }
