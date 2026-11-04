# Architecture Review

**Verdict:** the architecture is appropriate for the problem and should be kept. The defects found by
audit were *enforcement* defects — guarantees that existed on paper and not in code — not structural
ones. A rewrite would discard the parts that are right and reproduce the same gaps.

Reviewed against three questions: does the design fit the workload, where does it fail under load,
and what must change before a factory can rely on it.

---

## 1. What the design gets right

**Specialized models produce numbers; agents explain them.** The core boundary is stated in
`docs/architecture.md` and enforced in `agents/contracts.py`: an `observed_fact` cannot exist without
an evidence reference, and an `association` cannot be presented as a cause. This is the project's
central research claim expressed as a validation error rather than a prompt instruction, and it is
the single most defensible decision in the repository.

**Online ingestion is separated from offline analytics.** Telemetry arrives continuously and cheaply;
analytics run on windows. Sharing one path would mean either analytics blocking ingestion or
ingestion dictating analytics granularity. Keep this.

**The industrial data layer is shared, not per-agent.** Five agents reading five copies of machine
state is how a "multi-agent" system silently becomes five systems that disagree. One data layer is
correct and preserves the root cause contribution (RQ3).

**No machine control, anywhere.** FR-048 excludes actuators and PLC writes. The restriction is now
in code (`assert_tool_allowed` raises on control-tool prefixes) rather than in a requirements
paragraph. This is also what makes the system sellable: nobody deploys an inspection platform that
can move a loom.

**PostgreSQL + TimescaleDB, Redis, object storage, Qdrant.** Four storage roles, each with a distinct
access pattern. No exotic choices, all operable by a small team.

---

## 2. Where the design was not enforced (now addressed or scheduled)

### 2.1 Isolation was a property of intention, not of the system

Three independent defects had to line up for the platform to be multi-tenant, and none did:
policies were not forced, four tables had none, and the scoping statement could not be parameterized.
All three are fixed in `002_rls_hardening.sql` and `core/security.py`, with proof in
`tests/integration/test_tenant_isolation.py`.

The architectural lesson is not "we forgot FORCE". It is that **isolation was assumed to follow from
schema design**. It does not; it follows from a scoped connection, a non-superuser role, and a test
that asserts absence. That test now exists and runs in CI.

### 2.2 The service boundary had no contract

`apps/api` and `ai-services/*` were described as independently deployable but shared no definition of
a valid payload. The simulator and the ingest endpoint would have diverged on the first week of work,
and every synthetic experiment would then have validated a path production does not use.

`industrial/telemetry.py` is now that contract: one validator, imported by both. This is the cheapest
possible fix and it protects the research validity of every later experiment.

### 2.3 Dependency direction leaked upward

`apps/api` imported nothing from `agents/`, which is correct, but nothing prevented the reverse, and
the AI services imported from the API package. `industrial/` now sits at the root as a leaf
dependency that both may import, so the API, the simulator and the services depend *downward* onto
contracts instead of sideways onto each other.

### 2.4 Background work had no queue in front of it

AI inference is documented as asynchronous but nothing enqueues it. Today inference is unimplemented
(#3, #4), so this is not yet a defect; it becomes one the moment a model is wired in. The rule to
hold: an HTTP request never awaits model inference. See §4.

### 2.5 Blocking I/O in an async framework

SQLAlchemy sessions are synchronous. Routes are declared `def`, so Starlette runs them in a
threadpool and this is correct *today*. It becomes a production hazard the first time someone writes
`async def` on a route that touches the DB: one slow query then blocks the event loop for every
tenant. Two options are open (#16): keep sync and add a lint rule forbidding `async def` in
`routes/`, or migrate to async SQLAlchemy. Do not leave it undecided.

### 2.6 Readiness coupled to dependency construction

`/health/ready` depended on a database session being constructible, so a missing driver raised before
the health check could report it. Caught by a test and fixed; the general rule is that health
endpoints observe, never participate.

---

## 3. Recommended target architecture (delta from current)

```text
        ┌─────────────────────────────────────────────────────────┐
        │  Next.js dashboard  (auth-aware, no business logic)     │
        └───────────────────────────┬─────────────────────────────┘
                                    │ HTTPS, bearer token
        ┌───────────────────────────▼─────────────────────────────┐
        │  FastAPI  — thin: auth, RBAC, validation, persistence    │
        │  • scoped session per request (RLS enforced)            │
        │  • repository protocols (testable without a database)    │
        │  • enqueues; never awaits inference                      │
        └───────┬─────────────────────────────┬───────────────────┘
                │ publish                      │ read/write
        ┌───────▼─────────┐          ┌────────▼──────────────────┐
        │ Queue (Redis    │          │ PostgreSQL + Timescale     │
        │ Streams)        │          │ + RLS (non-superuser role) │
        └───────┬─────────┘          └────────┬──────────────────┘
                │ consume                     │
   ┌────────────▼─────────────┐    ┌──────────▼─────────────────┐
   │ Inference workers        │    │ Agent runtime (LangGraph)  │
   │ vision · anomaly · risk  │───▶│ contracts + tool allowlist │
   │ (own containers, scaled) │    │ evidence validation        │
   └──────────────────────────┘    └──────────┬─────────────────┘
                                              │ propose only
                                   ┌──────────▼─────────────────┐
                                   │ Human approval (FR-047)    │
                                   └────────────────────────────┘
```

Three deltas from the current design, each earning its complexity:

1. **A queue between the API and inference.** Otherwise a burst of images during a shift change
   saturates the API's threadpool and the whole platform becomes unresponsive exactly when the
   factory is busiest.
2. **Inference workers as separate deployments with their own resource limits.** A vision model that
   needs 2 GB resident memory must not share a limit with a 200 MB API.
3. **Agent runtime writes proposals, never actions.** Already in the contracts; it needs a queue and a
   state machine to hold across retries (AGT-002, #17).

---

## 4. Rules the architecture now depends on

These are the invariants a future contributor must not break, and each has a test or a documented
rationale:

| Invariant | Why | Enforced by |
|---|---|---|
| One tenant scope per transaction | Pooled connections must not leak scope | `deps.get_tenant_db` |
| 404, never 403, for foreign resources | A 403 confirms existence | `core/errors.NotFound` |
| Readings validated before storage | Bad data poisons every downstream model | `industrial.telemetry` |
| Reject, never clip, out-of-range values | Clipping destroys the informative sample | `validate_batch` |
| No stack traces to clients | Leaks schema, paths, credentials | `handlers` + tests |
| Inference never awaited in a request | One slow model stalls every tenant | documented; lint rule pending |
| No agent holds a control tool | Safety and product viability | `assert_tool_allowed` |
| Facts need evidence; associations are not causes | The entire research claim | `agents/contracts.py` |

---

## 5. Deliberately rejected alternatives

Recorded so the decision is not silently reversed later:

- **Microservices per agent.** Five agents coordinating over the network turn a function call into a
  distributed transaction with its own failure modes. Agents share a data layer and a process until
  measured load demands otherwise.
- **Vector search as the primary evidence store.** Qdrant is for technical documents. Operational
  evidence comes from relational queries with timestamps, which are auditable and cheap to verify.
  Embedding a sensor window loses the ability to check it.
- **An LLM computing anomaly scores.** Numbers come from models or deterministic functions. An LLM
  that estimates a failure probability produces an untraceable number, which is worse than no number.
- **Kafka.** Redis Streams covers this volume. Kafka's operational cost is not justified below
  hundreds of thousands of events per second.
- **A graph database for root cause.** The correlation queries are 2-3 joins over time windows. A
  graph database adds a second source of truth for machine identity.

---

## 6. Risks that remain architectural

| Risk | Impact | Mitigation |
|---|---|---|
| Timescale hypertable strategy unvalidated at volume | Slow windows, storage growth | Benchmark in #2 with realistic rates |
| Multi-tenancy in Qdrant (shared collection) | Cross-tenant retrieval leak | Per-tenant collection or mandatory filter; decide in #5 |
| Agent retries duplicating recommendations | Duplicate maintenance work orders | Idempotency key per (investigation, agent, input hash); #17 |
| Model version drift between registry and artifacts | A prediction cites a model that no longer exists | Pin artifact digest in `model_versions`; #18 |
| No offline story | A mill with intermittent internet loses inspection | Edge-compatible inference contract; #8 |
