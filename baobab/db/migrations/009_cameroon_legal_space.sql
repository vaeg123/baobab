-- BAOBAB 0.4 — espace dynamique du droit camerounais.

INSERT INTO legal_jurisdictions
    (code,name,kind,country_code,parent_code,legal_system,default_language,pack)
VALUES
    ('CM','Cameroun','NATIONAL','CM',NULL,'MIXED_CIVIL_COMMON_LAW','fr','cameroun'),
    ('CM.SUPREME','Cour suprême du Cameroun','COURT','CM','CM','MIXED_CIVIL_COMMON_LAW','fr','cameroun'),
    ('CM.ADMIN','Juridictions administratives du Cameroun','COURT','CM','CM','CIVIL_LAW','fr','cameroun')
ON CONFLICT (code) DO NOTHING;

INSERT INTO legal_sources
    (code,name,jurisdiction_code,source_type,base_url,access_mode,license_review_required)
VALUES
    ('CM.PRC.ACTES','Présidence de la République du Cameroun — Actes','CM',
     'LEGISLATION','https://www.prc.cm/fr/actualites/actes','OFFICIAL_HTML_PDF',TRUE),
    ('CM.MINJUSTICE','Ministère de la Justice du Cameroun','CM',
     'LEGISLATION_AND_JUDICIAL_INFORMATION','https://minjustice.gov.cm','OFFICIAL_DATABASE',TRUE),
    ('CM.MINJUSTICE.CASELAW','MINJUSTICE — Décisions de justice','CM.SUPREME',
     'CASE_LAW','https://www.minjustice.gov.cm/index.php/fr/e-justice/decisions-de-justice','OFFICIAL_DATABASE',TRUE),
    ('CM.JURICAF','JURICAF — jurisprudence camerounaise','CM.SUPREME',
     'CASE_LAW','https://juricaf.org','INSTITUTIONAL_AGGREGATOR',TRUE),
    ('CM.NATLEX','OIT NATLEX — législation camerounaise','CM',
     'LEGISLATION','https://natlex.ilo.org','INSTITUTIONAL_DATABASE',TRUE)
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name,base_url=EXCLUDED.base_url,
    access_mode=EXCLUDED.access_mode,enabled=TRUE;

CREATE TABLE IF NOT EXISTS legal_document_relations (
    relation_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_document_id UUID NOT NULL REFERENCES legal_corpus(id) ON DELETE CASCADE,
    target_document_id UUID NOT NULL REFERENCES legal_corpus(id) ON DELETE CASCADE,
    relation_type      VARCHAR(40) NOT NULL,
    provision_ref      VARCHAR(200),
    confidence_score   INTEGER NOT NULL DEFAULT 100,
    evidence           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_document_id,target_document_id,relation_type,provision_ref)
);

CREATE TABLE IF NOT EXISTS legal_provisions (
    provision_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id        UUID NOT NULL REFERENCES legal_corpus(id) ON DELETE CASCADE,
    provision_number   VARCHAR(100) NOT NULL,
    heading            TEXT,
    content            TEXT NOT NULL,
    valid_from         DATE,
    valid_until        DATE,
    status             VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    previous_version_id UUID REFERENCES legal_provisions(provision_id),
    source_url         TEXT,
    verification_status VARCHAR(30) NOT NULL DEFAULT 'TO_VERIFY',
    content_checksum   CHAR(64),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id,provision_number,valid_from)
);

CREATE INDEX IF NOT EXISTS idx_lc_cameroon_date
    ON legal_corpus (country_code,COALESCE(publication_date,date_decision),type);
CREATE INDEX IF NOT EXISTS idx_legal_relations_source ON legal_document_relations(source_document_id);
CREATE INDEX IF NOT EXISTS idx_legal_relations_target ON legal_document_relations(target_document_id);
CREATE INDEX IF NOT EXISTS idx_legal_provisions_lookup ON legal_provisions(document_id,provision_number);
