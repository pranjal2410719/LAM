# LAM Staging Release & Deployment Checklist

**Environment:** Qrie Staging (`staging-lam.qrie.internal` / containerized service)  
**Target Milestone:** M2 (Closed-Loop Cognitive Core with Qrie Staging)  
**Date:** 2026-10-19  
**Status:** `READY FOR STAGING REVIEW`  

---

## 1. Environment-Specific Configuration & Secret Governance

| Item | Requirement | Verification Command / Check | Status |
|:---|:---|:---|:---:|
| **JWT Secret** | Production/Staging secret must NEVER use dev default; minimum 32 random characters (`openssl rand -hex 32`). | `Settings.validate_production_security()` raises `RuntimeError` if insecure. | `VERIFIED` |
| **Database Credentials** | Staging PostgreSQL 16 credentials managed via environment variables (`DATABASE_URL`). Non-root database user. | Check `.env.staging` (excluded from version control). | `VERIFIED` |
| **Tenant Binding** | Token tenant claim `tenant_id` must match `X-Tenant-ID` header; cross-tenant requests must return 403. | `tests/security/test_tenant_isolation.py` (7/7 passed). | `VERIFIED` |
| **CORS Policy** | Restricted strictly to Qrie staging domains (`https://staging.qrie.ai`). | Configured in FastAPI middleware. | `VERIFIED` |

---

## 2. Database Migrations & Rollback Procedures

| Migration ID | Description | Transactional | Upgrade Verification | Downgrade Verification | Status |
|:---|:---|:---:|:---:|:---:|:---:|
| `6ed18e85f377` | Baseline schema: `learning_events` and `learner_states` | Yes | `alembic upgrade 6ed18e85f377` | Clean | `VERIFIED` |
| `435e371938d3` | BKT parameter version: add `bkt_parameter_version` column | Yes | `alembic upgrade 435e371938d3` | Clean | `VERIFIED` |
| `a78f20436d91` | Misconception persistence: `misconception_hypotheses` and `hypothesis_audit_entries` | Yes | `alembic upgrade a78f20436d91` | Clean | `VERIFIED` |

### Pre-Deployment Migration Verification Command:
```bash
DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
```

### Rollback Command (in case of staging failure):
```bash
DATABASE_URL="postgresql+asyncpg://..." alembic downgrade -1
```

---

## 3. Service Reliability, Timeouts & Retries

1. **Client Timeout:** Qrie backend requests to LAM should use a **2.0s connect timeout** and **5.0s read timeout**.
2. **Exponential Backoff:** If LAM returns 502/503/504, Qrie client should retry up to 3 times with jittered exponential backoff ($200\text{ms}, 500\text{ms}, 1200\text{ms}$).
3. **Safe Degradation (Fallback):** If LAM is unreachable after 3 retries, Qrie MUST NOT fabricate a mastery estimate or simulate BKT updates. Qrie falls back to standard practice mode using the last cached recommendation or default practice probe (`diagnostic_probe`, safe_fallback=True), queuing events in the offline ledger outbox.

---

## 4. Health Checks & Observability

- **Liveness Probe:** `GET /health/live` $\rightarrow$ returns `200 OK {"status": "alive"}`.
- **Readiness Probe:** `GET /health/ready` $\rightarrow$ verifies PostgreSQL connection pool (`SELECT 1`); returns `200 OK {"status": "ready", "database": "connected"}` or `503 Service Unavailable`.
- **Structured Error Responses:** All error responses adhere strictly to RFC 7807 problem details:
  ```json
  {
    "error": {
      "code": "INVALID_EVENT_SCHEMA",
      "message": "The submitted payload does not satisfy the required schema.",
      "request_id": "req_01J...",
      "details": []
    }
  }
  ```

---

## 5. Staging Smoke Test Suite

Execute the automated smoke verification against the running staging container:
```bash
# 1. Verify health
curl -s http://localhost:8000/health/ready | jq .

# 2. Ingest test event
curl -s -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer $STAGING_JWT" \
  -H "X-Tenant-ID: tenant_staging" \
  -H "Content-Type: application/json" \
  -d '{"event_id":"smoke_01","student_id":"stu_smoke","session_id":"sess_smoke","concept_ids":["math.fractions.addition"],"item_id":"i1","timestamp":"2026-10-19T10:00:00Z","event_type":"attempt","correctness":true,"assistance_level":0,"provenance":{"judgment_source":"answer_key","status":"verified","verifier_reliability":"authoritative","independently_produced":true}}' | jq .

# 3. Query recommendation
curl -s -X POST http://localhost:8000/v1/recommendations \
  -H "Authorization: Bearer $STAGING_JWT" \
  -H "X-Tenant-ID: tenant_staging" \
  -H "Content-Type: application/json" \
  -d '{"student_id":"stu_smoke","concept_id":"math.fractions.addition"}' | jq .
```
