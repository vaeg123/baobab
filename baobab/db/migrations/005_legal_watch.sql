CREATE TABLE IF NOT EXISTS legal_watch_subscriptions (
    watch_id VARCHAR(40) PRIMARY KEY,
    workspace_id VARCHAR(40) NOT NULL,
    name VARCHAR(120) NOT NULL,
    query TEXT,
    corpus VARCHAR(40) NOT NULL DEFAULT 'all',
    country_code VARCHAR(8),
    jurisdiction_code VARCHAR(40),
    email_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watch_workspace
    ON legal_watch_subscriptions (workspace_id, active);
