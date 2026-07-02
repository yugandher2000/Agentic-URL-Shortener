"""
Scenario 1 — Greenfield
───────────────────────
Build the URL shortener service from scratch.
Full pipeline: Req → Arch → Code → Test → Approval → Security ∥ Docs → Release
"""

GREENFIELD_REQUIREMENT = """\
Build a URL shortener service from scratch.

Core features:
1. Accept a long URL via REST API and return a short URL (6-character Base62 code).
2. Redirect any short URL to the original long URL with HTTP 302.
3. Persist all mappings in MySQL (table: url_mappings, columns: id, short_code,
   original_url, created_at, click_count).
4. Cache every redirect lookup in Redis (master/replica) with a 1-hour TTL.
   Write-through on shorten; read-through on redirect.
5. Track click analytics (increment click_count on every redirect).
6. Return a 404 JSON error when a short code does not exist.
7. Prevent duplicate entries — if the same long URL is submitted twice,
   return the existing short URL without creating a new record.

Non-functional:
- Base62 alphabet: 0-9 A-Z a-z; codes must be exactly 6 characters.
- Collision resolution: if generated code exists, increment a counter and re-hash.
- API must be secured against SQL injection and basic OWASP Top 10 risks.
"""
