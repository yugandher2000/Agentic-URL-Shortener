"""
Release Agent
─────────────
Generates deployment artifacts after security and docs are complete:
  • Dockerfile for the Spring Boot app
  • docker-compose.yml with MySQL + Redis (master + replica topology)
  • Deployment notes

This is the final stage — nothing runs after it without human approval,
satisfying the "controlled autonomy" governance requirement.
"""
from __future__ import annotations

import json
from pydantic import BaseModel

from agents.base_agent import make_llm, timed_stage
from orchestrator.state import SDLCState
from tools.audit_logger import make_audit_entry
import config


class ReleaseOutput(BaseModel):
    dockerfile_content: str
    docker_compose_content: str
    deployment_notes: str


_SYSTEM_PROMPT = f"""\
You are a DevOps engineer.  Generate deployment artifacts for a Spring Boot
URL shortener service.

Requirements:
  1. Dockerfile
     • Multi-stage build: Maven build stage → slim JRE runtime stage
     • Base image: eclipse-temurin:21-jre-alpine
     • Expose port 8080
     • HEALTHCHECK via /actuator/health

  2. docker-compose.yml
     • Service: app (builds from Dockerfile, depends on mysql + redis-master)
     • Service: mysql  (mysql:8.0, schema: {config.DB_SCHEMA_NAME}, user root/root)
     • Service: redis-master  (redis:7-alpine, port 6379)
     • Service: redis-replica (redis:7-alpine, replicaof redis-master 6379)
       — all writes → master, all reads → replica (demonstrates master/replica)
     • Named volumes for mysql data persistence
     • Health-checks on mysql and redis before app starts

  3. deployment_notes
     • How to run: `docker compose up --build`
     • How to switch Spring Boot to use Docker hostnames
       (SPRING_DATASOURCE_URL, SPRING_DATA_REDIS_HOST env vars)
     • Known limitations / next steps

Return a JSON object matching ReleaseOutput schema.
"""


def release_agent_node(state: SDLCState) -> dict:
    llm = make_llm()
    structured = llm.with_structured_output(ReleaseOutput)

    context = {
        "architecture":    state.get("architecture"),
        "security_report": {
            "risk_level": (state.get("security_report") or {}).get("risk_level"),
            "approved":   (state.get("security_report") or {}).get("approved"),
        },
        "generated_files": [f["path"] for f in (state.get("generated_files") or [])],
    }

    with timed_stage("generate_release") as timing:
        result: ReleaseOutput = structured.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Context:\n{json.dumps(context, indent=2)}"},
            ]
        )

    artifacts = result.model_dump()

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="generate_release",
        event="completed",
        details={"elapsed_s": timing["elapsed"]},
    )

    return {
        "release_artifacts": artifacts,
        "current_stage":     "release_complete",
        "audit_log":         [entry],
        "stage_timings":     {"generate_release": timing["elapsed"]},
    }
