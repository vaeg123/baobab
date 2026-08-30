-- Copies fidèles, OCR et PDF consultables dérivés d'un original immuable.

CREATE TABLE IF NOT EXISTS legal_document_renditions (
    rendition_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id             UUID NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    rendition_type          VARCHAR(40) NOT NULL,
    page_number             INTEGER,
    storage_uri             TEXT NOT NULL,
    mime_type               VARCHAR(120) NOT NULL,
    sha256                  CHAR(64) NOT NULL,
    byte_size               BIGINT NOT NULL,
    extraction_method       VARCHAR(60) NOT NULL,
    ocr_language            VARCHAR(30),
    ocr_confidence          NUMERIC(5,2),
    review_status           VARCHAR(30) NOT NULL DEFAULT 'TO_REVIEW',
    source_rendition_id     UUID REFERENCES legal_document_renditions(rendition_id),
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT rendition_page_positive CHECK (page_number IS NULL OR page_number > 0),
    CONSTRAINT rendition_confidence_range CHECK (ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 100),
    CONSTRAINT rendition_type_allowed CHECK (rendition_type IN (
        'ORIGINAL','PAGE_IMAGE','OCR_TEXT','SEARCHABLE_PDF','THUMBNAIL'
    )),
    CONSTRAINT rendition_review_allowed CHECK (review_status IN (
        'TO_REVIEW','DOCUMENT_VERIFIED','REJECTED'
    )),
    UNIQUE(document_id,rendition_type,page_number,sha256)
);

CREATE INDEX IF NOT EXISTS idx_document_renditions_lookup
    ON legal_document_renditions(document_id,rendition_type,page_number);

COMMENT ON TABLE legal_document_renditions IS 'Représentations dérivées; ORIGINAL demeure immuable et OCR_TEXT ne vaut jamais preuve contre son image source.';
