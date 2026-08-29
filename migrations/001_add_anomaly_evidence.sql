-- Apply this once to an existing TimescaleDB volume before starting the bridge.
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
