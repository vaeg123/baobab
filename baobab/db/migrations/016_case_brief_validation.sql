-- Contrôle documentaire automatisé des fiches jurisprudentielles.
-- DOCUMENT_VERIFIED ne vaut jamais validation juridique par un juriste.

ALTER TABLE legal_case_briefs DROP CONSTRAINT IF EXISTS case_brief_editorial_status;
ALTER TABLE legal_case_briefs ADD CONSTRAINT case_brief_editorial_status CHECK (editorial_status IN (
    'TO_REVIEW','DOCUMENT_VERIFIED','IN_REVIEW','VALIDATED','REJECTED'
));
ALTER TABLE legal_case_briefs ADD COLUMN IF NOT EXISTS validation_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE legal_case_briefs ADD COLUMN IF NOT EXISTS automated_validation JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE legal_case_briefs ADD COLUMN IF NOT EXISTS document_verified_at TIMESTAMPTZ;
DO $$ BEGIN
    ALTER TABLE legal_case_briefs ADD CONSTRAINT case_brief_validation_score CHECK (validation_score BETWEEN 0 AND 100);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS legal_case_brief_validation_runs (
    run_id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    algorithm_version       VARCHAR(40) NOT NULL,
    status                  VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    briefs_scanned          INTEGER NOT NULL DEFAULT 0,
    briefs_document_verified INTEGER NOT NULL DEFAULT 0,
    briefs_to_review        INTEGER NOT NULL DEFAULT 0,
    report                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ
);

COMMENT ON COLUMN legal_case_briefs.document_verified_at IS 'Date du contrôle automatisé des preuves documentaires; ne constitue pas une validation juridique humaine.';
