-- BAOBAB 0.3 — moteur continu de veille juridique.

CREATE TABLE IF NOT EXISTS legal_watch_runs (
    run_id                  VARCHAR(40) PRIMARY KEY,
    trigger                 VARCHAR(30) NOT NULL,
    status                  VARCHAR(30) NOT NULL,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at             TIMESTAMPTZ,
    sources_checked         INTEGER NOT NULL DEFAULT 0,
    sources_succeeded       INTEGER NOT NULL DEFAULT 0,
    sources_failed          INTEGER NOT NULL DEFAULT 0,
    artifacts_seen          INTEGER NOT NULL DEFAULT 0,
    events_created          INTEGER NOT NULL DEFAULT 0,
    matches_created         INTEGER NOT NULL DEFAULT 0,
    error_summary           TEXT,
    details                 JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS legal_source_snapshots (
    source_code             VARCHAR(60) PRIMARY KEY,
    discovery_url           TEXT NOT NULL,
    content_checksum        CHAR(64),
    http_etag               TEXT,
    http_last_modified      TEXT,
    last_checked_at         TIMESTAMPTZ,
    last_changed_at         TIMESTAMPTZ,
    last_status             VARCHAR(30) NOT NULL DEFAULT 'NEVER_CHECKED',
    last_error              TEXT,
    artifact_count          INTEGER NOT NULL DEFAULT 0,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_source_artifacts (
    artifact_id             VARCHAR(40) PRIMARY KEY,
    source_code             VARCHAR(60) NOT NULL,
    artifact_url            TEXT NOT NULL,
    title                   TEXT NOT NULL,
    corpus                  VARCHAR(40) NOT NULL,
    legal_date              DATE,
    date_precision          VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    content_checksum        CHAR(64) NOT NULL,
    state                   VARCHAR(30) NOT NULL,
    linked_corpus_id        UUID REFERENCES legal_corpus(id) ON DELETE SET NULL,
    first_seen_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_changed_at         TIMESTAMPTZ,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_code, artifact_url)
);

CREATE TABLE IF NOT EXISTS legal_watch_events (
    event_id                VARCHAR(40) PRIMARY KEY,
    run_id                  VARCHAR(40) REFERENCES legal_watch_runs(run_id) ON DELETE SET NULL,
    source_code             VARCHAR(60) NOT NULL,
    event_type              VARCHAR(50) NOT NULL,
    artifact_url            TEXT NOT NULL,
    title                   TEXT NOT NULL,
    corpus                  VARCHAR(40) NOT NULL,
    legal_date              DATE,
    content_checksum        CHAR(64) NOT NULL,
    review_status           VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    linked_corpus_id        UUID REFERENCES legal_corpus(id) ON DELETE SET NULL,
    discovered_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at             TIMESTAMPTZ,
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_code, artifact_url, content_checksum)
);

CREATE TABLE IF NOT EXISTS legal_watch_matches (
    match_id                VARCHAR(40) PRIMARY KEY,
    watch_id                VARCHAR(40) NOT NULL REFERENCES legal_watch_subscriptions(watch_id) ON DELETE CASCADE,
    event_id                VARCHAR(40) NOT NULL REFERENCES legal_watch_events(event_id) ON DELETE CASCADE,
    workspace_id            VARCHAR(40) NOT NULL,
    matched_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivery_status         VARCHAR(30) NOT NULL DEFAULT 'DISABLED',
    delivered_at            TIMESTAMPTZ,
    delivery_error          TEXT,
    UNIQUE (watch_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_watch_runs_started ON legal_watch_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_artifacts_seen ON legal_source_artifacts (source_code, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_events_review ON legal_watch_events (review_status, discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_matches_workspace ON legal_watch_matches (workspace_id, matched_at DESC);
