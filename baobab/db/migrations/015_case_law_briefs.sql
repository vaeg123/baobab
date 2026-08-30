-- Fiches jurisprudentielles structurées et contrôlables.
-- Une extraction automatique reste TO_REVIEW jusqu'à validation humaine.

CREATE TABLE IF NOT EXISTS legal_case_briefs (
    brief_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id            UUID NOT NULL UNIQUE REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    facts                   TEXT,
    procedure_history       TEXT,
    claims                  JSONB NOT NULL DEFAULT '[]'::jsonb,
    legal_question          TEXT,
    applied_rules           JSONB NOT NULL DEFAULT '[]'::jsonb,
    holding                 TEXT,
    exact_disposition       TEXT,
    significance            TEXT,
    precedent_status        VARCHAR(40) NOT NULL DEFAULT 'UNDETERMINED',
    past_context            JSONB NOT NULL DEFAULT '[]'::jsonb,
    present_effect          TEXT,
    future_assessment       TEXT,
    future_evidence         JSONB NOT NULL DEFAULT '[]'::jsonb,
    professional_actions    JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations             TEXT,
    evidence_refs           JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_method       VARCHAR(40) NOT NULL DEFAULT 'MANUAL',
    editorial_status        VARCHAR(40) NOT NULL DEFAULT 'TO_REVIEW',
    reviewed_by             VARCHAR(250),
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT case_brief_precedent_status CHECK (precedent_status IN (
        'UNDETERMINED','ISOLATED','RECURRING','PRINCIPLE','CONFIRMED','DIVERGENT','LIMITED','REVERSAL'
    )),
    CONSTRAINT case_brief_editorial_status CHECK (editorial_status IN (
        'TO_REVIEW','IN_REVIEW','VALIDATED','REJECTED'
    ))
);

CREATE INDEX IF NOT EXISTS idx_case_briefs_editorial
    ON legal_case_briefs(editorial_status, precedent_status, updated_at DESC);

-- Amorçage prudent : les anciennes métadonnées sont conservées, mais jamais
-- présentées comme validées par un juriste.
INSERT INTO legal_case_briefs (
    document_id, facts, procedure_history, claims, legal_question, applied_rules,
    holding, exact_disposition, significance, present_effect, professional_actions,
    limitations, evidence_refs, extraction_method, editorial_status
)
SELECT d.document_id,
       NULLIF(c.metadata->>'faits',''),
       NULLIF(COALESCE(c.metadata->>'procedure', c.metadata->>'procédure'),''),
       CASE WHEN jsonb_typeof(c.metadata->'pretentions')='array' THEN c.metadata->'pretentions' ELSE '[]'::jsonb END,
       NULLIF(COALESCE(c.metadata->>'question_droit',c.metadata->>'question_de_droit'),''),
       to_jsonb(COALESCE(c.articles_cites,ARRAY[]::text[])),
       NULLIF(c.resume,''),
       NULLIF(COALESCE(c.metadata->>'dispositif',c.sanction),''),
       NULLIF(COALESCE(c.metadata->>'portee',c.metadata->>'portée'),''),
       NULLIF(c.resume,''),
       '[]'::jsonb,
       'Fiche initiale issue des métadonnées historiques. Vérifier le texte intégral et les décisions liées avant toute conclusion.'::text,
       jsonb_build_array(jsonb_build_object('type','SOURCE_DOCUMENT','document_id',d.document_id)),
       'LEGACY_METADATA', 'TO_REVIEW'
FROM legal_documents d
JOIN legal_corpus c ON c.id=d.legacy_corpus_id
WHERE lower(c.type) ~ '(arret|arrêt|decision|décision|jugement|ordonnance|avis)'
ON CONFLICT (document_id) DO NOTHING;

COMMENT ON TABLE legal_case_briefs IS 'Analyse structurée des décisions; le statut éditorial indique explicitement si un juriste a validé la fiche.';
