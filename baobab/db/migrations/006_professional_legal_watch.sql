-- BAOBAB 0.3 — qualification éditoriale et provenance de la veille juridique.

ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS source_tier VARCHAR(40) NOT NULL DEFAULT 'UNVERIFIED';
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS source_verified_at TIMESTAMPTZ;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS editorial_status VARCHAR(40) NOT NULL DEFAULT 'TO_REVIEW';
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS impact_level VARCHAR(30) NOT NULL DEFAULT 'TO_QUALIFY';
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS impact_summary TEXT;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS change_type VARCHAR(50);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS detected_at TIMESTAMPTZ;

ALTER TABLE legal_corpus
ADD CONSTRAINT legal_corpus_source_tier_check
CHECK (source_tier IN ('OFFICIAL', 'INSTITUTIONAL_AGGREGATOR', 'SECONDARY', 'UNVERIFIED')) NOT VALID;

ALTER TABLE legal_corpus
ADD CONSTRAINT legal_corpus_editorial_status_check
CHECK (editorial_status IN ('TO_REVIEW', 'SOURCE_VERIFIED', 'EDITORIALLY_VALIDATED', 'REJECTED')) NOT VALID;

ALTER TABLE legal_corpus
ADD CONSTRAINT legal_corpus_impact_level_check
CHECK (impact_level IN ('TO_QUALIFY', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')) NOT VALID;

INSERT INTO legal_sources
    (code, name, jurisdiction_code, source_type, base_url, access_mode,
     license_review_required)
VALUES
    ('OHADA.BIBLIO', 'Bibliothèque OHADA', 'OHADA', 'LEGAL_LIBRARY',
     'https://biblio.ohada.org', 'OFFICIAL_DATABASE', TRUE),
    ('CIMA.OFFICIAL', 'CIMA', 'CIMA', 'LEGISLATION_AND_CASE_LAW',
     'https://cima-afrique.org', 'OFFICIAL_PUBLICATION', TRUE),
    ('BCEAO.OFFICIAL', 'BCEAO', 'BCEAO', 'REGULATION',
     'https://www.bceao.int', 'OFFICIAL_PUBLICATION', TRUE)
ON CONFLICT (code) DO NOTHING;

UPDATE legal_corpus
SET source_code = CASE
        WHEN source_url ~* '^https?://([^/]+\.)?biblio\.ohada\.org(/|$)' THEN 'OHADA.BIBLIO'
        WHEN source_url ~* '^https?://([^/]+\.)?ohada\.org(/|$)' THEN 'OHADA.OFFICIAL'
        WHEN source_url ~* '^https?://([^/]+\.)?(cima-afrique\.org|cima\.int)(/|$)' THEN 'CIMA.OFFICIAL'
        WHEN source_url ~* '^https?://([^/]+\.)?bceao\.int(/|$)' THEN 'BCEAO.OFFICIAL'
        WHEN source_url ~* '^https?://([^/]+\.)?legifrance\.gouv\.fr(/|$)' THEN 'FR.LEGIFRANCE'
        WHEN source_url ~* '^https?://([^/]+\.)?courdecassation\.fr(/|$)' THEN 'FR.JUDILIBRE'
        WHEN source_url ~* '^https?://([^/]+\.)?eur-lex\.europa\.eu(/|$)' THEN 'EU.EURLEX'
        WHEN source_url ~* '^https?://([^/]+\.)?juricaf\.org(/|$)' THEN 'AGG.JURICAF'
        WHEN source_url ~* '^https?://([^/]+\.)?ohadalegis\.com(/|$)' THEN 'PUB.OHADALEGIS'
        ELSE source_code
    END,
    source_tier = CASE
        WHEN source_url ~* '^https?://([^/]+\.)?(biblio\.ohada\.org|ohada\.org|cima-afrique\.org|cima\.int|bceao\.int|legifrance\.gouv\.fr|courdecassation\.fr|conseil-etat\.fr|conseil-constitutionnel\.fr|eur-lex\.europa\.eu|curia\.europa\.eu|echr\.coe\.int)(/|$)'
            THEN 'OFFICIAL'
        WHEN source_url ~* '^https?://([^/]+\.)?juricaf\.org(/|$)'
            THEN 'INSTITUTIONAL_AGGREGATOR'
        WHEN source_url ~* '^https?://([^/]+\.)?ohadalegis\.com(/|$)'
            THEN 'SECONDARY'
        ELSE 'UNVERIFIED'
    END,
    source_verified_at = CASE
        WHEN source_url ~* '^https?://([^/]+\.)?(biblio\.ohada\.org|ohada\.org|cima-afrique\.org|cima\.int|bceao\.int|legifrance\.gouv\.fr|courdecassation\.fr|conseil-etat\.fr|conseil-constitutionnel\.fr|eur-lex\.europa\.eu|curia\.europa\.eu|echr\.coe\.int)(/|$)'
            THEN NOW()
        ELSE NULL
    END,
    editorial_status = CASE
        WHEN source_url ~* '^https?://([^/]+\.)?(biblio\.ohada\.org|ohada\.org|cima-afrique\.org|cima\.int|bceao\.int|legifrance\.gouv\.fr|courdecassation\.fr|conseil-etat\.fr|conseil-constitutionnel\.fr|eur-lex\.europa\.eu|curia\.europa\.eu|echr\.coe\.int)(/|$)'
            THEN 'SOURCE_VERIFIED'
        ELSE 'TO_REVIEW'
    END,
    detected_at = COALESCE(detected_at, created_at)
WHERE COALESCE(source_url, '') ~* '^https?://';

ALTER TABLE legal_watch_subscriptions ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(30) NOT NULL DEFAULT 'DISABLED';
ALTER TABLE legal_watch_subscriptions ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ;
ALTER TABLE legal_watch_subscriptions ADD COLUMN IF NOT EXISTS last_match_at TIMESTAMPTZ;
ALTER TABLE legal_watch_subscriptions ADD COLUMN IF NOT EXISTS last_match_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_lc_watch_quality
    ON legal_corpus (source_tier, editorial_status, publication_date, date_decision);
CREATE INDEX IF NOT EXISTS idx_lc_detected_at ON legal_corpus (detected_at DESC);
