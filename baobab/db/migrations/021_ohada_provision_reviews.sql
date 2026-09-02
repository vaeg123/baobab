-- Journal d'audit éditorial des articles OHADA.

CREATE TABLE IF NOT EXISTS legal_provision_reviews (
    review_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provision_id UUID NOT NULL REFERENCES legal_provisions(provision_id) ON DELETE CASCADE,
    review_status VARCHAR(30) NOT NULL CHECK (
        review_status IN ('IN_REVIEW','DOCUMENT_VERIFIED','VALIDATED','REJECTED')
    ),
    review_note TEXT,
    reviewed_by TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provision_reviews_history
    ON legal_provision_reviews(provision_id,reviewed_at DESC);

COMMENT ON TABLE legal_provision_reviews IS 'Historique append-only des décisions éditoriales sur les articles juridiques.';
