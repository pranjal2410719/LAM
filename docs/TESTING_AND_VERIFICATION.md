# Testing and Verification Log

**Last Execution Date:** 2026-10-18  
**Environment:** Linux (x86_64), Python 3.11.16, PostgreSQL 16 (podman container `lam-postgres-test`) & SQLite (aiosqlite in-memory)  
**Milestone:** M0 (Service Foundation, Cryptographic Auth & Concurrency Hardening)  

---

## 1. Test Execution Summary

| Test Category | Command | Target | Total | Passed | Failed | Status | Evidence / Notes |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Code Style & Lint** | `ruff check .` | Whole project | - | - | 0 | `PASSED` | 0 errors across all Python files. |
| **Formatting** | `ruff format --check .` | Whole project | 36 files | 36 | 0 | `PASSED` | All source, test, and migration files formatted. |
| **Static Type Check** | `mypy --strict src/lam tests` | Source & tests | 25 files | 25 | 0 | `PASSED` | Zero type errors in strict mode. |
| **Unit Tests** | `pytest tests/unit/ -v` | Domain logic | 3 | 3 | 0 | `PASSED` | Valid event, non-coercion, bounds checking. |
| **SQLite Integration** | `pytest tests/integration/test_event_ingestion.py -v` | Fast local testing | 3 | 3 | 0 | `PASSED` | Ingestion, idempotency, assisted vs unassisted. |
| **PostgreSQL Integration**| `pytest tests/integration/test_postgres_integration.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Connection, ingestion, idempotency deduplication, and tenant isolation on live PostgreSQL. |
| **PostgreSQL Concurrency**| `pytest tests/integration/test_postgres_concurrency.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Race condition duplicate submission, concurrent distinct state serialization, optimistic concurrency, and transaction rollback. |
| **Security & Auth Tests** | `pytest tests/security/ -v` | Cryptographic Auth & Isolation| 7 | 7 | 0 | `PASSED` | Forged token, expired token, cross-tenant header mismatch (403), admin string prefix rejection, verified admin role access, tenant data isolation. |
| **Database Migrations**| `DATABASE_URL=... alembic upgrade head && downgrade base && upgrade head` | PostgreSQL 16 | 1 rev | 1 | 0 | `PASSED` | Transactional DDL upgrade, rollback, and re-upgrade clean on PostgreSQL 16. |

---

## 2. PostgreSQL 16 Concurrency Assertions (`tests/integration/test_postgres_concurrency.py`)

- `test_concurrent_duplicate_event_submissions_race`: Dispatches 10 simultaneous identical event submissions via `asyncio.gather`. Asserts that all 10 return HTTP 200 (no 500 internal errors), exactly 1 returns `ingested`, 9 return `duplicate`, and the learner state total events count is exactly 1.
- `test_concurrent_distinct_events_for_same_concept`: Dispatches 5 concurrent distinct events for the same student and concept. Asserts all 5 return HTTP 200 `ingested`, and the database learner state total events count is 5 with `state_version >= 5`, proving row-level locking eliminates lost updates.
- `test_state_version_conflict_optimistic_concurrency`: Asserts that an update carrying a stale `state_version` raises `StateVersionConflictError`.
- `test_transaction_atomicity_and_rollback`: Submits a conflicting event; asserts HTTP 409 and verifies that zero partial writes were committed to `learner_states`.

---

## 3. Cryptographic Security Assertions (`tests/security/test_tenant_isolation.py`)

- `test_tenant_data_isolation`: Ingests event in Tenant A; proves data is completely inaccessible and invisible from Tenant B (HTTP 404).
- `test_missing_or_invalid_authorization`: Missing headers, non-bearer schemes, and raw malformed tokens rejected with HTTP 401.
- `test_forged_or_tampered_token_rejected`: Token signed with an attacker key rejected with HTTP 401.
- `test_expired_token_rejected`: Token with expired timestamp rejected with HTTP 401.
- `test_cross_tenant_token_mismatch_rejected`: Caller possessing valid token for Tenant Alpha attempting `X-Tenant-ID: tenant_beta` rejected with HTTP 403 Forbidden.
- `test_admin_prefix_does_not_grant_privilege`: Caller attempting privilege escalation via `admin_` prefix without verified admin claim in JWT rejected with HTTP 403.
- `test_verified_admin_can_access_cross_tenant`: Token containing verified `admin` role claim permitted to perform cross-tenant operations.

---

## 4. PostgreSQL 16 Test Suite Assertions (`tests/integration/test_postgres_integration.py`)

- `test_postgres_connection_and_table_presence`: Queries `information_schema.tables` on PostgreSQL 16; proves that `learning_events`, `learner_states`, and `alembic_version` are present.
- `test_postgres_event_ingestion_and_state_update`: Submits valid HTTP POST to `/v1/events` against PostgreSQL session pool; asserts HTTP 200, status `ingested`, and queries state verifying `total_events_count == 1`.
- `test_postgres_idempotency_deduplication`: Submits identical event twice to `/v1/events` against PostgreSQL; asserts first returns `ingested`, second returns `duplicate`, and `total_events_count` remains 1. Proves database uniqueness constraint `uq_tenant_event_id` enforces deduplication.
- `test_postgres_tenant_isolation`: Ingests event in `tenant_pg_alpha` on PostgreSQL. Queries from `tenant_pg_beta`; asserts HTTP 404. Proves PostgreSQL queries enforce tenant boundary.
