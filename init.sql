CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1-jadval: Serverlar va ularning joriy statusi
CREATE TABLE IF NOT EXISTS monitored_servers (
    server_id VARCHAR(64) PRIMARY KEY,
    server_name VARCHAR(128) NOT NULL,
    region VARCHAR(32) NOT NULL,
    status VARCHAR(16) DEFAULT 'ONLINE',
    last_online_at TIMESTAMPTZ,
    last_offline_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2-jadval: Vaqt bo'yicha metrikalar (Hypertable)
CREATE TABLE IF NOT EXISTS server_metrics (
    time TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL REFERENCES monitored_servers(server_id),
    player_count INT NOT NULL,
    max_players INT NOT NULL,
    ping_ms NUMERIC(6, 2) NOT NULL
);

SELECT create_hypertable('server_metrics', 'time', if_not_exists => TRUE);

-- 3-jadval: Server hodisalari va o'chib qolish jurnali (Incidents/Logs)
CREATE TABLE IF NOT EXISTS server_events (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL REFERENCES monitored_servers(server_id),
    event_type VARCHAR(32) NOT NULL, -- 'CRASH', 'OFFLINE', 'HIGH_PING', 'RECOVERY'
    message TEXT NOT NULL
);