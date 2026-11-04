# Issue Traceability Matrix

Every open issue, mapped to what actually exists in the repository. The rule this document exists to
enforce: **an issue is not complete because a folder with its name exists.**

Status values: **Not started** · **Partial** · **In progress** · **Verified** (exit condition met and
demonstrated) · **Blocked** (external dependency)

Last updated: 2026-11-04, branch `foundation/p0-p1-hardening`.

---

## Phase issues

### #1 — Phase 1: Research and requirements
**Intended outcome:** literature review, gap analysis, SRS/BRD finalisation, dataset inspection.
**Exists:** `docs/BRD.md` (complete, 58 requirements), `docs/SRS.md`, `docs/architecture.md`,
`docs/datasets.md` with licences and limitations, `docs/research.md` with hypotheses and design.
**Missing:** literature review, formal gap analysis, per-dataset inspection notes.
**Status:** **Partial.** Requirements are genuinely usable; the research review is not written.

### #2 — Phase 2: Data engineering
**Intended outcome:** preprocessing pipelines, dataset versioning, common schemas, simulated streams,
database foundation.
**Exists:** full 24-table schema + RLS; deterministic simulator with 6 scenarios, ground truth and
corruption injection; shared telemetry contract; ingest endpoint.
**Missing:** MQTT consumer, dataset manifests (specified only), preprocessing pipelines, synthetic
loader into the database.
**Status:** **Partial**, and noticeably ahead of what the issue assumed.

### #3 — Phase 3: Fabric defect vision service
**Exists:** `ai-services/vision/` specification and configs; `fabric_images`, `inspection_results`,
`detected_defects` tables.
**Missing:** dataset acquisition, training, model, inference API, evaluation. No model exists.
**Status:** **Not started.** Gated on dataset access.

### #4 — Phase 4: Predictive maintenance models
**Exists:** specifications; `machine_sensors`, `sensor_readings`, `machine_predictions` tables; a
telemetry source that finally makes training possible.
**Missing:** feature engineering, models, calibration, evaluation, inference service.
**Status:** **Not started**, now unblocked in principle by the simulator.

### #5 — Phase 5: Root cause engine and five-agent system
**Exists:** `agents/contracts.py` (claim kinds, evidence requirement, tool allowlist, machine-control
prohibition) with 9 tests; agent skeletons that raise `NotImplementedError`; schema for
investigations, evidence, hypotheses, runs, actions.
**Missing:** correlation engine, evidence ranking, LangGraph orchestration, any agent execution.
**Status:** **Not started**, with contracts verified. The dependency order in
`docs/implementation-roadmap.md` explains why ranking must precede the LLM.

### #6 — Phase 6: Enterprise dashboard
**Exists:** Next.js app that builds; one page.
**Missing:** auth, API integration, machine views, inspection UI, investigation UI, states.
**Status:** **Not started.**

### #7 — Phase 7: Integration, testing, security assessment
**Exists:** 6 CI jobs; ~94 tests; tenant isolation proof; error-envelope proof; migration rollback;
security review document.
**Missing:** E2E tests, load test, second-party review, penetration test.
**Status:** **In progress** — the security leg is substantially further along than "assessment".

### #8 — Phase 8: Cloud deployment and research evaluation
**Exists:** Dockerfile, compose stack for local development, deployment documentation.
**Missing:** cloud environment, monitoring, model deployment, integrated experiments.
**Status:** **Not started.** Compose is explicitly not a production topology.

---

## Experiment issues

| Issue | Experiment | Exists | Missing | Status |
|---|---|---|---|---|
| #9 | E1 fabric defect benchmark | dataset inventory | data, models, metrics | Not started |
| #10 | E2 anomaly benchmark | simulator with ground truth | models, calibration, lead-time measurement | Not started |
| #11 | E3 root cause comparison | rubric in `docs/research-reproducibility.md` §4 | engine, cases, raters | Not started |
| #12 | E4 production analytics | OEE service with tests | forecasting, bottleneck detection, historical data | **Partial** |
| #13 | E5 integrated evaluation | traceability requirements | a running system to evaluate | Not started |

---

## Security issue

### #14 — Prove zero cross-tenant data access
**Intended outcome:** automated proof that one organization cannot read or modify another's data.
**Exists:** `database/migrations/002_rls_hardening.sql` (FORCE + 4 new policies + identity scoping +
natural key); `tests/integration/test_tenant_isolation.py` — 9 tests against real PostgreSQL as a
**non-superuser** role; CI job *Tenant isolation (real PostgreSQL)*; rollback migration verified in CI.
**Missing:** audit-log writes on denied access (SEC-010); API-level test through the HTTP layer rather
than the database layer; schema-driven table enumeration so a new table cannot be added without a
policy.
**Status:** **In progress**, with the core claim now proved at the database boundary.

---

## New issues raised by this audit

| # | Title | Priority | Why it exists |
|---|---|---|---|
| #16 | Foundation hardening: timestamps, audit writes, async decision, distributed limits | P1 | Six P1 findings share one root cause: defaults not enforced by the schema |
| #17 | Agent execution reliability: idempotency, retries, timeouts, approval state machine | P2 | AGT-002; retries could duplicate maintenance recommendations today |
| #18 | Research reproducibility tooling: manifests, experiment runner, leakage splitters, fuzzing | P2 | REAL-01..03; a result cannot currently cite a dataset version |
| #19 | Observability and supply chain: metrics, tracing, SBOM, signing, dependency scanning | P3 | DEV-001/003; nothing measures the system in operation |

Implementation for #14 and #16 is on pull request #15 (`foundation/p0-p1-hardening`).

---

## Traceability summary

| Status | Count | Issues |
|---|---|---|
| Verified | 0 | — |
| In progress | 2 | #7, #14 |
| Partial | 3 | #1, #2, #12 |
| Not started | 9 | #3, #4, #5, #6, #8, #9, #10, #11, #13 |
| New, unstarted | 4 | #16, #17, #18, #19 |

No issue is closed by this work. #14 is materially advanced but keeps its acceptance criteria open
until the audit-log and HTTP-layer legs exist, because closing it early would assert a guarantee the
tests do not yet cover.
