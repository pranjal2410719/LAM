# Learning Adaptation Model (LAM)

LAM is an independent, versioned backend service that converts structured student-learning evidence into an authoritative learner state and recommends the next optimal teaching action.

---

## 1. System Boundaries

* **LAM owns:** Learning evidence validation, immutable append-only event ledger, multi-dimensional learner state, Bayesian Knowledge Tracing (BKT) mastery estimation, misconception diagnosis hypotheses, assistance escalation policy, spaced retrieval scheduling, and decision auditability.
* **Qrie / Host Application owns:** Student UI, chat turns, avatar/voice delivery, curriculum content, question/hint authoring, answer verification (symbolic math check, code tests, etc.), and delivery of the recommended intervention.

---

## 2. Current Implementation Status

* **Active Milestone:** **M2 — Closed Loop with Qrie** (`IMPLEMENTED & LOCALLY VERIFIED`; Staging Deployment `UNVERIFIED / BLOCKED` pending remote staging infrastructure provisioning; Policies D-01 through D-07 remain `PROPOSED`)
* **Implemented & Verified:**
  - **M0 Foundation:** Append-only event ledger with database-level uniqueness constraints for idempotency, cryptographic JWT authentication, PostgreSQL 16 migrations & high-concurrency race safety, non-coercion rule (`None` remains `None`).
  - **M1 Deterministic Learner Model:** Corbett & Anderson BKT engine, authoritative evidence eligibility rules, pure domain state transition engine, persistent misconception hypothesis engine with competing hypothesis evaluation and audit log, deterministic 7-tier recommendation engine.
  - **M2 Closed Loop Engines & Persistence:** Curriculum DAG validator (DFS 3-color cycle detection and Kahn's topological sort), 9-level assistance escalation ladder (Levels 0–8 with Tier 1 safety stop at $\ge 3$ consecutive failures), spaced retrieval forgetting curve scheduler ($R(t)=\exp(-\Delta t / S)$), and persistent misconception storage with PostgreSQL 16 row locking (`a78f20436d91`).
  - **Host Integration Client SDK:** Production `LamRelayClient` in `src/lam/infrastructure/clients/lam_client.py` with explicit connect/read timeouts, exponential backoff with jitter on 502/503/504, fast-fail on 401/403/409/422, outbox sequential replay deduplication, and safe fallback without mastery fabrication.
  - **Full Quality Gates (100% passing):** `ruff check .` (0 errors), `ruff format --check .` (89 files clean), `mypy --strict src/lam tests` (0 issues across 71 source files), and `pytest -v` (**142 / 142 tests passing** against PostgreSQL 16).
* **Detailed Status & Deployment Runbooks:**
  - Completion Audit: [`docs/LAM_COMPLETION_AUDIT.md`](./docs/LAM_COMPLETION_AUDIT.md)
  - Current Status: [`docs/PROJECT_STATUS.md`](./docs/PROJECT_STATUS.md)
  - Integration Contract: [`docs/QRIE_INTEGRATION_CONTRACT.md`](./docs/QRIE_INTEGRATION_CONTRACT.md)
  - Staging Checklist: [`docs/STAGING_RELEASE_CHECKLIST.md`](./docs/STAGING_RELEASE_CHECKLIST.md)
  - Changelog: [`CHANGELOG.md`](./CHANGELOG.md)
  - Test Evidence: [`docs/TESTING_AND_VERIFICATION.md`](./docs/TESTING_AND_VERIFICATION.md)
  - Known Issues & Risks: [`docs/KNOWN_ISSUES_AND_RISKS.md`](./docs/KNOWN_ISSUES_AND_RISKS.md)
  - Technical Specification: [`docs/LAM_IMPLEMENTATION_SPECIFICATION.md`](./docs/LAM_IMPLEMENTATION_SPECIFICATION.md)

---

## 3. Local Setup & Prerequisites

### Prerequisites
- Python 3.11+
- `uv` (recommended) or `pip` / `poetry`
- PostgreSQL 15+ (or SQLite for local development/testing)

### Installation
```bash
# Clone and enter directory
cd /home/dev/Desktop/projects/ai-tuitor/lam

# Create virtual environment and install dependencies in editable mode
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
```

---

## 4. Database Migrations

LAM uses Alembic for asynchronous schema migrations:

```bash
# Apply migrations to head
alembic upgrade head

# Rollback migrations to base
alembic downgrade base

# Create a new migration revision
alembic revision --autogenerate -m "describe_change"
```

---

## 5. Verification & Testing

Every code change must pass all mandatory quality gates:

```bash
# 1. Code style and linter
ruff check .

# 2. Code formatting check
ruff format --check .

# 3. Strict static type checking
mypy --strict src/lam tests

# 4. Automated test suite
pytest -v
```

---

## 6. API Reference & Health Checks

Start the service locally:
```bash
uvicorn lam.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints (Milestones M0 – M2)
* **Health Probes:**
  - `GET /health/live` — Liveness probe returning `{"status": "alive"}`.
  - `GET /health/ready` — Readiness probe verifying PostgreSQL connection pool: `{"status": "ready", "database": "connected"}`.
* **Event Ingestion:**
  - `POST /v1/events` — Validates, deduplicates, and stores learning events. Ingests evidence, evaluates misconception hypotheses, and performs BKT state transitions for eligible events. Idempotent by `(tenant_id, event_id)`.
* **Recommendations:**
  - `POST /v1/recommendations` — 7-tier deterministic recommendation engine (Tier 1 Safety Stop $\rightarrow$ Tier 2 Prerequisite Remediation $\rightarrow$ Tier 3 Diagnostic Probe for confirmed misconceptions $\rightarrow$ Tier 4 Overdue Spaced Retrieval $\rightarrow$ Tier 5 Mastery Verification $\rightarrow$ Tier 6 Curriculum Progression $\rightarrow$ Tier 7 Practice Fit).
* **Learner State & Diagnoses:**
  - `GET /v1/learners/{learner_id}/state` — Retrieves all concept states for the authorized student.
  - `GET /v1/learners/{learner_id}/concepts/{concept_id}/state` — Retrieves state for a single concept.
  - `GET /v1/learners/{learner_id}/diagnoses` — Retrieves all misconception hypotheses and their confirmation/retirement status.
  - `GET /v1/learners/{learner_id}/concepts/{concept_id}/diagnoses` — Retrieves misconception hypotheses for a specific concept.
* **Spaced Retrieval Schedule:**
  - `GET /v1/learners/{learner_id}/reviews` — Evaluates forgetting curves ($R(t)=\exp(-\Delta t / S)$) and returns scheduled reviews categorized by priority (`overdue`, `due_soon`, `maintained`).
* **Curriculum Knowledge Graph:**
  - `POST /v1/curriculum/validate` — Validates curriculum graph acyclicity (DFS 3-color) and returns topological sort order.
  - `POST /v1/curriculum/check-prerequisites` — Evaluates student prerequisite readiness given their current concept mastery map.

---

## 7. Containerized Deployment (Docker & Compose)

Build and run using the production multi-stage `Dockerfile`:
```bash
# Build the container image
docker build -t lam-service:latest .

# Run container with environment configuration
docker run -d -p 8000:8000 --env-file .env.production lam-service:latest
```

Or spin up the complete local staging stack (PostgreSQL 16 container + LAM service) using Docker Compose:
```bash
docker compose up --build
```

---

## 8. Host Integration Client SDK

Host applications (e.g. Qrie backend relay) interact with LAM using `LamRelayClient` in `src/lam/infrastructure/clients/lam_client.py`:

```python
from lam.infrastructure.clients.lam_client import LamClientConfig, LamRelayClient

config = LamClientConfig(
    base_url="http://localhost:8000",
    tenant_id="tenant_qrie_staging",
    jwt_token=jwt_token,
    connect_timeout_seconds=2.0,
    read_timeout_seconds=5.0,
    max_retries=3,
)

async with LamRelayClient(config) as client:
    # 1. Ingest learning event
    response = await client.ingest_event(event_dict)

    # 2. Query next-action recommendation
    recommendation = await client.get_recommendation(
        student_id="stu_01",
        concept_id="math.fractions.addition",
    )

    # 3. Replay offline outbox batch
    outbox_result = await client.replay_outbox(outbox_events)
```

