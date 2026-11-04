# Repository Audit

**Repository:** `MuhammadAbuBakar69/threadmind-ai`
**Audited commit:** `16323a2` (foundation baseline v1.0)
**Audit date:** 2026-11-04
**Scope:** full tree, 81 files, 24 database tables, 3 CI workflows, 14 GitHub issues

---

## 1. Executive summary

The repository is a **well-documented scaffold, not a working platform**. That distinction is not a
criticism of the scaffold — it is a precise statement about what can be relied on today, and it
matters because the README's language ("five-agent system", "industrial intelligence platform") reads
as description rather than intent.

Three findings dominate everything else:

1. **Tenant isolation did not work.** Row-level security was enabled on 16 tables but never
   `FORCE`d, and the application connected as the schema owner. PostgreSQL lets a table owner bypass
   its own policies, so the 16 policies were decoration in the deployed configuration. Four further
   tables reachable by tenant-scoped queries had no coverage at all. For a multi-tenant platform
   holding factory production data, this was the single highest-severity defect in the repository.
2. **There was no authentication.** The tenant middleware assigned `request.state.principal = None`
   and no route required a principal. Every endpoint was open, and `organization_id` arrived from
   the client as a claim with nothing to verify it against.
3. **The scoping helper could not have worked even if called.** It issued
   `SET LOCAL app.current_org = :org`. PostgreSQL's `SET` does not accept bind parameters, so the
   statement fails against a driver that binds server-side. This is a correctness bug, not a style
   preference, and it would have surfaced as a runtime error at the first scoped query.

None of the three would have been caught by the existing test suite, because the existing suite
tested contracts and liveness only — and none of it touched a database or an HTTP route.

Everything else is ordinary early-stage debt, catalogued below with severity and status.

### Status of this audit's remediation

Work is on branch `foundation/p0-p1-hardening` (PR pending review). Nothing in this document claims
a fix is verified unless a command was actually run; the **Evidence** column says which.

---

## 2. Method

1. Cloned the default branch and read every file (`git ls-files`, 81 files).
2. Parsed `database/schemas/001_initial.sql` programmatically to enumerate tables and the RLS block,
   then diffed the two sets. This is what surfaced the four uncovered tables; reading the file by eye
   does not reliably do it.
3. Enumerated routes by importing the FastAPI app and inspecting `app.routes`.
4. Treated `docs/` claims as *assertions to verify*, not as descriptions. Where a document claimed
   behaviour, the corresponding code was checked for it.
5. Ran the existing suite, lint, and build to establish a real baseline rather than an assumed one.
6. Wrote tests for the defects found, then fixed them — in that order, so each fix has a failing test
   behind it.

---

## 3. Verified implementation status

Legend: **Implemented** = code exists · **Tested** = automated test exercises it · **Verified** =
test executed and passed · **Prod-ready** = tested, operational concerns handled, documented.

| Area | Implemented | Tested | Verified | Prod-ready | Notes |
|---|---|---|---|---|---|
| Agent contracts (claim kinds, evidence, forbidden tools) | Yes | Yes | **Yes** | No | 9 tests; strongest asset in the repo |
| Database schema (24 tables, keys, indexes) | Yes | Schema apply in CI | **Yes** | No | `created_at` missing on several tables |
| Row-level security | Yes | Yes (new) | **Yes, in CI** | Partial | Was non-functional; now forced + covered |
| Tenant isolation endpoints | Partial | Yes (new) | **CI** | No | API-level proof pending (#14) |
| JWT authentication | Yes (new) | Yes | **Yes** | No | No IdP; dev-signed tokens (SEC-002) |
| RBAC | Yes (new) | Yes | **Yes** | No | Enforced on telemetry only so far |
| Error envelope, no stack traces | Yes (new) | Yes | **Yes** | Yes | Contract documented in `docs/API.md` |
| Request correlation + structured logs | Yes (new) | Partial | **Yes** | Yes | Log *volume* controls absent |
| Rate limiting | Yes (new) | No | No | No | In-process only; needs Redis (SEC-005) |
| Telemetry contract + ingest | Yes (new) | Yes | **Yes** | Partial | MQTT consumer not implemented |
| Telemetry simulator | Yes (new) | Yes | **Yes** | Yes (as research tool) | Deterministic, labelled, corruption-injecting |
| OEE calculation | Yes (new) | Yes | **Yes** | Yes | Explicit definitions, invalid inputs raise |
| Health / readiness | Yes | Yes | **Yes** | Yes | Readiness degrades instead of raising |
| Research provenance (manifests, splits) | Partial (simulator) | Partial | Partial | No | REAL-01 |
| CI/CD | Yes | — | **Yes** | Partial | 6 jobs; no dependency scanning |
| Container image | Yes | Build in CI | **Yes** | Partial | No SBOM, no signing |
| Vision service | Spec only | No | No | No | No model, no code (#3) |
| Predictive maintenance | Spec only | No | No | No | No model, no code (#4) |
| Agent implementations | Skeletons raise `NotImplementedError` | Contracts only | No | No | No agent has ever run (#5) |
| Orchestrator | Skeleton | Contract helpers only | No | No | No LangGraph dependency installed |
| Frontend | One static page | Build + typecheck | **Yes** | No | No auth, no data, no states (#6) |
| Notifications | Schema only | No | No | No | No delivery code |

**Nothing in this repository is production-ready for a real factory**, and the definition of that
bar is in `docs/production-readiness.md` rather than asserted here.

---

## 4. Findings

Severity: **P0** blocks any use with real data · **P1** blocks reliable operation · **P2** blocks
research validity · **P3** product/scale.

### P0 — Security and data integrity

| ID | Finding | Evidence | Status |
|---|---|---|---|
| DB-001 | RLS enabled but not forced; owner role bypasses all policies | `pg_class.relforcerowsecurity = false` for all 17 tables pre-fix | **Fixed** (`002`, CI asserts forced) |
| DB-002 | `organization_members`, `investigation_evidence`, `root_cause_hypotheses`, `agent_actions` had no RLS | Set-difference of tables vs policy block | **Fixed** (parent-`EXISTS` policies) |
| DB-003 | `SET LOCAL ... :org` cannot be parameterized; scoping would fail at runtime | `core/security.py` pre-fix | **Fixed** (`set_config(..., true)`) |
| SEC-001 | No authentication; `principal` was always `None` | `middleware/tenant.py` pre-fix | **Fixed** (bearer + claims + RBAC) |
| SEC-002 | No identity provider; dev tokens self-signed with one shared secret | `core/auth.py` | **Blocked** — needs IdP decision |
| SEC-006 | Sensor telemetry accepted without range/freshness validation | no ingestion existed | **Fixed** (shared contract, rejects not clips) |
| DB-004 | No idempotency key on `sensor_readings`; at-least-once redelivery double-counts | schema had no unique constraint | **Fixed** (natural key + test) |

### P1 — Reliability and correctness

| ID | Finding | Status |
|---|---|---|
| API-001 | No error contract; unhandled exceptions could return framework detail | **Fixed** (envelope + last-resort handler) |
| API-002 | No request correlation; support had no way to locate a request | **Fixed** (`X-Request-ID`, structured logs) |
| API-003 | Readiness raised instead of reporting when a dependency was down | **Fixed** (caught by the new test) |
| API-004 | No rate limiting | **Partial** (in-process; SEC-005) |
| API-005 | Route handlers had no dependency-injected data access, making them untestable without a database | **Fixed** (repository protocol + overrides) |
| DB-005 | No migration rollback path | **Fixed** (`900_rollback_002.sql`, applied in CI) |
| DB-006 | Several tables lack `created_at`/`updated_at`, weakening audit trails | **Open** (#15) |
| DB-007 | `audit_logs` table exists; nothing writes to it | **Open** (#14) |

### P2 — Research validity

| ID | Finding | Status |
|---|---|---|
| REAL-01 | No dataset manifest or versioning; a split cannot be re-derived | **Partial** (simulator `config_hash`) |
| REAL-02 | No experiment runner, no result provenance record, no evaluation scripts | **Open** (#17) |
| REAL-03 | Dataset licences recorded but not enforced anywhere in code | **Open** (#17) |
| ML-001 | Zero models. Every metric in the BRD is an unvalidated target | **Open** (by design; #3, #4) |
| AGT-001 | No agent has executed; latency, cost, and failure modes unmeasured | **Open** (#5) |
| AGT-002 | No retry/idempotency design for agent actions; a retried run could duplicate recommendations | **Open** (#16) |

### P3 — Product

| ID | Finding | Status |
|---|---|---|
| FE-001 | Dashboard is a static page; no auth, data, loading/empty/error states | **Open** (#6) |
| DEV-001 | No dependency vulnerability scanning or SBOM | **Open** (#18) |
| DEV-002 | Compose stack has no resource limits and uses anonymous MQTT | **Documented** as dev-only (`docs/operations-runbook.md`) |
| DEV-003 | No observability beyond logs; no metrics endpoint, no tracing | **Open** (#18) |

---

## 5. What is genuinely good and should not be rewritten

Recording this matters as much as the defects, because a rewrite would lose it:

- **`agents/contracts.py`** encodes the project's central claim in code: a fact cannot exist without
  evidence, and an agent cannot hold a machine-control tool. These are validation errors, not prompt
  instructions, which is the difference between a constraint and a suggestion.
- **The research framing is unusually honest.** Targets are labelled as proposals, synthetic data is
  labelled as pipeline validation, RUL is explicitly refused without run-to-failure data, and
  correlation-as-causation is called out as a failure mode. This is the hard part to get right and it
  is already right.
- **The database design is sound** in its structure: UUID keys, explicit tenant ownership, natural
  keys on registers, JSONB confined to metadata.
- **Separation of online ingestion from offline analytics** in the architecture is the correct call
  for this workload and should survive.

---

## 6. Technical debt register

| Debt | Cost if unaddressed |
|---|---|
| No ORM models; SQL is hand-written strings | Drift between schema and code as tables are added |
| Sync SQLAlchemy in an async framework | A single blocking query under `async def` stalls the event loop |
| No dependency-injected clock | Time-dependent logic untestable without `freezegun` |
| Docker compose doubles as the only environment definition | Production topology untested until deployment |
| `docs/` volume is high relative to code | Documentation decay; mitigated by issue traceability |
| No `conftest`-level database fixture besides the integration module | Each new DB test pays setup cost |

---

## 7. Prioritised remediation

**P0 (this branch, complete pending review):** DB-001 … DB-004, SEC-001, SEC-006, API-001 … API-003.

**P1 (next):** SEC-002 identity provider, SEC-005 distributed rate limiting, DB-006 timestamps,
DB-007 audit writes, MQTT consumer sharing the telemetry validator, `async` correctness pass.

**P2 (before any experiment is reported):** REAL-01 … REAL-03, experiment runner, then #3/#4/#5.

**P3:** FE-001 dashboard, DEV-001/DEV-003 observability and supply chain.

Sequencing rationale is in `docs/implementation-roadmap.md`; per-issue mapping in
`docs/issue-traceability.md`.

---

## 8. Remaining external dependencies

| Dependency | Blocks | Owner |
|---|---|---|
| Identity provider choice (Auth0 / Clerk / Keycloak / Base44 auth) | SEC-002, real user accounts | User decision |
| Real textile factory data + permission | Any claim of local generalization (REAL-03) | Factory partnership |
| Sensor hardware / MQTT gateway | Method B connectivity | Factory |
| Dataset licence confirmation (DME, Lusitano) | Commercial model training | User review |
| Redis in deployment | Distributed rate limiting, queue coordination | Infra |
| GPU inference host | Vision training and latency benchmarks | Infra/budget |

The audit does not treat these as excuses. Each has a safe interface implemented or specified, and
each is recorded as blocked rather than silently deferred.
