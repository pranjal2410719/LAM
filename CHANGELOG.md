# Changelog

All notable changes to the Learning Adaptation Model (LAM) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-10-18

### Added
- **Repository Scaffold & Configuration:**
  - Setup Python 3.11+ project using `pyproject.toml`.
  - Configured `ruff` for linting and code formatting.
  - Configured `mypy` in `--strict` mode for static type safety.
  - Configured `pytest` with `pytest-asyncio` for asynchronous test execution.
- **Domain Layer (`src/lam/domain/`):**
  - `LearningEvent` model enforcing the non-coercion rule (missing signals remain `None`).
  - `LearnerConceptState` model separating independent mastery from assisted performance.
- **Persistence Layer (`src/lam/infrastructure/database/`):**
  - SQLAlchemy 2.0 async models for `learning_events` (append-only ledger) and `learner_states`.
  - Database-enforced idempotency via `UniqueConstraint("tenant_id", "event_id")`.
  - Optimistic concurrency control via `state_version` column.
  - Initial Alembic migration `6ed18e85f377` with tested upgrade and downgrade cycles.
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
- **Automated Verification Suite (`tests/`):**
  - Unit tests for event validation and non-coercion.
  - Integration tests for event ingestion, idempotency replay, and assisted vs unassisted metrics.
  - Security tests for multi-tenant isolation and 401 rejection.
