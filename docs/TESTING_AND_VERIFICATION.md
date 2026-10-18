# Testing and Verification Log

**Last Execution Date:** 2026-10-18  
**Environment:** Linux (x86_64), Python 3.11.16, PostgreSQL 16 (podman container `lam-postgres-test`) & SQLite (aiosqlite in-memory)  
**Milestone:** M0 (Foundation Hardened) & M1 (BKT Domain Engine & Integration)  

---

## 1. Test Execution Summary

| Test Category | Command | Target | Total | Passed | Failed | Status | Evidence / Notes |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Code Style & Lint** | `ruff check .` | Whole project | - | - | 0 | `PASSED` | 0 errors across all Python files. |
| **Formatting** | `ruff format --check .` | Whole project | 40 files | 40 | 0 | `PASSED` | All source, test, and migration files formatted. |
| **Static Type Check** | `mypy --strict src/lam tests` | Source & tests | 29 files | 29 | 0 | `PASSED` | Zero type errors in strict mode. |
| **BKT Domain Tests** | `pytest tests/unit/test_bkt.py -v` | Pure Python BKT engine | 7 | 7 | 0 | `PASSED` | Parameters, bounds, 4-step D-02 vectors, assisted bypass, missing signal bypass, boundary stability, $n \ge 44$ uncertainty threshold. |
| **Config Security Tests**| `pytest tests/unit/test_config_security.py -v` | Fail-closed production config | 5 | 5 | 0 | `PASSED` | Dev default allowed; production rejects missing, default, or weak secrets (< 32 chars); production accepts valid strong keys. |
| **Unit Event Validation**| `pytest tests/unit/test_events_validation.py -v` | Domain event schema | 3 | 3 | 0 | `PASSED` | Valid event, non-coercion, bounds checking. |
| **SQLite Integration** | `pytest tests/integration/test_event_ingestion.py -v` | Fast local testing | 4 | 4 | 0 | `PASSED` | Ingestion, idempotency, assisted vs unassisted, and end-to-end multi-step BKT trajectory matching D-02. |
| **PostgreSQL Integration**| `pytest tests/integration/test_postgres_integration.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Connection, ingestion, idempotency deduplication, and tenant isolation on live PostgreSQL. |
| **PostgreSQL Concurrency**| `pytest tests/integration/test_postgres_concurrency.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Race condition duplicate submission, concurrent distinct state serialization, optimistic concurrency, and transaction rollback. |
| **Security & Auth Tests** | `pytest tests/security/ -v` | Cryptographic Auth & Isolation| 7 | 7 | 0 | `PASSED` | Forged token, expired token, cross-tenant header mismatch (403), admin string prefix rejection, verified admin role access, tenant data isolation. |
| **Database Migrations**| `DATABASE_URL=... alembic upgrade head` | PostgreSQL 16 | 1 rev | 1 | 0 | `PASSED` | Transactional DDL upgrade clean on PostgreSQL 16. |

---

## 2. BKT Domain Test Assertions (`tests/unit/test_bkt.py`)

- `test_bkt_default_parameters`: Validates $P(L_0)=0.10, P(T)=0.20, P(G)=0.20, P(S)=0.10$ and version `bkt_v1_baseline`.
- `test_bkt_parameter_validation_rejects_invalid_values`: Validates open intervals for $P(L_0)$, half-open for $P(T)$, and positive discrimination ($P(G) < 0.50$, $P(S) < 0.50$).
- `test_d02_published_deterministic_test_vectors`: Verifies exact mathematical outputs for the 4-step sequence from Decision D-02:
  - Step 0 (Prior): `0.1000`
  - Step 1 (Correct): Intermediate `0.3333`, Posterior `0.4667`
  - Step 2 (Incorrect): Intermediate `0.0986`, Posterior `0.2789`
  - Step 3 (Correct): Intermediate `0.6351`, Posterior `0.7081`
- `test_assisted_attempt_bypasses_bkt_transition`: Proves scaffolded attempts leave BKT mastery untouched.
- `test_missing_correctness_signal_bypasses_bkt`: Proves non-scored events leave BKT mastery untouched.
- `test_boundary_values_and_numerical_stability`: Proves stability at 0.0 and 1.0 probability extremes.
- `test_operational_uncertainty_threshold_arithmetic`: Proves $U(43) \approx 0.15076 > 0.15$ (fails) and $U(44) \approx 0.14907 \le 0.15$ (passes).

---

## 3. Production Configuration Security Assertions (`tests/unit/test_config_security.py`)

- `test_development_allows_default_secret`: Confirms local dev/testing environments function without manual key configuration.
- `test_production_rejects_missing_secret`: Confirms production fails closed if secret is empty or omitted.
- `test_production_rejects_insecure_default_secret`: Confirms production fails closed if the dev default secret is supplied.
- `test_production_rejects_short_secret`: Confirms production fails closed if the secret has fewer than 32 characters.
- `test_production_accepts_valid_strong_secret`: Confirms production initializes when a high-entropy 32+ character secret is provided.

---

## 4. PostgreSQL 16 Concurrency Assertions (`tests/integration/test_postgres_concurrency.py`)

- `test_concurrent_duplicate_event_submissions_race`: Dispatches 10 simultaneous identical event submissions via `asyncio.gather`. Asserts that all 10 return HTTP 200 (no 500 internal errors), exactly 1 returns `ingested`, 9 return `duplicate`, and the learner state total events count is exactly 1.
- `test_concurrent_distinct_events_for_same_concept`: Dispatches 5 concurrent distinct events for the same student and concept. Asserts all 5 return HTTP 200 `ingested`, and the database learner state total events count is 5 with `state_version >= 5`, proving row-level locking eliminates lost updates.
- `test_state_version_conflict_optimistic_concurrency`: Asserts that an update carrying a stale `state_version` raises `StateVersionConflictError`.
- `test_transaction_atomicity_and_rollback`: Submits a conflicting event; asserts HTTP 409 and verifies that zero partial writes were committed to `learner_states`.

---

## 5. Cryptographic Security Assertions (`tests/security/test_tenant_isolation.py`)

- `test_tenant_data_isolation`: Ingests event in Tenant A; proves data is completely inaccessible and invisible from Tenant B (HTTP 404).
- `test_missing_or_invalid_authorization`: Missing headers, non-bearer schemes, and raw malformed tokens rejected with HTTP 401.
- `test_forged_or_tampered_token_rejected`: Token signed with an attacker key rejected with HTTP 401.
- `test_expired_token_rejected`: Token with expired timestamp rejected with HTTP 401.
- `test_cross_tenant_token_mismatch_rejected`: Caller possessing valid token for Tenant Alpha attempting `X-Tenant-ID: tenant_beta` rejected with HTTP 403 Forbidden.
- `test_admin_prefix_does_not_grant_privilege`: Caller attempting privilege escalation via `admin_` prefix without verified admin claim in JWT rejected with HTTP 403.
- `test_verified_admin_can_access_cross_tenant`: Token containing verified `admin` role claim permitted to perform cross-tenant operations.
