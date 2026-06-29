-- BAOBAB — Initial schema
-- Legal Atoms, Events, Processes, Digital Twins

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE legal_atoms (
    id              TEXT PRIMARY KEY,
    corpus          TEXT NOT NULL,
    territory       TEXT NOT NULL,
    article_ref     TEXT NOT NULL,
    version         TEXT NOT NULL,
    source_text     TEXT NOT NULL,
    effective_date  TIMESTAMPTZ NOT NULL,
    abrogated       BOOLEAN DEFAULT FALSE,
    abrogated_by    TEXT,
    language        TEXT DEFAULT 'fr',
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE legal_entities (
    entity_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    entity_type         TEXT NOT NULL,
    territory           TEXT NOT NULL,
    registration_number TEXT,
    regulated_by        TEXT[],
    compliance_score    NUMERIC(5,3),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE legal_events (
    event_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      TEXT NOT NULL,
    entity_id       TEXT NOT NULL REFERENCES legal_entities(entity_id),
    occurred_at     TIMESTAMPTZ NOT NULL,
    corpus          TEXT NOT NULL,
    territory       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    metadata        JSONB DEFAULT '{}',
    cascade_id      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE legal_processes (
    process_id      TEXT PRIMARY KEY,
    process_type    TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    trigger_event_id UUID NOT NULL,
    steps           JSONB NOT NULL DEFAULT '[]',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE compliance_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id       TEXT NOT NULL,
    process_id      TEXT NOT NULL,
    score           NUMERIC(5,3) NOT NULL,
    status          TEXT NOT NULL,
    overdue_count   INT DEFAULT 0,
    total_steps     INT DEFAULT 0,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON legal_atoms (corpus, territory);
CREATE INDEX ON legal_events (entity_id, status);
CREATE INDEX ON legal_processes (entity_id);
