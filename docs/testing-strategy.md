# Testing Strategy

The suite exists to protect specific claims. A test that does not defend a claim is maintenance cost
with no return, so this document starts from the claims and works backwards to the tests.

---

## 1. Claims under test

| Claim | Where it is proved |
|---|---|
| Tenant data cannot cross organizations | `tests/integration/test_tenant_isolation.py` |
| An unauthenticated caller reaches nothing | `tests/unit/test_api_errors.py` |
| A forged, expired or incomplete token never becomes a principal | `tests/unit/test_auth.py` |
| Bad telemetry is rejected, good telemetry survives in the same batch | `tests/unit/test_telemetry_contract.py`, `test_api_errors.py` |
| A redelivered reading is counted as a duplicate, not a new row | `test_api_errors.py`, isolation natural-key test |
| Failures disclose nothing internal | `test_api_errors.py` |
| Synthetic data is reproducible bit for bit | `tests/unit/test_simulator.py` |
| Injected corruption is actually invalid | `test_simulator.py`, `test_telemetry_contract.py` |
| A fact cannot exist without evidence; no agent holds a control tool | `tests/unit/test_contracts.py` |
| OEE is computed by one explicit definition | `tests/unit/test_oee.py` |
| Production cannot start with a placeholder secret | `tests/unit/test_config.py` |
| Every tenant table has RLS enabled **and** forced | isolation suite + CI schema job |

---

## 2. Layers and where they run

```text
        ┌──────────────────────────────────────────┐
   E2E  │ deferred until the dashboard has data    │  #6
        ├──────────────────────────────────────────┤
  API   │ TestClient + dependency overrides        │  no database needed
        ├──────────────────────────────────────────┤
  DB    │ real PostgreSQL, non-superuser role      │  CI service container
        ├──────────────────────────────────────────┤
 Unit   │ contracts, simulator, OEE, auth, config  │  any machine
        └──────────────────────────────────────────┘
```

**Why API tests do not need a database.** Routes depend on a `TelemetryRepository` protocol. Tests
inject `InMemoryTelemetryRepository`, so the middleware stack, exception handlers, validation and
status codes are exercised in milliseconds and on any machine. A route that can only be tested
against live PostgreSQL is a route that stops being tested the day the container breaks.

**Why DB tests do need one.** Row-level security depends on the connecting role. A superuser bypasses
policies regardless of `FORCE`, so the only meaningful test connects as a non-superuser against real
PostgreSQL. The suite therefore:

1. applies `database/schemas/001_initial.sql` then every migration, using the real files;
2. creates a `threadmind_app` role and grants table privileges;
3. connects as that role for assertions.

Without step 2 the suite would pass while production leaked everything. This is the most important
sentence in this document.

---

## 3. Running

```bash
# unit + API (default, no external services)
pytest -q

# everything, including tenant isolation (needs PostgreSQL)
DATABASE_URL_TEST=postgresql+psycopg://threadmind:threadmind@localhost:5432/threadmind_test pytest -q

# lint and format
ruff check . && ruff format --check .
```

Integration tests skip cleanly and loudly when `DATABASE_URL_TEST` is unset. They are not silently
excluded from a run: `pytest` reports them as skipped, and CI treats a skip in the isolation job as a
failure because that job sets the variable unconditionally.

---

## 4. Failure cases that are tested deliberately

The valuable tests are the ones where something is supposed to *not* happen:

- An expired token does not yield a principal.
- A row belonging to another tenant is not returned by id.
- An `UPDATE` against another tenant's machine affects zero rows.
- An unscoped connection sees zero rows (default deny).
- A malformed batch does not discard its valid readings.
- A 500 does not contain `Traceback`, `RuntimeError` or a connection string.
- A validation error does not echo the submitted value.
- An out-of-range reading is not stored with its value clipped.
- OEE does not report 100% for inputs that cannot be true.

---

## 5. Gaps, stated rather than hidden

| Gap | Risk | Plan |
|---|---|---|
| No coverage measurement in CI | Regressions in untouched modules | Add `--cov` with a floor once agents exist |
| No MQTT consumer tests | The real ingestion path is untested | Consumer lands with the same contract; #2 |
| No concurrency tests (parallel ingest) | Duplicate handling under load unproven | Add a threaded ingest test against Timescale; #16 |
| No frontend tests | UI regressions silent | Playwright once #6 has real data |
| No fuzzing on the telemetry contract | Unhandled shape crashes ingest | Hypothesis-based test; #18 |
| No load test | P95 claims unvalidated | k6 against `/api/v1/telemetry`; #8 |
| No mutation testing on contracts | Contract tests may be weaker than they look | Periodic `mutmut` run; #18 |

None of these gaps weakens a claim above; they weaken claims the repository does **not** currently
make. That distinction is the point of keeping this table honest.

---

## 6. Test data policy

- No real factory data in the repository, ever. Simulator output only.
- UUIDs in tests are fixed constants so failures are diffable.
- Timestamps are constructed from an explicit `NOW`, never `datetime.now()` inside an assertion.
- Randomness is seeded, and a test asserts that the seed reproduces (`test_same_config_produces_identical_output`).
- A fixture never reaches the network. If a future test needs it, it must say so in its name.
