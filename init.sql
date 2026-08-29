CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Table 1: Monitored servers metadata and current status
CREATE TABLE IF NOT EXISTS monitored_servers (
    server_id VARCHAR(64) PRIMARY KEY,
    server_name VARCHAR(256) NOT NULL,
    region VARCHAR(32) NOT NULL,
    status VARCHAR(16) DEFAULT 'ONLINE',
    last_online_at TIMESTAMPTZ,
    last_offline_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table 2: Time-series server metrics (TimescaleDB Hypertable)
CREATE TABLE IF NOT EXISTS server_metrics (
    time TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL REFERENCES monitored_servers(server_id),
    player_count INT NOT NULL,
    max_players INT NOT NULL,
    ping_ms NUMERIC(6, 2) NOT NULL
);

SELECT create_hypertable('server_metrics', 'time', if_not_exists => TRUE);

-- Table 3: Server incident logs, crash events, and ML root causes
CREATE TABLE IF NOT EXISTS server_events (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL REFERENCES monitored_servers(server_id),
    event_type VARCHAR(32) NOT NULL, -- 'CRASH', 'OFFLINE', 'HIGH_PING', 'RECOVERY'
    root_cause VARCHAR(32) DEFAULT 'NORMAL', -- Target label for ML / Root Cause Classifier
    message TEXT NOT NULL
);

-- Detector evidence and classifier output are retained for incident review and
-- future supervised training. IF NOT EXISTS makes this safe for existing DBs.
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS root_cause VARCHAR(64) DEFAULT 'NORMAL';
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS label_source VARCHAR(32) DEFAULT 'model'; -- 'model' or 'manual'
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS anomaly_score NUMERIC(5, 4);
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS anomaly_reasons TEXT[];
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS player_count INT;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS max_players INT;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS ping_ms NUMERIC(6, 2);
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS ping_delta NUMERIC(8, 2);
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS player_delta INT;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS servers_affected_same_region INT;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS diagnosis JSONB;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS label_source VARCHAR(32);

-- Index for fast active learning retraining queries
CREATE INDEX IF NOT EXISTS idx_server_events_label_source 
ON server_events(label_source, root_cause) 
WHERE root_cause IS NOT NULL AND root_cause NOT IN ('UNKNOWN', 'NORMAL');