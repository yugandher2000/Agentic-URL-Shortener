"""
Testing Agent
─────────────
Runs `mvn test` against the Spring Boot project and parses Surefire output.

No LLM is needed here — this is pure deterministic tool execution.
The test results (pass/fail + failure details) feed back into the graph
router so the Coding Agent can fix issues on retry.
"""
from __future__ import annotations

import re

from agents.base_agent import timed_stage
from orchestrator.state import SDLCState, TestResults
from tools.audit_logger import make_audit_entry
from tools.test_runner import run_maven_tests


# ── Surefire output parsers ───────────────────────────────────────────────────

_RESULTS_RE = re.compile(
    r"Tests run:\s*(?P<total>\d+),\s*Failures:\s*(?P<failures>\d+),"
    r"\s*Errors:\s*(?P<errors>\d+),\s*Skipped:\s*(?P<skipped>\d+)"
)
_FAILURE_RE = re.compile(r"FAILED\s+(?P<test>\S+)")


def _parse_results(stdout: str) -> TestResults:
    totals = {"total": 0, "failures": 0, "errors": 0, "skipped": 0}
    for m in _RESULTS_RE.finditer(stdout):
        totals["total"]    += int(m.group("total"))
        totals["failures"] += int(m.group("failures"))
        totals["errors"]   += int(m.group("errors"))
        totals["skipped"]  += int(m.group("skipped"))

    all_failures = totals["failures"] + totals["errors"]

    failure_details = [
        {"test_name": m.group("test"), "message": "See raw_output for details"}
        for m in _FAILURE_RE.finditer(stdout)
    ]

    return {
        "passed":         all_failures == 0 and totals["total"] > 0,
        "total":          totals["total"],
        "failures":       all_failures,
        "skipped":        totals["skipped"],
        "failure_details": failure_details,
        "coverage_pct":   None,
        "raw_output":     stdout[-4000:],  # keep last 4 KB
    }


# ── Node function ─────────────────────────────────────────────────────────────

def testing_agent_node(state: SDLCState) -> dict:
    with timed_stage("run_tests") as timing:
        raw = run_maven_tests()

    results = _parse_results(raw["stdout"] + raw["stderr"])

    # If Maven couldn't even compile, mark as failed with a clear message
    if raw["return_code"] not in (0, 1):
        results["passed"] = False
        results["failure_details"].insert(
            0,
            {
                "test_name": "BUILD",
                "message": f"Maven exited with code {raw['return_code']}. "
                           "Likely a compilation error — check errors list.",
            },
        )

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="run_tests",
        event="completed",
        details={
            "passed":    results["passed"],
            "total":     results["total"],
            "failures":  results["failures"],
            "elapsed_s": timing["elapsed"],
        },
    )

    return {
        "test_results":  results,
        "current_stage": "tests_complete",
        "audit_log":     [entry],
        "errors":        [] if results["passed"] else [
            f"Test failure: {d['test_name']}" for d in results["failure_details"]
        ],
        "stage_timings": {"run_tests": timing["elapsed"]},
    }
