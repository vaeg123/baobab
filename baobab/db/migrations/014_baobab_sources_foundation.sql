-- BAOBAB 0.5 — fondation documentaire contractuelle et traçable.
-- Cette migration coexiste avec legal_corpus pendant la transition.

ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS institution_name VARCHAR(250);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS authority_type VARCHAR(50) NOT NULL DEFAULT 'UNCLASSIFIED';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS acquisition_channel VARCHAR(50) NOT NULL DEFAULT 'LEGACY_IMPORT';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS agreement_reference VARCHAR(250);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS agreement_status VARCHAR(40) NOT NULL DEFAULT 'TO_REVIEW';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS agreement_review_due_at DATE;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS display_rights VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS indexing_rights VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS analysis_rights VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN';
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS expected_frequency VARCHAR(40);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS technical_format VARCHAR(80);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS contact_email VARCHAR(250);
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS coverage_scope JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS last_audit_at TIMESTAMPTZ;
ALTER TABLE legal_sources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE legal_sources SET
    institution_name='Organisation pour l''Harmonisation en Afrique du Droit des Affaires',
    authority_type=CASE WHEN code='OHADA.BIBLIO' THEN 'REGIONAL_LEGAL_LIBRARY' ELSE authority_type END,
    acquisition_channel=CASE WHEN code='OHADA.BIBLIO' THEN 'LEGACY_PUBLIC_COLLECTION' ELSE acquisition_channel END,
    technical_format=CASE WHEN code='OHADA.BIBLIO' THEN 'HTML_NOTICE_AND_PDF' ELSE technical_format END,
    expected_frequency=COALESCE(expected_frequency,'IRREGULAR'),updated_at=NOW()
WHERE code IN ('OHADA.BIBLIO','OHADA.OFFICIAL','OHADA.CCJA');

UPDATE legal_sources SET
    institution_name='Conférence Interafricaine des Marchés d''Assurances',
    authority_type='REGIONAL_REGULATOR',acquisition_channel='LEGACY_PUBLIC_COLLECTION',
    technical_format='HTML_AND_PDF',expected_frequency=COALESCE(expected_frequency,'IRREGULAR'),updated_at=NOW()
WHERE code='CIMA.OFFICIAL';

UPDATE legal_sources SET authority_type='INSTITUTIONAL_AGGREGATOR',
    acquisition_channel='LEGACY_AGGREGATOR_IMPORT',updated_at=NOW()
WHERE code IN ('AGG.JURICAF','CM.JURICAF.SEARCH','PUB.OHADALEGIS');

CREATE TABLE IF NOT EXISTS legal_documents (
    document_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legacy_corpus_id        UUID UNIQUE REFERENCES legal_corpus(id) ON DELETE SET NULL,
    source_code             VARCHAR(60) REFERENCES legal_sources(code),
    jurisdiction_code       VARCHAR(40) REFERENCES legal_jurisdictions(code),
    official_identifier     VARCHAR(250),
    official_citation       TEXT,
    document_type           VARCHAR(60) NOT NULL,
    title                   TEXT NOT NULL,
    issuing_institution     VARCHAR(250),
    country_code            CHAR(2),
    language_code           VARCHAR(10) NOT NULL DEFAULT 'fr',
    adoption_date           DATE,
    publication_date        DATE,
    effective_from          DATE,
    effective_to            DATE,
    legal_status            VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    authority_level         VARCHAR(40) NOT NULL DEFAULT 'UNCLASSIFIED',
    editorial_status        VARCHAR(40) NOT NULL DEFAULT 'TO_REVIEW',
    validation_level        VARCHAR(40) NOT NULL DEFAULT 'UNVERIFIED',
    source_url              TEXT,
    original_file_uri       TEXT,
    original_mime_type      VARCHAR(120),
    original_sha256         CHAR(64),
    normalized_text         TEXT,
    normalized_sha256       CHAR(64),
    license_name            VARCHAR(200),
    rights_snapshot         JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_received_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at        TIMESTAMPTZ,
    published_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legal_documents_country_check CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$'),
    CONSTRAINT legal_documents_original_hash_check CHECK (original_sha256 IS NULL OR original_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT legal_documents_normalized_hash_check CHECK (normalized_sha256 IS NULL OR normalized_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_documents_official_identity
    ON legal_documents(source_code, official_identifier)
    WHERE source_code IS NOT NULL AND official_identifier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_legal_documents_source ON legal_documents(source_code, editorial_status);
CREATE INDEX IF NOT EXISTS idx_legal_documents_temporal ON legal_documents(jurisdiction_code,effective_from,effective_to);
CREATE INDEX IF NOT EXISTS idx_legal_documents_validation ON legal_documents(validation_level,last_verified_at);

CREATE TABLE IF NOT EXISTS legal_document_versions (
    version_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id             UUID NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    version_number          INTEGER NOT NULL,
    version_label           VARCHAR(150),
    valid_from              DATE,
    valid_until             DATE,
    legal_status            VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    original_file_uri       TEXT,
    original_sha256         CHAR(64),
    normalized_text         TEXT,
    normalized_sha256       CHAR(64),
    change_summary          TEXT,
    supersedes_version_id   UUID REFERENCES legal_document_versions(version_id),
    provenance              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id,version_number),
    CONSTRAINT legal_document_versions_original_hash_check CHECK (original_sha256 IS NULL OR original_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT legal_document_versions_normalized_hash_check CHECK (normalized_sha256 IS NULL OR normalized_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE IF NOT EXISTS legal_source_acquisitions (
    acquisition_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_code             VARCHAR(60) REFERENCES legal_sources(code),
    document_id             UUID REFERENCES legal_documents(document_id) ON DELETE SET NULL,
    external_batch_id       VARCHAR(250),
    external_document_id    VARCHAR(250),
    channel                 VARCHAR(50) NOT NULL,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_by             VARCHAR(250) NOT NULL,
    original_filename       TEXT,
    original_uri            TEXT,
    original_sha256         CHAR(64),
    signature_status        VARCHAR(40) NOT NULL DEFAULT 'NOT_PROVIDED',
    integrity_status        VARCHAR(40) NOT NULL DEFAULT 'TO_VERIFY',
    rights_status           VARCHAR(40) NOT NULL DEFAULT 'TO_REVIEW',
    processing_status       VARCHAR(40) NOT NULL DEFAULT 'RECEIVED',
    transformations         JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_report            JSONB NOT NULL DEFAULT '{}'::jsonb,
    acknowledged_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legal_source_acquisitions_hash_check CHECK (original_sha256 IS NULL OR original_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_source_acquisitions_batch ON legal_source_acquisitions(source_code,external_batch_id);
CREATE INDEX IF NOT EXISTS idx_source_acquisitions_status ON legal_source_acquisitions(processing_status,rights_status,received_at DESC);

CREATE TABLE IF NOT EXISTS legal_editorial_reviews (
    review_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id             UUID NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    review_type             VARCHAR(50) NOT NULL,
    decision                VARCHAR(40) NOT NULL,
    reviewer_identity       VARCHAR(250) NOT NULL,
    reviewer_role           VARCHAR(80) NOT NULL,
    notes                   TEXT,
    evidence                JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_editorial_reviews_document ON legal_editorial_reviews(document_id,reviewed_at DESC);

CREATE TABLE IF NOT EXISTS legal_knowledge_relations (
    relation_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_document_id      UUID NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    target_document_id      UUID NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    relation_type           VARCHAR(40) NOT NULL,
    source_provision_ref    VARCHAR(150),
    target_provision_ref    VARCHAR(150),
    valid_from              DATE,
    valid_until             DATE,
    confidence_score        INTEGER NOT NULL DEFAULT 0,
    qualification_status    VARCHAR(40) NOT NULL DEFAULT 'MACHINE_SUGGESTED',
    evidence                JSONB NOT NULL DEFAULT '{}'::jsonb,
    validated_by            VARCHAR(250),
    validated_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legal_knowledge_relations_confidence CHECK (confidence_score BETWEEN 0 AND 100),
    CONSTRAINT legal_knowledge_relations_distinct CHECK (source_document_id <> target_document_id),
    UNIQUE(source_document_id,target_document_id,relation_type,source_provision_ref,target_provision_ref)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_relations_source ON legal_knowledge_relations(source_document_id,relation_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_relations_target ON legal_knowledge_relations(target_document_id,relation_type);

CREATE TABLE IF NOT EXISTS legal_corpus_audit_runs (
    audit_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scope                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                  VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    documents_scanned       INTEGER NOT NULL DEFAULT 0,
    documents_usable        INTEGER NOT NULL DEFAULT 0,
    documents_incomplete    INTEGER NOT NULL DEFAULT 0,
    documents_rights_review INTEGER NOT NULL DEFAULT 0,
    duplicates_suspected    INTEGER NOT NULL DEFAULT 0,
    report                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ
);

COMMENT ON TABLE legal_documents IS 'Modèle documentaire canonique Baobab; legal_corpus reste la projection de compatibilité pendant la migration.';
COMMENT ON TABLE legal_source_acquisitions IS 'Journal immuable de réception et de transformation des documents juridiques.';
COMMENT ON TABLE legal_knowledge_relations IS 'Relations juridiques qualifiées; toute relation forte doit conserver sa preuve et sa validation.';
