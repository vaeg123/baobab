"""
Routes API corpus juridique — recherche fulltext + sémantique + analyse.

POST /api/v1/legal/search   — recherche dans le corpus (fulltext + vecteur)
GET  /api/v1/legal/corpus   — liste paginée du corpus
GET  /api/v1/legal/corpus/{id} — détail d'un document
POST /api/v1/legal/analyze  — analyse d'une question juridique (IA)
"""

import json
import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["legal"])

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://baobab:baobab@localhost:5432/baobab")

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


# ─── Modèles ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    corpus: Literal["cima", "ohada", "ci", "all"] = "all"
    type: str | None = None        # decision_crca | arret_ccja | acte_uniforme | loi
    pays: str | None = None
    domaine: str | None = None
    limit: int = 20
    offset: int = 0
    mode: Literal["fulltext", "semantic", "hybrid"] = "fulltext"


class AnalyzeRequest(BaseModel):
    question: str
    corpus: Literal["cima", "ohada", "ci", "all"] = "all"
    context_docs: int = 5          # nombre de docs à récupérer pour le contexte


class DocResult(BaseModel):
    id: str
    ref: str
    titre: str
    type: str
    corpus: str
    juridiction: str | None
    date_decision: str | None
    pays: str | None
    domaine: str | None
    resume: str | None
    sanction: str | None
    source_url: str | None
    score: float | None = None


# ─── Helper DB ────────────────────────────────────────────────────────────────

async def _conn():
    if not HAS_ASYNCPG:
        raise HTTPException(503, "asyncpg non disponible")
    return await asyncpg.connect(DATABASE_URL)


def _row_to_doc(row, score: float | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "ref": row["ref"] or "",
        "titre": row["titre"] or "",
        "type": row["type"],
        "corpus": row["corpus"],
        "juridiction": row["juridiction"],
        "date_decision": str(row["date_decision"]) if row["date_decision"] else None,
        "pays": row["pays"],
        "domaine": row["domaine"],
        "resume": (row["resume"] or "")[:500],
        "sanction": row["sanction"],
        "source_url": row["source_url"],
        "score": score,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/legal/search")
async def search_corpus(req: SearchRequest):
    """Recherche fulltext dans le corpus juridique BAOBAB."""
    conn = await _conn()
    try:
        conditions = ["1=1"]
        params: list = []
        p = 1

        if req.corpus != "all":
            conditions.append(f"corpus = ${p}"); params.append(req.corpus); p += 1
        if req.type:
            conditions.append(f"type = ${p}"); params.append(req.type); p += 1
        if req.pays:
            conditions.append(f"pays ILIKE ${p}"); params.append(f"%{req.pays}%"); p += 1
        if req.domaine:
            conditions.append(f"domaine ILIKE ${p}"); params.append(f"%{req.domaine}%"); p += 1

        where = " AND ".join(conditions)

        if req.mode == "fulltext" or req.mode == "hybrid":
            # Recherche fulltext PostgreSQL
            fts_cond = (
                f"to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'') "
                f"|| ' ' || coalesce(texte_integral,'')) @@ plainto_tsquery('french', ${p})"
            )
            params.append(req.query)
            rank_expr = (
                f"ts_rank(to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'')"
                f" || ' ' || coalesce(texte_integral,'')), plainto_tsquery('french', ${p})) AS rank"
            )
            p += 1

            sql = f"""
                SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                       pays, domaine, resume, sanction, source_url,
                       {rank_expr}
                FROM legal_corpus
                WHERE {where} AND {fts_cond}
                ORDER BY rank DESC
                LIMIT ${p} OFFSET ${p+1}
            """
            params += [req.limit, req.offset]
            rows = await conn.fetch(sql, *params)

        else:
            # Fallback ILIKE si pas de fulltext
            like_cond = f"(titre ILIKE ${p} OR resume ILIKE ${p} OR texte_integral ILIKE ${p})"
            params.append(f"%{req.query}%"); p += 1
            sql = f"""
                SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                       pays, domaine, resume, sanction, source_url,
                       1.0 AS rank
                FROM legal_corpus
                WHERE {where} AND {like_cond}
                ORDER BY date_decision DESC NULLS LAST
                LIMIT ${p} OFFSET ${p+1}
            """
            params += [req.limit, req.offset]
            rows = await conn.fetch(sql, *params)

        results = [_row_to_doc(r, float(r["rank"])) for r in rows]

        # Compte total
        count_sql = f"SELECT COUNT(*) FROM legal_corpus WHERE {where}"
        count_params = params[: p - 3]  # exclure query + limit + offset
        total = await conn.fetchval(count_sql, *count_params)

        return {
            "query": req.query,
            "total": total,
            "limit": req.limit,
            "offset": req.offset,
            "results": results,
        }

    finally:
        await conn.close()


@router.get("/legal/corpus")
async def list_corpus(
    corpus: str | None = Query(None),
    type: str | None = Query(None),
    pays: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    """Liste paginée du corpus juridique."""
    conn = await _conn()
    try:
        conditions = ["1=1"]
        params: list = []
        p = 1

        if corpus:
            conditions.append(f"corpus = ${p}"); params.append(corpus); p += 1
        if type:
            conditions.append(f"type = ${p}"); params.append(type); p += 1
        if pays:
            conditions.append(f"pays ILIKE ${p}"); params.append(f"%{pays}%"); p += 1

        where = " AND ".join(conditions)

        sql = f"""
            SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                   pays, domaine, resume, sanction, source_url
            FROM legal_corpus
            WHERE {where}
            ORDER BY date_decision DESC NULLS LAST
            LIMIT ${p} OFFSET ${p+1}
        """
        params += [limit, offset]
        rows = await conn.fetch(sql, *params)

        total = await conn.fetchval(f"SELECT COUNT(*) FROM legal_corpus WHERE {where}", *params[:-2])

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [_row_to_doc(r) for r in rows],
        }
    finally:
        await conn.close()


@router.get("/legal/corpus/{doc_id}")
async def get_document(doc_id: str):
    """Détail complet d'un document du corpus."""
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM legal_corpus WHERE id = $1",
            doc_id,
        )
        if not row:
            raise HTTPException(404, f"Document {doc_id} introuvable")
        return {
            "id": str(row["id"]),
            "ref": row["ref"],
            "type": row["type"],
            "corpus": row["corpus"],
            "juridiction": row["juridiction"],
            "titre": row["titre"],
            "date_decision": str(row["date_decision"]) if row["date_decision"] else None,
            "parties": json.loads(row["parties"] or "{}"),
            "pays": row["pays"],
            "domaine": row["domaine"],
            "resume": row["resume"],
            "texte_integral": row["texte_integral"],
            "mots_cles": list(row["mots_cles"] or []),
            "source_url": row["source_url"],
            "source_pdf_url": row["source_pdf_url"],
            "sanction": row["sanction"],
            "articles_cites": list(row["articles_cites"] or []),
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": str(row["created_at"]),
        }
    finally:
        await conn.close()


@router.post("/legal/analyze")
async def analyze_question(req: AnalyzeRequest):
    """
    Analyse une question juridique :
    1. Recherche les documents pertinents dans le corpus
    2. Appelle Claude pour une réponse fondée sur le droit CIMA/OHADA/CI
    """
    # Étape 1 : récupérer le contexte documentaire
    search_req = SearchRequest(
        query=req.question,
        corpus=req.corpus,
        limit=req.context_docs,
        mode="fulltext",
    )
    search_result = await search_corpus(search_req)
    docs = search_result.get("results", [])

    context_parts = []
    for d in docs:
        snippet = f"[{d['ref'] or d['titre']}] {d['resume'] or ''}"
        context_parts.append(snippet)
    context = "\n\n".join(context_parts) if context_parts else "Aucun document trouvé dans le corpus."

    # Étape 2 : appel Claude
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": (
                    "Tu es BAOBAB, un assistant juridique spécialisé en droit africain "
                    "(CIMA, OHADA, droit ivoirien). Réponds en français de façon précise et structurée.\n\n"
                    f"QUESTION : {req.question}\n\n"
                    f"CORPUS DISPONIBLE :\n{context}\n\n"
                    "Fournis une analyse juridique rigoureuse en citant les textes pertinents."
                ),
            }],
        )
        analysis = message.content[0].text
    except ImportError:
        analysis = (
            "Module anthropic non disponible. "
            "Installez-le avec : pip install anthropic"
        )
    except Exception as exc:
        analysis = f"Erreur lors de l'analyse IA : {exc}"

    return {
        "question": req.question,
        "corpus": req.corpus,
        "context_docs": docs,
        "analysis": analysis,
    }


@router.get("/legal/stats")
async def corpus_stats():
    """Statistiques du corpus juridique."""
    conn = await _conn()
    try:
        by_type = await conn.fetch(
            "SELECT type, corpus, COUNT(*) as n FROM legal_corpus GROUP BY type, corpus ORDER BY n DESC"
        )
        by_pays = await conn.fetch(
            "SELECT pays, COUNT(*) as n FROM legal_corpus WHERE pays != '' GROUP BY pays ORDER BY n DESC LIMIT 20"
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM legal_corpus")
        return {
            "total": total,
            "by_type": [{"type": r["type"], "corpus": r["corpus"], "count": r["n"]} for r in by_type],
            "by_pays": [{"pays": r["pays"], "count": r["n"]} for r in by_pays],
        }
    finally:
        await conn.close()
