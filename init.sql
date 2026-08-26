-- CS2 metrikalar jadvali
CREATE TABLE IF NOT EXISTS server_metrics (
    timestamp TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL,
    game VARCHAR(16) NOT NULL,
    region VARCHAR(32) NOT NULL,
    player_count INT NOT NULL,
    max_players INT,
    tick_rate FLOAT,
    ping_ms FLOAT,
    map VARCHAR(64)
);

-- TimescaleDB Hypertable ga o'tkazish (vaqt seriyali ma'lumotlarni tezkor so'rash uchun)
SELECT create_hypertable('server_metrics', 'timestamp', if_not_exists => TRUE);

-- Monitoring qilinadigan serverlar ro'yxati
CREATE TABLE IF NOT EXISTS monitored_servers (
    server_id VARCHAR(64) PRIMARY KEY,
    server_name VARCHAR(128),
    region VARCHAR(32) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI anomaliyalari va bildirishnomalar tarixi
CREATE TABLE IF NOT EXISTS anomalies_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    server_id VARCHAR(64) NOT NULL,
    anomaly_score FLOAT NOT NULL,
    root_cause VARCHAR(64) NOT NULL,
    telegram_sent BOOLEAN DEFAULT FALSE
);