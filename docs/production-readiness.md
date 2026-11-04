# Production Readiness

A checklist with honest answers. "Building" is not on it, because a repository that builds proves
almost nothing about whether a factory can depend on it.

Legend: **Yes** · **Partial** · **No** · **Blocked** (external decision or access required)

---

## 1. Foundation (required before any real tenant data)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Repo installs and builds reproducibly | **Yes** | CI: Python 3.11 + 3.12, web build |
| 2 | Migrations apply cleanly from empty | **Yes** | CI schema job runs `001` + all migrations |
| 3 | Migrations roll back | **Yes** | CI applies `900_rollback_002.sql` and asserts zero policies remain |
| 4 | Critical API paths tested | **Yes** | 85 unit/API tests + 9 DB tests |
| 5 | Tenant isolation demonstrated by automated tests | **Yes, in CI** | `tests/integration/test_tenant_isolation.py` |
| 6 | Agent contracts enforced | **Yes** | `tests/unit/test_contracts.py` |
| 7 | Unsafe tools rejected | **Yes** | `assert_tool_allowed` raises on control tools |
| 8 | Telemetry payloads validated | **Yes** | shared contract, both producers |
| 9 | Failures and retries handled safely | **Partial** | ingest is idempotent; agent retries unbuilt (#17) |
| 10 | Logs and health checks operational | **Yes** | JSON logs, request id, `/health`, `/health/ready` |
| 11 | Secrets handled securely | **Partial** | no secrets in repo, production refuses placeholder; no vault (SEC-002) |
| 12 | CI passes | **Yes** | 6 jobs |
| 13 | Documentation matches behaviour | **Yes** | corrected by this audit; claims traceable to tests |
| 14 | Known limitations recorded | **Yes** | audit §4, testing §5, this table |
| 15 | Deployment and backup procedures documented | **Yes** | `docs/operations-runbook.md` |
| 16 | Authentication is real, not mechanism-only | **Blocked** | needs an IdP decision (SEC-002) |
| 17 | Audit trail written for privileged actions | **No** | #14/#16 |
| 18 | Rate limiting distributed across replicas | **No** | in-process only (SEC-005) |

**Verdict: the foundation is verifiable, and not yet operational.** Criteria 1-15 hold; 16-18 do not,
and 16 is the gate — a platform with one shared signing secret cannot hold factory data.

---

## 2. Operational readiness (required before a pilot)

| # | Criterion | Status | Note |
|---|---|---|---|
| 19 | Metrics endpoint and dashboards | **No** | #19 |
| 20 | Tracing across API → queue → worker | **No** | #19 |
| 21 | Alerting on error rate, latency, queue depth | **No** | #19 |
| 22 | Backup schedule + a restore actually performed | **No** | procedure documented, rehearsal not done |
| 23 | Load test at target telemetry rate | **No** | #8; P95 claims unvalidated |
| 24 | Dependency vulnerability scanning | **No** | #19 |
| 25 | SBOM and image signing | **No** | #19 |
| 26 | Container runs as non-root | **Yes** | uid 10001 |
| 27 | Migration executed as a controlled step, not at boot | **Yes** | documented in runbook |
| 28 | Horizontal scale of inference workers | **Partial** | containers exist, queue does not |

---

## 3. Industrial readiness (required before a factory relies on output)

| # | Criterion | Status | Note |
|---|---|---|---|
| 29 | Models trained and evaluated on real data | **No** | no data access; #3/#4 |
| 30 | Human approval enforced in the path, not just in a field | **Partial** | contract holds `requires_human_approval`; no workflow |
| 31 | Recommendation traceability (every claim → evidence id) | **Partial** | contract validates; renderer unbuilt |
| 32 | Uncertainty communicated, not implied | **Partial** | contract supports it; UI unbuilt |
| 33 | No path to machine control | **Yes** | no control tool exists; contract forbids them |
| 34 | Model version recorded on every prediction | **Partial** | schema has `model_version_id`; nothing writes it |
| 35 | Data retention and deletion policy | **No** | not defined |
| 36 | Signed data-processing agreement with factory | **Blocked** | commercial/legal |

---

## 4. What "production-ready" will mean here

The platform is production-ready for a paying factory when:

1. An identity provider issues real tokens and RBAC is enforced on every route (16).
2. Every privileged action and every denied access writes to `audit_logs` (17).
3. Rate limiting is shared across replicas and a load test has validated the P95 target (18, 23).
4. A restore from backup has been performed and timed (22).
5. Models report metrics measured on data the platform actually ingests, with the manifest and commit
   recorded (29, `docs/research-reproducibility.md`).
6. A human approval step is enforced by the state machine, not by a text field (30).
7. Alerting exists for the four failure modes that matter: ingest rejection rate spike, agent failure
   rate, queue depth, and any cross-tenant access attempt (21).

Until then the correct description is: **secure, tested research foundation with a verified
isolation boundary.** That is a real achievement and it is not the same thing as production-ready.

---

## 5. Deception checklist

Things that would look like readiness and are not:

- A green CI badge on a suite that never touches a database. *(Was true before this audit.)*
- RLS policies that exist but are not forced. *(Was true before this audit.)*
- A dashboard with hardcoded metrics.
- A BRD table of "targets" quoted as results.
- An agent that produces fluent output nobody verified.
- A README that describes intent in the present tense.
