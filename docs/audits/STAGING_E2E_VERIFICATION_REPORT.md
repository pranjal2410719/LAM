# LAM Staging End-to-End Verification & Readiness Audit

**Audit date:** 2026-10-25  
**Target:** https://lam-service-staging.onrender.com  
**Intended release branch:** `release/v0.4.0-staging`  
**Reported deployed commit:** `6447b94ac0c56897903e72d72cd8157968349c3d`  
**Overall verdict:** **STAGING VALIDATION INCOMPLETE**

## Evidence provenance

This report records the terminal audit summary supplied by the project owner on 2026-10-25. The assistant did not independently rerun the live probes or inspect Render deployment metadata. Treat the following as **reported results** until independently reproduced. This report does not claim that a migration has been applied.

## Executive summary

- Public and health endpoints reportedly returned HTTP 200: `/`, `/health/live`, `/health/ready`, `/openapi.json`, and `/docs`.
- Authentication/authorization baseline reportedly passed 23/23 scenarios.
- Authorized in-memory curriculum DAG validation reportedly returned HTTP 200.
- The Render PostgreSQL connection reportedly succeeds, but the database schema is reported to be unmigrated.
- Authorized database-backed requests reportedly return HTTP 500 because required application tables are absent.
- Event ingestion, learner-state persistence, duplicate-event idempotency, BKT updates, persisted-state recommendations, and the full deployed learning lifecycle remain **not proven**.
- LAM is **not ready for Qrie staging integration** and is **not production-ready** until the migration state and stateful lifecycle are verified.

## 1. Deployment identity

| Check | Reported result | Status |
|---|---|---|
| Intended release branch | `release/v0.4.0-staging` | Reported |
| Deployed commit | `6447b94ac0c56897903e72d72cd8157968349c3d` | Reported; confirm in Render metadata |
| Public/health endpoints | HTTP 200 | Reported pass |
| Database readiness | Connected | Connectivity only; not schema proof |

## 2. Authentication and authorization baseline

The audit summary reports 23/23 scenarios passed, including:

- Missing, malformed, expired, tampered, wrong-issuer and wrong-audience JWTs rejected with HTTP 401.
- Missing canonical `sub` or `tid` claims rejected with HTTP 401.
- Multiple roles and unrecognized roles rejected with HTTP 403.
- Mismatched and whitespace-only `X-Tenant-ID` headers rejected with HTTP 403.
- Student attempts at event ingestion, recommendations and curriculum DAG validation rejected with HTTP 403.
- Student access to another learner's state or reviews rejected with HTTP 403.
- Authorized service token calling in-memory curriculum DAG validation returned HTTP 200.

**Scope limitation:** These reported cases support the specific tested controls. They do not independently prove every route, every object type, or full cross-tenant isolation under all valid identity combinations.

## 3. Database migration blocker

The audit reports that the Render staging PostgreSQL database has not had Alembic migrations applied. The expected migration head is reported as `a78f20436d91`.

Reported symptoms:
- `/health/ready` returns HTTP 200 with database connected.
- Authorized requests to database-backed routes such as `POST /v1/events` and `GET /v1/learners/{id}/state` return HTTP 500.
- The suspected cause is that required application tables do not exist.

**Required verification before migration:** confirm the deployed commit, database target, current Alembic revision, expected migration head, and whether any existing data must be preserved. Applying migrations changes persistent database schema and requires explicit authorization. Do not treat this report as authorization to mutate the database.

## 4. Stateful lifecycle verification matrix

| Test | Current status | Exit criterion |
|---|---|---|
| Authenticated event ingestion | BLOCKED / NOT PROVEN | Valid authorized event is accepted and durably persisted |
| Learner-state read/write | BLOCKED / NOT PROVEN | Persisted state matches the accepted evidence |
| Duplicate event replay | NOT PROVEN | Same tenant/event ID produces one logical effect and no state drift |
| BKT/mastery update | NOT PROVEN | State changes match a documented, independently calculated test case |
| Recommendation based on persisted state | NOT PROVEN | Recommendation corresponds to the resulting learner state and policy |
| Reviews/retrieval scheduling | NOT PROVEN on deployed DB | Review state and due dates match expected rules |
| Cross-tenant isolation | PARTIALLY REPORTED | Re-run against two authorized disposable tenants and all relevant resource types |
| Complete deployed lifecycle | BLOCKED | Event → persistence → state → recommendation → review completes over public HTTP |

## 5. Safe next steps

1. Inspect the local audit-agent changes and preserve unrelated work; this report does not assert the local worktree is clean.
2. Independently confirm the running deployment SHA from Render metadata.
3. Confirm the current Alembic revision and target database identity using an approved, non-destructive inspection.
4. Obtain explicit authorization before applying `alembic upgrade head` to staging.
5. Apply the migration using a controlled method appropriate to the actual Render service plan and verify the database revision and required tables.
6. Re-run stateful tests using disposable staging tenants and learners only.
7. Capture sanitized request/response evidence, state before/after, event IDs and timestamps.
8. Reassess readiness only after P0 security, integrity and lifecycle checks pass.

Render documents that Free web services do not support dashboard shell/SSH access, and pre-deploy commands are available for paid web services, private services and background workers. See [Render Free limitations](https://render.com/docs/free), [Deploys](https://render.com/docs/deploys), and [SSH and Shell Access](https://render.com/docs/ssh).

## 6. Readiness verdict

**STAGING VALIDATION INCOMPLETE.**

- Authentication/authorization baseline: reported pass for tested scenarios.
- Database connectivity: reported pass.
- Database schema: reported unmigrated; verify actual revision.
- Stateful E2E: blocked.
- Qrie staging integration: not ready.
- Production readiness: not established.

Do not use real student data or claim educational effectiveness from these results. Code-level tests and successful health checks do not substitute for an authenticated, persisted, end-to-end learning lifecycle.
