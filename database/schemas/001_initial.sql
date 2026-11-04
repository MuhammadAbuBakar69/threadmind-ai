-- ===========================================================================
-- ThreadMind AI — initial relational schema
-- PostgreSQL 15+  (TimescaleDB optional, see sensor_readings at the bottom)
--
-- Conventions
--   * UUID primary keys (gen_random_uuid via pgcrypto).
--   * Every tenant-owned table carries organization_id and is covered by RLS.
--   * Timestamps are TIMESTAMPTZ. Client-supplied organization_id is NEVER trusted:
--     the application sets app.current_org from the authenticated membership, and
--     RLS enforces the rest.
--   * JSONB only for genuinely flexible metadata, never for queryable columns.
-- ===========================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Organization and access
-- ---------------------------------------------------------------------------

CREATE TABLE organizations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    industry         TEXT DEFAULT 'textile',
    subscription_plan TEXT NOT NULL DEFAULT 'starter'
                     CHECK (subscription_plan IN ('starter','professional','enterprise')),
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','suspended','closed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                     CITEXT UNIQUE,
    full_name                 TEXT,
    authentication_provider_id TEXT,
    status                    TEXT NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active','invited','disabled')),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN (
                        'super_admin','factory_admin','factory_manager',
                        'quality_inspector','maintenance_engineer','production_supervisor')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);
CREATE INDEX idx_org_members_user ON organization_members(user_id);

-- ---------------------------------------------------------------------------
-- Factory structure
-- ---------------------------------------------------------------------------

CREATE TABLE factories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    location        TEXT,
    timezone        TEXT NOT NULL DEFAULT 'Asia/Karachi',
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','archived'))
);
CREATE INDEX idx_factories_org ON factories(organization_id);

CREATE TABLE production_lines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    factory_id      UUID NOT NULL REFERENCES factories(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    production_type TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX idx_lines_factory ON production_lines(factory_id);

CREATE TABLE machines (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    factory_id         UUID NOT NULL REFERENCES factories(id) ON DELETE CASCADE,
    production_line_id UUID REFERENCES production_lines(id) ON DELETE SET NULL,
    machine_code       TEXT NOT NULL,
    machine_name       TEXT NOT NULL,
    machine_type       TEXT,
    manufacturer       TEXT,
    model              TEXT,
    installation_date  DATE,
    operating_status   TEXT NOT NULL DEFAULT 'unknown'
                       CHECK (operating_status IN ('running','idle','maintenance','fault','unknown')),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (factory_id, machine_code)          -- FR-010
);
CREATE INDEX idx_machines_org ON machines(organization_id);
CREATE INDEX idx_machines_line ON machines(production_line_id);

-- ---------------------------------------------------------------------------
-- Production management
-- ---------------------------------------------------------------------------

CREATE TABLE production_batches (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    factory_id         UUID NOT NULL REFERENCES factories(id) ON DELETE CASCADE,
    production_line_id UUID REFERENCES production_lines(id) ON DELETE SET NULL,
    batch_code         TEXT NOT NULL,
    fabric_type        TEXT,
    fabric_material    TEXT,
    production_start   TIMESTAMPTZ,
    production_end     TIMESTAMPTZ,
    planned_quantity   NUMERIC(14,3),
    actual_quantity    NUMERIC(14,3),
    status             TEXT NOT NULL DEFAULT 'planned'
                       CHECK (status IN ('planned','running','paused','completed','cancelled')),
    UNIQUE (organization_id, batch_code)
);
CREATE INDEX idx_batches_org_time ON production_batches(organization_id, production_start DESC);

CREATE TABLE production_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    batch_id        UUID REFERENCES production_batches(id) ON DELETE CASCADE,
    machine_id      UUID REFERENCES machines(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_data      JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_prod_events_batch_time ON production_events(batch_id, event_timestamp DESC);

-- ---------------------------------------------------------------------------
-- Computer vision  (images live in object storage; only keys in the database)
-- ---------------------------------------------------------------------------

CREATE TABLE fabric_images (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    batch_id        UUID REFERENCES production_batches(id) ON DELETE SET NULL,
    machine_id      UUID REFERENCES machines(id) ON DELETE SET NULL,
    storage_key     TEXT NOT NULL,
    image_hash      TEXT NOT NULL,
    image_width     INTEGER,
    image_height    INTEGER,
    captured_at     TIMESTAMPTZ,
    camera_id       TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_fabric_images_org_captured ON fabric_images(organization_id, captured_at DESC);
CREATE UNIQUE INDEX uq_fabric_images_hash ON fabric_images(organization_id, image_hash);

CREATE TABLE inspection_results (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    fabric_image_id      UUID NOT NULL REFERENCES fabric_images(id) ON DELETE CASCADE,
    model_version_id     UUID,                  -- FK added after model_versions exists
    overall_status       TEXT NOT NULL CHECK (overall_status IN ('pass','fail','uncertain')),
    inference_duration_ms INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_inspections_image ON inspection_results(fabric_image_id);

CREATE TABLE detected_defects (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_result_id UUID NOT NULL REFERENCES inspection_results(id) ON DELETE CASCADE,
    defect_class         TEXT NOT NULL,
    confidence_score     NUMERIC(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    bounding_box         JSONB,                 -- {"x":..,"y":..,"w":..,"h":..} in pixels
    segmentation_mask_key TEXT,                 -- object-storage key for the mask
    severity             TEXT CHECK (severity IN ('minor','major','critical')),
    verification_status  TEXT NOT NULL DEFAULT 'pending'
                         CHECK (verification_status IN ('pending','confirmed','rejected','corrected'))
);
CREATE INDEX idx_defects_inspection ON detected_defects(inspection_result_id);
CREATE INDEX idx_defects_class ON detected_defects(defect_class);

-- ---------------------------------------------------------------------------
-- Machine intelligence
-- ---------------------------------------------------------------------------

CREATE TABLE machine_sensors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    machine_id        UUID NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    sensor_type       TEXT NOT NULL,     -- temperature|vibration|speed|torque|current|pressure
    sensor_name       TEXT NOT NULL,
    measurement_unit  TEXT,
    sampling_interval INTERVAL,
    UNIQUE (machine_id, sensor_name)
);

CREATE TABLE sensor_readings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    machine_id      UUID NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    sensor_id       UUID NOT NULL REFERENCES machine_sensors(id) ON DELETE CASCADE,
    "timestamp"     TIMESTAMPTZ NOT NULL,
    numeric_value   DOUBLE PRECISION NOT NULL,
    quality_flag    TEXT NOT NULL DEFAULT 'good'
                    CHECK (quality_flag IN ('good','suspect','missing','interpolated'))
);
-- Telemetry is queried as (machine, time window). Partition or convert to a
-- Timescale hypertable before production volumes:
--   SELECT create_hypertable('sensor_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_readings_machine_time ON sensor_readings(machine_id, "timestamp" DESC);

CREATE TABLE machine_predictions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    machine_id           UUID NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    model_version_id     UUID,                  -- FK added after model_versions exists
    prediction_type      TEXT NOT NULL,         -- anomaly|failure_risk
    anomaly_score        NUMERIC(8,6),
    failure_probability  NUMERIC(5,4) CHECK (failure_probability BETWEEN 0 AND 1),
    risk_level           TEXT CHECK (risk_level IN ('low','medium','high','critical')),
    prediction_timestamp TIMESTAMPTZ NOT NULL,
    prediction_metadata  JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_predictions_machine_time ON machine_predictions(machine_id, prediction_timestamp DESC);

-- ---------------------------------------------------------------------------
-- Maintenance
-- ---------------------------------------------------------------------------

CREATE TABLE maintenance_records (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    machine_id         UUID NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    maintenance_type   TEXT NOT NULL,           -- preventive|corrective|inspection
    description        TEXT,
    maintenance_date   TIMESTAMPTZ NOT NULL,
    technician_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    downtime_minutes   INTEGER CHECK (downtime_minutes >= 0),
    resolution_status  TEXT NOT NULL DEFAULT 'open'
                       CHECK (resolution_status IN ('open','resolved','deferred'))
);
CREATE INDEX idx_maint_machine_date ON maintenance_records(machine_id, maintenance_date DESC);

CREATE TABLE maintenance_recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    machine_id          UUID NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    prediction_id       UUID REFERENCES machine_predictions(id) ON DELETE SET NULL,
    recommendation_text TEXT NOT NULL,
    priority            TEXT NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low','medium','high','critical')),
    approval_status     TEXT NOT NULL DEFAULT 'pending'
                        CHECK (approval_status IN ('pending','approved','rejected','deferred')),
    approved_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Root cause analysis
-- ---------------------------------------------------------------------------

CREATE TABLE investigations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    factory_id           UUID REFERENCES factories(id) ON DELETE SET NULL,
    batch_id             UUID REFERENCES production_batches(id) ON DELETE SET NULL,
    machine_id           UUID REFERENCES machines(id) ON DELETE SET NULL,
    issue_type           TEXT NOT NULL,
    investigation_status TEXT NOT NULL DEFAULT 'open'
                         CHECK (investigation_status IN ('open','investigating','awaiting_review','closed')),
    start_timestamp      TIMESTAMPTZ NOT NULL,
    end_timestamp        TIMESTAMPTZ,
    final_summary        TEXT
);

CREATE TABLE investigation_evidence (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id     UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    evidence_type        TEXT NOT NULL,   -- sensor_window|inspection|maintenance|batch|document
    source_record_id     UUID,
    evidence_description TEXT NOT NULL,
    relevance_score      NUMERIC(5,4) CHECK (relevance_score BETWEEN 0 AND 1),
    "timestamp"          TIMESTAMPTZ
);
CREATE INDEX idx_evidence_investigation ON investigation_evidence(investigation_id);

CREATE TABLE root_cause_hypotheses (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id          UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    hypothesis                TEXT NOT NULL,
    confidence_score          NUMERIC(5,4) CHECK (confidence_score BETWEEN 0 AND 1),
    supporting_evidence       JSONB NOT NULL DEFAULT '[]'::jsonb,
    alternative_explanations  JSONB NOT NULL DEFAULT '[]'::jsonb,
    claim_kind                TEXT NOT NULL DEFAULT 'association'
                              CHECK (claim_kind IN ('observed_fact','association','hypothesis')),
    verification_status       TEXT NOT NULL DEFAULT 'unverified'
                              CHECK (verification_status IN ('unverified','confirmed','rejected'))
);
CREATE INDEX idx_hypotheses_investigation ON root_cause_hypotheses(investigation_id);

-- ---------------------------------------------------------------------------
-- AI agent infrastructure
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    agent_name       TEXT NOT NULL,
    workflow_id      TEXT,
    status           TEXT NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running','succeeded','failed','awaiting_approval')),
    input_reference  JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_reference JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_name       TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    token_usage      INTEGER
);
CREATE INDEX idx_agent_runs_investigation ON agent_runs(investigation_id);

CREATE TABLE agent_actions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id     UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    action_type      TEXT NOT NULL,
    action_input     JSONB NOT NULL DEFAULT '{}'::jsonb,
    action_output    JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_status TEXT NOT NULL DEFAULT 'ok'
                     CHECK (execution_status IN ('ok','error','skipped')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_actions_run ON agent_actions(agent_run_id);

-- ---------------------------------------------------------------------------
-- Models and monitoring
-- ---------------------------------------------------------------------------

CREATE TABLE model_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name       TEXT NOT NULL,
    model_type       TEXT NOT NULL,   -- detection|segmentation|anomaly|classification|forecast
    version          TEXT NOT NULL,
    artifact_uri     TEXT NOT NULL,
    dataset_version  TEXT,
    evaluation_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    deployment_status TEXT NOT NULL DEFAULT 'staging'
                      CHECK (deployment_status IN ('staging','production','retired')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_name, version)
);

ALTER TABLE inspection_results
    ADD CONSTRAINT fk_inspection_model FOREIGN KEY (model_version_id)
    REFERENCES model_versions(id) ON DELETE SET NULL;

ALTER TABLE machine_predictions
    ADD CONSTRAINT fk_prediction_model FOREIGN KEY (model_version_id)
    REFERENCES model_versions(id) ON DELETE SET NULL;

CREATE TABLE system_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    factory_id      UUID REFERENCES factories(id) ON DELETE CASCADE,
    machine_id      UUID REFERENCES machines(id) ON DELETE SET NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    message         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','acknowledged','resolved','escalated')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ
);
CREATE INDEX idx_alerts_org_status ON system_alerts(organization_id, status, created_at DESC);

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     UUID,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_time ON audit_logs(organization_id, created_at DESC);

-- ===========================================================================
-- Tenant isolation
--
-- The API sets  SET LOCAL app.current_org = '<uuid>'  inside every request
-- transaction, after resolving the caller's membership. Policy therefore
-- applies to any query regardless of what the client sent.
-- ===========================================================================

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
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING '
      '(organization_id = current_setting(''app.current_org'', true)::uuid)', t);
  END LOOP;
END $$;

-- Tables without their own organization_id inherit isolation through their parent.
ALTER TABLE detected_defects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON detected_defects USING (EXISTS (
    SELECT 1 FROM inspection_results ir
    WHERE ir.id = detected_defects.inspection_result_id
      AND ir.organization_id = current_setting('app.current_org', true)::uuid));
