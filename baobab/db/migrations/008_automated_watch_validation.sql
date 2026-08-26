-- BAOBAB 0.3 — validation automatique explicable et livraison des alertes.

ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS observation_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS consecutive_observation_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS last_observed_run_id VARCHAR(40);
ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS validation_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS validation_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE legal_source_artifacts ADD COLUMN IF NOT EXISTS auto_validated_at TIMESTAMPTZ;

ALTER TABLE legal_watch_events ADD COLUMN IF NOT EXISTS validation_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE legal_watch_events ADD COLUMN IF NOT EXISTS validation_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE legal_watch_events ADD COLUMN IF NOT EXISTS auto_validated_at TIMESTAMPTZ;

ALTER TABLE legal_watch_runs ADD COLUMN IF NOT EXISTS events_auto_validated INTEGER NOT NULL DEFAULT 0;
ALTER TABLE legal_watch_runs ADD COLUMN IF NOT EXISTS emails_sent INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_source_artifacts_validation
    ON legal_source_artifacts (state, validation_score, auto_validated_at);
CREATE INDEX IF NOT EXISTS idx_watch_events_validation
    ON legal_watch_events (review_status, validation_score, discovered_at DESC);
