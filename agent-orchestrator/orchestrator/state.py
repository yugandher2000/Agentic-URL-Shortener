"""
Shared state TypedDict for the entire SDLC pipeline.

LangGraph passes this dict between every node.  Fields annotated with
`operator.add` use a reducer — parallel branches safely append without
overwriting each other.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional, TypedDict


# ── Sub-shapes ────────────────────────────────────────────────────────────────

class AuditEntry(TypedDict):
    timestamp: str
    session_id: str
    stage: str
    event: str
    details: dict


class EndpointSpec(TypedDict):
    method: str
    path: str
    description: str
    request_body: Optional[dict]
    response_schema: Optional[dict]


class ColumnSpec(TypedDict):
    name: str
    sql_type: str
    nullable: bool
    primary_key: bool


class DataModelSpec(TypedDict):
    table_name: str
    columns: list[ColumnSpec]


class ParsedRequirements(TypedDict):
    feature_name: str
    scenario_type: Literal["greenfield", "brownfield", "ambiguous"]
    description: str
    endpoints: list[EndpointSpec]
    data_model: DataModelSpec
    caching_strategy: str
    ambiguities: list[str]       # flagged unknowns
    assumptions: list[str]       # documented assumptions
    acceptance_criteria: list[str]


class ArchitectureDecision(TypedDict):
    components: list[str]
    sql_schema: str              # DDL
    openapi_spec: dict           # OpenAPI 3.0 dict
    impacted_files: list[str]    # non-empty only for brownfield
    design_notes: str


class GeneratedFile(TypedDict):
    path: str        # relative to Spring Boot project root
    content: str
    language: str    # java | yaml | sql


class TestResults(TypedDict):
    passed: bool
    total: int
    failures: int
    skipped: int
    failure_details: list[dict]  # [{test_name, message}]
    coverage_pct: Optional[float]
    raw_output: str


class SecurityFinding(TypedDict):
    owasp_category: str   # e.g. A03:Injection
    file: str
    description: str
    recommendation: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class SecurityReport(TypedDict):
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    findings: list[SecurityFinding]
    owasp_checks: dict   # {A01: "PASS", A03: "FAIL", ...}
    approved: bool       # True when risk_level is LOW or MEDIUM


class Documentation(TypedDict):
    readme_content: str
    api_docs_yaml: str   # OpenAPI YAML string
    setup_instructions: str


class ReleaseArtifacts(TypedDict):
    dockerfile_content: str
    docker_compose_content: str
    deployment_notes: str


# ── Top-level pipeline state ──────────────────────────────────────────────────

class SDLCState(TypedDict):
    # Input
    requirement: str
    session_id: str

    # Stage outputs (None until that stage runs)
    parsed_requirements: Optional[ParsedRequirements]
    architecture: Optional[ArchitectureDecision]
    generated_files: Optional[list[GeneratedFile]]
    test_results: Optional[TestResults]
    security_report: Optional[SecurityReport]
    documentation: Optional[Documentation]
    release_artifacts: Optional[ReleaseArtifacts]

    # Control flow
    current_stage: str
    retry_count: int
    human_approval: Optional[Literal["approved", "rejected"]]
    rejection_reason: Optional[str]
    rejection_target_stage: Optional[str]  # which node to re-run

    # Observability — reducers make these append-only across parallel branches
    audit_log: Annotated[list[AuditEntry], operator.add]
    errors: Annotated[list[str], operator.add]

    # Timing metrics — reducer merges dicts
    stage_timings: Annotated[dict, lambda a, b: {**a, **b}]
