-- BAOBAB 0.2 — international legal fabric and source provenance.

CREATE TABLE IF NOT EXISTS legal_jurisdictions (
    code                VARCHAR(40) PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    kind                VARCHAR(30) NOT NULL,
    country_code        CHAR(2),
    parent_code         VARCHAR(40) REFERENCES legal_jurisdictions(code),
    legal_system        VARCHAR(50) NOT NULL,
    default_language    VARCHAR(10) NOT NULL DEFAULT 'fr',
    pack                VARCHAR(50) NOT NULL,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legal_jurisdiction_country_format CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$')
);

CREATE TABLE IF NOT EXISTS legal_sources (
    code                    VARCHAR(60) PRIMARY KEY,
    name                    VARCHAR(200) NOT NULL,
    jurisdiction_code       VARCHAR(40) NOT NULL REFERENCES legal_jurisdictions(code),
    source_type             VARCHAR(50) NOT NULL,
    base_url                TEXT NOT NULL,
    access_mode             VARCHAR(50) NOT NULL,
    license_name            VARCHAR(200),
    license_url             TEXT,
    license_review_required BOOLEAN NOT NULL DEFAULT TRUE,
    enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    last_successful_sync_at TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS jurisdiction_code VARCHAR(40);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS country_code CHAR(2);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS language_code VARCHAR(10) NOT NULL DEFAULT 'fr';
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS source_code VARCHAR(60);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS official_identifier VARCHAR(250);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS official_citation TEXT;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS publication_date DATE;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS effective_from DATE;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS effective_to DATE;
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS legal_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS source_license VARCHAR(200);
ALTER TABLE legal_corpus ADD COLUMN IF NOT EXISTS content_checksum CHAR(64);

INSERT INTO legal_jurisdictions (code, name, kind, country_code, parent_code, legal_system, default_language, pack) VALUES
('FR', 'France', 'NATIONAL', 'FR', NULL, 'CIVIL_LAW', 'fr', 'france'),
('EU', 'Union européenne', 'REGIONAL', NULL, NULL, 'EU_LAW', 'fr', 'europe'),
('ECHR', 'Convention européenne des droits de l''homme', 'INTERNATIONAL', NULL, NULL, 'INTERNATIONAL_LAW', 'fr', 'echr'),
('OHADA', 'OHADA', 'REGIONAL', NULL, NULL, 'OHADA_LAW', 'fr', 'ohada'),
('CIMA', 'CIMA', 'REGIONAL', NULL, NULL, 'CIMA_LAW', 'fr', 'cima'),
('UEMOA', 'UEMOA', 'REGIONAL', NULL, NULL, 'COMMUNITY_LAW', 'fr', 'uemoa'),
('UN.ICJ', 'Cour internationale de Justice', 'COURT', NULL, NULL, 'INTERNATIONAL_LAW', 'fr', 'international'),
('ICC', 'Cour pénale internationale', 'COURT', NULL, NULL, 'INTERNATIONAL_LAW', 'fr', 'international')
ON CONFLICT (code) DO NOTHING;

INSERT INTO legal_jurisdictions (code, name, kind, country_code, parent_code, legal_system, default_language, pack) VALUES
('FR.CASS', 'Cour de cassation', 'COURT', 'FR', 'FR', 'CIVIL_LAW', 'fr', 'france'),
('FR.CE', 'Conseil d''État', 'COURT', 'FR', 'FR', 'CIVIL_LAW', 'fr', 'france'),
('FR.CC', 'Conseil constitutionnel', 'COURT', 'FR', 'FR', 'CIVIL_LAW', 'fr', 'france'),
('EU.CJUE', 'Cour de justice de l''Union européenne', 'COURT', NULL, 'EU', 'EU_LAW', 'fr', 'europe'),
('ECHR.COURT', 'Cour européenne des droits de l''homme', 'COURT', NULL, 'ECHR', 'INTERNATIONAL_LAW', 'fr', 'echr'),
('OHADA.CCJA', 'Cour commune de justice et d''arbitrage', 'COURT', NULL, 'OHADA', 'OHADA_LAW', 'fr', 'ohada'),
('BCEAO', 'BCEAO', 'REGIONAL', NULL, 'UEMOA', 'COMMUNITY_LAW', 'fr', 'bceao')
ON CONFLICT (code) DO NOTHING;

INSERT INTO legal_sources (code, name, jurisdiction_code, source_type, base_url, access_mode) VALUES
('FR.LEGIFRANCE', 'Légifrance', 'FR', 'LEGISLATION', 'https://www.legifrance.gouv.fr', 'PISTE_API'),
('FR.JUDILIBRE', 'Judilibre', 'FR.CASS', 'CASE_LAW', 'https://www.courdecassation.fr', 'PISTE_API'),
('EU.EURLEX', 'EUR-Lex', 'EU', 'LEGISLATION_AND_CASE_LAW', 'https://eur-lex.europa.eu', 'WEBSERVICE_CELLAR'),
('ECHR.HUDOC', 'HUDOC', 'ECHR.COURT', 'CASE_LAW', 'https://hudoc.echr.coe.int', 'OFFICIAL_DATABASE'),
('OHADA.OFFICIAL', 'OHADA', 'OHADA', 'LEGISLATION', 'https://www.ohada.org', 'OFFICIAL_PUBLICATION'),
('OHADA.CCJA', 'Jurisprudence CCJA', 'OHADA.CCJA', 'CASE_LAW', 'https://www.ohada.org', 'OFFICIAL_PUBLICATION')
ON CONFLICT (code) DO NOTHING;

UPDATE legal_corpus SET jurisdiction_code = CASE
    WHEN corpus = 'cima' THEN 'CIMA'
    WHEN corpus = 'ohada' AND type ILIKE '%ccja%' THEN 'OHADA.CCJA'
    WHEN corpus = 'ohada' THEN 'OHADA'
    WHEN corpus = 'fr' THEN 'FR'
    ELSE jurisdiction_code
END
WHERE jurisdiction_code IS NULL;

UPDATE legal_corpus SET country_code = 'CI'
WHERE country_code IS NULL AND corpus = 'ci';

ALTER TABLE legal_corpus
ADD CONSTRAINT legal_corpus_country_format_check
CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$') NOT VALID;

ALTER TABLE legal_corpus
ADD CONSTRAINT legal_corpus_checksum_format_check
CHECK (content_checksum IS NULL OR content_checksum ~ '^[a-f0-9]{64}$') NOT VALID;

CREATE INDEX IF NOT EXISTS idx_lc_jurisdiction ON legal_corpus (jurisdiction_code);
CREATE INDEX IF NOT EXISTS idx_lc_country_code ON legal_corpus (country_code);
CREATE INDEX IF NOT EXISTS idx_lc_language ON legal_corpus (language_code);
CREATE INDEX IF NOT EXISTS idx_lc_legal_status ON legal_corpus (legal_status);
CREATE INDEX IF NOT EXISTS idx_lc_effective_dates ON legal_corpus (effective_from, effective_to);
