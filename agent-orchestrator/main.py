"""
SDLC Agentic Orchestrator — Main Entry Point
============================================

Usage:
    python main.py --scenario greenfield
    python main.py --scenario brownfield
    python main.py --scenario ambiguous
    python main.py --requirement "Add URL expiry after 30 days"

What it does:
  1. Initialises a LangGraph pipeline with 8 specialised agents
  2. Runs until the Human Approval Gate — then pauses and shows you the
     generated artifacts + test results
  3. You approve or reject (with feedback routed back to the right stage)
  4. On approval: Security ∥ Documentation agents run in parallel,
     followed by the Release Agent
  5. Final summary printed; full audit trail written to audit/audit.log
"""
from __future__ import annotations

import argparse
import sys
import uuid

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from langgraph.types import Command

from orchestrator.graph import SDLC_GRAPH
from orchestrator.state import SDLCState
from scenarios.greenfield import GREENFIELD_REQUIREMENT
from scenarios.brownfield import BROWNFIELD_REQUIREMENT
from scenarios.ambiguous import AMBIGUOUS_REQUIREMENT

console = Console()

SCENARIOS: dict[str, str] = {
    "greenfield": GREENFIELD_REQUIREMENT,
    "brownfield": BROWNFIELD_REQUIREMENT,
    "ambiguous":  AMBIGUOUS_REQUIREMENT,
}

# Stage display metadata
_STAGES = [
    ("parse_requirements",   "Requirement Agent"),
    ("design_architecture",  "Architecture Agent"),
    ("generate_code",        "Coding Agent"),
    ("run_tests",            "Testing Agent"),
    ("human_approval",       "Human Approval Gate"),
    ("security_scan",        "Security Agent     [parallel]"),
    ("generate_docs",        "Documentation Agent[parallel]"),
    ("generate_release",     "Release Agent"),
]


# ── Display helpers ───────────────────────────────────────────────────────────

def _banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]  AGENTIC SDLC ORCHESTRATOR  [/bold cyan]\n"
            "[dim]  URL Shortener · Full Lifecycle Automation  [/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )


def _pipeline_table(timings: dict, stopped_at: str = "") -> None:
    table = Table(
        title="Pipeline Status",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Stage",    style="bold", min_width=32)
    table.add_column("Status",   min_width=16)
    table.add_column("Duration", justify="right")

    done = set(timings.keys())

    for stage_id, label in _STAGES:
        if stage_id in done:
            status   = "[green]✓ Done[/green]"
            duration = f"{timings[stage_id]:.1f}s"
        elif stage_id == stopped_at:
            status   = "[yellow]⏸ Paused[/yellow]"
            duration = "—"
        else:
            status   = "[dim]○ Pending[/dim]"
            duration = "—"
        table.add_row(label, status, duration)

    console.print(table)


def _show_artifacts(state: dict) -> None:
    files = state.get("generated_files") or []
    if files:
        console.print("\n[bold]Generated files:[/bold]")
        for f in files:
            console.print(f"  [cyan]•[/cyan] {f['path']}")

    tr = state.get("test_results")
    if tr:
        color = "green" if tr["passed"] else "red"
        label = "PASSED" if tr["passed"] else "FAILED"
        console.print(
            f"\n[bold]Tests:[/bold] [{color}]{label}[/{color}]  "
            f"{tr['total']} total · {tr['failures']} failures · {tr['skipped']} skipped"
        )
        if not tr["passed"] and tr["failure_details"]:
            for fd in tr["failure_details"][:5]:
                console.print(f"    [red]✗[/red] {fd['test_name']}: {fd.get('message','')}")


def _show_security(state: dict) -> None:
    sr = state.get("security_report")
    if not sr:
        return
    risk = sr.get("risk_level", "UNKNOWN")
    colour = {"LOW": "green", "MEDIUM": "yellow",
              "HIGH": "red", "CRITICAL": "bold red"}.get(risk, "white")
    console.print(f"\n[bold]Security risk:[/bold] [{colour}]{risk}[/{colour}]")
    for f in (sr.get("findings") or [])[:5]:
        console.print(f"  [yellow]⚠[/yellow] [{f['owasp_category']}] {f['description']}")


def _show_release(state: dict) -> None:
    ra = state.get("release_artifacts")
    if ra:
        console.print("\n[bold green]✓ Release artifacts ready:[/bold green]")
        console.print("  • Dockerfile")
        console.print("  • docker-compose.yml")
        console.print("  • Deployment notes")


# ── Human approval gate UI ────────────────────────────────────────────────────

def _human_approval_ui(state: dict) -> dict:
    console.rule("[yellow]⏸  HUMAN APPROVAL GATE[/yellow]")
    console.print(
        "\n[bold]Review the generated artifacts and test results above.[/bold]\n"
        "  [1] [green]approve[/green]   — proceed to security scan + release\n"
        "  [2] [red]reject[/red]    — send back for revision\n"
    )

    while True:
        choice = console.input("[bold]Decision [1/2]:[/bold] ").strip()
        if choice in ("1", "approve", "yes", "y"):
            return {"decision": "approved", "reason": "", "target_stage": ""}

        if choice in ("2", "reject", "no", "n"):
            reason = console.input("[bold]Reason:[/bold] ").strip()
            console.print(
                "\n  [1] generate_code        (fix the code)\n"
                "  [2] design_architecture  (revisit design)\n"
                "  [3] parse_requirements   (re-interpret requirement)\n"
            )
            stage_choice = console.input("[bold]Revisit stage [1/2/3, default 1]:[/bold] ").strip()
            stage_map = {
                "1": "generate_code",
                "2": "design_architecture",
                "3": "parse_requirements",
            }
            target = stage_map.get(stage_choice, "generate_code")
            return {"decision": "rejected", "reason": reason, "target_stage": target}

        console.print("[red]Please enter 1 or 2[/red]")


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(requirement: str, scenario_label: str) -> None:
    session_id = str(uuid.uuid4())[:8]
    thread_cfg = {"configurable": {"thread_id": session_id}}

    initial_state: SDLCState = {
        "requirement":            requirement,
        "session_id":             session_id,
        "current_stage":          "start",
        "retry_count":            0,
        "human_approval":         None,
        "rejection_reason":       None,
        "rejection_target_stage": None,
        "parsed_requirements":    None,
        "architecture":           None,
        "generated_files":        None,
        "test_results":           None,
        "security_report":        None,
        "documentation":          None,
        "release_artifacts":      None,
        "audit_log":              [],
        "errors":                 [],
        "stage_timings":          {},
    }

    _banner()
    console.print(f"\n[bold]Scenario  :[/bold] {scenario_label}")
    console.print(f"[bold]Session ID:[/bold] {session_id}")
    console.print(f"[bold]Requirement:[/bold]\n{requirement[:300]}{'...' if len(requirement) > 300 else ''}\n")

    # ── Phase 1: Run until human approval pause ───────────────────────────────
    with console.status("[cyan]Running SDLC pipeline…[/cyan]", spinner="dots"):
        state = SDLC_GRAPH.invoke(initial_state, thread_cfg)

    snapshot = SDLC_GRAPH.get_state(thread_cfg)

    if snapshot.next:
        # Interrupted at human_approval gate
        _pipeline_table(state.get("stage_timings", {}), stopped_at="human_approval")
        _show_artifacts(state)

        human_input = _human_approval_ui(state)

        # ── Phase 2: Resume after human decision ──────────────────────────────
        with console.status("[cyan]Resuming pipeline…[/cyan]", spinner="dots"):
            state = SDLC_GRAPH.invoke(Command(resume=human_input), thread_cfg)

    # ── Final summary ─────────────────────────────────────────────────────────
    console.print()
    _pipeline_table(state.get("stage_timings", {}))
    _show_security(state)
    _show_release(state)

    errors = state.get("errors") or []
    if errors:
        console.print(f"\n[bold red]Errors ({len(errors)}):[/bold red]")
        for e in errors[:10]:
            console.print(f"  [red]•[/red] {e}")

    console.print(
        f"\n[dim]Audit log → agent-orchestrator/audit/audit.log  "
        f"(session: {session_id})[/dim]\n"
    )


# ── CLI entry ─────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SDLC Agentic Orchestrator — URL Shortener",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --scenario greenfield\n"
            "  python main.py --scenario brownfield\n"
            "  python main.py --scenario ambiguous\n"
            "  python main.py --requirement \"Add URL expiry after 30 days\"\n"
        ),
    )
    p.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="greenfield",
        help="Pre-defined scenario (default: greenfield)",
    )
    p.add_argument(
        "--requirement",
        type=str,
        default=None,
        help="Custom requirement text — overrides --scenario",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.requirement:
        req   = args.requirement
        label = "Custom"
    else:
        req   = SCENARIOS[args.scenario]
        label = args.scenario.capitalize()

    try:
        run_pipeline(req, label)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)
