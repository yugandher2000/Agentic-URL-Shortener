"""
Security Agent
──────────────
Scans the generated Java source files for OWASP Top 10 vulnerabilities.

Uses the LLM to reason about security issues across the generated codebase,
then returns a structured report with risk level and actionable findings.

Runs in PARALLEL with Documentation Agent after human approval.
"""
from __future__ import annotations

import json
from typing import Literal
from pydantic import BaseModel, Field

from agents.base_agent import make_llm, timed_stage
from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry
from tools.file_tools import read_project_file


class _FindingOut(BaseModel):
    owasp_category: str = Field(description="e.g. A03:Injection")
    file: str
    description: str
    recommendation: str
    severity: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")


class SecurityOutput(BaseModel):
    risk_level: str = Field(description="Overall risk: LOW | MEDIUM | HIGH | CRITICAL")
    findings: list[_FindingOut]
    owasp_checks: dict = Field(
        description="Keys A01–A10, values PASS or FAIL"
    )
    summary: str


_SYSTEM_PROMPT = """\
You are an application security engineer conducting an OWASP Top 10 code review.

Review the provided Java source files for:
  A01 Broken Access Control       — missing auth checks, IDOR
  A02 Cryptographic Failures      — sensitive data in logs/plain text
  A03 Injection                   — SQL injection, log injection
  A05 Security Misconfiguration   — CORS wildcard, exposed actuator endpoints
  A07 Auth & Session Failures     — hardcoded credentials
  A09 Security Logging Failures   — missing audit on sensitive operations

For each finding include the filename, a clear description, and a concrete fix.
Determine the overall risk level (use the highest single finding).
Return a JSON object matching the SecurityOutput schema.
"""


def security_agent_node(state: SDLCState) -> dict:
    llm = make_llm()
    structured = llm.with_structured_output(SecurityOutput)

    # Gather generated source files for review
    code_snippets: list[str] = []
    for gf in (state.get("generated_files") or []):
        if gf["language"] == "java":
            try:
                content = read_project_file(gf["path"])
                code_snippets.append(f"// FILE: {gf['path']}\n{content}")
            except Exception:
                code_snippets.append(f"// FILE: {gf['path']}\n[could not read]")

    code_block = "\n\n".join(code_snippets) if code_snippets else "[no Java files found]"

    with timed_stage("security_scan") as timing:
        result: SecurityOutput = structured.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Source files to review:\n\n{code_block}"},
            ]
        )

    report = result.model_dump()
    report["approved"] = report["risk_level"] in ("LOW", "MEDIUM")

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="security_scan",
        event="completed",
        details={
            "risk_level":    report["risk_level"],
            "findings_count": len(report["findings"]),
            "approved":       report["approved"],
            "elapsed_s":      timing["elapsed"],
        },
    )

    return {
        "security_report": report,
        "current_stage":   "security_complete",
        "audit_log":       [entry],
        "stage_timings":   {"security_scan": timing["elapsed"]},
    }
