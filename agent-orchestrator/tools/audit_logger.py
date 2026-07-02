"""
Audit logger — append-only, JSON Lines format.

Every agent calls make_audit_entry() which:
  1. Returns a dict to be added to state["audit_log"] (in-memory)
  2. Simultaneously writes the same entry to audit/audit.log on disk

This satisfies the assignment requirement for "audit-grade observability
and traceability" with a persistent, searchable record.

Log format (one JSON object per line):
  {"timestamp":"...","session_id":"...","stage":"...","event":"...","details":{...}}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import config


def make_audit_entry(
    session_id: str,
    stage: str,
    event: str,
    details: dict | None = None,
) -> dict:
    """
    Create a structured audit entry, persist it to disk, and return it
    so the caller can append it to state["audit_log"].
    """
    entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "stage":      stage,
        "event":      event,
        "details":    details or {},
    }
    _append_to_disk(entry)
    return entry


def _append_to_disk(entry: dict) -> None:
    """Write one JSON line to the audit log file (creates file if needed)."""
    config.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_audit_log(session_id: str | None = None) -> list[dict]:
    """
    Read all audit entries from disk.
    If session_id is provided, filter to that session only.
    """
    if not config.AUDIT_LOG_PATH.exists():
        return []

    entries: list[dict] = []
    with config.AUDIT_LOG_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if session_id is None or entry.get("session_id") == session_id:
                    entries.append(entry)
            except json.JSONDecodeError:
                pass
    return entries
