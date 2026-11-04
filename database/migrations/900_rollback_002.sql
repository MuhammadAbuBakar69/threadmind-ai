-- Rollback for 002_rls_hardening.sql.
--
-- Deliberately small: it removes the policies and forced-RLS flags added by 002 and drops the
-- indexes it created. It does NOT drop any table or column, so it is safe to run while the
-- previous application version is still serving traffic.
--
-- Removing FORCE ROW LEVEL SECURITY returns the database to a state where the owner bypasses
-- policies. That is a security regression, not a neutral rollback: only use this to unblock a
-- failed deployment, then re-apply 002.

DROP INDEX IF EXISTS uq_readings_natural_key;
DROP INDEX IF EXISTS idx_readings_org_time;
DROP INDEX IF EXISTS idx_agent_actions_run_status;

DROP POLICY IF EXISTS tenant_isolation ON investigation_evidence;
DROP POLICY IF EXISTS tenant_isolation ON root_cause_hypotheses;
DROP POLICY IF EXISTS tenant_isolation ON agent_actions;
DROP POLICY IF EXISTS tenant_isolation ON users;
DROP POLICY IF EXISTS tenant_isolation ON organizations;
DROP POLICY IF EXISTS tenant_isolation ON organization_members;
DROP POLICY IF EXISTS self_membership_lookup ON organization_members;

-- NO FORCE must precede DISABLE: disabling RLS does not clear the FORCE flag, so a table left
-- behind by DISABLE alone keeps relforcerowsecurity = true and re-enabling RLS later would silently
-- re-force it. The order is observed behaviour, not preference - the CI rollback check caught it.
ALTER TABLE investigation_evidence NO FORCE ROW LEVEL SECURITY;
ALTER TABLE investigation_evidence DISABLE ROW LEVEL SECURITY;
ALTER TABLE root_cause_hypotheses NO FORCE ROW LEVEL SECURITY;
ALTER TABLE root_cause_hypotheses DISABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_actions DISABLE ROW LEVEL SECURITY;
ALTER TABLE users NO FORCE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE organizations NO FORCE ROW LEVEL SECURITY;
ALTER TABLE organizations DISABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members NO FORCE ROW LEVEL SECURITY;
ALTER TABLE organization_members DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'factories','production_lines','machines','production_batches','production_events',
    'fabric_images','inspection_results','machine_sensors','sensor_readings','machine_predictions',
    'maintenance_records','maintenance_recommendations','investigations','agent_runs',
    'system_alerts','audit_logs','detected_defects'
  ] LOOP
    EXECUTE format('ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
