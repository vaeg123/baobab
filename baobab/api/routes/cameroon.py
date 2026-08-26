"""Espace premium et dynamique du droit camerounais."""

from datetime import date

from fastapi import APIRouter, Header, Query

from baobab.api.routes.accounts import require_workspace_service
from baobab.api.routes.legal import _conn

router = APIRouter(tags=["droit-camerounais"])


async def _require_cameroon(x_user_token: str | None) -> dict:
    return await require_workspace_service(x_user_token, "legal_cm")


@router.get("/legal-cm/overview")
async def cameroon_overview(x_user_token: str | None = Header(default=None)):
    await _require_cameroon(x_user_token)
    conn = await _conn()
    try:
        stats = await conn.fetchrow(
            """SELECT COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE source_tier='OFFICIAL') AS official,
                      COUNT(*) FILTER (WHERE type ILIKE ANY(ARRAY['%loi%','%decret%','%ordonnance%','%arrete%','%code%'])) AS legislation,
                      COUNT(*) FILTER (WHERE type ILIKE ANY(ARRAY['%arret%','%decision%','%jugement%'])) AS case_law,
                      MAX(COALESCE(publication_date,date_decision)) AS latest_legal_date,
                      MAX(detected_at) AS latest_detection
               FROM legal_corpus WHERE country_code='CM'"""
        )
        by_type = await conn.fetch(
            """SELECT type,COUNT(*) AS count FROM legal_corpus WHERE country_code='CM'
               GROUP BY type ORDER BY count DESC,type LIMIT 20"""
        )
        sources = await conn.fetch(
            """SELECT s.code,s.name,s.source_type,s.base_url,s.access_mode,s.enabled,
                      s.last_successful_sync_at,COUNT(c.id) AS document_count
               FROM legal_sources s LEFT JOIN legal_corpus c ON c.source_code=s.code
               WHERE s.jurisdiction_code LIKE 'CM%'
               GROUP BY s.code ORDER BY CASE WHEN s.access_mode LIKE 'OFFICIAL%' THEN 0 ELSE 1 END,s.name"""
        )
        return {
            "country": {"code": "CM", "name": "Cameroun", "legal_system": "Droit mixte"},
            "coverage": dict(stats),
            "by_type": [dict(row) for row in by_type],
            "sources": [dict(row) for row in sources],
            "principles": [
                "Le document original demeure la source.",
                "La doctrine est séparée des normes et de la jurisprudence.",
                "Toute évolution doit être reliée à son texte antérieur.",
                "Une analyse sans source vérifiable est signalée comme non étayée.",
            ],
        }
    finally:
        await conn.close()


@router.get("/legal-cm/timeline")
async def cameroon_timeline(
    query: str | None = Query(default=None, max_length=250),
    document_type: str | None = Query(default=None, max_length=60),
    from_year: int | None = Query(default=None, ge=1960, le=2100),
    to_year: int | None = Query(default=None, ge=1960, le=2100),
    limit: int = Query(default=60, ge=1, le=200),
    x_user_token: str | None = Header(default=None),
):
    await _require_cameroon(x_user_token)
    conditions = ["country_code='CM'", "COALESCE(publication_date,date_decision) IS NOT NULL"]
    params: list = []
    if query:
        params.append(f"%{query}%")
        conditions.append(f"(titre ILIKE ${len(params)} OR ref ILIKE ${len(params)} OR resume ILIKE ${len(params)})")
    if document_type:
        params.append(document_type)
        conditions.append(f"type=${len(params)}")
    if from_year:
        params.append(date(from_year, 1, 1))
        conditions.append(f"COALESCE(publication_date,date_decision)>=${len(params)}")
    if to_year:
        params.append(date(to_year, 12, 31))
        conditions.append(f"COALESCE(publication_date,date_decision)<=${len(params)}")
    params.append(limit)
    conn = await _conn()
    try:
        rows = await conn.fetch(
            f"""SELECT id,ref,type,titre,juridiction,COALESCE(publication_date,date_decision) AS legal_date,
                       legal_status,source_url,source_code,source_tier,editorial_status,change_type,
                       impact_level,official_citation
                FROM legal_corpus WHERE {' AND '.join(conditions)}
                ORDER BY legal_date DESC,created_at DESC LIMIT ${len(params)}""",
            *params,
        )
        return {"view": "timeline", "results": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await conn.close()


@router.get("/legal-cm/documents/{document_id}/evolution")
async def document_evolution(document_id: str, x_user_token: str | None = Header(default=None)):
    await _require_cameroon(x_user_token)
    conn = await _conn()
    try:
        document = await conn.fetchrow(
            "SELECT * FROM legal_corpus WHERE id=$1::uuid AND country_code='CM'", document_id
        )
        if not document:
            return {"document": None, "versions": [], "relations": []}
        provisions = await conn.fetch(
            """SELECT provision_id,provision_number,heading,content,valid_from,valid_until,
                      status,previous_version_id,source_url,verification_status
               FROM legal_provisions WHERE document_id=$1::uuid
               ORDER BY provision_number,valid_from NULLS FIRST""", document_id,
        )
        relations = await conn.fetch(
            """SELECT r.relation_type,r.provision_ref,r.confidence_score,r.evidence,
                      c.id,c.ref,c.titre,c.type,COALESCE(c.publication_date,c.date_decision) AS legal_date,
                      c.source_url,c.source_tier
               FROM legal_document_relations r JOIN legal_corpus c
                 ON c.id=CASE WHEN r.source_document_id=$1::uuid THEN r.target_document_id ELSE r.source_document_id END
               WHERE r.source_document_id=$1::uuid OR r.target_document_id=$1::uuid
               ORDER BY legal_date""", document_id,
        )
        return {"document": dict(document), "versions": [dict(row) for row in provisions],
                "relations": [dict(row) for row in relations]}
    finally:
        await conn.close()
