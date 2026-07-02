"""
Human-in-the-loop approval gate.

Uses LangGraph's `interrupt()` to pause the graph and surface generated
artifacts to the operator before any destructive/release actions proceed.
"""
from __future__ import annotations

from langgraph.types import interrupt

from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry


def human_approval_gate(state: SDLCState) -> dict:
    """
    Pauses execution and waits for the operator to approve or reject.

    The caller (main.py) resumes by calling:
        graph.invoke(Command(resume={"decision": "approved"|"rejected",
                                     "reason": "...",
                                     "target_stage": "..."}), config)
    """
    # Surface a review payload so the CLI can display it
    review_payload = {
        "session_id": state["session_id"],
        "generated_files": [f["path"] for f in (state.get("generated_files") or [])],
        "test_summary": {
            "passed": state.get("test_results", {}).get("passed"),
            "total":  state.get("test_results", {}).get("total", 0),
            "failures": state.get("test_results", {}).get("failures", 0),
        },
        "architecture_notes": (state.get("architecture") or {}).get("design_notes", ""),
        "prompt": (
            "Review the generated artifacts above.\n"
            "Reply with: {decision: approved|rejected, reason: '...', "
            "target_stage: generate_code|design_architecture|parse_requirements}"
        ),
    }

    # ── PAUSE — control returns to main.py here ──────────────────────────────
    response: dict = interrupt(review_payload)
    # ── RESUME — response contains the operator's decision ───────────────────

    decision = response.get("decision", "rejected")
    reason = response.get("reason", "")
    target_stage = response.get("target_stage", "generate_code")

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="human_approval",
        event="decision_recorded",
        details={"decision": decision, "reason": reason, "target_stage": target_stage},
    )

    return {
        "human_approval": decision,
        "rejection_reason": reason,
        "rejection_target_stage": target_stage,
        "current_stage": "human_approval_complete",
        "audit_log": [entry],
    }
