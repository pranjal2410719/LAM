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
  - **Full Quality Gates (100% passing in CI):** `ruff check .` (0 errors), `ruff format --check .` (89 files clean), `mypy --strict src/lam tests` (0 issues across 71 source files), and `pytest -v` (**142 / 142 tests passing** against PostgreSQL 16 in remote CI).
* **Detailed Status & Deployment Runbooks:**
  - Day 1 Baseline Audit: [`docs/audits/issue-3-baseline-audit.md`](./docs/audits/issue-3-baseline-audit.md)
  - Completion Audit: [`docs/LAM_COMPLETION_AUDIT.md`](./docs/LAM_COMPLETION_AUDIT.md)
  - Current Status: [`docs/PROJECT_STATUS.md`](./docs/PROJECT_STATUS.md)
  - Integration Contract: [`docs/QRIE_INTEGRATION_CONTRACT.md`](./docs/QRIE_INTEGRATION_CONTRACT.md)
  - Staging Checklist: [`docs/STAGING_RELEASE_CHECKLIST.md`](./docs/STAGING_RELEASE_CHECKLIST.md)
  - Changelog: [`CHANGELOG.md`](./CHANGELOG.md)
  - Test Evidence: [`docs/TESTING_AND_VERIFICATION.md`](./docs/TESTING_AND_VERIFICATION.md)
  - Known Issues & Risks: [`docs/KNOWN_ISSUES_AND_RISKS.md`](./docs/KNOWN_ISSUES_AND_RISKS.md)
  - Technical Specification: [`docs/LAM_IMPLEMENTATION_SPECIFICATION.md`](./docs/LAM_IMPLEMENTATION_SPECIFICATION.md)

---

## 3. Supported Developer Workflows

LAM supports two distinct, isolated development workflows:
1. **Workflow A: Local SQLite Development (Zero External Services)** — Ideal for fast local development, unit tests, and lightweight endpoint debugging without running Docker or PostgreSQL.
2. **Workflow B: Docker Compose Multi-Container Stack (PostgreSQL 16 + LAM Service)** — Ideal for full production simulation, transactional DDL verification, concurrency checks, and running the entire integration test suite.

---

### Workflow A: Local SQLite Development (Zero External Services)

#### Prerequisites
- **Python:** `3.11.x` (`>=3.11, <3.13` supported).
- **Package Manager:** Astral `uv` (recommended) or standard `pip`.

#### A.1 Setup & Installation

##### Windows (PowerShell)
```powershell
# 1. Clone repository and navigate to root
git clone https://github.com/pranjal2410719/LAM.git
cd LAM

# 2. Install uv (if not already installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. Create virtual environment with Python 3.11
uv venv --python 3.11 .venv

# 4. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 5. Install dependencies in editable mode
uv pip install -e ".[dev]"

# 6. Configure local environment for SQLite
Copy-Item .env.example .env
```

*Alternative using standard `python -m venv` without `uv`:*
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

##### Linux / macOS (Bash / Zsh)
```bash
# 1. Clone repository and navigate to root
git clone https://github.com/pranjal2410719/LAM.git
cd LAM

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Create virtual environment with Python 3.11
uv venv --python 3.11 .venv

# 4. Activate virtual environment
source .venv/bin/activate

# 5. Install dependencies in editable mode
uv pip install -e ".[dev]"

# 6. Configure local environment for SQLite
cp .env.example .env
```

#### A.2 Database Migrations (Local SQLite)
By default, `.env` points to `sqlite+aiosqlite:///./lam_dev.db`:
```bash
alembic upgrade head
```

#### A.3 Run Local Unit & SQLite Tests
```bash
# Pure in-memory unit tests (79 tests — executes in seconds)
pytest tests/unit

# Unit + SQLite-backed integration tests (130 tests — zero external services needed)
pytest tests/unit tests/integration/test_curriculum_api.py tests/integration/test_event_ingestion.py tests/integration/test_recommendation_api.py tests/integration/test_reviews_api.py tests/integration/test_qrie_*.py tests/security
```

#### A.4 Start Local API & Health Verification
```bash
uvicorn lam.main:app --host 0.0.0.0 --port 8000 --reload
```
In a separate terminal:
```bash
# Verify liveness (returns {"status": "alive"})
curl -i http://localhost:8000/health/live

# Verify readiness (returns {"status": "ready", "database": "connected"})
curl -i http://localhost:8000/health/ready
```

---

### Workflow B: Multi-Container Stack via Docker Compose (PostgreSQL 16)

The Docker Compose stack starts an isolated PostgreSQL 16 container and the containerized LAM FastAPI service.

#### B.1 Prepare Configuration
Docker Compose uses `.env.compose` to prevent accidental contamination from local SQLite `.env` files:

##### Windows (PowerShell)
```powershell
Copy-Item .env.compose.example .env.compose
```

##### Linux / macOS (Bash / Zsh)
```bash
cp .env.compose.example .env.compose
```

Edit `.env.compose` to provide your local development secrets:
- `POSTGRES_PASSWORD`: Required password for the PostgreSQL container.
- `LAM_JWT_SECRET_KEY`: Required high-entropy JWT secret (minimum 32 characters).
- `HOST_PORT`: Host port mapping for LAM (defaults to `8000`, e.g. `http://localhost:8000`).
  *(Note: The container internally always listens on port 8000; `HOST_PORT` controls the external workstation port mapping).*
- `POSTGRES_HOST_PORT`: Host port mapping for PostgreSQL (defaults to `5432`).
- `COMPOSE_DATABASE_URL`: *(Optional)* Percent-encoded SQLAlchemy connection string override. Docker Compose variable substitution performs raw string interpolation and does **not** URL-encode characters. If `POSTGRES_PASSWORD` contains URL-reserved characters (e.g. `@`, `:`, `/`, `?`, `#`), the generated URL will cause SQLAlchemy connection parsing errors. In that case, manually construct the percent-encoded URL and set it here (e.g. `COMPOSE_DATABASE_URL=postgresql+asyncpg://lam_user:percent_encoded_password@postgres:5432/lam_db`).

> [!IMPORTANT]
> `docker-compose.yml` uses fail-closed variable interpolation (`${POSTGRES_PASSWORD:?Error...}`). If `POSTGRES_PASSWORD` or `LAM_JWT_SECRET_KEY` is missing, Compose refuses to start. Furthermore, Compose uses `COMPOSE_DATABASE_URL` internally to target the `postgres` container on port 5432, guaranteeing that an accidental SQLite `DATABASE_URL` in `.env` cannot contaminate the container.

#### B.2 Start the Services
```bash
# Validate configuration and start containers
docker compose --env-file .env.compose up -d --build
```

#### B.3 Verify Service Health & Readiness
```bash
# Check container status
docker compose ps

# Check liveness probe over HTTP
curl -i http://localhost:8000/health/live

# Check readiness probe (verifies database connectivity)
curl -i http://localhost:8000/health/ready
```

#### B.4 Run Migrations & Full Test Suite (PostgreSQL 16)
Once the PostgreSQL container is healthy:

##### Option 1: Run migrations inside the running LAM container
Inside the Docker network, database hostname `postgres` resolves to the PostgreSQL container.
The Compose service is defined as `lam-service` with container name `lam-api`:

```bash
# Using the Compose service name:
docker compose exec lam-service alembic upgrade head

# Or using the container name directly:
docker exec -it lam-api alembic upgrade head
```

##### Option 2: Run migrations from your host workstation
When running Alembic from the host workstation, the container-internal hostname `postgres` is not resolvable. Migrations must target `localhost` on the published PostgreSQL port (default `5432`).
Because `.env` defaults to local SQLite (`lam_dev.db`), you must explicitly override `DATABASE_URL` in your shell to point to the Compose PostgreSQL database:

**Windows PowerShell:**
```powershell
$env:DATABASE_URL="postgresql+asyncpg://lam_user:your_secure_postgres_password_here@localhost:5432/lam_db"
alembic upgrade head
```

**Linux / macOS (Bash / Zsh):**
```bash
DATABASE_URL="postgresql+asyncpg://lam_user:your_secure_postgres_password_here@localhost:5432/lam_db" alembic upgrade head
```

##### Full Integration Test Suite (Requires PostgreSQL 16)
With `DATABASE_URL` pointing to localhost PostgreSQL:
```bash
pytest -v
```

#### B.5 Stopping the Services
```bash
docker compose --env-file .env.compose down
```

---

## 4. Code Quality & Verification Gates

Before submitting any code changes, ensure all quality gates pass:

```bash
# 1. Code style and linter
ruff check .

# 2. Code formatting check
ruff format --check .

# 3. Strict static type checking
mypy --strict src/lam tests

# 4. Automated tests (Unit suite)
pytest tests/unit

# 5. Full automated test suite (requires PostgreSQL 16)
pytest -v
```

---

## 5. Host Integration Client SDK

Host applications (such as Qrie) interact with LAM using `LamRelayClient` in `src/lam/infrastructure/clients/lam_client.py`:

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
