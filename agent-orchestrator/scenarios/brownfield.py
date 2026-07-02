"""
Scenario 2 — Brownfield
────────────────────────
Enhance the existing URL shortener with rate limiting.
The Architecture Agent scans existing code; the Coding Agent patches only
the relevant files rather than regenerating everything.
"""

BROWNFIELD_REQUIREMENT = """\
The URL shortener service is already running in production.
Add rate limiting to the POST /api/shorten endpoint:

Requirements:
1. Allow each IP address a maximum of 10 requests per minute.
2. Return HTTP 429 Too Many Requests with a Retry-After header when the
   limit is exceeded.
3. Implement using Redis (already in the stack) — use a sliding-window
   counter keyed by IP address.
4. The rate limit window and maximum count must be configurable via
   application.yaml (rate-limit.window-seconds, rate-limit.max-requests).
5. Add a unit test for the rate limiting service.
6. Do NOT break any existing endpoints or tests.
7. Document the new configuration properties in the README.

This is a brownfield change — minimise the diff.  Only touch files that
need to change.
"""
