# Learning Adaptation Model (LAM)

LAM is an independent, versioned backend service that converts structured student-learning evidence into an authoritative learner state and recommends the next optimal teaching action.

---

## 1. System Boundaries

* **LAM owns:** Learning evidence validation, immutable append-only event ledger, multi-dimensional learner state, Bayesian Knowledge Tracing (BKT) mastery estimation, misconception diagnosis hypotheses, assistance escalation policy, spaced retrieval scheduling, and decision auditability.
* **Qrie / Host Application owns:** Student UI, chat turns, avatar/voice delivery, curriculum content, question/hint authoring, answer verification (symbolic math check, code tests, etc.), and delivery of the recommended intervention.

---

## 2. Current Implementation Status

* **Active Milestone:** **M0 — Service Foundation** (`VERIFIED`)
* **Implemented & Verified:**
  - Strict Pydantic v2 schemas enforcing the non-coercion rule (`None` remains `None`).
  - Append-only event ledger with database-level uniqueness constraints for idempotency.
  - Persistent multi-dimensional learner state strictly separating independent mastery from assisted performance.
  - Server-side tenant authorization and cross-tenant data isolation.
  - Alembic asynchronous database migrations with verified upgrade and downgrade cycles.
  - Full CI test suite (100% passing): `ruff`, `mypy --strict`, and `pytest`.
* **Detailed Status & Roadmap:**
  - Current Status: [`docs/PROJECT_STATUS.md`](./docs/PROJECT_STATUS.md)
  - Task Backlog: [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md)
  - Changelog: [`CHANGELOG.md`](./CHANGELOG.md)
  - Test Evidence: [`docs/TESTING_AND_VERIFICATION.md`](./docs/TESTING_AND_VERIFICATION.md)
  - Traceability Matrix: [`docs/REQUIREMENT_TRACEABILITY.md`](./docs/REQUIREMENT_TRACEABILITY.md)
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

### Endpoints (Milestone M0)
* **Health Probes:**
  - `GET /health/live` — Returns `{"status": "alive"}`
  - `GET /health/ready` — Returns `{"status": "ready", "database": "connected"}`
* **Event Ingestion:**
  - `POST /v1/events` — Validates and stores a learning event. Requires `Authorization: Bearer <token>` and `X-Tenant-ID: <tenant>`. Idempotent: replaying identical `event_id` returns duplicate status without mutating state.
* **Learner State:**
  - `GET /v1/learners/{learner_id}/state` — Retrieves all concept states for the authorized student.
  - `GET /v1/learners/{learner_id}/concepts/{concept_id}/state` — Retrieves state for a single concept.
