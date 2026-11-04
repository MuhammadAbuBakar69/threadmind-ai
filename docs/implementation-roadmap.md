# Implementation Roadmap

Sequenced by dependency and risk, not by feature appeal. Each phase has an exit condition that is a
command or a test, not an opinion.

---

## Phase 0 — Audit (complete)

**Delivered:** `docs/repository-audit.md`, `docs/security-review.md`, `docs/architecture-review.md`.
**Exit condition:** three P0s identified with evidence and reproduced as failing behaviour. Met.

---

## Phase 1 — P0 fixes: security and isolation (this branch)

| Task | Files | Exit condition |
|---|---|---|
| RLS forced on every tenant table | `database/migrations/002_rls_hardening.sql` | CI asserts `relrowsecurity AND relforcerowsecurity` ≥ 18 |
| Policies for the four uncovered tables | same | isolation suite green |
| Parameterizable tenant scoping | `apps/api/core/security.py` | scope applied, transaction-local |
| Bearer authentication + RBAC | `core/auth.py`, `deps.py` | 401/403 paths tested |
| Error contract without disclosure | `core/errors.py` | 500 body contains no internals |
| Request correlation + structured logs | `middleware/request_context.py` | header asserted |
| Rate limiting | `middleware/rate_limit.py` | implemented; distributed form deferred (#15) |
| Telemetry contract + ingest | `industrial/telemetry.py`, `routes/telemetry.py` | contract tests green |
| Tenant isolation proof | `tests/integration/test_tenant_isolation.py` | 9 tests green in CI |
| Migration rollback | `database/migrations/900_rollback_002.sql` | applied in CI, policies removed |

**Exit condition:** every CI job green, including the database jobs, on a real PostgreSQL 16 service.

---

## Phase 2 — P1 foundation (next)

1. **Identity provider** (SEC-002). Blocks real accounts. Requires a product decision.
2. **Distributed rate limiting + audit writes** (#14/#15): Redis counters, `audit_logs` written on
   privileged actions and denied access.
3. **MQTT consumer** using `industrial.telemetry` unchanged. The contract already exists; the
   consumer must not introduce a second one.
4. **Timestamps on all tables** (#15): `created_at`/`updated_at` where missing, and a trigger to keep
   `updated_at` honest.
5. **Async correctness decision** (#15): either forbid `async def` in routes by lint rule, or move to
   async SQLAlchemy. Choosing is the work; drifting is the risk.
6. **Schema-driven RLS assertion** (#15): derive the table list from `information_schema` so a new
   table without a policy fails CI by default.

**Exit condition:** a new table added without a policy fails CI without anyone editing a list.

---

## Phase 3 — Research infrastructure (before any experiment is reported)

1. Dataset manifests and the loader that enforces them (`docs/research-reproducibility.md`).
2. Experiment runner producing the artifact layout in that document, recording the git commit.
3. Leakage-safe splitters (group by image/roll/session) with tests proving no group crosses splits.
4. Evaluation scripts with fixed metric definitions and confidence intervals.
5. Contract fuzzing and a concurrency test for ingestion.

**Exit condition:** E1 can be run twice from a clean checkout and produce identical metrics files.

---

## Phase 4 — Intelligence (issues #3, #4, #5)

Order is forced: vision and anomaly models before agents, because agents explain numbers and there are
no numbers yet. Within the agents, root cause and its evidence ranking come **before** LLM
explanation, per #5. If the ranking is computed first, the LLM explains a result; if the LLM is wired
first, it invents the reasoning and the ranking becomes decoration.

**Exit condition:** each agent produces contract-valid output on a real case, with evidence refs that
resolve, and an unsupported-claim count of zero on the E3 rubric.

---

## Phase 5 — Product surface (#6)

Dashboard with real data only, auth-aware, with loading/empty/error states. No static demo metrics.

**Exit condition:** a factory manager can register a machine, upload a fabric image, see a defect,
and read an investigation without a developer present.

---

## Phase 6 — Operations (#8, #18)

Metrics endpoint, tracing, dashboards, backup/restore rehearsal, load test, SBOM and image signing,
dependency scanning. Runbook already drafted in `docs/operations-runbook.md`.

**Exit condition:** a restore from backup has actually been performed and timed.

---

## Dependency graph

```text
P0 audit ─▶ P1 security/isolation ─▶ P2 foundation ─▶ P3 research infra
                                                          │
                                          ┌───────────────┴───────────────┐
                                          ▼                               ▼
                                   #3 vision                       #4 predictive
                                          └──────────┬────────────────────┘
                                                     ▼
                                            #5 root cause engine
                                                     ▼
                                            #5 agents + orchestrator
                                                     ▼
                                          #6 dashboard  ─▶  #8 deployment
```

Blocked items are listed as blocked, not as deferred: identity provider, factory data, GPU host,
dataset licences. See `docs/repository-audit.md` §8.

---

## Deliberate non-goals for now

Digital twin, edge deployment, acoustic modality, causal discovery, automated quality grading. All
appear in the BRD's future-work section; implementing any of them before Phase 3 would produce results
that cannot be validated.
