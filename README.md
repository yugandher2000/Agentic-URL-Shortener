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
