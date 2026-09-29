-- Migration 002: Alert Mute / Acknowledge controls
-- Run once against the existing database before deploying the new services.

-- Acknowledge columns on server_events
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS is_acknowledged BOOLEAN DEFAULT FALSE;
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS acknowledged_by VARCHAR(64);
ALTER TABLE server_events ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ;

-- alert_silences: per-server temporary mutes
CREATE TABLE IF NOT EXISTS alert_silences (
    id          SERIAL PRIMARY KEY,
    server_id   VARCHAR(64) REFERENCES monitored_servers(server_id) ON DELETE CASCADE,
    muted_until TIMESTAMPTZ NOT NULL,
    muted_by    VARCHAR(64),
    reason      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Fast lookup: "is this server currently silenced?"
CREATE INDEX IF NOT EXISTS idx_alert_silences_active
    ON alert_silences(server_id, muted_until);
