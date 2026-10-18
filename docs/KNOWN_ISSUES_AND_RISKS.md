# Known Issues and Risks

**Last Updated:** 2026-10-18  

---

## 1. Unresolved Decisions (Pre-Implementation Blockers)

| Decision ID | Area | Severity | Impact | Resolution Criteria | Status |
|:---|:---|:---:|:---|:---|:---:|
| **D-01** | Mastery Policy | **P1 (High)** | Blocks implementation of deterministic mastery transitions in M1. | Approved numeric threshold (e.g., $\ge 0.9$) and evidence counts ($\ge 3$ independent successes across $\ge 2$ sessions). | `PROPOSED` |
| **D-02** | BKT Parameters | **P1 (High)** | Blocks implementation of the BKT engine in M1. | Approved baseline parameter values for $P(L_0), P(T), P(G), P(S)$ and parameter versioning scheme. | `PROPOSED` |
| **D-04** | Diagnosis Confirmation | **P2 (Medium)** | Blocks automated confirmation of misconception hypotheses in M1. | Approved confidence threshold ($\ge 0.8$) and independent observation requirement. | `PROPOSED` |
| **D-05** | Assistance Ladder Transitions | **P2 (Medium)** | Blocks assistance policy escalation logic in M2. | Approved escalation and reset criteria for Levels 0 through 8. | `PROPOSED` |
| **D-06** | Decision Ranking Priority | **P2 (Medium)** | Blocks deterministic next-action recommendation policy in M1. | Approved priority ordering and tie-breaking algorithms. | `PROPOSED` |

---

## 2. Technical Debt & Operational Risks

| Issue ID | Description | Severity | Impact | Mitigation / Next Steps |
|:---|:---|:---:|:---|:---|
| **TECH-01** | Test suite currently executes on SQLite (`aiosqlite`), not live PostgreSQL. | **P2 (Medium)** | While ORM code and Alembic migrations use standard ANSI/generic types, concurrency behaviors and native JSON operators may subtly differ in PostgreSQL. | Spin up a PostgreSQL test container via podman or local instance and add a dedicated CI integration job. |
| **TECH-02** | Bearer authentication in M0 uses token prefix matching rather than signed cryptographic JWTs. | **P3 (Low)** | Adequate for M0 test environment; production will require asymmetric JWT verification and key rotation. | Upgrade auth middleware when host service key server integration is implemented. |
| **TECH-03** | Git repository not yet initialized locally. | **P3 (Low)** | Changes are saved on the filesystem but lack local git commit history. | Initialize git repository and commit M0 baseline once authorized. |
