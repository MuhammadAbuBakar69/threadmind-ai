-- ===========================================================================
-- 002 — Row-level security hardening
--
-- Three defects motivate this migration, all found by audit rather than by test:
--
-- 1. RLS was enabled on 16 tables but NOT forced. In PostgreSQL a table owner
--    bypasses its own policies unless FORCE ROW LEVEL SECURITY is set. The
--    application connected as the schema owner, so in the deployed configuration
--    the policies were decoration: every query saw every tenant's rows.
--
-- 2. Four tables reachable by tenant-scoped queries had no coverage at all:
--    organization_members (the authorization table itself),
--    investigation_evidence, root_cause_hypotheses and agent_actions.
--    Child tables without organization_id must inherit isolation from their
--    parent, and nothing enforced that.
--
-- 3. Policies compared against `current_setting('app.current_org', true)::uuid`
--    with no empty-string guard. A custom GUC reverts to the empty string, not
--    NULL, when a transaction-local setting ends, so the next statement on that
--    pooled connection raises `invalid input syntax for type uuid: ""` instead of
--    denying. Deny-by-default must return no rows, not an error. Hence NULLIF.
--
-- This migration is additive and reversible; see 900_rollback_002.sql.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Re-declare the tenant policy on every table that owns an organization_id.
--    Uniform definition, empty-string safe, and supersedes the policies created
--    by 001 so there is exactly one interpretation in the database.
-- ---------------------------------------------------------------------------

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'factories','production_lines','machines','production_batches','production_events',
    'fabric_images','inspection_results','machine_sensors','sensor_readings','machine_predictions',
    'maintenance_records','maintenance_recommendations','investigations','agent_runs',
    'system_alerts','audit_logs'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
    EXECUTE format(
      $policy$CREATE POLICY tenant_isolation ON %I USING
        (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid)$policy$, t);
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 2. organization_members — the table authorization decisions are made from.
--    A leak here is a leak of every organization's user list.
-- ---------------------------------------------------------------------------

ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON organization_members;
CREATE POLICY tenant_isolation ON organization_members
    USING (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid);

-- A user must be able to resolve their own memberships before a principal
-- exists, otherwise login is impossible. Read-only, self-scoped.
DROP POLICY IF EXISTS self_membership_lookup ON organization_members;
CREATE POLICY self_membership_lookup ON organization_members
    FOR SELECT
    USING (user_id = NULLIF(current_setting('app.current_user', true), '')::uuid);

-- ---------------------------------------------------------------------------
-- 3. Identity tables. organizations and users are global, but a connection with
--    the app role must not be able to enumerate every tenant.
-- ---------------------------------------------------------------------------

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON organizations;
CREATE POLICY tenant_isolation ON organizations
    USING (id = NULLIF(current_setting('app.current_org', true), '')::uuid);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON users;
CREATE POLICY tenant_isolation ON users
    USING (
        id = NULLIF(current_setting('app.current_user', true), '')::uuid
        OR id IN (
            SELECT m.user_id FROM organization_members m
            WHERE m.organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid
        )
    );

-- ---------------------------------------------------------------------------
-- 4. Child tables inherit isolation from their parent record.
--    Each policy uses EXISTS against the parent, so a row whose parent belongs
--    to another organization is invisible regardless of how it is queried.
-- ---------------------------------------------------------------------------

ALTER TABLE detected_defects ENABLE ROW LEVEL SECURITY;
ALTER TABLE detected_defects FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON detected_defects;
CREATE POLICY tenant_isolation ON detected_defects
    USING (EXISTS (
        SELECT 1 FROM inspection_results ir
        WHERE ir.id = detected_defects.inspection_result_id
          AND ir.organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    ));

ALTER TABLE investigation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation_evidence FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON investigation_evidence;
CREATE POLICY tenant_isolation ON investigation_evidence
    USING (EXISTS (
        SELECT 1 FROM investigations i
        WHERE i.id = investigation_evidence.investigation_id
          AND i.organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    ));

ALTER TABLE root_cause_hypotheses ENABLE ROW LEVEL SECURITY;
ALTER TABLE root_cause_hypotheses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON root_cause_hypotheses;
CREATE POLICY tenant_isolation ON root_cause_hypotheses
    USING (EXISTS (
        SELECT 1 FROM investigations i
        WHERE i.id = root_cause_hypotheses.investigation_id
          AND i.organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    ));

ALTER TABLE agent_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON agent_actions;
CREATE POLICY tenant_isolation ON agent_actions
    USING (EXISTS (
        SELECT 1 FROM agent_runs r
        WHERE r.id = agent_actions.agent_run_id
          AND r.organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    ));

-- ---------------------------------------------------------------------------
-- 5. model_versions is a global registry: every tenant may read the set of
--    deployed models, because predictions cite them. Writes are restricted by
--    role at the application layer; no tenant may see another tenant's private
--    artifact URIs, so URIs are not exposed through the API.
-- ---------------------------------------------------------------------------

COMMENT ON TABLE model_versions IS
    'Global model registry. Readable by all authenticated tenants so predictions can cite a '
    'version; artifact_uri must never be returned by an API response.';

-- ---------------------------------------------------------------------------
-- 6. Telemetry idempotency.
--    MQTT QoS 1 is at-least-once, so duplicate delivery is expected, not
--    exceptional. Without a natural key, a redelivered burst double-counts
--    readings and distorts every downstream window statistic.
-- ---------------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_natural_key
    ON sensor_readings (machine_id, sensor_id, "timestamp");

CREATE INDEX IF NOT EXISTS idx_readings_org_time
    ON sensor_readings (organization_id, "timestamp" DESC);

CREATE INDEX IF NOT EXISTS idx_agent_actions_run_status
    ON agent_actions (agent_run_id, execution_status);
