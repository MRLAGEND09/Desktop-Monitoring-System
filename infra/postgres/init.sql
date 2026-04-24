-- ============================================================================
-- init.sql — PostgreSQL schema bootstrap
-- Run automatically on first docker-compose up via postgres initdb.d mount
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role          VARCHAR(16) NOT NULL CHECK (role IN ('admin','monitor','viewer'))
                  DEFAULT 'viewer',
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default admin (password: ChangeMe123!)
-- bcrypt hash of 'ChangeMe123!' with cost 12
INSERT INTO users (username, password_hash, role)
VALUES (
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBdXIG/0I.N7mS',
    'admin'
) ON CONFLICT DO NOTHING;

-- ── Devices ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(128) NOT NULL,
    hostname    VARCHAR(128),
    ip_address  VARCHAR(45),
    os_info     VARCHAR(256),
    status      VARCHAR(16) NOT NULL DEFAULT 'offline'
                CHECK (status IN ('online','offline','idle','streaming')),
    active_app  VARCHAR(128),
    last_seen   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
-- Covering index for the dashboard query: list all devices ordered by last_seen
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen DESC NULLS LAST);
-- Partial index: only online/streaming devices (used by metrics gauge)
CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(id)
    WHERE status IN ('online', 'streaming');

-- ── Activity logs (partitioned by month) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_logs (
    id            BIGSERIAL,
    device_id     UUID        NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    active_app    VARCHAR(128),
    window_title  TEXT,
    app_category  VARCHAR(16) NOT NULL DEFAULT 'unknown'
                  CHECK (app_category IN ('work','non-work','unknown')),
    idle_seconds  INTEGER     NOT NULL DEFAULT 0,
    is_idle       BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Monthly partitions (extend as needed)
CREATE TABLE IF NOT EXISTS activity_logs_2026_04
    PARTITION OF activity_logs FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_05
    PARTITION OF activity_logs FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_06
    PARTITION OF activity_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_07
    PARTITION OF activity_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_08
    PARTITION OF activity_logs FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_09
    PARTITION OF activity_logs FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_10
    PARTITION OF activity_logs FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_11
    PARTITION OF activity_logs FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS activity_logs_2026_12
    PARTITION OF activity_logs FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

CREATE INDEX IF NOT EXISTS idx_logs_device_time
    ON activity_logs(device_id, created_at DESC);
-- For category breakdown queries (work vs non-work per device)
CREATE INDEX IF NOT EXISTS idx_logs_category
    ON activity_logs(device_id, app_category, created_at DESC);
-- For pagination on the logs page (latest entries across all devices)
CREATE INDEX IF NOT EXISTS idx_logs_time ON activity_logs(created_at DESC);

-- ── Alerts ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id          BIGSERIAL   PRIMARY KEY,
    device_id   UUID        REFERENCES devices(id) ON DELETE SET NULL,
    severity    VARCHAR(16) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    message     TEXT        NOT NULL,
    resolved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON alerts(created_at DESC)
    WHERE resolved_at IS NULL;
-- For filtering by device on the alerts page
CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device_id, created_at DESC);
-- For severity-based webhook filtering (avoid seq scan on large tables)
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, created_at DESC)
    WHERE resolved_at IS NULL;

-- ── Audit logs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id         BIGSERIAL   PRIMARY KEY,
    user_id    UUID        REFERENCES users(id) ON DELETE SET NULL,
    action     VARCHAR(128) NOT NULL,
    detail     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at DESC);

-- ── Webhooks ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhooks (
    id               BIGSERIAL    PRIMARY KEY,
    url              VARCHAR(512) NOT NULL,
    secret           VARCHAR(128),
    severity_filter  VARCHAR(64)  NOT NULL DEFAULT '',
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       UUID         REFERENCES users(id) ON DELETE SET NULL
);
