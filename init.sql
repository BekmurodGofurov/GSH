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