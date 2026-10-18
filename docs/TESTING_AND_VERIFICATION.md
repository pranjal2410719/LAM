# Testing and Verification Log

**Last Execution Date:** 2026-10-18  
**Environment:** Linux (x86_64), Python 3.11.16, PostgreSQL 16 (podman container) & SQLite (aiosqlite in-memory)  
**Milestone:** M0 (Service Foundation & Hardening)  

---

## 1. Test Execution Summary

| Test Category | Command | Target | Total | Passed | Failed | Status | Evidence / Notes |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Code Style & Lint** | `ruff check .` | Whole project | - | - | 0 | `PASSED` | 0 errors across all Python files. |
| **Formatting** | `ruff format --check .` | Whole project | 30 files | 30 | 0 | `PASSED` | All source, test, and migration files formatted. |
| **Static Type Check** | `mypy --strict src/lam tests` | Source & tests | 21 files | 21 | 0 | `PASSED` | Zero type errors in strict mode. |
| **Unit Tests** | `pytest tests/unit/ -v` | Domain logic | 3 | 3 | 0 | `PASSED` | Valid event, non-coercion, bounds checking. |
| **SQLite Integration** | `pytest tests/integration/test_event_ingestion.py -v` | Fast local testing | 3 | 3 | 0 | `PASSED` | Ingestion, idempotency, assisted vs unassisted. |
| **PostgreSQL Integration**| `pytest tests/integration/test_postgres_integration.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Connection, ingestion, idempotency deduplication, and tenant isolation on live PostgreSQL. |
| **Security Tests** | `pytest tests/security/ -v` | Auth & Isolation| 2 | 2 | 0 | `PASSED` | Tenant isolation, 401 unauthenticated check. |
| **Database Migrations**| `DATABASE_URL=... alembic upgrade head && downgrade base && upgrade head` | PostgreSQL 16 | 1 rev | 1 | 0 | `PASSED` | Transactional DDL upgrade, rollback, and re-upgrade clean on PostgreSQL 16. |

---

## 2. PostgreSQL 16 Test Suite Assertions (`tests/integration/test_postgres_integration.py`)

- `test_postgres_connection_and_table_presence`: Queries `information_schema.tables` on PostgreSQL 16; proves that `learning_events`, `learner_states`, and `alembic_version` are present.
- `test_postgres_event_ingestion_and_state_update`: Submits valid HTTP POST to `/v1/events` against PostgreSQL session pool; asserts HTTP 200, status `ingested`, and queries state verifying `total_events_count == 1`.
- `test_postgres_idempotency_deduplication`: Submits identical event twice to `/v1/events` against PostgreSQL; asserts first returns `ingested`, second returns `duplicate`, and `total_events_count` remains 1. Proves database uniqueness constraint `uq_tenant_event_id` enforces deduplication.
- `test_postgres_tenant_isolation`: Ingests event in `tenant_pg_alpha` on PostgreSQL. Queries from `tenant_pg_beta`; asserts HTTP 404. Proves PostgreSQL queries enforce tenant boundary.

---

## 3. SQLite Local Test Suite Assertions (`tests/integration/test_event_ingestion.py`)

- `test_successful_event_ingestion`: Proves basic local flow.
- `test_idempotent_event_deduplication`: Proves in-memory deduplication.
- `test_assisted_success_does_not_advance_independent_mastery`: Asserts that `assistance_level=4` updates `assisted_performance` while `independent_mastery` remains strictly `0.0`.
