"""
Coding Agent
────────────
Generates (or patches) production-quality Spring Boot Java source files
based on architecture decisions and requirement spec.

On retry runs (retry_count > 0), the agent also receives the test failure
details and focuses on fixing the broken logic rather than re-writing from
scratch.

Files written to disk:
  src/main/java/.../model/UrlMapping.java
  src/main/java/.../repository/UrlMappingRepository.java
  src/main/java/.../service/UrlShortenerService.java
  src/main/java/.../controller/UrlShortenerController.java
  src/main/java/.../exception/UrlNotFoundException.java
  src/test/java/.../service/UrlShortenerServiceTest.java
"""
from __future__ import annotations

import json
from pydantic import BaseModel, Field

from agents.base_agent import make_llm, timed_stage
from orchestrator.state import SDLCState, GeneratedFile
from tools.audit_logger import make_audit_entry
from tools.file_tools import write_project_file
import config


class _FileOut(BaseModel):
    path: str = Field(description="Relative path from project root, e.g. src/main/java/...")
    content: str
    language: str = Field(description="java | yaml | sql")


class CodingOutput(BaseModel):
    files: list[_FileOut]
    summary: str
    key_decisions: list[str]


_SYSTEM_PROMPT = f"""\
You are a senior Java developer.  Generate production-quality Spring Boot source
files for a URL shortener service.

Tech stack:
  • Java 21, Spring Boot (latest), Lombok
  • Spring Data JPA + MySQL 8
  • Spring Data Redis for caching (Lettuce client)
  • Base62 encoding — alphabet: 0-9 A-Z a-z (62 chars), 6-character codes
  • Collision resolution: append a counter suffix and re-encode if the short
    code already exists in the database

Package root: {config.JAVA_PACKAGE}
Base URL property: ${{url.base-url}}
Code length property: ${{url.code-length:6}}

Requirements:
  1. UrlMapping JPA entity  — fields: id (Long, auto), shortCode (String, unique),
     originalUrl (String), createdAt (LocalDateTime), clickCount (Long default 0)
  2. UrlMappingRepository — extends JpaRepository, add findByShortCode and
     findByOriginalUrl
  3. UrlShortenerService  — shortenUrl(String original) → String shortUrl,
     getOriginalUrl(String shortCode) → String, recordClick(String shortCode)
     Cache read-through: check Redis first, then DB, then store in Redis
  4. UrlShortenerController — POST /api/shorten (body: {{longUrl}}),
     GET /{shortCode} (redirect 302), GET /api/analytics/{shortCode}
  5. UrlNotFoundException — extends RuntimeException, @ResponseStatus(404)
  6. One JUnit 5 unit test class for UrlShortenerService using Mockito

Return only valid, compilable Java.  Use Lombok @Data, @Builder, @RequiredArgsConstructor.
"""


def coding_agent_node(state: SDLCState) -> dict:
    llm = make_llm(temperature=0.1)
    structured = llm.with_structured_output(CodingOutput)

    # Build context — on retry include test failures for targeted fixes
    context_parts = [
        f"Requirements:\n{json.dumps(state['parsed_requirements'], indent=2)}",
        f"Architecture:\n{json.dumps(state['architecture'], indent=2)}",
    ]

    retry_count = state.get("retry_count", 0)
    if retry_count > 0 and state.get("test_results"):
        failures = state["test_results"].get("failure_details", [])
        context_parts.append(
            f"RETRY #{retry_count} — Fix these test failures:\n"
            + json.dumps(failures, indent=2)
        )

    user_content = "\n\n---\n\n".join(context_parts)

    with timed_stage("generate_code") as timing:
        result: CodingOutput = structured.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ]
        )

    # Write files to the Spring Boot project
    written: list[GeneratedFile] = []
    write_errors: list[str] = []

    for f in result.files:
        try:
            write_project_file(f.path, f.content)
            written.append({"path": f.path, "content": f.content, "language": f.language})
        except Exception as exc:
            write_errors.append(f"Could not write {f.path}: {exc}")

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="generate_code",
        event="completed",
        details={
            "files_written": [f["path"] for f in written],
            "retry_count": retry_count,
            "key_decisions": result.key_decisions,
            "elapsed_s": timing["elapsed"],
        },
    )

    return {
        "generated_files": written,
        "retry_count": retry_count + 1,
        "current_stage": "code_generation_complete",
        "audit_log": [entry],
        "errors": write_errors,
        "stage_timings": {"generate_code": timing["elapsed"]},
    }
