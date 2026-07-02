"""
SDLC LangGraph StateGraph
=========================

Dependency graph (ASCII):

  START
    └─► parse_requirements
          └─► design_architecture
                └─► generate_code ◄──────────────────────┐
                      └─► run_tests                       │ retry ≤ MAX
                            ├─[fail, retry]───────────────┘
                            ├─[fail, exhausted]──► END
                            └─[pass]──► human_approval
                                          ├─[reject]──► (target stage)
                                          └─[approve]──► post_approval_fanout
                                                            ├──► security_scan ─┐
                                                            └──► generate_docs  ─┤
                                                                                 ▼
                                                                        generate_release
                                                                                 └─► END

Key design properties
─────────────────────
• Explicit dependency graph with named nodes and typed edges
• Conditional routing (test retry, human approval feedback)
• Parallel fan-out  (security ∥ docs) with synchronised fan-in
• Human-in-the-loop via interrupt() — no destructive action without approval
• State reducers (audit_log, errors, stage_timings) ensure safe concurrent writes
• MemorySaver checkpointer enables resume after interrupt
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

import config
from orchestrator.state import SDLCState
from orchestrator.gates import human_approval_gate
from agents.requirement_agent import requirement_agent_node
from agents.architecture_agent import architecture_agent_node
from agents.coding_agent import coding_agent_node
from agents.testing_agent import testing_agent_node
from agents.security_agent import security_agent_node
from agents.documentation_agent import documentation_agent_node
from agents.release_agent import release_agent_node


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_tests(state: SDLCState) -> str:
    """
    After run_tests:
    - tests pass  → pause for human approval
    - tests fail  → retry coding (up to MAX_CODING_RETRIES)
    - retries exhausted → terminal failure
    """
    if (state.get("test_results") or {}).get("passed"):
        return "human_approval"
    if state.get("retry_count", 0) < config.MAX_CODING_RETRIES:
        return "generate_code"
    return END   # bounded retries exhausted — safe-stop


def route_after_approval(state: SDLCState) -> str:
    """
    After human_approval:
    - approved  → fan-out (security ∥ docs)
    - rejected  → back to stage specified by reviewer
    """
    if state.get("human_approval") == "approved":
        return "post_approval_fanout"
    return state.get("rejection_target_stage", "generate_code")


# ── No-op fan-out node ────────────────────────────────────────────────────────

def post_approval_fanout(state: SDLCState) -> dict:
    """
    Purely structural node.  LangGraph fans out to both security_scan
    and generate_docs from here; generate_release waits for both (fan-in).
    """
    return {"current_stage": "post_approval_fanout"}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_sdlc_graph():
    workflow = StateGraph(SDLCState)

    # ── Register nodes ────────────────────────────────────────────────────────
    workflow.add_node("parse_requirements",   requirement_agent_node)
    workflow.add_node("design_architecture",  architecture_agent_node)
    workflow.add_node("generate_code",        coding_agent_node)
    workflow.add_node("run_tests",            testing_agent_node)
    workflow.add_node("human_approval",       human_approval_gate)
    workflow.add_node("post_approval_fanout", post_approval_fanout)
    workflow.add_node("security_scan",        security_agent_node)
    workflow.add_node("generate_docs",        documentation_agent_node)
    workflow.add_node("generate_release",     release_agent_node)

    # ── Sequential backbone ───────────────────────────────────────────────────
    workflow.add_edge(START,                  "parse_requirements")
    workflow.add_edge("parse_requirements",   "design_architecture")
    workflow.add_edge("design_architecture",  "generate_code")
    workflow.add_edge("generate_code",        "run_tests")

    # ── Conditional: tests ────────────────────────────────────────────────────
    workflow.add_conditional_edges(
        "run_tests",
        route_after_tests,
        {
            "human_approval": "human_approval",
            "generate_code":  "generate_code",
            END:              END,
        },
    )

    # ── Conditional: human approval ───────────────────────────────────────────
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "post_approval_fanout": "post_approval_fanout",
            "generate_code":        "generate_code",
            "design_architecture":  "design_architecture",
            "parse_requirements":   "parse_requirements",
        },
    )

    # ── Parallel fan-out: security ∥ docs ─────────────────────────────────────
    # Both nodes are triggered simultaneously from post_approval_fanout.
    # generate_release (fan-in) waits until BOTH complete before running.
    workflow.add_edge("post_approval_fanout", "security_scan")
    workflow.add_edge("post_approval_fanout", "generate_docs")

    # ── Fan-in → release ──────────────────────────────────────────────────────
    workflow.add_edge("security_scan",   "generate_release")
    workflow.add_edge("generate_docs",   "generate_release")
    workflow.add_edge("generate_release", END)

    # ── Compile with checkpointer (required for interrupt/resume) ─────────────
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Singleton — imported by main.py
SDLC_GRAPH = build_sdlc_graph()
