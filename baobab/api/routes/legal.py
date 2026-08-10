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
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from baobab.rate_limit import client_ip, enforce_rate_limit

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


# ─── Prompt builders ──────────────────────────────────────────────────────────

def _build_prompt(question: str, query_type: str, context: str, n_docs: int) -> str:
    base = (
        "Tu es BAOBAB, assistant juridique spécialisé en droit africain (CIMA, OHADA, droit ivoirien).\n"
        "RÈGLE ABSOLUE : réponds UNIQUEMENT à partir des documents du corpus fournis.\n"
        "FORMAT : retourne UNIQUEMENT un objet JSON valide, sans markdown, sans ``` ni texte autour.\n\n"
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
            + f"TYPE : Analyse d'un arrêt ou décision juridique.\n\n"
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
            + f"TYPE : Analyse d'un texte de loi, article ou acte uniforme.\n\n"
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
            + "IMPORTANT : Ne génère PAS de timeline procédurale ni de section Passé/Présent/Futur. "
            + "Réponds de façon structurée, directe et pratique.\n\n"
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
    if not x_user_token:
        raise HTTPException(
            status_code=401,
            detail="Authentification requise (en-tête X-User-Token). "
            "Créez un espace gratuit via POST /api/v1/accounts/workspaces.",
        )
    from baobab.api.routes.accounts import _find_workspace_by_token

    workspace = await _find_workspace_by_token(x_user_token)
    if not workspace:
        raise HTTPException(status_code=401, detail="Token utilisateur invalide.")
    if workspace.get("suspended"):
        raise HTTPException(status_code=403, detail="Ce compte est suspendu.")
    return workspace


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
async def get_document(doc_id: str, x_user_token: str | None = Header(default=None)):
    """Détail complet d'un document du corpus. Nécessite un compte actif."""
    await _require_active_workspace(x_user_token)
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
    http_request: Request,
    x_user_token: str = Header(...),
):
    """
    Analyse une question juridique :
    1. Recherche les documents pertinents dans le corpus
    2. Appelle Claude pour une réponse fondée sur le droit CIMA/OHADA/CI

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
                    f"SELECT id, texte_integral FROM legal_corpus WHERE id = ANY($1::uuid[])",
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
