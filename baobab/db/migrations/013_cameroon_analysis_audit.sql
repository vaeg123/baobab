-- Add reproducibility and operational diagnostics to Cameroon AI analyses.
ALTER TABLE cm_analyze_log
    ADD COLUMN IF NOT EXISTS model_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(40) NOT NULL DEFAULT 'cm-v1',
    ADD COLUMN IF NOT EXISTS source_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER,
    ADD COLUMN IF NOT EXISTS provider_status VARCHAR(30) NOT NULL DEFAULT 'NOT_CALLED';

ALTER TABLE cm_analyze_log
    DROP CONSTRAINT IF EXISTS ck_cm_analyze_log_duration;

ALTER TABLE cm_analyze_log
    ADD CONSTRAINT ck_cm_analyze_log_duration
    CHECK (duration_ms IS NULL OR duration_ms >= 0);

CREATE INDEX IF NOT EXISTS idx_cm_analyze_log_provider_status
    ON cm_analyze_log(provider_status, created_at DESC);
