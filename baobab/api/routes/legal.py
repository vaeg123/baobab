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

from fastapi import APIRouter, Header, HTTPException, Query
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
        # Snapshot des params filtres uniquement (pour la requête COUNT)
        filter_params = list(params)

        rows = []

        if req.mode == "fulltext" or req.mode == "hybrid":
            fts_cond = (
                f"to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'') "
                f"|| ' ' || coalesce(texte_integral,'')) @@ plainto_tsquery('french', ${p})"
            )
            rank_expr = (
                f"ts_rank(to_tsvector('french', coalesce(titre,'') || ' ' || coalesce(resume,'')"
                f" || ' ' || coalesce(texte_integral,'')), plainto_tsquery('french', ${p})) AS rank"
            )
            fts_params = params + [req.query, req.limit, req.offset]
            fts_p = p + 1  # after query param
            sql = f"""
                SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                       pays, domaine, resume, sanction, source_url,
                       {rank_expr}
                FROM legal_corpus
                WHERE {where} AND {fts_cond}
                ORDER BY rank DESC
                LIMIT ${fts_p} OFFSET ${fts_p+1}
            """
            rows = await conn.fetch(sql, *fts_params)

        # Fallback ILIKE si FTS vide ou mode semantic/ilike
        if not rows:
            keywords = [w for w in req.query.split() if len(w) > 3][:6]
            if not keywords:
                keywords = [req.query]
            like_parts = []
            score_parts = []
            ilike_params = list(params)
            ip = p
            for kw in keywords:
                like_parts.append(
                    f"(titre ILIKE ${ip} OR resume ILIKE ${ip} OR texte_integral ILIKE ${ip})"
                )
                # Score : titre/résumé matchent = 3pts, texte_intégral = 1pt
                score_parts.append(
                    f"(CASE WHEN titre ILIKE ${ip} OR resume ILIKE ${ip} THEN 3 ELSE 0 END)"
                    f" + (CASE WHEN texte_integral ILIKE ${ip} THEN 1 ELSE 0 END)"
                )
                ilike_params.append(f"%{kw}%"); ip += 1
            like_cond = " OR ".join(like_parts)
            relevance = " + ".join(score_parts) if score_parts else "1"
            ilike_params += [req.limit, req.offset]
            sql = f"""
                SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                       pays, domaine, resume, sanction, source_url,
                       ({relevance})::float AS rank
                FROM legal_corpus
                WHERE {where} AND ({like_cond})
                ORDER BY rank DESC, date_decision DESC NULLS LAST
                LIMIT ${ip} OFFSET ${ip+1}
            """
            rows = await conn.fetch(sql, *ilike_params)

        results = [_row_to_doc(r, float(r["rank"])) for r in rows]

        count_sql = f"SELECT COUNT(*) FROM legal_corpus WHERE {where}"
        total = await conn.fetchval(count_sql, *filter_params)

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
async def analyze_question(
    req: AnalyzeRequest,
    x_user_token: str | None = Header(None),
):
    """
    Analyse une question juridique :
    1. Recherche les documents pertinents dans le corpus
    2. Appelle Claude pour une réponse fondée sur le droit CIMA/OHADA/CI
    """
    # Étape 1 : récupérer le contexte documentaire
    search_req = SearchRequest(
        query=req.question,
        corpus=req.corpus,
        limit=max(req.context_docs, 8),
        mode="fulltext",
    )
    # Quota par utilisateur
    quota_info: dict = {"allowed": True, "used": None, "limit": None, "remaining": None}
    if x_user_token:
        from baobab.api.routes.accounts import check_and_increment_analyses_quota
        quota_info = await check_and_increment_analyses_quota(x_user_token)

    try:
        search_result = await search_corpus(search_req)
        docs = search_result.get("results", [])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Erreur base de données : {exc}") from exc

    context_parts = []
    for d in docs:
        snippet = f"[{d['ref'] or d['titre']}] {d['resume'] or ''}"
        context_parts.append(snippet)
    context = "\n\n".join(context_parts) if context_parts else "Aucun document trouvé dans le corpus."

    # Étape 2 : appel Claude (optionnel — dégradé si clé absente)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    analysis = None
    ai_available = bool(api_key)

    if ai_available:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3072,
                messages=[{
                    "role": "user",
                    "content": (
                        "Tu es BAOBAB, un assistant juridique spécialisé en droit africain "
                        "(CIMA, OHADA, droit ivoirien).\n\n"
                        "RÈGLE ABSOLUE : Tu dois répondre UNIQUEMENT en te basant sur les documents "
                        "du corpus ci-dessous. Ne complète JAMAIS avec ta connaissance générale.\n\n"
                        "FORMAT DE RÉPONSE : Retourne UNIQUEMENT un objet JSON valide, sans bloc "
                        "markdown, sans texte avant ou après, sans ``` ni ```json. "
                        "La réponse doit commencer directement par { et finir par }.\n\n"
                        "SCHÉMA JSON REQUIS :\n"
                        "{\n"
                        '  "identite": {\n'
                        '    "numero": "Analyse #001",\n'
                        '    "date": "date du jour en français ex: 9 juillet 2026",\n'
                        '    "juridiction": "BAOBAB — Analyse Juridique CIMA/OHADA",\n'
                        '    "formation": "corpus concerné ex: Droit CIMA — Zone CIMA",\n'
                        '    "numero_recueil": "Corpus BAOBAB · [nombre] documents analysés",\n'
                        '    "domaine": "ex: Contrôle prudentiel · Sanctions CRCA"\n'
                        "  },\n"
                        '  "solidite": { "score": 4, "label": "ex: Jurisprudence établie" },\n'
                        '  "principe": "Le principe juridique central dégagé en 1-2 phrases.",\n'
                        '  "schema": {\n'
                        '    "question": "La question juridique reformulée précisément",\n'
                        '    "reponse": "Réponse courte directe (1 ligne)",\n'
                        '    "consequence": "Conséquence pratique principale"\n'
                        "  },\n"
                        '  "passe": [\n'
                        '    { "date": "1992", "texte": "Événement législatif ou jurisprudentiel historique pertinent" }\n'
                        "  ],\n"
                        '  "present": {\n'
                        '    "faits": "Contexte factuel et juridique de la question posée, 3-5 phrases.",\n'
                        '    "pretentions": [\n'
                        '      { "partie": "Demandeur (position favorable)", "arg": "Argument en faveur de la thèse A" },\n'
                        '      { "partie": "Défendeur (position contraire)", "arg": "Argument en faveur de la thèse B" }\n'
                        "    ],\n"
                        '    "moyens": ["Point juridique clé 1", "Point juridique clé 2"],\n'
                        '    "question_droit": "La question de droit précise à trancher.",\n'
                        '    "raisonnement": "L\'analyse juridique complète et rigoureuse fondée sur les documents du corpus. Paragraphes détaillés.",\n'
                        '    "visa": ["Art. 312 Code CIMA", "Art. 325 Code CIMA"],\n'
                        '    "dispositif": "Conclusion juridique claire et applicable."\n'
                        "  },\n"
                        '  "futur": {\n'
                        '    "citations": 0,\n'
                        '    "decisions": 0,\n'
                        '    "statut": "consacre",\n'
                        '    "statut_label": "Consacré en droit CIMA",\n'
                        '    "usages": [\n'
                        '      { "annee": "2024", "texte": "Application pratique ou recommandation concrète" }\n'
                        "    ]\n"
                        "  },\n"
                        '  "juges": []\n'
                        "}\n\n"
                        "NOTES :\n"
                        "- passe = évolution législative/jurisprudentielle chronologique\n"
                        "- futur.usages = recommandations pratiques concrètes\n"
                        "- juges = [] si aucun juge identifié (c'est le cas par défaut pour les analyses thématiques)\n"
                        "- Si le corpus ne permet pas de répondre, remplis quand même le JSON avec "
                        "une réponse honnête indiquant le manque de sources dans les champs textuels.\n\n"
                        f"QUESTION : {req.question}\n\n"
                        f"CORPUS BAOBAB ({len(docs)} document(s)) :\n{context}\n\n"
                        "Retourne le JSON ci-dessus complété, sans aucun texte autour :"
                    ),
                }],
            )
            analysis = message.content[0].text
        except Exception as exc:
            analysis = f"Erreur IA : {exc}"

    import json as json_lib
    fiche = None
    if analysis:
        try:
            fiche = json_lib.loads(analysis)
        except Exception:
            fiche = None

    return {
        "question": req.question,
        "corpus": req.corpus,
        "context_docs": docs,
        "analysis": analysis,
        "fiche": fiche,
        "ai_available": ai_available,
        "quota": quota_info,
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
