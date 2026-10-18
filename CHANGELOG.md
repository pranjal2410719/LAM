# Changelog

All notable changes to the Learning Adaptation Model (LAM) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-10-18 (BKT Domain Engine & Production Fail-Closed Configuration)

### Added
- **Pure Python BKT Engine (`src/lam/domain/mastery/bkt.py`):**
  - Implemented Corbett & Anderson (1995) two-step Bayesian Knowledge Tracing engine.
  - Zero framework/database dependencies; fully typed dataclasses for `BKTParameters` and `BKTTransitionResult`.
  - Non-degeneracy validation enforcing positive item discrimination ($P(G) < 0.50$, $P(S) < 0.50$, $P(G) + P(S) < 1.0$).
  - Negative evidence gating: assisted attempts and missing correctness signals bypass BKT updates.
  - Unit tests (`tests/unit/test_bkt.py`) verifying all four D-02 published deterministic test vectors.
- **Operative Epistemic Uncertainty Calculator (`bkt.py::compute_operational_uncertainty`):**
  - Formally implemented $U(n) = \min(1.0, \frac{1}{\sqrt{n_{\text{indep}} + 1}})$.
  - Corrected arithmetic: exactly $n_{\text{indep}} \ge 44$ observations are required for $U \le 0.15$.
- **Fail-Closed Production JWT Configuration (`src/lam/infrastructure/config.py`):**
  - Enforced that production environments reject startup with missing, empty, default, or weak (< 32 chars) JWT secrets.
  - Added unit test suite `tests/unit/test_config_security.py` (5/5 passed).
- **End-to-End Trajectory Ingestion Test (`tests/integration/test_event_ingestion.py`):**
  - Multi-step integration test verifying unassisted correct/incorrect attempts produce exact BKT trajectory.

### Changed
- **Learner State Transition (`src/lam/infrastructure/repositories/state_repository.py`):**
  - Replaced interim fixed-step `+0.2` increments with the pure domain `BKTEngine`.
  - Persisted BKT independent mastery and operational uncertainty on unassisted attempts.

---

## [0.1.2] - 2026-10-18 (Authentication Security Hardening & Concurrency Safety)

### Added
- **Cryptographic JWT Authentication (`src/lam/infrastructure/authentication/jwt.py`):**
  - Cryptographically signed JWT token creation and verification (`PyJWT`).
  - Strict verification of signature, expiration (`exp`), issuer (`iss`), and audience (`aud`).
  - Explicit claims for tenant (`tid`), client subject (`sub`), and roles (`roles`).
  - Configuration settings via `pydantic-settings` in `src/lam/infrastructure/config.py`.
- **PostgreSQL High-Concurrency & Race Verification (`tests/integration/test_postgres_concurrency.py`):**
  - Simultaneous duplicate event submissions race test with 10 concurrent requests (1 ingested, 9 duplicate, 0 internal errors).
  - Concurrent distinct event submissions for same student safely serialized via PostgreSQL row locks (`with_for_update`).
  - Optimistic concurrency control test (`StateVersionConflictError` on stale `state_version`).
  - Atomic transaction rollback test (no partial writes on failed requests).
- **Expanded Security Test Suite (`tests/security/test_tenant_isolation.py`):**
  - Rejection of forged/tampered tokens (401).
  - Rejection of expired tokens (401).
  - Rejection of cross-tenant token mismatch with `X-Tenant-ID` header (403).
  - Rejection of caller-controlled `admin_` prefix escalation attempts.
  - Verification of authorized multi-tenant access for tokens with verified `admin` role claim.

### Fixed
- **Authentication Bypass / Spoofing Vulnerability (P1 Security Fix):**
  - Eliminated caller-controlled token string prefix checking (`admin_`) and unverified client ID derivation.
  - Enforced server-side cryptographic token validation and tenant claim binding.
- **Concurrent Ingestion & State Race Conditions (P2 Concurrency Fix):**
  - Added savepoint retries to `LedgerRepository` to handle race conditions during concurrent duplicate event submissions without raising 500s.
  - Added row-level locking (`with_for_update`) to `StateRepository.record_event_state_transition` ensuring serializable, race-safe learner state updates.

### Changed
- **Mastery Decision Records (`docs/decisions/`):**
  - Clarified statistical distinction in `D-01` and `D-02`: standard BKT yields a point estimate $P(L_t)$, not a parameter credible interval. Defined M1 operational epistemic uncertainty bound based on unassisted observation counts.
  - Explicitly marked candidate parameter status ($P(L_0)=0.10, P(T)=0.20, P(G)=0.20, P(S)=0.10$).

---

## [0.1.1] - 2026-10-18 (M0 Hardening & PostgreSQL Verification)

### Added
- **PostgreSQL Integration Suite (`tests/integration/test_postgres_integration.py`):**
  - Live PostgreSQL 16 container test coverage: schema verification, event ingestion, idempotency deduplication, and multi-tenant isolation.
- **GitHub Actions CI (`.github/workflows/ci.yml`):**
  - Workflow executing `ruff check`, `ruff format`, `mypy --strict`, Alembic migrations on a live PostgreSQL service container, and `pytest`.
- **Decision Records (`docs/decisions/`):**
  - Drafted `docs/decisions/D-01-mastery-policy.md` (Mastery confirmation rules, evidence count, and session separation).
  - Drafted `docs/decisions/D-02-bkt-parameters.md` (Mathematical BKT equations, candidate parameters $P(L_0), P(T), P(G), P(S)$, and deterministic test vectors).
- **Repository Hygiene:**
  - Added `.gitignore` covering bytecode, test caches, local databases (`lam_dev.db`), and environment files.

### Changed
- **Schema Lifecycle Decoupling (`src/lam/main.py`, `src/lam/infrastructure/database/session.py`):**
  - Removed `Base.metadata.create_all()` table creation on service startup.
  - Added non-mutating connection check `verify_db_connection()` executing `SELECT 1`.
  - Enforced Alembic migrations as the exclusive schema lifecycle authority.

### Fixed
- **Git Tracking Cleanup:**
  - Safely untracked committed bytecode caches (`__pycache__`, `*.pyc`) and local SQLite database (`lam_dev.db`) from git index.

---

## [0.1.0] - 2026-10-18 (Initial Foundation Release)

### Added
- **Repository Scaffold & Configuration:**
  - Setup Python 3.11+ project using `pyproject.toml`.
  - Configured `ruff`, `mypy --strict`, and `pytest`.
- **Domain Layer (`src/lam/domain/`):**
  - `LearningEvent` model enforcing the non-coercion rule (missing signals remain `None`).
  - `LearnerConceptState` model separating independent mastery from assisted performance.
- **Persistence Layer (`src/lam/infrastructure/database/`):**
  - SQLAlchemy 2.0 async models for `learning_events` (append-only ledger) and `learner_states`.
  - Database-enforced idempotency via `UniqueConstraint("tenant_id", "event_id")`.
  - Optimistic concurrency control via `state_version` column.
  - Initial Alembic migration `6ed18e85f377`.
  - `LedgerRepository` and `StateRepository` for database access.
- **Application Services (`src/lam/application/`):**
  - `EventIngestionService` coordinating atomic ledger insertion and state updates.
- **API Layer (`src/lam/api/`):**
  - `POST /v1/events` endpoint with server-side tenant authorization.
  - `GET /v1/learners/{learner_id}/state` and `GET /v1/learners/{learner_id}/concepts/{concept_id}/state`.
  - Liveness and readiness probes (`/health/live`, `/health/ready`).
  - Standardized error response contract `ErrorResponse`.
- **Security & Authorization (`src/lam/infrastructure/authentication/`):**
  - Server-side token and `X-Tenant-ID` verification dependency.
  - Cross-tenant data isolation preventing unauthorized access.
