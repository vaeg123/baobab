-- Coffre binaire initial Neon. Les URI restent abstraites pour migration objet ultérieure.

CREATE TABLE IF NOT EXISTS legal_document_rendition_blobs (
    rendition_id UUID PRIMARY KEY REFERENCES legal_document_renditions(rendition_id) ON DELETE CASCADE,
    content BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT rendition_blob_size CHECK (octet_length(content) BETWEEN 1 AND 20971520)
);

COMMENT ON TABLE legal_document_rendition_blobs IS 'Stockage initial plafonné à 20 Mo par rendu; à migrer vers un stockage objet pour les grands volumes.';
