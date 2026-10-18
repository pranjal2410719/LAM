# Changelog

All notable changes to the Learning Adaptation Model (LAM) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
