"""Veille juridique persistante alimentée par le corpus BAOBAB."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from baobab.api.routes.accounts import require_workspace_service
from baobab.api.routes.legal import _conn

router = APIRouter(tags=["veille-juridique"])

PACK_CORPORA = {
    "france": {"fr", "france"},
    "europe": {"eu", "cedh", "echr"},
    "ohada": {"ohada", "ccja"},
    "cima": {"cima", "crca"},
    "bceao_uemoa": {"bceao", "uemoa"},
    "international": {"international", "icj", "icc"},
}


class WatchCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    query: str | None = Field(default=None, max_length=300)
    corpus: str = Field(default="all", min_length=2, max_length=40)
    country_code: str | None = Field(default=None, min_length=2, max_length=8)
    jurisdiction_code: str | None = Field(default=None, min_length=2, max_length=40)
    email_enabled: bool = False


async def _ensure_watch_table(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_watch_subscriptions (
            watch_id VARCHAR(40) PRIMARY KEY,
            workspace_id VARCHAR(40) NOT NULL,
            name VARCHAR(120) NOT NULL,
            query TEXT,
            corpus VARCHAR(40) NOT NULL DEFAULT 'all',
            country_code VARCHAR(8),
            jurisdiction_code VARCHAR(40),
            email_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_watch_workspace ON legal_watch_subscriptions (workspace_id, active)"
    )


def _allowed_corpora(workspace: dict) -> set[str] | None:
    services = set((workspace.get("plan_details") or {}).get("services") or [])
    services.update(workspace.get("enabled_services") or [])
    if "all_verticals" in services:
        return None

    packs = workspace.get("legal_packs")
    if packs is None:
        from baobab.api.routes.accounts import _workspace_legal_packs

        packs = _workspace_legal_packs(workspace)
    allowed: set[str] = set()
    for pack in packs:
        allowed.update(PACK_CORPORA.get(pack, set()))
    return allowed


def _validate_requested_corpus(workspace: dict, corpus: str) -> None:
    if corpus == "all":
        return
    allowed = _allowed_corpora(workspace)
    if allowed is not None and corpus.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce corpus n'est pas inclus dans vos packs juridiques.",
        )


@router.get("/legal/watch/feed")
async def watch_feed(
    corpus: str = Query("all", max_length=40),
    query: str | None = Query(None, max_length=300),
    limit: int = Query(30, ge=1, le=100),
    x_user_token: str | None = Header(default=None),
):
    workspace = await require_workspace_service(x_user_token, "alerts")
    corpus = corpus.lower()
    _validate_requested_corpus(workspace, corpus)
    allowed = _allowed_corpora(workspace)

    conditions = ["1=1"]
    params: list = []
    position = 1
    if corpus != "all":
        conditions.append(f"LOWER(corpus) = ${position}")
        params.append(corpus)
        position += 1
    elif allowed is not None:
        if not allowed:
            return {"generated_at": datetime.now(UTC).isoformat(), "results": [], "total": 0}
        conditions.append(f"LOWER(corpus) = ANY(${position}::text[])")
        params.append(sorted(allowed))
        position += 1
    if query:
        conditions.append(
            f"(titre ILIKE ${position} OR resume ILIKE ${position} OR domaine ILIKE ${position})"
        )
        params.append(f"%{query}%")
        position += 1

    params.append(limit)
    conn = await _conn()
    try:
        rows = await conn.fetch(
            f"""
            SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                   publication_date, created_at, pays, domaine, resume,
                   source_url, source_code, country_code, jurisdiction_code,
                   official_citation, legal_status
            FROM legal_corpus
            WHERE {' AND '.join(conditions)}
            ORDER BY COALESCE(publication_date, date_decision, created_at::date) DESC,
                     created_at DESC
            LIMIT ${position}
            """,
            *params,
        )
    finally:
        await conn.close()

    results = [
        {
            "id": str(row["id"]),
            "ref": row["ref"],
            "type": row["type"],
            "corpus": row["corpus"],
            "juridiction": row["juridiction"],
            "titre": row["titre"],
            "date": str(row["publication_date"] or row["date_decision"] or row["created_at"].date()),
            "pays": row["pays"],
            "domaine": row["domaine"],
            "resume": row["resume"],
            "source_url": row["source_url"],
            "source_code": row["source_code"],
            "country_code": row["country_code"],
            "jurisdiction_code": row["jurisdiction_code"],
            "official_citation": row["official_citation"],
            "legal_status": row["legal_status"],
        }
        for row in rows
    ]
    return {"generated_at": datetime.now(UTC).isoformat(), "results": results, "total": len(results)}


@router.get("/legal/watch/subscriptions")
async def list_watches(x_user_token: str | None = Header(default=None)):
    workspace = await require_workspace_service(x_user_token, "alerts")
    conn = await _conn()
    try:
        await _ensure_watch_table(conn)
        rows = await conn.fetch(
            "SELECT * FROM legal_watch_subscriptions WHERE workspace_id = $1 AND active = TRUE ORDER BY created_at DESC",
            workspace["workspace_id"],
        )
        return {"subscriptions": [dict(row) for row in rows]}
    finally:
        await conn.close()


@router.post("/legal/watch/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_watch(request: WatchCreate, x_user_token: str | None = Header(default=None)):
    workspace = await require_workspace_service(x_user_token, "alerts")
    corpus = request.corpus.lower()
    _validate_requested_corpus(workspace, corpus)
    watch_id = f"watch_{uuid4().hex[:16]}"
    conn = await _conn()
    try:
        await _ensure_watch_table(conn)
        row = await conn.fetchrow(
            """
            INSERT INTO legal_watch_subscriptions
                (watch_id, workspace_id, name, query, corpus, country_code,
                 jurisdiction_code, email_enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            watch_id,
            workspace["workspace_id"],
            request.name,
            request.query,
            corpus,
            request.country_code.upper() if request.country_code else None,
            request.jurisdiction_code.upper() if request.jurisdiction_code else None,
            request.email_enabled,
        )
        return dict(row)
    finally:
        await conn.close()


@router.delete("/legal/watch/subscriptions/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watch(watch_id: str, x_user_token: str | None = Header(default=None)):
    workspace = await require_workspace_service(x_user_token, "alerts")
    conn = await _conn()
    try:
        await _ensure_watch_table(conn)
        result = await conn.execute(
            "UPDATE legal_watch_subscriptions SET active = FALSE, updated_at = NOW() WHERE watch_id = $1 AND workspace_id = $2 AND active = TRUE",
            watch_id,
            workspace["workspace_id"],
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Surveillance introuvable.")
    finally:
        await conn.close()
