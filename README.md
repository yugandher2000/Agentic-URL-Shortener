# Agentic URL Shortener

A production-grade URL Shortener built with full **Agentic SDLC automation**. The project combines a working Spring Boot + Angular application with a LangGraph-based AI orchestrator that automates the entire software development lifecycle — from requirement parsing to release — with human-in-the-loop approval gates.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start — Docker](#quick-start--docker-recommended)
- [Manual Setup](#manual-setup)
- [Using the Application](#using-the-application)
- [Agent Orchestrator — Deep Dive](#agent-orchestrator--deep-dive)
  - [How the Orchestration Works](#how-the-orchestration-works)
  - [Pipeline Stages](#pipeline-stages)
  - [LangGraph State Machine](#langgraph-state-machine)
  - [Routing Logic](#routing-logic)
  - [Human Approval Gate](#human-approval-gate)
  - [Parallel Fan-Out](#parallel-fan-out)
  - [Shared State](#shared-state)
  - [Audit Trail](#audit-trail)
  - [Running the Orchestrator](#running-the-orchestrator)
  - [Three Built-in Scenarios](#three-built-in-scenarios)
  - [Model & Provider](#model--provider)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Known Issues & Notes](#known-issues--notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:4200)                  │
│                     Angular 21 — Ink.ly UI                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP REST
┌───────────────────────────▼─────────────────────────────────────┐
│               Spring Boot 3  (localhost:8080)                    │
│   POST /api/shorten  │  GET /{code}  │  GET /api/analytics/{code}│
└──────────┬────────────────────────────────────┬──────────────────┘
           │ JPA / Hibernate                    │ Spring Data Redis
┌──────────▼──────────┐              ┌──────────▼──────────────────┐
│   MySQL 8 (3306)    │              │  Redis Master (6379) WRITE  │
│   url_mappings      │              │  Redis Replica (6380) READ  │
└─────────────────────┘              └─────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 21, SSR-ready, Neumorphic dark theme (SCSS) |
| Backend API | Java 21, Spring Boot 3, Spring Data JPA, Spring Data Redis |
| Database | MySQL 8 |
| Cache | Redis 7 (Master + Replica) |
| Agent Orchestrator | Python 3.14, LangGraph 1.x, LangChain, Groq (LLaMA 3.3 70B) |
| Containerisation | Docker, Docker Compose |
| Build tools | Maven 3.9 (backend), npm 11 / Angular CLI 21 (frontend) |

---

## Prerequisites

| Tool | Version |
|---|---|
| Docker Desktop | 4.x+ |
| Java JDK | 21+ (manual run only) |
| Maven | 3.9+ (manual run only) |
| Node.js | 20+ (manual run only) |
| Python | 3.14+ (orchestrator only) |

---

## Quick Start — Docker (Recommended)

```bash
git clone https://github.com/yugandher2000/Agentic-URL-Shortener.git
cd Agentic-URL-Shortener
docker compose up --build
```

| Service | URL |
|---|---|
| Angular UI | http://localhost:4200 |
| Spring Boot API | http://localhost:8080 |
| MySQL | localhost:3307 ⚠️ |
| Redis Master (writes) | localhost:6379 |
| Redis Replica (reads) | localhost:6380 |

> ⚠️ **MySQL port note:** Docker MySQL is mapped to host port `3307` because Windows installs a local MySQL service that permanently holds `3306`. Containers communicate on `3306` internally — Spring Boot is unaffected. To connect via MySQL Workbench, use `127.0.0.1:3307 / root / root`.

```bash
docker compose down        # stop containers, keep data
docker compose down -v     # stop containers + wipe MySQL volume
```

---

## Manual Setup

### 1. Infrastructure
```bash
docker run -d --name url_mysql \
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=url_shortener \
  -p 3306:3306 mysql:8.0

docker run -d --name url_redis_master -p 6379:6379 redis:7-alpine
docker run -d --name url_redis_replica -p 6380:6379 redis:7-alpine \
  redis-server --replicaof host.docker.internal 6379
```

### 2. Backend
```bash
cd backend
mvn spring-boot:run
# API at http://localhost:8080
```

### 3. Frontend
```bash
cd frontEnd
npm install
npm start
# UI at http://localhost:4200
```

---

## Using the Application

1. Open **http://localhost:4200**
2. Paste any URL into **"PASTE YOUR LONG URL"** and click **⚡ Shorten URL**
3. The short link appears in **Recent Links** — hover to reveal copy/delete buttons
4. Three **stat cards** update automatically: Total Links, Total Clicks, Active Today
5. Click a short URL in your browser to trigger a redirect — click count increments

---

## Agent Orchestrator — Deep Dive

### How the Orchestration Works

The orchestrator models the entire **Software Development Lifecycle (SDLC)** as a directed graph of AI agent nodes. Each node is a specialised LLM agent with a defined input/output contract. LangGraph manages execution, state passing, conditional routing, parallel branches, and human-in-the-loop interrupts.

```
                          ┌──────────────────────────────────┐
                          │       SDLC Agent Pipeline        │
                          │  (LangGraph StateGraph + Groq)   │
                          └──────────────────────────────────┘

   START
     │
     ▼
┌─────────────────────┐
│  Requirement Agent  │  Parses raw text → structured spec
│  (parse_req)        │  (endpoints, schema, scenario type,
└─────────┬───────────┘   acceptance criteria, ambiguities)
          │
          ▼
┌─────────────────────┐
│ Architecture Agent  │  Designs SQL DDL, OpenAPI 3.0 spec,
│ (design_arch)       │  component list, design notes
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐◄─────────────────────────┐
│   Coding Agent      │                           │
│  (generate_code)    │  Generates Java files     │ retry
│                     │  (one LLM call per file)  │ ≤ MAX_CODING_RETRIES
└─────────┬───────────┘                           │
          │                                       │
          ▼                                       │
┌─────────────────────┐  fail + retries left ─────┘
│   Testing Agent     │
│   (run_tests)       │  Runs mvn test, parses results
└─────────┬───────────┘
          │ fail + no retries left → END (safe-stop)
          │ pass
          ▼
┌─────────────────────┐
│ Human Approval Gate │  ← PAUSES HERE — waits for operator input
│ (human_approval)    │
└────────┬────────────┘
         │ reject → back to selected stage
         │ approve
         ▼
┌─────────────────────┐
│  Post-Approval      │  Fan-out trigger node (structural)
│  Fanout             │
└──────┬──────────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌────────────┐
│  Security  │  │   Docs     │  ← run IN PARALLEL
│   Agent    │  │   Agent    │
└────────────┘  └────────────┘
       │              │
       └──────┬───────┘
              ▼ (fan-in — waits for both)
     ┌─────────────────┐
     │  Release Agent  │  Generates release notes + deployment checklist
     └────────┬────────┘
              ▼
             END
```

---

### Pipeline Stages

| # | Stage | Agent | What It Does |
|---|---|---|---|
| 1 | `parse_requirements` | **Requirement Agent** | Reads raw requirement text. Classifies as `greenfield / brownfield / ambiguous`. Extracts endpoint specs, data model, caching strategy, acceptance criteria. Flags ambiguities and documents assumptions. |
| 2 | `design_architecture` | **Architecture Agent** | Produces MySQL DDL schema, OpenAPI 3.0 contract, software component list, and design rationale. For brownfield, identifies impacted files. |
| 3 | `generate_code` | **Coding Agent** | Makes one LLM call per Java source file (entity, repository, exception, service, controller, test). Writes files to `SPRING_PROJECT_PATH`. Retries on test failure with failure details injected into the prompt. |
| 4 | `run_tests` | **Testing Agent** | Runs `mvn test` via subprocess. Parses Surefire XML reports. Returns pass/fail, total count, failure details, and elapsed time. |
| — | `human_approval` | **Gate** | Calls LangGraph `interrupt()` to pause the graph. Surfaces artifacts to the operator. Resumes only after explicit `approve` or `reject` decision. |
| 5 | `security_scan` | **Security Agent** | Reviews generated source code for OWASP Top 10 risks. Returns findings list, risk level (LOW/MEDIUM/HIGH/CRITICAL), and recommended fixes. |
| 6 | `generate_docs` | **Documentation Agent** | Produces API documentation, changelog entry, and setup notes based on requirements, architecture, and generated files. |
| 7 | `generate_release` | **Release Agent** | Creates release notes, deployment checklist, version tag recommendation, and rollback plan. |

---

### LangGraph State Machine

The pipeline is built as a LangGraph `StateGraph`. All agents share a single `SDLCState` TypedDict that flows through every node:

```python
# orchestrator/state.py (simplified)
class SDLCState(TypedDict):
    requirement:         str               # raw input text
    session_id:          str               # unique run ID
    parsed_requirements: ParsedRequirements
    architecture:        ArchitectureDecision
    generated_files:     list[GeneratedFile]
    test_results:        TestResults
    human_approval:      str               # "approved" | "rejected"
    security_report:     SecurityReport
    documentation:       Documentation
    release_artifacts:   ReleaseArtifacts
    retry_count:         int
    audit_log:           Annotated[list, operator.add]   # reducer: parallel-safe append
    errors:              Annotated[list, operator.add]   # reducer: parallel-safe append
    stage_timings:       dict
```

Fields annotated with `Annotated[list, operator.add]` use **reducers** — when parallel branches (Security + Docs) both write to `audit_log` or `errors` simultaneously, LangGraph merges the lists safely instead of one overwriting the other.

---

### Routing Logic

Two conditional edges control non-linear execution:

**After Testing Agent:**
```python
def route_after_tests(state):
    if state["test_results"]["passed"]:
        return "human_approval"        # → proceed to gate
    if state["retry_count"] < MAX_CODING_RETRIES:
        return "generate_code"         # → retry with failure context
    return END                         # → safe-stop (retries exhausted)
```

**After Human Approval Gate:**
```python
def route_after_approval(state):
    if state["human_approval"] == "approved":
        return "post_approval_fanout"  # → parallel security + docs
    return state["rejection_target_stage"]  # → any earlier stage
```

---

### Human Approval Gate

The gate uses LangGraph's `interrupt()` primitive to **pause the graph mid-execution**:

```python
# orchestrator/gates.py
def human_approval_gate(state):
    review_payload = {
        "generated_files": [...],
        "test_summary": {"passed": True, "total": 12, "failures": 0},
        "architecture_notes": "...",
    }

    response = interrupt(review_payload)   # ← GRAPH PAUSES HERE
    # Graph resumes when main.py calls:
    # SDLC_GRAPH.invoke(Command(resume={"decision": "approved"}), thread_cfg)

    return {
        "human_approval": response["decision"],
        "rejection_target_stage": response["target_stage"],
    }
```

- The `MemorySaver` checkpointer saves full state to memory before pausing
- `main.py` detects the interrupt via `SDLC_GRAPH.get_state().next`
- The operator types `1` (approve) or `2` (reject) in the CLI
- On rejection, the operator chooses which stage to revert to (code, architecture, or requirements)

---

### Parallel Fan-Out

After approval, Security and Documentation agents run **simultaneously**:

```
post_approval_fanout ──► security_scan ──┐
                     └──► generate_docs  ─┴──► generate_release
```

LangGraph automatically schedules both branches as concurrent tasks. The `generate_release` node acts as a **fan-in** — it only executes after **both** upstream branches complete. The `operator.add` reducers on `audit_log` and `errors` ensure the parallel branches can safely append their entries to the shared state.

---

### Shared State

Every agent reads from and writes to the same `SDLCState`. This enables **cross-stage context**:
- The Coding Agent sees the architecture decisions
- The Testing Agent's failures are injected into the Coding Agent's retry prompt
- The Security Agent reviews the actual generated source files
- The Release Agent knows the security risk level before finalising artifacts

---

### Audit Trail

Every agent writes a structured entry to `audit_log`:

```json
{
  "timestamp": "2026-07-03T10:15:30Z",
  "session_id": "85356239",
  "stage": "generate_code",
  "event": "completed",
  "details": {
    "files_written": ["src/main/java/.../UrlShortenerService.java"],
    "retry_count": 0,
    "key_decisions": ["SHA-256 + Base62 encoding", "Redis write-through"],
    "elapsed_s": 53.8
  }
}
```

Full audit log written to `agent-orchestrator/audit/audit.log` after each run.

---

### Running the Orchestrator

```bash
cd agent-orchestrator

# Install dependencies
pip install -r requirements.txt

# Configure (copy the example and add your Groq API key)
copy .env.example .env
# Edit .env:
#   GROQ_API_KEY=your_groq_key_here
#   LLM_MODEL=llama-3.3-70b-versatile
#   SPRING_PROJECT_PATH=C:/path/to/your/backend  ← point to backend/ dir

# Run a scenario
python main.py --scenario greenfield
python main.py --scenario brownfield
python main.py --scenario ambiguous

# Or provide a custom requirement
python main.py --requirement "Add URL expiry after 30 days"
```

**At the Human Approval Gate** (after 4 agents complete):
```
Pipeline Status
╭──────────────────────────┬──────────┬──────────╮
│ Stage                    │ Status   │ Duration │
├──────────────────────────┼──────────┼──────────┤
│ Requirement Agent        │ ✓ Done   │     1.2s │
│ Architecture Agent       │ ✓ Done   │     1.7s │
│ Coding Agent             │ ✓ Done   │    53.8s │
│ Testing Agent            │ ✓ Done   │     5.7s │
│ Human Approval Gate      │ ○ Pending│        — │
...

  [1] approve  — proceed to security scan + release
  [2] reject   — send back for revision

Decision [1/2]: 1
```

---

### Three Built-in Scenarios

| Scenario | Flag | What Happens |
|---|---|---|
| **Greenfield** | `--scenario greenfield` | Builds the full URL shortener from scratch. Full 8-stage pipeline. |
| **Brownfield** | `--scenario brownfield` | Adds Redis-based rate limiting to the existing service. Architecture Agent identifies impacted files; Coding Agent patches only those files. |
| **Ambiguous** | `--scenario ambiguous` | Input: *"Make the URLs smarter and add some analytics."* The Requirement Agent flags open questions, documents assumptions, and the pipeline proceeds with explicit ambiguity notes. |

---

### Model & Provider

| | Detail |
|---|---|
| **LLM** | Meta LLaMA 3.3 70B (open-source) |
| **Inference Provider** | [Groq](https://console.groq.com) — fast inference API |
| **GitHub Copilot** | Used only as a coding assistant in VS Code — **not** involved in the orchestrator pipeline |
| **API Key** | Your own `GROQ_API_KEY` in `agent-orchestrator/.env` |

> **Important:** The coding agent writes generated Java files directly to `SPRING_PROJECT_PATH`. To protect your production backend, set `SPRING_PROJECT_PATH` to a separate output directory:
> ```
> SPRING_PROJECT_PATH=C:/Project/TGONGCodeBase/Agentic-URL-Shortener/agent-orchestrator/generated-output
> ```

---

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `MAX_CODING_RETRIES` | `3` | Max test-failure retry cycles |
| `SPRING_PROJECT_PATH` | project root | Path the coding agent writes Java files to |
| `DB_SCHEMA_NAME` | `url_shortener` | MySQL schema name |

---

## Project Structure

```
Agentic-URL-Shortener/
├── dockerfile                        # Backend multi-stage Docker build (Maven → JRE)
├── docker-compose.yml                # Full stack: MySQL + Redis×2 + Spring Boot + Angular
├── Assignment-requirements.md        # Original assignment brief
│
├── backend/                          # Spring Boot 3 REST API
│   ├── pom.xml
│   └── src/
│       ├── main/java/.../
│       │   ├── controller/           # REST endpoints
│       │   ├── service/              # Business logic + Base62 encoding
│       │   ├── model/                # UrlMapping JPA entity
│       │   ├── repository/           # Spring Data JPA repository
│       │   ├── dto/                  # Request / Response shapes
│       │   ├── config/               # AppProperties, RedisConfig
│       │   └── exception/            # GlobalExceptionHandler, UrlNotFoundException
│       └── main/resources/
│           └── application.yaml      # DB, Redis, server config
│
├── frontEnd/                         # Angular 21 SPA
│   ├── Dockerfile                    # Node build → nginx serve
│   ├── nginx.conf                    # SPA routing + static asset caching
│   └── src/app/url-shortener/
│       ├── url-shortener.component.html   # Ink.ly Neumorphic UI
│       ├── url-shortener.component.scss   # SCSS neumorphic styles
│       ├── url-shortener.component.ts     # Signals, computed stats, recent links
│       └── url-shortener.service.ts       # HTTP client (shorten, analytics)
│
└── agent-orchestrator/               # Python LangGraph SDLC pipeline
    ├── main.py                       # CLI entry point + approval UI
    ├── config.py                     # Central configuration
    ├── requirements.txt
    ├── .env.example                  # Environment template
    ├── agents/
    │   ├── base_agent.py             # make_llm(), invoke_structured() helper
    │   ├── requirement_agent.py      # Stage 1: parse + classify requirements
    │   ├── architecture_agent.py     # Stage 2: DDL, OpenAPI, component design
    │   ├── coding_agent.py           # Stage 3: per-file Java code generation
    │   ├── testing_agent.py          # Stage 4: mvn test execution + parsing
    │   ├── security_agent.py         # Stage 6: OWASP code review (parallel)
    │   ├── documentation_agent.py    # Stage 7: API docs + changelog (parallel)
    │   └── release_agent.py          # Stage 8: release notes + checklist
    ├── orchestrator/
    │   ├── graph.py                  # LangGraph StateGraph + routing functions
    │   ├── state.py                  # SDLCState TypedDict + reducers
    │   └── gates.py                  # Human approval interrupt() logic
    ├── scenarios/
    │   ├── greenfield.py             # Full build from scratch
    │   ├── brownfield.py             # Rate limiting enhancement
    │   └── ambiguous.py              # Vague requirement handling
    └── tools/
        ├── audit_logger.py           # Structured audit entry builder
        ├── file_tools.py             # Read/write Spring Boot source files
        └── test_runner.py            # Maven test subprocess + Surefire XML parser
```

---

## API Reference

### `POST /api/shorten`
```json
// Request
{ "longUrl": "https://example.com/very/long/path" }

// Response 200
{ "shortUrl": "http://localhost:8080/aB3xZ9" }
```

| Code | Reason |
|---|---|
| `400` | URL is blank or does not start with `http(s)://` |
| `500` | Server error — check `docker logs url_app` |

### `GET /{shortCode}`
Redirects `302` to the original URL and records a click.

### `GET /api/analytics/{shortCode}`
```json
{
  "shortCode": "aB3xZ9",
  "shortUrl": "http://localhost:8080/aB3xZ9",
  "originalUrl": "https://example.com/very/long/path",
  "clickCount": 7,
  "createdAt": "2026-07-02T14:50:17"
}
```

---

## Known Issues & Notes

| Issue | Detail |
|---|---|
| **MySQL port 3307** | Windows MySQL service permanently holds `3306`. Docker MySQL is mapped to `3307`. Use `127.0.0.1:3307` in DB clients. |
| **Coding agent writes to backend** | By default `SPRING_PROJECT_PATH` points to `backend/`. The agent overwrites source files. Set it to a separate output directory to protect production code. |
| **Session-only stats** | Recent Links list resets on page refresh. A `/api/links` endpoint would persist this across sessions. |
| **Base62 sign bug (fixed)** | SHA-256 hash bytes treated as signed longs caused negative Base62 indices for ~50% of URLs. Fixed by masking sign bit (`value & Long.MAX_VALUE`). |
| **originalUrl index (fixed)** | `@Index` on `VARCHAR(2048)` with `utf8mb4` exceeded MySQL's 3072-byte key limit, preventing table creation. Index removed. |
| **Groq TPM limit** | Free tier `llama-3.3-70b-versatile` has ~30k TPM. A 3-second sleep between coding agent LLM calls prevents rate limit errors. |


---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start — Docker](#quick-start--docker-recommended)
- [Manual Setup](#manual-setup)
- [Using the Application](#using-the-application)
- [Agent Orchestrator](#agent-orchestrator)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Known Issues & Notes](#known-issues--notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:4200)                  │
│                     Angular 21 — Ink.ly UI                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP REST
┌───────────────────────────▼─────────────────────────────────────┐
│               Spring Boot 3  (localhost:8080)                    │
│   POST /api/shorten  │  GET /{code}  │  GET /api/analytics/{code}│
└──────────┬────────────────────────────────────┬──────────────────┘
           │ JPA / Hibernate                    │ Spring Data Redis
┌──────────▼──────────┐              ┌──────────▼──────────────────┐
│   MySQL 8 (3306)    │              │  Redis Master (6379) WRITE  │
│   url_mappings      │              │  Redis Replica (6380) READ  │
└─────────────────────┘              └─────────────────────────────┘

Agent Orchestrator (Python / LangGraph)
────────────────────────────────────────
START → Requirement Agent → Architecture Agent → Coding Agent
     → Testing Agent ──(fail: retry ≤3)──► Coding Agent
                    ──(pass)──► Human Approval Gate
                                  ├─(reject)──► target stage
                                  └─(approve)──► Security ∥ Docs
                                                      └──► Release → END
```

### Key Design Properties
- **Non-linear execution** — test failures trigger bounded retries back to the coding stage
- **Human-in-the-loop** — mandatory approval gate before any release action
- **Parallel fan-out** — Security Agent and Documentation Agent run concurrently after approval
- **Stateful checkpointing** — LangGraph `MemorySaver` allows resume after interruption
- **Audit trail** — every agent action logged to `agent-orchestrator/audit/audit.log`
- **Redis read/write split** — writes go to master, reads routed to replica

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 21, SSR-ready, Neumorphic dark theme (SCSS) |
| Backend API | Java 21, Spring Boot 3, Spring Data JPA, Spring Data Redis |
| Database | MySQL 8 |
| Cache | Redis 7 (Master + Replica) |
| Agent Orchestrator | Python 3.14, LangGraph, LangChain, Groq LLM |
| Containerisation | Docker, Docker Compose |
| Build tools | Maven 3.9 (backend), npm 11 / Angular CLI 21 (frontend) |

---

## Prerequisites

| Tool | Version |
|---|---|
| Docker Desktop | 4.x+ |
| Java JDK | 21+ (manual run only) |
| Maven | 3.9+ (manual run only) |
| Node.js | 20+ (manual run only) |
| Python | 3.14+ (orchestrator only) |

---

## Quick Start — Docker (Recommended)

Starts **MySQL + Redis Master + Redis Replica + Spring Boot + Angular** in one command.

```bash
git clone https://github.com/yugandher2000/Agentic-URL-Shortener.git
cd Agentic-URL-Shortener
docker compose up --build
```

| Service | URL |
|---|---|
| Angular UI | http://localhost:4200 |
| Spring Boot API | http://localhost:8080 |
| MySQL | localhost:3307 ⚠️ |
| Redis Master (writes) | localhost:6379 |
| Redis Replica (reads) | localhost:6380 |

> ⚠️ **MySQL port note:** The Docker MySQL is mapped to host port `3307` because Windows installs a local MySQL service that permanently holds `3306`. Containers communicate on `3306` internally — Spring Boot is unaffected. To connect via MySQL Workbench, use `127.0.0.1:3307 / root / root`.

### Stop the stack
```bash
docker compose down        # stop containers, keep data
docker compose down -v     # stop containers + wipe MySQL volume
```

---

## Manual Setup

Run each component in its own terminal.

### 1. Infrastructure (Docker)
```bash
docker run -d --name url_mysql \
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=url_shortener \
  -p 3306:3306 mysql:8.0

docker run -d --name url_redis_master -p 6379:6379 redis:7-alpine
docker run -d --name url_redis_replica -p 6380:6379 redis:7-alpine \
  redis-server --replicaof host.docker.internal 6379
```

### 2. Backend (Spring Boot)
```bash
cd backend
mvn spring-boot:run
# API available at http://localhost:8080
```

### 3. Frontend (Angular)
```bash
cd frontEnd
npm install
npm start
# UI available at http://localhost:4200
```

---

## Using the Application

1. Open **http://localhost:4200**
2. Paste any URL into the **"PASTE YOUR LONG URL"** input field
3. Click **⚡ Shorten URL**
4. The short link appears in the **Recent Links** section
5. **Hover** a row to reveal the copy and delete action buttons
6. The three **stat cards** update automatically:
   - **Total Links** — URLs shortened this session
   - **Total Clicks** — sum of all click counts fetched from the backend
   - **Active Today** — links created today
7. Click a short URL (e.g. `http://localhost:8080/PWG3Bu`) in your browser to trigger a redirect — the backend records the click

---

## Agent Orchestrator

The orchestrator automates the full SDLC for new URL shortener features.

### Setup
```bash
cd agent-orchestrator
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your LLM API key:
#   GROQ_API_KEY=your_key_here
#   LLM_MODEL=openai/gpt-oss-120b
```

### Run a scenario
```bash
# Greenfield — build a new feature from scratch
python main.py --scenario greenfield

# Brownfield — enhance or refactor existing code
python main.py --scenario brownfield

# Ambiguous — orchestrator clarifies unclear requirements
python main.py --scenario ambiguous

# Custom requirement
python main.py --requirement "Add URL expiry after 30 days"
```

### Pipeline stages

```
1. Requirement Agent    — parses intent, identifies ambiguities, defines acceptance criteria
2. Architecture Agent   — produces SQL schema, OpenAPI spec, component list
3. Coding Agent         — generates Spring Boot Java code (retries on test failure, ≤3x)
4. Testing Agent        — compiles and runs tests; routes back to Coding on failure
── HUMAN APPROVAL GATE ── (type approve / reject with optional feedback)
5. Security Agent  ┐    — OWASP scan, dependency audit            (parallel)
6. Documentation   ┘    — generates API docs and changelog        (parallel)
7. Release Agent        — produces release notes and deployment artifact
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | LLM provider API key |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Model identifier |
| `MAX_CODING_RETRIES` | `3` | Max test-failure retry cycles |
| `SPRING_PROJECT_PATH` | project root | Path to the backend source |
| `DB_SCHEMA_NAME` | `url_shortener` | MySQL schema name |

---

## Project Structure

```
Agentic-URL-Shortener/
├── dockerfile                        # Backend multi-stage Docker build (Maven → JRE)
├── docker-compose.yml                # Full stack: MySQL + Redis×2 + Spring Boot + Angular
├── Assignment-requirements.md        # Original assignment brief
│
├── backend/                          # Spring Boot 3 REST API
│   ├── pom.xml
│   └── src/
│       ├── main/java/.../
│       │   ├── controller/           # REST endpoints
│       │   ├── service/              # Business logic + Base62 encoding
│       │   ├── model/                # UrlMapping JPA entity
│       │   ├── repository/           # Spring Data JPA repository
│       │   ├── dto/                  # Request / Response shapes
│       │   ├── config/               # AppProperties, RedisConfig
│       │   └── exception/            # GlobalExceptionHandler, UrlNotFoundException
│       └── main/resources/
│           └── application.yaml      # DB, Redis, server config
│
├── frontEnd/                         # Angular 21 SPA
│   ├── Dockerfile                    # Node build → nginx serve
│   ├── nginx.conf                    # SPA routing + static asset caching
│   └── src/app/url-shortener/
│       ├── url-shortener.component.html   # Ink.ly Neumorphic UI
│       ├── url-shortener.component.scss   # SCSS variables + neumorphic styles
│       ├── url-shortener.component.ts     # Signals, computed stats, recent links
│       └── url-shortener.service.ts       # HTTP client (shorten, analytics)
│
└── agent-orchestrator/               # Python LangGraph SDLC pipeline
    ├── main.py                       # CLI entry point
    ├── config.py                     # Central configuration
    ├── requirements.txt
    ├── agents/                       # 8 specialised AI agents
    │   ├── requirement_agent.py
    │   ├── architecture_agent.py
    │   ├── coding_agent.py
    │   ├── testing_agent.py
    │   ├── security_agent.py
    │   ├── documentation_agent.py
    │   └── release_agent.py
    ├── orchestrator/
    │   ├── graph.py                  # LangGraph StateGraph + routing logic
    │   ├── state.py                  # Shared TypedDict state
    │   └── gates.py                  # Human approval interrupt
    ├── scenarios/
    │   ├── greenfield.py             # New feature requirements
    │   ├── brownfield.py             # Enhancement requirements
    │   └── ambiguous.py              # Under-specified requirements
    └── tools/
        ├── audit_logger.py           # Structured audit trail
        ├── file_tools.py             # Read/write source files
        └── test_runner.py            # Maven test execution
```

---

## API Reference

### `POST /api/shorten`
Shorten a URL.

**Request**
```json
{ "longUrl": "https://example.com/very/long/path" }
```
**Response `200`**
```json
{ "shortUrl": "http://localhost:8080/aB3xZ9" }
```
**Errors**
| Code | Reason |
|---|---|
| `400` | `longUrl` is blank or does not start with `http://` / `https://` |
| `500` | Unexpected server error (check `docker logs url_app`) |

---

### `GET /{shortCode}`
Redirect to the original URL (records a click).

**Response `302`** — `Location: <originalUrl>`  
**Response `404`** — `{ "error": "Short code not found: {shortCode}" }`

---

### `GET /api/analytics/{shortCode}`
Fetch metadata for a short link.

**Response `200`**
```json
{
  "shortCode": "aB3xZ9",
  "shortUrl": "http://localhost:8080/aB3xZ9",
  "originalUrl": "https://example.com/very/long/path",
  "clickCount": 7,
  "createdAt": "2026-07-02T14:50:17"
}
```

---

## Known Issues & Notes

| Issue | Detail |
|---|---|
| **MySQL port 3307** | Windows MySQL service permanently holds `3306`. Docker MySQL is mapped to `3307`. Use `127.0.0.1:3307` in DB clients. |
| **Session-only stats** | The Recent Links list and stats cards are in-memory only — they reset on page refresh. A `/api/links` endpoint would persist this across sessions. |
| **Base62 sign bug (fixed)** | SHA-256 hash bytes were treated as signed longs, producing negative Base62 indices for ~50% of URLs. Fixed by masking the sign bit (`value & Long.MAX_VALUE`). |
| **originalUrl index (fixed)** | `@Index` on `VARCHAR(2048)` with `utf8mb4` exceeded MySQL's 3072-byte key limit, preventing table creation. Index removed — lookups are by `shortCode` only. |
| **Orchestrator LLM key** | The agent orchestrator requires a valid `GROQ_API_KEY` in `agent-orchestrator/.env`. Without it, all agent calls will fail. |
