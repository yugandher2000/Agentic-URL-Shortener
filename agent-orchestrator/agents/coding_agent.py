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
import re
import time
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

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
     GET /{{shortCode}} (redirect 302), GET /api/analytics/{{shortCode}}
  5. UrlNotFoundException — extends RuntimeException, @ResponseStatus(404)
  6. One JUnit 5 unit test class for UrlShortenerService using Mockito

Return only valid, compilable Java.  Use Lombok @Data, @Builder, @RequiredArgsConstructor.

IMPORTANT: Your entire response must be a single valid JSON object (no markdown fences, no explanation) with this exact structure:
{{
  "files": [
    {{
      "path": "src/main/java/com/yugandher/urlShortener/model/UrlMapping.java",
      "language": "java",
      "content": "<full java source>"
    }}
  ],
  "summary": "one-line summary",
  "key_decisions": ["decision 1", "decision 2"]
}}
"""

# Each entry: (relative_path, what to generate)
_FILE_SPECS = [
    (
        f"src/main/java/{config.JAVA_PACKAGE.replace('.','/')}/model/UrlMapping.java",
        "JPA entity UrlMapping with fields: id (Long PK auto), shortCode (String unique length 10), "
        "originalUrl (String length 2048 no index), createdAt (LocalDateTime), clickCount (Long default 0). "
        "Use Lombok @Entity @Table(name='url_mappings') @Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor.",
    ),
    (
        f"src/main/java/{config.JAVA_PACKAGE.replace('.','/')}/repository/UrlMappingRepository.java",
        "Spring Data JPA repository extending JpaRepository<UrlMapping,Long>. "
        "Add: Optional<UrlMapping> findByShortCode(String), Optional<UrlMapping> findByOriginalUrl(String), "
        "@Modifying @Query(\"UPDATE UrlMapping u SET u.clickCount = u.clickCount+1 WHERE u.shortCode=:s\") void incrementClickCount(@Param(\"s\") String shortCode).",
    ),
    (
        f"src/main/java/{config.JAVA_PACKAGE.replace('.','/')}/exception/UrlNotFoundException.java",
        "RuntimeException subclass annotated @ResponseStatus(HttpStatus.NOT_FOUND). "
        "Constructor takes shortCode String and passes message 'Short code not found: <shortCode>' to super().",
    ),
    (
        f"src/main/java/{config.JAVA_PACKAGE.replace('.','/')}/service/UrlShortenerService.java",
        "Spring @Service using SHA-256 + Base62 (6 chars) to generate short codes. "
        "Methods: shortenUrl(String)→String (idempotent, saves to DB, writes to Redis master), "
        "getOriginalUrl(String)→String (Redis replica read-through then DB), "
        "recordClick(String) (calls repo.incrementClickCount), getAnalytics(String)→UrlMapping. "
        "Use @Qualifier(\"masterRedisTemplate\") and @Qualifier(\"replicaRedisTemplate\") StringRedisTemplate. "
        "Key prefix: 'url:', TTL: props.getCacheTtlSeconds(). Fix sign-bit issue: value = value & Long.MAX_VALUE.",
    ),
    (
        f"src/main/java/{config.JAVA_PACKAGE.replace('.','/')}/controller/UrlShortenerController.java",
        "@RestController with @CrossOrigin(origins='*'). "
        "POST /api/shorten (@Valid @RequestBody ShortenRequest) → ResponseEntity<ShortenResponse>. "
        "GET /{shortCode} → 302 redirect after calling recordClick. "
        "GET /api/analytics/{shortCode} → ResponseEntity<AnalyticsResponse>. "
        "Inject UrlShortenerService and AppProperties.",
    ),
    (
        f"src/test/java/{config.JAVA_PACKAGE.replace('.','/')}/service/UrlShortenerServiceTest.java",
        "JUnit 5 + Mockito test class for UrlShortenerService. "
        "Mock UrlMappingRepository, masterRedisTemplate, replicaRedisTemplate, AppProperties. "
        "Tests: shortenUrl_returnsShortUrl, shortenUrl_idempotent, getOriginalUrl_cacheHit, getOriginalUrl_cacheMiss, recordClick_callsRepo.",
    ),
]


def _parse_coding_output(raw: str) -> CodingOutput:
    """Extract JSON from the LLM response and validate it."""
    text = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    parsed = json.loads(match.group() if match else text)
    return CodingOutput.model_validate(parsed)


def coding_agent_node(state: SDLCState) -> dict:
    llm = make_llm(temperature=0.1)

    retry_count = state.get("retry_count", 0)
    context_prefix = (
        f"Package: {config.JAVA_PACKAGE}\n"
        f"Architecture: {json.dumps(state.get('architecture', {}), indent=2)}\n"
    )
    if retry_count > 0 and state.get("test_results"):
        failures = state["test_results"].get("failure_details", [])
        context_prefix += f"\nRETRY #{retry_count} - fix failures:\n{json.dumps(failures, indent=2)}"

    written: list[GeneratedFile] = []
    write_errors: list[str] = []
    all_decisions: list[str] = []

    with timed_stage("generate_code") as timing:
        for file_path, spec in _FILE_SPECS:
            prompt = (
                f"{_SYSTEM_PROMPT}\n\n{context_prefix}\n\n"
                f"Generate ONLY this single file: {file_path}\n"
                f"Requirements for this file: {spec}\n\n"
                "Respond with a JSON object:\n"
                '{"path":"<path>","language":"java","content":"<full source>","key_decisions":["..."]}'
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            raw = resp.content.strip()
            # Strip markdown fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\n?```$", "", raw.strip(), flags=re.MULTILINE)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            try:
                obj = json.loads(match.group() if match else raw, strict=False)
                path = obj.get("path", file_path)
                content = obj.get("content", "")
                lang = obj.get("language", "java")
                all_decisions.extend(obj.get("key_decisions", []))
                write_project_file(path, content)
                written.append({"path": path, "content": content, "language": lang})
            except Exception as exc:
                write_errors.append(f"Error generating {file_path}: {exc}")
            time.sleep(3)  # respect TPM rate limit between calls

    entry = make_audit_entry(
        session_id=state["session_id"],
        stage="generate_code",
        event="completed",
        details={
            "files_written": [f["path"] for f in written],
            "retry_count": retry_count,
            "key_decisions": all_decisions,
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
