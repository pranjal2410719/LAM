# Architecture & Policy Decision Register

This directory contains records of significant architectural, mathematical, and algorithmic decisions for the Learning Adaptation Model (LAM).

Each decision follows the structure defined in Section 17 of [`docs/LAM_IMPLEMENTATION_SPECIFICATION.md`](../LAM_IMPLEMENTATION_SPECIFICATION.md):
- Context & Problem
- Considered Alternatives
- Decision & Rationale
- Mathematical / Algorithmic Specification
- Consequences & Migration Impact
- Approver & Status

---

## Decision Status Matrix

| ID | Title | Status | Impact Area | Mandatory Before |
|:---|:---|:---:|:---|:---|
| **D-01** | Mastery Policy & Confirmation Criteria | `PROPOSED` | Domain / Mastery | M1 Implementation |
| **D-02** | Bayesian Knowledge Tracing (BKT) Parameters | `PROPOSED` | Domain / Mastery | M1 Implementation |
| **D-03** | Uncertainty Semantics & Credible Intervals | `PROPOSED` | Domain / State | M1 Implementation |
| **D-04** | Misconception Hypothesis Lifecycle & Thresholds | `PROPOSED` | Domain / Diagnosis | M1 Implementation |
| **D-05** | Productive-Struggle Assistance Ladder Transitions | `PROPOSED` | Domain / Decision | M2 Implementation |
| **D-06** | Deterministic Decision Priority & Tie-Breaking | `PROPOSED` | Domain / Decision | M1 Implementation |
| **D-07** | Spaced Retrieval Scheduling Baseline Ladder | `PROPOSED` | Domain / Retrieval | M2 Implementation |
| **D-08** | Event Idempotency & Conflict Quarantine Protocol | `IMPLEMENTED` | Infra / Persistence | M0 Implementation |
| **D-09** | Identity Propagation & Multi-Tenant Authorization | `IMPLEMENTED` | Infra / Security | M0 Implementation |
| **D-10** | Curriculum Knowledge Graph Contract & DAG Validation | `PROPOSED` | Domain / Curriculum | M2 Implementation |
| **D-11** | Asynchronous Learning Scientist Worker Semantics | `PROPOSED` | Application / Worker | M2 Implementation |
| **D-12** | Verification Provenance & Trust Hierarchy | `PROPOSED` | Domain / Assessment | M2 Implementation |
| **D-13** | Student Data Privacy, Deletion & Consent Lifecycle | `PROPOSED` | Infra / Governance | M4 Implementation |
| **D-14** | Operational SLA & Performance Targets | `PROPOSED` | Operations / SLA | M2 Integration |
| **D-15** | API Versioning, Deprecation & SDK Contracts | `PROPOSED` | API / SDK | M2 Integration |
| **D-16** | Baseline Evaluation Metrics & Model Promotion Gate | `PROPOSED` | Evaluation / ML | M3/M4 |
