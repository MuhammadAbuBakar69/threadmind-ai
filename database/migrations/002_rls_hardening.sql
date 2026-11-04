-- ===========================================================================
-- 002 — Row-level security hardening
--
-- Two defects motivate this migration, both found by audit rather than by test:
--
-- 1. RLS was enabled on 16 tables but NOT forced. In PostgreSQL a table owner
--    bypasses its own RLS policies unless FORCE ROW LEVEL SECURITY is set. The
--    application connected as the schema owner, so in the deployed configuration
--    the policies were decoration: every query saw every tenant's rows.
--
-- 2. Four tables reachable by tenant-scoped queries had no coverage at all:
--    organization_members (the authorization table itself),
--    investigation_evidence, root_cause_hypotheses and agent_actions.
--    Child tables without organization_id must inherit isolation from their
--    parent, and nothing enforced that.
--
-- This migration is additive and reversible; see 900_rollback_002.sql.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Force RLS so it applies to the table owner as well.
-- ---------------------------------------------------------------------------

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'factories','production_lines','machines','production_batches','production_events',
    'fabric_images','inspection_results','machine_sensors','sensor_readings','machine_predictions',
    'maintenance_records','maintenance_recommendations','investigations','agent_runs',
    'system_alerts','audit_logs','detected_defects'
  ] LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
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
    USING (organization_id = current_setting('app.current_org', true)::uuid);

-- A user must be able to resolve their own memberships before a principal
-- exists, otherwise login is impossible. Read-only, self-scoped.
DROP POLICY IF EXISTS self_membership_lookup ON organization_members;
CREATE POLICY self_membership_lookup ON organization_members
    FOR SELECT
    USING (user_id = current_setting('app.current_user', true)::uuid);

-- ---------------------------------------------------------------------------
-- 3. Identity tables.
--    organizations and users are global, but a connection with the app role
--    must not be able to enumerate every tenant.
-- ---------------------------------------------------------------------------

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON organizations;
CREATE POLICY tenant_isolation ON organizations
    USING (id = current_setting('app.current_org', true)::uuid);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON users;
CREATE POLICY tenant_isolation ON users
    USING (
        id = current_setting('app.current_user', true)::uuid
        OR id IN (
            SELECT m.user_id FROM organization_members m
            WHERE m.organization_id = current_setting('app.current_org', true)::uuid
        )
    );

-- ---------------------------------------------------------------------------
-- 4. Child tables inherit isolation from their parent record.
--    Each policy uses EXISTS against the parent, so a row whose parent belongs
--    to another organization is invisible regardless of how it is queried.
-- ---------------------------------------------------------------------------

ALTER TABLE investigation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation_evidence FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON investigation_evidence;
CREATE POLICY tenant_isolation ON investigation_evidence
    USING (EXISTS (
        SELECT 1 FROM investigations i
        WHERE i.id = investigation_evidence.investigation_id
          AND i.organization_id = current_setting('app.current_org', true)::uuid
    ));

ALTER TABLE root_cause_hypotheses ENABLE ROW LEVEL SECURITY;
ALTER TABLE root_cause_hypotheses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON root_cause_hypotheses;
CREATE POLICY tenant_isolation ON root_cause_hypotheses
    USING (EXISTS (
        SELECT 1 FROM investigations i
        WHERE i.id = root_cause_hypotheses.investigation_id
          AND i.organization_id = current_setting('app.current_org', true)::uuid
    ));

ALTER TABLE agent_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON agent_actions;
CREATE POLICY tenant_isolation ON agent_actions
    USING (EXISTS (
        SELECT 1 FROM agent_runs r
        WHERE r.id = agent_actions.agent_run_id
          AND r.organization_id = current_setting('app.current_org', true)::uuid
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
