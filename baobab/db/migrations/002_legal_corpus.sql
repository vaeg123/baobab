-- BAOBAB — Legal Corpus table
-- Stocke décisions CRCA, arrêts CCJA, actes uniformes OHADA, lois CI

CREATE TABLE IF NOT EXISTS legal_corpus (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ref             VARCHAR(200),
    type            VARCHAR(50)  NOT NULL,   -- decision_crca | arret_ccja | acte_uniforme | loi | decision_tca
    corpus          VARCHAR(50)  NOT NULL,   -- cima | ohada | ci
    juridiction     VARCHAR(200),
    titre           TEXT,
    date_decision   DATE,
    parties         JSONB  DEFAULT '{}',
    pays            VARCHAR(100),
    domaine         VARCHAR(200),
    resume          TEXT,
    texte_integral  TEXT,
    mots_cles       TEXT[]  DEFAULT '{}',
    source_url      TEXT,
    source_pdf_url  TEXT,
    sanction        VARCHAR(200),
    articles_cites  TEXT[]  DEFAULT '{}',
    metadata        JSONB  DEFAULT '{}',
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lc_type    ON legal_corpus (type);
CREATE INDEX IF NOT EXISTS idx_lc_corpus  ON legal_corpus (corpus);
CREATE INDEX IF NOT EXISTS idx_lc_date    ON legal_corpus (date_decision DESC);
CREATE INDEX IF NOT EXISTS idx_lc_pays    ON legal_corpus (pays);
CREATE INDEX IF NOT EXISTS idx_lc_domaine ON legal_corpus (domaine);

-- Recherche full-text sur titre + résumé
CREATE INDEX IF NOT EXISTS idx_lc_fts ON legal_corpus
    USING gin(to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'')));

-- Index vecteur pour recherche sémantique (IVFFlat, 50 listes pour ~5k docs)
CREATE INDEX IF NOT EXISTS idx_lc_emb ON legal_corpus
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
