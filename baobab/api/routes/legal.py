"""
Routes API corpus juridique — recherche fulltext + sémantique + analyse.

POST /api/v1/legal/search   — recherche dans le corpus (fulltext + vecteur)
GET  /api/v1/legal/corpus   — liste paginée du corpus
GET  /api/v1/legal/corpus/{id} — détail d'un document
POST /api/v1/legal/analyze  — analyse d'une question juridique (IA)
"""

import json
import os
import re as _re_cls
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel

from baobab.rate_limit import client_ip, enforce_rate_limit
from baobab.core.temporal import TEMPORAL_PROMPT_CONTRACT, normalize_temporal_fiche
from baobab.core.africa import OHADA_COUNTRY_CODES, africa_country_payload

router = APIRouter(tags=["legal"])


# ─── Query classifier ─────────────────────────────────────────────────────────

def _classify_query(question: str) -> str:
    """Returns: 'arret' | 'loi' | 'question' | 'analyse'"""
    q = question.lower()
    # Court decision signals
    if any(_re_cls.search(p, q) for p in [
        r'\b(ccja|crca|tca|cour suprême|tribunal)\b',
        r'\b(décision|arrêt|jugement|délibération)\b.*n[°o]',
        r'\bn[°o]\s*[\d]{2,}[\s/]\d{4}',
    ]):
        return 'arret'
    # Statute/text signals
    if any(_re_cls.search(p, q) for p in [
        r'\b(art\.?|article)\s+\d+',
        r'\b(acte uniforme|code cima|code ohada|loi\s+n[°o]|décret|ordonnance|circulaire|instruction)\b',
        r'\b(audcg|auscgie|ausc|aucap|syscohada|cima)\b',
    ]):
        return 'loi'
    # Practical question signals
    if any(w in q for w in [
        'comment ', 'quelles sont les étapes', 'quels sont les délais', 'que faire',
        'combien de temps', 'comment créer', 'comment déclarer', 'comment obtenir',
        'quelle est la procédure', 'quelles formalités', 'comment calculer',
        'est-ce que je peux', 'puis-je ', 'quels documents', 'quelles conditions',
    ]):
        return 'question'
    return 'analyse'


def _json_field(value, fallback):
    """Normalise les champs JSONB, asyncpg pouvant les retourner sous forme de texte."""
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback
    return value


# ─── Prompt builders ──────────────────────────────────────────────────────────

def _build_prompt(question: str, query_type: str, context: str, n_docs: int) -> str:
    base = (
        "Tu es BAOBAB, assistant juridique multi-juridictionnel spécialisé en droit français, "
        "européen, africain et international.\n"
        "RÈGLE ABSOLUE : réponds UNIQUEMENT à partir des documents du corpus fournis.\n"
        "Ne présente jamais une source étrangère ou internationale comme directement applicable "
        "sans expliquer son autorité dans la juridiction demandée.\n"
        + TEMPORAL_PROMPT_CONTRACT
        + "FORMAT : retourne UNIQUEMENT un objet JSON valide, sans markdown, sans ``` ni texte autour.\n\n"
    )

    if query_type == 'arret':
        schema = '''{
  "type": "arret",
  "identite": {
    "numero": "Référence de la décision ou Analyse #001",
    "date": "date en français",
    "juridiction": "CCJA / CRCA / TCA / BAOBAB Analyse",
    "formation": "Chambre ou formation concernée",
    "numero_recueil": "Corpus BAOBAB · N documents analysés",
    "domaine": "Domaine juridique précis"
  },
  "solidite": { "score": 4, "label": "ex: Jurisprudence établie — 3 citations recensées" },
  "principe": "Principe juridique central en 1-2 phrases.",
  "schema": {
    "question": "Question juridique reformulée",
    "reponse": "Réponse directe en 1 ligne",
    "consequence": "Conséquence pratique principale"
  },
  "passe": [{ "date": "1992", "texte": "Événement législatif ou procédural historique" }],
  "present": {
    "faits": "Faits et contexte en 3-5 phrases.",
    "pretentions": [
      { "partie": "Demandeur", "arg": "Argument" },
      { "partie": "Défendeur", "arg": "Argument" }
    ],
    "moyens": ["Moyen 1", "Moyen 2"],
    "question_droit": "Question de droit précise.",
    "raisonnement": "Analyse rigoureuse en markdown — **gras** pour termes clés, tirets pour listes.",
    "visa": ["Art. 312 Code CIMA"],
    "dispositif": "Conclusion en paragraphes ou liste à tirets."
  },
  "futur": {
    "citations": 0, "decisions": 0,
    "statut": "consacre", "statut_label": "Consacré en droit applicable",
    "usages": [{ "annee": "2025", "texte": "Application pratique recommandée" }]
  },
  "juges": []
}'''
        return (
            base
            + "TYPE : Analyse d'un arrêt ou décision juridique.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    elif query_type == 'loi':
        schema = '''{
  "type": "loi",
  "reference": "Art. 260 Code CIMA — Délais sinistres",
  "titre": "Titre court du texte ou article",
  "domaine": "Droit des assurances · CIMA",
  "texte_article": "Reproduction fidèle ou paraphrase du texte si disponible.",
  "explication": "Explication juridique claire du texte en 3-5 phrases.",
  "historique": [
    { "annee": "1992", "texte": "Adoption ou modification historique" }
  ],
  "applicabilite": ["Côte d\'Ivoire", "Sénégal"],
  "points_attention": ["Point important 1", "Point important 2"],
  "sanctions": "Sanctions applicables si l\'article prévoit des sanctions, sinon null.",
  "jurisprudence_associee": ["Décision CRCA 2023/045 — résumé bref"],
  "textes_lies": ["Art. 261 Code CIMA", "Art. 312 Code CIMA"]
}'''
        return (
            base
            + "TYPE : Analyse d'un texte de loi, article ou acte uniforme.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    elif query_type == 'question':
        schema = '''{
  "type": "question",
  "titre": "Titre de la question reformulée de façon précise",
  "domaine": "Droit des sociétés · OHADA · Côte d\'Ivoire",
  "reponse_directe": "Réponse directe en 1-2 phrases percutantes.",
  "etapes": [
    { "numero": 1, "titre": "Titre de l\'étape", "detail": "Explication de l\'étape avec les exigences légales." }
  ],
  "points_cles": [
    "Point juridique important 1",
    "Point juridique important 2"
  ],
  "textes_applicables": ["Art. 5 AUSC", "Art. 27 AUDCG"],
  "delais": "Délais légaux applicables si pertinents, sinon null.",
  "cout_indicatif": "Coût indicatif si connu, sinon null.",
  "organisme_competent": "CEPICI, tribunal, RCCM, etc. selon le cas.",
  "avertissement": "Limite du corpus : ce que le corpus ne couvre pas et ce qu\'il faut vérifier.",
  "corps": "Développement complet en markdown : paragraphes avec **gras** pour les obligations, tirets pour les listes. Doit être exhaustif."
}'''
        return (
            base
            + "TYPE : Question juridique pratique ou procédurale.\n"
            + "IMPORTANT : réponds de façon structurée, directe et pratique, puis relie obligatoirement "
            + "la réponse à son origine, au droit applicable à la date d'analyse et aux seules évolutions sourcées.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    else:  # analyse
        schema = '''{
  "type": "analyse",
  "titre": "Titre de l\'analyse doctrinale",
  "domaine": "Droit des sociétés · OHADA",
  "principe": "Principe juridique central en 1-2 phrases.",
  "introduction": "Mise en contexte de la question en 3-4 phrases.",
  "developpement": "Analyse approfondie en markdown. **Gras** pour concepts clés. Tirets pour listes. Sauts de ligne entre paragraphes.",
  "positions": [
    { "titre": "Position A", "argument": "Développement de l\'argument" },
    { "titre": "Position B", "argument": "Développement de l\'argument contraire" }
  ],
  "jurisprudence": [
    { "ref": "CCJA n°045/2019", "apport": "Ce que cet arrêt apporte à la question" }
  ],
  "textes_applicables": ["Art. 5 AUSC"],
  "conclusion": "Synthèse et prise de position doctrinale motivée.",
  "limites": "Limites de l\'analyse au regard du corpus disponible."
}'''
        return (
            base
            + "TYPE : Analyse doctrinale ou question abstraite de droit.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://baobab:baobab@localhost:5432/baobab")

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


async def _require_active_workspace(x_user_token: str | None) -> dict:
    """
    Exige un token de workspace valide et actif (compte non suspendu).

    Avant correctif, tout le corpus juridique (le produit payant de
    BAOBAB) était lisible anonymement via /legal/search, /legal/corpus
    et /legal/corpus/{id} — le système de quota par plan n'était en fait
    appliqué qu'à /legal/analyze, et seulement quand le client daignait
    envoyer son token (cf. audit sécurité). Toute lecture du corpus
    nécessite désormais un compte, même gratuit.
    """
    from baobab.api.routes.accounts import require_workspace_service

    return await require_workspace_service(x_user_token, "legal_search")


# ─── Modèles ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    corpus: str = "all"
    type: str | None = None        # decision_crca | arret_ccja | acte_uniforme | loi
    pays: str | None = None
    country_code: str | None = None
    jurisdiction_code: str | None = None
    language_code: str | None = None
    legal_status: str | None = None
    as_of: str | None = None
    domaine: str | None = None
    limit: int = 20
    offset: int = 0
    mode: Literal["fulltext", "semantic", "hybrid"] = "fulltext"


class AnalyzeRequest(BaseModel):
    question: str
    corpus: str = "all"
    country_code: str | None = None
    jurisdiction_code: str | None = None
    as_of: str | None = None
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
    country_code: str | None = None
    jurisdiction_code: str | None = None
    language_code: str | None = None
    legal_status: str | None = None
    official_citation: str | None = None
    source_code: str | None = None
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
        "country_code": row["country_code"],
        "jurisdiction_code": row["jurisdiction_code"],
        "language_code": row["language_code"],
        "legal_status": row["legal_status"],
        "official_citation": row["official_citation"],
        "source_code": row["source_code"],
        "score": score,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/legal/search")
async def search_corpus(req: SearchRequest, x_user_token: str | None = Header(default=None)):
    """Recherche fulltext dans le corpus juridique BAOBAB. Nécessite un compte actif."""
    await _require_active_workspace(x_user_token)
    return await _search_corpus_impl(req)


async def _search_corpus_impl(req: SearchRequest) -> dict:
    conn = await _conn()
    try:
        conditions = ["1=1"]
        params: list = []
        p = 1

        if req.corpus != "all":
            conditions.append(f"corpus = ${p}")
            params.append(req.corpus)
            p += 1
        if req.type:
            conditions.append(f"type = ${p}")
            params.append(req.type)
            p += 1
        if req.pays:
            conditions.append(f"pays ILIKE ${p}")
            params.append(f"%{req.pays}%")
            p += 1
        if req.country_code:
            conditions.append(f"country_code = ${p}")
            params.append(req.country_code.upper())
            p += 1
        if req.jurisdiction_code:
            conditions.append(f"jurisdiction_code = ${p}")
            params.append(req.jurisdiction_code.upper())
            p += 1
        if req.language_code:
            conditions.append(f"language_code = ${p}")
            params.append(req.language_code.lower())
            p += 1
        if req.legal_status:
            conditions.append(f"legal_status = ${p}")
            params.append(req.legal_status.upper())
            p += 1
        if req.as_of:
            conditions.append(f"(effective_from IS NULL OR effective_from <= ${p}::date)")
            params.append(req.as_of)
            p += 1
            conditions.append(f"(effective_to IS NULL OR effective_to >= ${p}::date)")
            params.append(req.as_of)
            p += 1
        if req.domaine:
            conditions.append(f"domaine ILIKE ${p}")
            params.append(f"%{req.domaine}%")
            p += 1

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
                       pays, domaine, resume, sanction, source_url, country_code,
                       jurisdiction_code, language_code, legal_status, official_citation, source_code,
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
                ilike_params.append(f"%{kw}%")
                ip += 1
            like_cond = " OR ".join(like_parts)
            relevance = " + ".join(score_parts) if score_parts else "1"
            ilike_params += [req.limit, req.offset]
            sql = f"""
                SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                       pays, domaine, resume, sanction, source_url, country_code,
                       jurisdiction_code, language_code, legal_status, official_citation, source_code,
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
    country_code: str | None = Query(None),
    jurisdiction_code: str | None = Query(None),
    language_code: str | None = Query(None),
    legal_status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    x_user_token: str | None = Header(default=None),
):
    """Liste paginée du corpus juridique. Nécessite un compte actif."""
    await _require_active_workspace(x_user_token)
    conn = await _conn()
    try:
        conditions = ["1=1"]
        params: list = []
        p = 1

        if corpus:
            conditions.append(f"corpus = ${p}")
            params.append(corpus)
            p += 1
        if type:
            conditions.append(f"type = ${p}")
            params.append(type)
            p += 1
        if pays:
            conditions.append(f"pays ILIKE ${p}")
            params.append(f"%{pays}%")
            p += 1
        if country_code:
            conditions.append(f"country_code = ${p}")
            params.append(country_code.upper())
            p += 1
        if jurisdiction_code:
            conditions.append(f"jurisdiction_code = ${p}")
            params.append(jurisdiction_code.upper())
            p += 1
        if language_code:
            conditions.append(f"language_code = ${p}")
            params.append(language_code.lower())
            p += 1
        if legal_status:
            conditions.append(f"legal_status = ${p}")
            params.append(legal_status.upper())
            p += 1

        where = " AND ".join(conditions)

        sql = f"""
            SELECT id, ref, type, corpus, juridiction, titre, date_decision,
                   pays, domaine, resume, sanction, source_url, country_code,
                   jurisdiction_code, language_code, legal_status, official_citation, source_code
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
async def get_document(doc_id: str, x_user_token: str | None = Header(default=None)):
    """Détail complet d'un document du corpus. Nécessite un compte actif."""
    await _require_active_workspace(x_user_token)
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            """SELECT c.*,
                      b.facts AS brief_facts,b.procedure_history AS brief_procedure_history,
                      b.claims AS brief_claims,b.legal_question AS brief_legal_question,
                      b.applied_rules AS brief_applied_rules,b.holding AS brief_holding,
                      b.exact_disposition AS brief_exact_disposition,b.significance AS brief_significance,
                      b.precedent_status AS brief_precedent_status,b.past_context AS brief_past_context,
                      b.present_effect AS brief_present_effect,b.future_assessment AS brief_future_assessment,
                      b.future_evidence AS brief_future_evidence,b.professional_actions AS brief_professional_actions,
                      b.limitations AS brief_limitations,b.evidence_refs AS brief_evidence_refs,
                      b.extraction_method AS brief_extraction_method,b.editorial_status AS brief_editorial_status,
                      b.validation_score AS brief_validation_score,
                      b.automated_validation AS brief_automated_validation,
                      b.document_verified_at AS brief_document_verified_at,
                      b.reviewed_by AS brief_reviewed_by,b.reviewed_at AS brief_reviewed_at
               FROM legal_corpus c
               LEFT JOIN legal_documents d ON d.legacy_corpus_id=c.id
               LEFT JOIN legal_case_briefs b ON b.document_id=d.document_id
               WHERE c.id = $1""",
            doc_id,
        )
        if not row:
            raise HTTPException(404, f"Document {doc_id} introuvable")
        brief = None
        if row["brief_editorial_status"]:
            brief = {
                "faits": row["brief_facts"],
                "procedure": row["brief_procedure_history"],
                "pretentions": _json_field(row["brief_claims"], []),
                "question_droit": row["brief_legal_question"],
                "regles_appliquees": _json_field(row["brief_applied_rules"], []),
                "solution": row["brief_holding"],
                "dispositif": row["brief_exact_disposition"],
                "portee": row["brief_significance"],
                "statut_jurisprudentiel": row["brief_precedent_status"],
                "passe": _json_field(row["brief_past_context"], []),
                "present": row["brief_present_effect"],
                "futur": row["brief_future_assessment"],
                "preuves_futur": _json_field(row["brief_future_evidence"], []),
                "actions": _json_field(row["brief_professional_actions"], []),
                "limites": row["brief_limitations"],
                "preuves": _json_field(row["brief_evidence_refs"], []),
                "methode_extraction": row["brief_extraction_method"],
                "statut_editorial": row["brief_editorial_status"],
                "score_documentaire": row["brief_validation_score"],
                "controles_documentaires": _json_field(row["brief_automated_validation"], {}),
                "controle_documentaire_le": str(row["brief_document_verified_at"]) if row["brief_document_verified_at"] else None,
                "valide_par": row["brief_reviewed_by"],
                "valide_le": str(row["brief_reviewed_at"]) if row["brief_reviewed_at"] else None,
            }
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
            "country_code": row["country_code"],
            "jurisdiction_code": row["jurisdiction_code"],
            "language_code": row["language_code"],
            "legal_status": row["legal_status"],
            "source_code": row["source_code"],
            "official_identifier": row["official_identifier"],
            "official_citation": row["official_citation"],
            "publication_date": str(row["publication_date"]) if row["publication_date"] else None,
            "effective_from": str(row["effective_from"]) if row["effective_from"] else None,
            "effective_to": str(row["effective_to"]) if row["effective_to"] else None,
            "source_license": row["source_license"],
            "content_checksum": row["content_checksum"],
            "source_pdf_url": row["source_pdf_url"],
            "sanction": row["sanction"],
            "articles_cites": list(row["articles_cites"] or []),
            "metadata": json.loads(row["metadata"] or "{}"),
            "fiche_jurisprudentielle": brief,
            "created_at": str(row["created_at"]),
        }
    finally:
        await conn.close()


@router.get("/legal/corpus/{doc_id}/renditions")
async def list_document_renditions(doc_id: str, x_user_token: str | None = Header(default=None)):
    """Liste les copies internes disponibles, sans exposer leur URI de stockage."""
    await _require_active_workspace(x_user_token)
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """SELECT r.rendition_id,r.rendition_type,r.page_number,r.mime_type,r.sha256,
                      r.byte_size,r.extraction_method,r.ocr_language,r.ocr_confidence,
                      r.review_status,r.created_at
               FROM legal_document_renditions r
               JOIN legal_documents d ON d.document_id=r.document_id
               WHERE d.legacy_corpus_id=$1::uuid
               ORDER BY CASE r.rendition_type WHEN 'ORIGINAL' THEN 0
                    WHEN 'SEARCHABLE_PDF' THEN 1 WHEN 'PAGE_IMAGE' THEN 2 ELSE 3 END,
                    r.page_number NULLS FIRST""",
            doc_id,
        )
        return {"results": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await conn.close()


@router.get("/legal/corpus/{doc_id}/renditions/{rendition_id}/content")
async def get_document_rendition_content(
    doc_id: str, rendition_id: str, x_user_token: str | None = Header(default=None),
):
    """Diffuse une copie interne après vérification du compte et de l'appartenance au document."""
    await _require_active_workspace(x_user_token)
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            """SELECT r.mime_type,r.rendition_type,r.sha256,b.content
               FROM legal_document_renditions r
               JOIN legal_document_rendition_blobs b ON b.rendition_id=r.rendition_id
               JOIN legal_documents d ON d.document_id=r.document_id
               WHERE d.legacy_corpus_id=$1::uuid AND r.rendition_id=$2::uuid""",
            doc_id, rendition_id,
        )
        if not row:
            raise HTTPException(404, "Copie documentaire introuvable")
        disposition = "inline" if row["mime_type"].startswith(("application/pdf", "image/")) else "attachment"
        return Response(
            content=bytes(row["content"]), media_type=row["mime_type"],
            headers={
                "Content-Disposition": f'{disposition}; filename="baobab-{row["rendition_type"].lower()}"',
                "X-Content-SHA256": row["sha256"],
                "Cache-Control": "private, max-age=300",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        await conn.close()


@router.post("/legal/analyze")
async def analyze_question(
    req: AnalyzeRequest,
    http_request: Request,
    x_user_token: str = Header(...),
):
    """
    Analyse une question juridique :
    1. Recherche les documents pertinents dans le corpus
    2. Appelle Claude pour une réponse fondée sur la juridiction et la date demandées

    Le token utilisateur est OBLIGATOIRE et le quota est TOUJOURS vérifié
    et incrémenté avant tout appel IA. Avant correctif, ce contrôle était
    ignoré lorsque le client omettait simplement l'en-tête X-User-Token,
    ce qui permettait un accès anonyme et illimité à un appel Claude
    payant (cf. audit sécurité — vulnérabilité de logique métier,
    équivalent du contournement de paywall décrit au ch. 18 du livre).
    """
    # IP throttling en complément du quota par compte : ralentit aussi un
    # abus distribué sur plusieurs comptes gratuits créés en masse.
    await enforce_rate_limit(
        key=f"legal-analyze:{client_ip(http_request)}", limit=30, window_seconds=3600
    )

    from baobab.api.routes.accounts import check_and_increment_analyses_quota

    quota_info = await check_and_increment_analyses_quota(x_user_token)

    # Étape 1 : récupérer le contexte documentaire
    search_req = SearchRequest(
        query=req.question,
        corpus=req.corpus,
        country_code=req.country_code,
        jurisdiction_code=req.jurisdiction_code,
        as_of=req.as_of,
        limit=max(req.context_docs, 8),
        mode="fulltext",
    )

    try:
        search_result = await _search_corpus_impl(search_req)
        docs = search_result.get("results", [])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Erreur base de données : {exc}") from exc

    # Récupère le texte intégral pour chaque document trouvé
    import re as _re
    import html as _html

    def _clean_text(raw: str) -> str:
        """Supprime les balises HTML et décode les entités."""
        if not raw:
            return ""
        # Décode entités HTML (&nbsp; &#039; etc.)
        text = _html.unescape(raw)
        # Supprime les balises HTML
        text = _re.sub(r"<[^>]+>", " ", text)
        # Normalise les espaces
        text = _re.sub(r"\s{3,}", "\n", text)
        text = _re.sub(r" {2,}", " ", text)
        return text.strip()

    doc_ids = [d["id"] for d in docs if d.get("id")]
    full_texts: dict[str, str] = {}
    if doc_ids:
        try:
            conn2 = await _conn()
            try:
                rows = await conn2.fetch(
                    "SELECT id, texte_integral FROM legal_corpus WHERE id = ANY($1::uuid[])",
                    [__import__("uuid").UUID(i) for i in doc_ids],
                )
                for r in rows:
                    full_texts[str(r["id"])] = _clean_text(r["texte_integral"] or "")
            finally:
                await conn2.close()
        except Exception:
            pass  # on continue sans les textes intégraux si erreur

    context_parts = []
    for d in docs:
        ref = d["ref"] or d["titre"] or "Document"
        resume = (d["resume"] or "").strip()
        full = full_texts.get(d["id"], "")
        # Tronque le texte intégral à 1500 chars par doc pour libérer des tokens de sortie
        body = full[:1500] if full else resume
        snippet = f"--- [{ref}] ---\n{body}"
        context_parts.append(snippet)
    context = "\n\n".join(context_parts) if context_parts else "Aucun document trouvé dans le corpus."

    # Étape 2 : appel Claude (optionnel — dégradé si clé absente)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    analysis = None
    ai_available = bool(api_key)

    query_type = _classify_query(req.question)

    if ai_available:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = _build_prompt(req.question, query_type, context, len(docs))
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
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
            # Tentative de réparation si JSON tronqué (manque de tokens)
            try:
                txt = analysis.strip()
                # Ferme les structures JSON ouvertes non fermées
                opens = txt.count('{') - txt.count('}')
                arr_opens = txt.count('[') - txt.count(']')
                # Retire la dernière ligne incomplète (pas de virgule/quote fermante)
                lines = txt.rsplit('\n', 1)
                if len(lines) == 2 and not lines[1].strip().endswith(('}', ']', '"', ',')):
                    txt = lines[0].rstrip().rstrip(',')
                txt += ']' * max(0, arr_opens) + '}' * max(0, opens)
                fiche = json_lib.loads(txt)
            except Exception:
                fiche = None

    if fiche is not None:
        fiche = normalize_temporal_fiche(
            fiche,
            as_of=req.as_of,
            source_documents=docs,
        )

    return {
        "question": req.question,
        "corpus": req.corpus,
        "response_type": query_type,
        "context_docs": docs,
        "analysis": analysis,
        "fiche": fiche,
        "ai_available": ai_available,
        "quota": quota_info,
    }


@router.get("/legal/africa/coverage")
async def africa_coverage():
    """Couverture réelle par État africain, sans confondre national et régional."""
    conn = await _conn()
    try:
        country_rows = await conn.fetch(
            """SELECT country_code,count(*) AS total,
                      count(*) FILTER (WHERE lower(type) ~ '(loi|code|decret|décret|arrete|arrêté|ordonnance|reglement|règlement)') AS legislation,
                      count(*) FILTER (WHERE lower(type) ~ '(arret|arrêt|decision|décision|jugement|jurisprudence)') AS case_law,
                      count(*) FILTER (WHERE source_code IS NOT NULL) AS sourced,
                      max(updated_at) AS last_update
               FROM legal_corpus WHERE country_code IS NOT NULL
               GROUP BY country_code"""
        )
        actual = {row["country_code"]: dict(row) for row in country_rows}
        ohada = await conn.fetchrow(
            """SELECT count(*) AS total,
                      count(*) FILTER (WHERE lower(type) ~ '(acte|traite|traité|reglement|règlement|loi|code)') AS legislation,
                      count(*) FILTER (WHERE lower(type) ~ '(arret|arrêt|avis|ordonnance|decision|décision)') AS case_law,
                      count(*) FILTER (WHERE coalesce(texte_integral,'')<>'') AS full_text,
                      max(updated_at) AS last_update
               FROM legal_corpus WHERE lower(corpus)='ohada'"""
        )
        countries = []
        for country in africa_country_payload():
            row = actual.get(country["code"], {})
            national_total = int(row.get("total") or 0)
            regional_total = int(ohada["total"] or 0) if country["ohada_member"] else 0
            countries.append({
                **country,
                "national": {
                    "total": national_total,
                    "legislation": int(row.get("legislation") or 0),
                    "case_law": int(row.get("case_law") or 0),
                    "sourced": int(row.get("sourced") or 0),
                    "last_update": str(row.get("last_update")) if row.get("last_update") else None,
                },
                "regional": {"ohada_documents": regional_total},
                "integration_status": "NATIONAL_ACTIVE" if national_total else (
                    "OHADA_ONLY" if regional_total else "PLANNED"
                ),
            })
        return {
            "countries": countries,
            "total_countries": len(countries),
            "ohada": dict(ohada),
            "methodology": "Les volumes nationaux proviennent des documents explicitement rattachés au code du pays. Le corpus OHADA est affiché séparément pour ses 17 États membres.",
        }
    finally:
        await conn.close()


@router.get("/legal/ohada/coverage")
async def ohada_coverage():
    """Mesure exploitable de l'implémentation OHADA par grande matière."""
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """WITH classified AS (
                 SELECT CASE
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(sûret|surete|caution|hypoth|nantiss|gage)' THEN 'Sûretés'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(recouvr|saisie|exécution|execution|injonction)' THEN 'Recouvrement et voies d’exécution'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(sociét|societ|gie|gouvernance)' THEN 'Sociétés commerciales et GIE'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(collective|faillite|liquidation|redressement|concordat)' THEN 'Procédures collectives'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(arbitr|médiation|mediation)' THEN 'Arbitrage et médiation'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(comptab|syscohada)' THEN 'Droit comptable'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(transport)' THEN 'Transport routier'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(coopér|cooper)' THEN 'Sociétés coopératives'
                   WHEN lower(coalesce(domaine,'')||' '||coalesce(titre,'')) ~ '(commercial|commerçant|commercant|bail|fonds de commerce)' THEN 'Droit commercial général'
                   ELSE 'Autres matières OHADA' END AS matter,
                   type,texte_integral,source_code,updated_at
                 FROM legal_corpus WHERE lower(corpus)='ohada'
               )
               SELECT matter,count(*) AS documents,
                      count(*) FILTER (WHERE lower(type) ~ '(arret|arrêt|avis|ordonnance|decision|décision)') AS decisions,
                      count(*) FILTER (WHERE coalesce(texte_integral,'')<>'') AS full_text,
                      count(*) FILTER (WHERE source_code IS NOT NULL) AS sourced,
                      max(updated_at) AS last_update
               FROM classified GROUP BY matter ORDER BY documents DESC"""
        )
        return {
            "members": sorted(OHADA_COUNTRY_CODES),
            "member_count": len(OHADA_COUNTRY_CODES),
            "matters": [dict(row) for row in rows],
            "methodology": "Classement documentaire automatique à contrôler éditorialement. Les chiffres décrivent le corpus présent, pas l’exhaustivité du droit OHADA.",
        }
    finally:
        await conn.close()


@router.get("/legal/ohada/codes")
async def ohada_codes():
    """Actes uniformes découpés en articles, avec niveau de complétude explicite."""
    conn = await _conn()
    try:
        rows = await conn.fetch(
            """SELECT c.id,c.ref,c.titre,c.domaine,c.publication_date,c.source_url,
                      count(p.provision_id) AS articles,
                      count(p.provision_id) FILTER (WHERE p.verification_status='AUTOMATED_PARTIAL_SOURCE') AS partial_articles,
                      max(p.created_at) AS indexed_at
               FROM legal_corpus c
               LEFT JOIN legal_provisions p ON p.document_id=c.id
               WHERE c.corpus='ohada' AND c.type='acte_uniforme'
               GROUP BY c.id HAVING count(p.provision_id)>0
               ORDER BY c.publication_date DESC NULLS LAST,c.ref"""
        )
        return {
            "results": [dict(row) for row in rows], "total": len(rows),
            "coverage_complete": False,
            "notice": "Découpage automatisé d’extraits plafonnés. Chaque article doit être comparé au Journal officiel avant usage professionnel.",
        }
    finally:
        await conn.close()


@router.get("/legal/ohada/codes/{document_id}/articles")
async def ohada_code_articles(document_id: str, query: str | None = None, limit: int = 200):
    limit = max(1, min(limit, 500))
    query = query.strip() or None if query is not None else None
    conn = await _conn()
    try:
        document = await conn.fetchrow(
            """SELECT id,ref,titre,domaine,publication_date,source_url
               FROM legal_corpus WHERE id=$1::uuid AND corpus='ohada' AND type='acte_uniforme'""",
            document_id,
        )
        if not document:
            raise HTTPException(404, "Acte uniforme introuvable")
        rows = await conn.fetch(
            """SELECT provision_id,provision_number,heading,content,valid_from,valid_until,status,
                      verification_status,content_checksum,source_url,
                      (SELECT count(*) FROM legal_document_relations r
                       WHERE r.target_document_id=legal_provisions.document_id
                         AND r.relation_type='EXPLICITLY_CITES_PROVISION'
                         AND r.provision_ref='Article '||legal_provisions.provision_number) AS citation_count
               FROM legal_provisions WHERE document_id=$1::uuid
                 AND ($2::text IS NULL OR provision_number ILIKE $2 OR content ILIKE $3)
               ORDER BY CASE WHEN provision_number ~ '^[0-9]+$' THEN provision_number::int ELSE 999999 END,
                        provision_number LIMIT $4""",
            document_id, query, f"%{query}%" if query else None, limit,
        )
        return {"document": dict(document), "results": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await conn.close()


@router.get("/legal/ohada/codes/{document_id}/articles/{provision_number}/decisions")
async def ohada_article_decisions(document_id: str, provision_number: str, limit: int = 50):
    """Décisions qui citent explicitement un article, avec la preuve textuelle du lien."""
    limit = max(1, min(limit, 100))
    conn = await _conn()
    try:
        provision = await conn.fetchrow(
            """SELECT p.provision_id,p.provision_number,c.ref AS document_ref,c.titre AS document_title
               FROM legal_provisions p JOIN legal_corpus c ON c.id=p.document_id
               WHERE p.document_id=$1::uuid AND p.provision_number=$2
                 AND c.corpus='ohada' AND c.type='acte_uniforme'""",
            document_id,
            provision_number,
        )
        if not provision:
            raise HTTPException(404, "Article OHADA introuvable")
        relation_ref = f"Article {provision_number}"
        total = await conn.fetchval(
            """SELECT count(*) FROM legal_document_relations
               WHERE target_document_id=$1::uuid AND relation_type='EXPLICITLY_CITES_PROVISION'
                 AND provision_ref=$2""",
            document_id,
            relation_ref,
        )
        rows = await conn.fetch(
            """SELECT d.id,d.ref,d.titre,d.type,d.juridiction,d.pays,d.date_decision,
                      d.resume,d.source_url,d.source_pdf_url,r.confidence_score,r.evidence
               FROM legal_document_relations r
               JOIN legal_corpus d ON d.id=r.source_document_id
               WHERE r.target_document_id=$1::uuid
                 AND r.relation_type='EXPLICITLY_CITES_PROVISION' AND r.provision_ref=$2
               ORDER BY d.date_decision DESC NULLS LAST,d.ref LIMIT $3""",
            document_id,
            relation_ref,
            limit,
        )
        decisions = []
        for row in rows:
            decision = dict(row)
            decision["evidence"] = _json_field(decision.get("evidence"), {})
            decisions.append(decision)
        return {
            "article": dict(provision),
            "results": decisions,
            "total": int(total or 0),
            "methodology": "Citation textuelle explicite détectée automatiquement ; le lien reste à valider éditorialement.",
        }
    finally:
        await conn.close()


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
