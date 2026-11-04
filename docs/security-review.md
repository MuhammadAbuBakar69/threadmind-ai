# Security Review

**Scope:** API, database, agents, container, supply chain
**Method:** code inspection, threat modelling, and executable tests where a claim is testable
**Date:** 2026-11-04

Findings use stable IDs (`SEC-00n`) so commits, tests and issues can cite them. A finding is only
marked **Fixed** when a test exercises the control; **Mitigated** means a compensating control exists
with a known gap.

---

## 1. Threat model

### Assets

Fabric images and defect records (commercially sensitive: they describe a mill's quality), machine
telemetry, maintenance history, production volumes, model artifacts, and user identities.

### Adversaries

| Adversary | Motive | Most relevant control |
|---|---|---|
| Competing tenant (legitimate account, hostile query) | Read a rival mill's quality data | RLS, tenant-scoped sessions, 404-not-403 |
| Malicious insider with a valid low-privilege account | Escalate to quality-owner data | RBAC, audit log |
| Device or gateway spoofing | Inject false telemetry to hide a fault | Payload validation, org match on ingest |
| Prompt injection via uploaded document | Make an agent exfiltrate data or call a tool | Tool allowlist, evidence validation |
| Opportunistic attacker | Credential stuffing, scraping | Rate limits, auth, no existence disclosure |

### Explicitly out of scope at this stage

Physical machine safety (the platform controls nothing), denial-of-service at network layer,
and supply-chain attacks beyond dependency scanning. These require infrastructure controls this
repository does not own.

---

## 2. Findings

### SEC-001 — No authentication anywhere (P0, **Fixed**)

`middleware/tenant.py` set `request.state.principal = None` and no route depended on a principal.
Every endpoint was anonymous, and `organization_id` was whatever the client sent.

**Fix:** `deps.get_principal` verifies a bearer token via `core/auth.decode_token` and returns a
`Principal`; `require_role` enforces RBAC ranking. Missing or invalid token → 401 with a
`WWW-Authenticate: Bearer` header. Tests: `tests/unit/test_auth.py` (8), `test_api_errors.py`
(401 path).

**Residual:** tokens are self-signed (SEC-002), so this proves *the mechanism*, not *identity*.

---

### SEC-002 — No identity provider; one shared secret authenticates everyone (P0, **Blocked**)

`core/auth.py` issues development tokens signed with `JWT_SECRET`. Every environment that shares that
secret can mint a `super_admin` token for any organization.

**Why it is blocked:** choosing an IdP is a product decision (Base44 auth, Clerk, Auth0, Keycloak),
not an engineering shortcut to take unilaterally.

**Interim controls:** `scripts/dev_token.py` is the only issuer; the token TTL defaults to 60 min;
production refuses to start with the default secret (see SEC-003). Documented in
`docs/operations-runbook.md`.

**Required before any real tenant data exists.**

---

### SEC-003 — Default `JWT_SECRET` in the environment template (P1, **Fixed**)

`.env.example` shipped `JWT_SECRET=change-me-in-production`, which is the value a hurried deployment
inherits.

**Fix:** `Settings` now refuses to run in production with the placeholder secret. Implemented in
`core/config.py`; see `docs/operations-runbook.md` for the startup check.

---

### SEC-004 — Tenant isolation was not enforced (P0, **Fixed**)

Three separate defects, all confirmed by measurement:

1. RLS **enabled** on 16 tables, never **forced**. Table owners bypass their own policies, and the
   application connected as the owner. Effective isolation: none.
2. Four tenant-reachable tables had **no RLS at all** — `organization_members` (the authorization
   table), `investigation_evidence`, `root_cause_hypotheses`, `agent_actions`.
3. The scoping helper used `SET LOCAL app.current_org = :org`, which PostgreSQL cannot parameterize.
   It would error rather than scope.

**Fix:** `database/migrations/002_rls_hardening.sql` forces RLS on all 17 tenant tables, adds policies
for the four uncovered tables (child tables use `EXISTS` against their parent), scopes identity tables
(`organizations`, `users`, `organization_members`) to the caller, and `core/security.py` uses
`set_config(..., true)` so the scope is both parameterized and transaction-local.

**Proof:** `tests/integration/test_tenant_isolation.py` — 9 tests against real PostgreSQL, connecting
as a **non-superuser** role so RLS actually applies. CI job *Tenant isolation (real PostgreSQL)*.
Assertions are on absence: zero rows, zero affected rows, `IntegrityError`.

**Residual:** every new table needs a policy. The test enumerates tables explicitly, so a table added
without a policy is only caught if the list is updated — a schema-driven assertion is tracked in #16.

---

### SEC-005 — Rate limiting is per-process (P2, **Mitigated**)

`middleware/rate_limit.py` keeps counters in a dict. With N replicas the effective limit is N ×
configured. `/health` and `/health/ready` are exempt so an orchestrator can still reach a busy
service.

**Why acceptable now:** single-replica research deployment.
**Required for production:** Redis-backed counters (`REDIS_URL` is already provisioned). Tracked in #16.

---

### SEC-006 — Telemetry was accepted without validation (P0, **Fixed**)

No ingestion path validated ranges, freshness, or duplicate identity. Anomaly models trained on
unvalidated data learn to detect sensor faults as machine faults — a silent, expensive failure.

**Fix:** `industrial/telemetry.py` is one contract used by the simulator, the HTTP endpoint, and
(subsequently) the MQTT consumer:

- physical range per sensor type, **rejected not clipped** (clipping destroys the most informative
  sample);
- timezone-aware timestamps required, future-skew tolerance 300 s;
- non-finite values rejected;
- `extra="forbid"`, so a gateway typo fails loudly;
- per-batch de-duplication plus a database natural key for redelivery;
- partial acceptance: one bad sample does not discard the other 999.

**Proof:** `tests/unit/test_telemetry_contract.py` (12), `test_simulator.py` (corruption rejection),
`test_api_errors.py` (partial acceptance, duplicate counting).

---

### SEC-007 — Cross-tenant telemetry submission (P0, **Fixed**)

A gateway could previously POST readings tagged with any `organization_id`.

**Fix:** `routes/telemetry.py` rejects any reading whose `organization_id` differs from the caller's
resolved organization (403). Test: `test_reading_for_another_organization_is_refused`.

---

### SEC-008 — Error responses could disclose internals (P1, **Fixed**)

**Fix:** four exception handlers produce a stable envelope (`error.code`, safe `message`, optional
`requirement`, plus `request_id`). The last-resort handler logs the traceback and returns a
correlation id only. Validation errors report field locations **without echoing submitted values**,
because a submitted value may be a credential.

**Proof:** `test_internal_failure_hides_details` asserts the body contains no `RuntimeError`,
`Traceback`, or connection string. `test_malformed_payload_reports_fields_without_echoing_values`
asserts the submitted value is absent from the response.

---

### SEC-009 — Agent tool permissions (P0, **Fixed at contract level**)

`assert_tool_allowed` raises on any `machine.control`, `plc.write`, `scada.`, or `actuator.` prefix for
**every** agent (FR-048), and rejects a tool outside the agent's declared set.

**Residual:** no agent executes yet, so the control is proven at the contract boundary only. Tool
invocation must route through `agents/tools/registry.py` when agents are implemented (#5).

---

### SEC-010 — No audit trail written (P1, **Open**)

`audit_logs` exists; nothing writes to it. Cross-tenant access attempts are logged to the application
log but not to the tenant-visible audit table.

**Required:** write on privileged actions and on denied access. Tracked in #14.

---

### SEC-011 — Upload handling unimplemented (P1, **Open**)

No upload endpoint exists yet, so no validation exists. When image ingestion lands (#3) it must
validate by content type **and** magic bytes, cap size, hash before storage, and never serve from a
shared bucket without a signed URL.

---

### SEC-012 — Container hardening (P3, **Partial**)

Present: multi-stage build, non-root user (uid 10001), no build tools in the runtime layer, health
check, explicit `COPY` (no `ADD` of a tarball).

Missing: read-only root filesystem, dropped capabilities, pinned base image digest, SBOM, image
signing. Tracked in #19.

---

### SEC-013 — Dependency and supply-chain scanning (P3, **Open**)

No `pip-audit`, `npm audit`, Dependabot, or lockfile verification in CI. Tracked in #19.

---

## 3. Control summary

| Control | Requirement | Status |
|---|---|---|
| Authentication | FR-001 | Implemented (mechanism), blocked on IdP |
| RBAC | FR-002 | Implemented, enforced on telemetry |
| Tenant isolation (RLS + scoping) | FR-004 | **Enforced and tested** |
| 404 for foreign resources | FR-004 | Implemented |
| Input validation | FR-023 | **Enforced and tested** |
| Idempotent ingestion | FR-022 | **Enforced and tested** |
| Error hygiene | — | **Enforced and tested** |
| Rate limiting | FR-001 | Partial |
| Audit logging | FR-006 | Open |
| Agent tool restrictions | FR-042/048 | Enforced at contract level |
| Human approval gate | FR-047 | Contract field only |

---

## 4. Honest limitations

- These tests prove behaviour against **PostgreSQL 16 with TimescaleDB**. A different engine or a
  managed service that disables RLS would invalidate them; the CI job is the guarantee, not the
  document.
- The isolation suite runs as a role created by the test itself. If production connects as a
  superuser, isolation is bypassed regardless of these tests — deployment must use a dedicated
  application role, stated in `docs/operations-runbook.md`.
- No penetration test, no fuzzing, and no adversarial review by a second party has been performed.
  Nothing here should be read as a security certification.
