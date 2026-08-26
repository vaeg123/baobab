"""Veille juridique sourcée et qualifiée, alimentée par le corpus BAOBAB."""

from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from baobab.api.routes.accounts import require_workspace_service
from baobab.api.routes.legal import _conn
from baobab.auth import constant_time_equals
from baobab.config import settings

router = APIRouter(tags=["veille-juridique"])

PACK_CORPORA = {
    "france": {"fr", "france"},
    "europe": {"eu", "cedh", "echr"},
    "ohada": {"ohada", "ccja"},
    "cima": {"cima", "crca"},
    "bceao_uemoa": {"bceao", "uemoa"},
    "international": {"international", "icj", "icc"},
}

CORPUS_FILTERS = {
    "france": {"fr", "france"},
    "europe": {"eu", "cedh", "echr"},
    "ohada": {"ohada", "ccja"},
    "cima": {"cima", "crca"},
    "bceao": {"bceao", "uemoa"},
    "bceao_uemoa": {"bceao", "uemoa"},
    "international": {"international", "icj", "icc"},
}

# Registre éditorial minimal. Une URL n'est qualifiée d'officielle que si son
# hôte appartient explicitement à ce registre. Le classement est exposé dans
# l'API pour que l'interface n'assimile jamais agrégateur et autorité émettrice.
SOURCE_REGISTRY = (
    {"host": "biblio.ohada.org", "code": "OHADA.BIBLIO", "name": "Bibliothèque OHADA", "tier": "OFFICIAL"},
    {"host": "ohada.org", "code": "OHADA.OFFICIAL", "name": "OHADA", "tier": "OFFICIAL"},
    {"host": "cima-afrique.org", "code": "CIMA.OFFICIAL", "name": "CIMA", "tier": "OFFICIAL"},
    {"host": "cima.int", "code": "CIMA.OFFICIAL", "name": "CIMA", "tier": "OFFICIAL"},
    {"host": "bceao.int", "code": "BCEAO.OFFICIAL", "name": "BCEAO", "tier": "OFFICIAL"},
    {"host": "uemoa.int", "code": "UEMOA.OFFICIAL", "name": "UEMOA", "tier": "OFFICIAL"},
    {"host": "legifrance.gouv.fr", "code": "FR.LEGIFRANCE", "name": "Légifrance", "tier": "OFFICIAL"},
    {"host": "courdecassation.fr", "code": "FR.JUDILIBRE", "name": "Cour de cassation", "tier": "OFFICIAL"},
    {"host": "conseil-etat.fr", "code": "FR.CE", "name": "Conseil d'État", "tier": "OFFICIAL"},
    {"host": "conseil-constitutionnel.fr", "code": "FR.CC", "name": "Conseil constitutionnel", "tier": "OFFICIAL"},
    {"host": "eur-lex.europa.eu", "code": "EU.EURLEX", "name": "EUR-Lex", "tier": "OFFICIAL"},
    {"host": "curia.europa.eu", "code": "EU.CURIA", "name": "CURIA", "tier": "OFFICIAL"},
    {"host": "echr.coe.int", "code": "ECHR.OFFICIAL", "name": "Cour européenne des droits de l'homme", "tier": "OFFICIAL"},
    {"host": "juricaf.org", "code": "AGG.JURICAF", "name": "JURICAF", "tier": "INSTITUTIONAL_AGGREGATOR"},
    {"host": "ohadalegis.com", "code": "PUB.OHADALEGIS", "name": "OHADA Legis", "tier": "SECONDARY"},
)

SOURCE_TIER_LABELS = {
    "OFFICIAL": "Source officielle",
    "INSTITUTIONAL_AGGREGATOR": "Agrégateur institutionnel",
    "SECONDARY": "Source secondaire",
    "UNVERIFIED": "Source non qualifiée",
}


def classify_source(source_url: str | None, source_code: str | None = None) -> dict:
    """Retourne une qualification explicite et déterministe de provenance."""
    try:
        host = (urlsplit(source_url or "").hostname or "").lower().removeprefix("www.")
    except ValueError:
        host = ""
    for source in SOURCE_REGISTRY:
        registered_host = source["host"]
        if host == registered_host or host.endswith(f".{registered_host}"):
            tier = source["tier"]
            return {
                "code": source_code or source["code"],
                "name": source["name"],
                "host": host,
                "tier": tier,
                "tier_label": SOURCE_TIER_LABELS[tier],
                "verified": tier == "OFFICIAL",
            }
    return {
        "code": source_code,
        "name": host or "Source inconnue",
        "host": host or None,
        "tier": "UNVERIFIED",
        "tier_label": SOURCE_TIER_LABELS["UNVERIFIED"],
        "verified": False,
    }


def _source_scope_condition(scope: str) -> str:
    tiers = {"official": {"OFFICIAL"}, "trusted": {"OFFICIAL", "INSTITUTIONAL_AGGREGATOR"}}
    selected_tiers = tiers.get(scope)
    if selected_tiers is None:
        return "1=1"
    hosts = [source["host"] for source in SOURCE_REGISTRY if source["tier"] in selected_tiers]
    clauses = []
    for host in hosts:
        escaped_host = host.replace("'", "''")
        clauses.append(
            f"(source_url ILIKE '%://{escaped_host}/%' OR source_url ILIKE '%://%.{escaped_host}/%')"
        )
    return f"({' OR '.join(clauses)})"


def _document_qualification(row, source: dict) -> dict:
    date_kind = "integration"
    event_label = "Document juridique référencé"
    legal_date = row["publication_date"] or row["date_decision"]
    date_precision = "DAY"
    if row["publication_date"]:
        date_kind = "publication"
        event_label = "Publication juridique"
    elif row["date_decision"]:
        date_kind = "decision"
        event_label = "Décision de justice"
    if legal_date and legal_date.month == 1 and legal_date.day == 1 and not row["publication_date"]:
        date_precision = "YEAR"
    return {
        "event_label": event_label,
        "date_kind": date_kind,
        "date_precision": date_precision,
        "display_date": str(legal_date.year) if date_precision == "YEAR" else str(legal_date),
        "source_verified": source["verified"],
        "legal_status_qualified": row["legal_status"] not in (None, "", "UNKNOWN"),
        "impact_level": row["impact_level"],
        "impact_label": {
            "LOW": "Impact faible",
            "MEDIUM": "Impact modéré",
            "HIGH": "Impact élevé",
            "CRITICAL": "Impact critique",
        }.get(row["impact_level"], "Impact à qualifier"),
        "impact_summary": row["impact_summary"],
        "change_type": row["change_type"],
        "editorial_status": row["editorial_status"],
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
    source_scope: str = Query("official", pattern="^(official|trusted|all)$"),
    since_days: int | None = Query(None, ge=1, le=3650),
    limit: int = Query(30, ge=1, le=100),
    x_user_token: str | None = Header(default=None),
):
    workspace = await require_workspace_service(x_user_token, "alerts")
    corpus = corpus.lower()
    _validate_requested_corpus(workspace, corpus)
    allowed = _allowed_corpora(workspace)

    # La veille est publique pour les utilisateurs du service : elle ne doit
    # contenir que des publications dont la provenance peut être vérifiée.
    # Les imports locaux mis en quarantaine restent dans le corpus pour audit,
    # mais ne sont jamais exposés par ce flux.
    conditions = [
        "COALESCE(source_url, '') ~* '^https?://'",
        "COALESCE(publication_date, date_decision) IS NOT NULL",
        "COALESCE(metadata->>'watch_quarantined', 'false') <> 'true'",
        _source_scope_condition(source_scope),
    ]
    params: list = []
    position = 1
    if corpus != "all":
        requested_corpora = sorted(CORPUS_FILTERS.get(corpus, {corpus}))
        conditions.append(f"LOWER(corpus) = ANY(${position}::text[])")
        params.append(requested_corpora)
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
    if since_days:
        conditions.append(
            f"COALESCE(publication_date, date_decision) >= "
            f"CURRENT_DATE - ${position}::int"
        )
        params.append(since_days)
        position += 1

    params.append(limit)
    conn = await _conn()
    try:
        rows = await conn.fetch(
            f"""
            SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                   publication_date, created_at, pays, domaine, resume,
                   source_url, source_code, country_code, jurisdiction_code,
                   official_identifier, official_citation, legal_status,
                   effective_from, effective_to, source_license,
                   source_tier, source_verified_at, editorial_status,
                   impact_level, impact_summary, change_type, detected_at,
                   COUNT(*) OVER() AS filtered_total
            FROM legal_corpus
            WHERE {' AND '.join(conditions)}
            ORDER BY COALESCE(publication_date, date_decision) DESC,
                     created_at DESC
            LIMIT ${position}
            """,
            *params,
        )
    finally:
        await conn.close()

    results = []
    for row in rows:
        source = classify_source(row["source_url"], row["source_code"])
        results.append({
            "id": str(row["id"]),
            "ref": row["ref"],
            "type": row["type"],
            "corpus": row["corpus"],
            "juridiction": row["juridiction"],
            "titre": row["titre"],
            "date": str(row["publication_date"] or row["date_decision"]),
            "pays": row["pays"],
            "domaine": row["domaine"],
            "resume": row["resume"],
            "source_url": row["source_url"],
            "source_code": row["source_code"],
            "country_code": row["country_code"],
            "jurisdiction_code": row["jurisdiction_code"],
            "official_citation": row["official_citation"],
            "legal_status": row["legal_status"],
            "official_identifier": row["official_identifier"],
            "effective_from": str(row["effective_from"]) if row["effective_from"] else None,
            "effective_to": str(row["effective_to"]) if row["effective_to"] else None,
            "source_license": row["source_license"],
            "source": source,
            "qualification": _document_qualification(row, source),
        })
    filtered_total = int(rows[0]["filtered_total"]) if rows else 0
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": results,
        "total": len(results),
        "filtered_total": filtered_total,
        "source_scope": source_scope,
        "methodology": {
            "label": "Veille sourcée BAOBAB",
            "source_policy": "Une source n'est dite officielle que si son domaine figure dans le registre éditorial BAOBAB.",
            "impact_policy": "L'impact reste à qualifier tant qu'aucune analyse éditoriale n'a été validée.",
            "coverage_notice": "Le flux reflète les documents collectés et datés par BAOBAB. Les documents sans date juridique restent consultables dans le corpus mais sont exclus de la veille.",
            "automatic_email_notifications": False,
            "latest_matching_legal_date": results[0]["date"] if results else None,
        },
    }


@router.get("/legal/watch/sources")
async def watch_sources(x_user_token: str | None = Header(default=None)):
    await require_workspace_service(x_user_token, "alerts")
    return {
        "sources": [
            {**source, "tier_label": SOURCE_TIER_LABELS[source["tier"]]}
            for source in SOURCE_REGISTRY
        ],
        "tiers": SOURCE_TIER_LABELS,
    }


@router.get("/legal/watch/engine/run", include_in_schema=False)
async def run_watch_engine(authorization: str | None = Header(default=None)):
    if not settings.cron_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Moteur planifié non configuré.",
        )
    expected = f"Bearer {settings.cron_secret}"
    if not constant_time_equals(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autorisé.")
    from baobab.watch_engine import run_watch_cycle

    return await run_watch_cycle(trigger="vercel_cron")


@router.get("/legal/watch/engine/status")
async def watch_engine_status(x_user_token: str | None = Header(default=None)):
    workspace = await require_workspace_service(x_user_token, "alerts")
    conn = await _conn()
    try:
        latest_run = await conn.fetchrow(
            """SELECT run_id,status,trigger,started_at,finished_at,sources_checked,
                      sources_succeeded,sources_failed,artifacts_seen,events_created,
                      matches_created,error_summary
               FROM legal_watch_runs ORDER BY started_at DESC LIMIT 1"""
        )
        sources = await conn.fetch(
            """SELECT source_code,discovery_url,last_checked_at,last_changed_at,
                      last_status,last_error,artifact_count
               FROM legal_source_snapshots ORDER BY source_code"""
        )
        pending_matches = await conn.fetchval(
            """SELECT COUNT(*) FROM legal_watch_matches
               WHERE workspace_id=$1 AND delivery_status IN ('DISABLED','PENDING')""",
            workspace["workspace_id"],
        )
        return {
            "latest_run": dict(latest_run) if latest_run else None,
            "sources": [dict(row) for row in sources],
            "pending_matches": int(pending_matches or 0),
            "schedule": "Tous les jours à 05:15 UTC",
            "email_delivery_enabled": False,
        }
    finally:
        await conn.close()


@router.get("/legal/watch/matches")
async def watch_matches(
    limit: int = Query(30, ge=1, le=100),
    x_user_token: str | None = Header(default=None),
):
    workspace = await require_workspace_service(x_user_token, "alerts")
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """SELECT m.match_id,m.watch_id,m.matched_at,m.delivery_status,
                      e.event_id,e.event_type,e.source_code,e.artifact_url,e.title,
                      e.corpus,e.legal_date,e.review_status,e.discovered_at,
                      s.name AS watch_name
               FROM legal_watch_matches m
               JOIN legal_watch_events e ON e.event_id=m.event_id
               JOIN legal_watch_subscriptions s ON s.watch_id=m.watch_id
               WHERE m.workspace_id=$1
               ORDER BY m.matched_at DESC LIMIT $2""",
            workspace["workspace_id"], limit,
        )
        return {"matches": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await conn.close()


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
