-- BAOBAB — Submissions table
-- Documents soumis par les utilisateurs, en attente de validation superadmin.

CREATE TABLE IF NOT EXISTS submissions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Soumetteur
    submitter_name   VARCHAR(200),
    submitter_email  VARCHAR(200),

    -- Informations fournies par l'utilisateur
    corpus           VARCHAR(50)  NOT NULL,  -- cima | ohada | ci
    type             VARCHAR(50),            -- arret_ccja | decision_crca | acte_uniforme | loi | autre
    titre_user       TEXT,                   -- titre saisi par l'utilisateur
    date_str         VARCHAR(50),            -- date brute saisie
    notes            TEXT,                   -- commentaires du soumetteur

    -- Texte extrait (depuis PDF uploadé ou collé directement)
    texte_integral   TEXT,

    -- Analyse IA automatique au moment de la soumission
    metadata_ia      JSONB DEFAULT '{}',
    -- Structure attendue : {
    --   titre, ref, date_str, juridiction, parties, pays,
    --   domaine, mots_cles, resume, articles_cites, sanction,
    --   is_legal_document, score_confiance, note_ia
    -- }

    score_confiance  FLOAT,   -- extrait de metadata_ia pour indexation rapide

    -- Workflow de validation
    statut           VARCHAR(20) DEFAULT 'pending',  -- pending | approved | rejected
    reviewed_at      TIMESTAMPTZ,
    review_note      TEXT,

    -- Référence vers legal_corpus après approbation
    corpus_id        UUID REFERENCES legal_corpus(id) ON DELETE SET NULL,

    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sub_statut  ON submissions (statut);
CREATE INDEX IF NOT EXISTS idx_sub_corpus  ON submissions (corpus);
CREATE INDEX IF NOT EXISTS idx_sub_created ON submissions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sub_email   ON submissions (submitter_email);
