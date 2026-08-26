"""Espace premium et dynamique du droit camerounais."""

from __future__ import annotations

import json as _json
import os
import re
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from baobab.api.routes.accounts import require_workspace_service
from baobab.api.routes.legal import _conn, _search_corpus_impl, SearchRequest
from baobab.rate_limit import client_ip, enforce_rate_limit

router = APIRouter(tags=["droit-camerounais"])


# ─── Auth helper ──────────────────────────────────────────────────────────────

async def _require_cameroon(x_user_token: str | None) -> dict:
    return await require_workspace_service(x_user_token, "legal_cm")


# ─── Query classifier CM ──────────────────────────────────────────────────────

def _classify_cm_query(question: str) -> Literal["arret", "loi", "question", "analyse"]:
    """Classifie la question selon le contexte juridique camerounais.

    Reconnaît les signaux propres au droit CM : Cour Suprême, CEMAC,
    COBAC, codes nationaux, système mixte civil/common law.
    """
    q = question.lower()

    # Questions pratiques — priorité haute car elles contiennent des mots-clés explicites
    if any(re.search(p, q) for p in [
        r"\bcomment\b",
        r"\bquel(?:le)?s?\s+(?:est\s+la\s+proc|sont\s+les\s+(?:d[ée]lais|formalit|[ée]tapes|conditions|documents))",
        r"\bque\s+faire\b",
        r"\bcombien\s+de\s+temps\b",
        r"\best-ce\s+que\s+je\s+peux\b",
        r"\bpuis-je\b",
    ]):
        return "question"

    # Décisions juridictionnelles
    if any(re.search(p, q) for p in [
        r"\b(cour\s+supr[êe]me|tgi|tpi|tribunal|juridiction|cour\s+d.appel)\b",
        r"\b(arr[êe]t|jugement|d[ée]cision|d[ée]lib[ée]ration)\b.*n[°o]",
        r"\b(cobac|ccja|crca)\b",
        r"\bn[°o]\s*\d{2,}[\s/]\d{4}",
    ]):
        return "arret"

    # Textes normatifs et références législatives
    if any(re.search(p, q) for p in [
        r"\b(art\.?|article)\s+\d+",
        r"\b(code\s+p[ée]nal|code\s+du\s+travail|code\s+civil|code\s+de\s+proc[ée]dure|constitution)\b",
        r"\b(loi\s+n[°o]|d[ée]cret|ordonnance)\s*\d",
        r"\b(cemac|ohada|acte\s+uniforme|audcg|auscgie|ausc)\b",
        r"\b(rccm|syscohada|statut\s+g[ée]n[ée]ral|fonction\s+publique)\b",
    ]):
        return "loi"

    return "analyse"


# ─── Prompt builder CM ────────────────────────────────────────────────────────

def _build_cm_prompt(question: str, query_type: str, context: str, n_docs: int) -> str:
    base = (
        "Tu es BAOBAB, assistant juridique spécialisé en droit camerounais.\n\n"
        "CONTEXTE JURIDIQUE CAMEROUNAIS :\n"
        "Le Cameroun applique un système MIXTE : droit civil (provinces francophones, héritage français) "
        "et Common Law (régions anglophones Nord-Ouest et Sud-Ouest, héritage britannique).\n"
        "Hiérarchie des normes applicables :\n"
        "  1. Constitution du 18 janvier 1996\n"
        "  2. Droit OHADA — Actes uniformes (applicable dans les 17 États parties dont le Cameroun)\n"
        "  3. Droit CEMAC — règlements communautaires (6 États CEMAC)\n"
        "  4. Codes nationaux camerounais : Code pénal (2016), Code du travail (1992), "
        "Code de procédure pénale (2005), Code civil (francophone) / Common Law (anglophone)\n"
        "  5. Jurisprudence de la Cour Suprême du Cameroun\n\n"
        "RÈGLE ABSOLUE : réponds UNIQUEMENT à partir des documents du corpus fournis ci-dessous.\n"
        "Pour chaque affirmation, indique si elle relève du droit national CM, de l'OHADA, "
        "du CEMAC, ou d'un autre corpus. Ne fais jamais de confusion entre ces niveaux.\n"
        "FORMAT : retourne UNIQUEMENT un objet JSON valide, sans markdown, sans ``` ni texte autour.\n\n"
    )

    if query_type == "arret":
        schema = """{
  "type": "arret",
  "identite": {
    "numero": "Référence de la décision ou Analyse #001",
    "date": "date en français",
    "juridiction": "Cour Suprême du Cameroun / Cour d'appel / Tribunal",
    "formation": "Chambre civile / pénale / sociale / administrative / CCJA",
    "numero_recueil": "Corpus BAOBAB · N documents analysés",
    "domaine": "Domaine juridique précis"
  },
  "corpus_applicable": "Droit national CM / OHADA / CEMAC / Common Law anglophone",
  "solidite": { "score": 4, "label": "Jurisprudence établie / Arrêt isolé / Décision administrative" },
  "principe": "Principe juridique central en 1-2 phrases.",
  "schema": {
    "question": "Question juridique reformulée",
    "reponse": "Réponse directe en 1 ligne",
    "consequence": "Conséquence pratique principale"
  },
  "passe": [{ "date": "1996", "texte": "Événement législatif ou procédural historique CM" }],
  "present": {
    "faits": "Faits et contexte en 3-5 phrases.",
    "pretentions": [
      { "partie": "Demandeur", "arg": "Argument" },
      { "partie": "Défendeur", "arg": "Argument" }
    ],
    "moyens": ["Moyen 1", "Moyen 2"],
    "question_droit": "Question de droit précise.",
    "raisonnement": "Analyse rigoureuse en markdown — **gras** pour termes clés.",
    "visa": ["Art. X Constitution CM", "Art. X Code pénal 2016", "Art. X Acte uniforme OHADA"],
    "dispositif": "Conclusion en paragraphes ou liste à tirets."
  },
  "futur": {
    "citations": 0, "decisions": 0,
    "statut": "consacre", "statut_label": "Consacré en droit camerounais applicable",
    "usages": [{ "annee": "2025", "texte": "Application pratique recommandée au Cameroun" }]
  },
  "juges": [],
  "avertissement_dualisme": "Préciser si la solution diffère entre provinces francophones et régions anglophones."
}"""
        return (
            base
            + "TYPE : Analyse d'une décision juridictionnelle camerounaise.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    elif query_type == "loi":
        schema = """{
  "type": "loi",
  "reference": "Art. X Code pénal CM 2016 / Loi N°92/007 / Art. X Acte uniforme OHADA",
  "titre": "Titre court du texte ou article",
  "corpus_source": "Droit national CM / OHADA / CEMAC",
  "domaine": "Droit pénal · Cameroun / Droit du travail · Cameroun / OHADA",
  "texte_article": "Reproduction fidèle ou paraphrase du texte si disponible.",
  "explication": "Explication juridique claire du texte en 3-5 phrases.",
  "applicabilite_territoriale": "Toutes provinces CM / Francophones uniquement / Anglophones (Common Law)",
  "historique": [{ "annee": "2016", "texte": "Adoption ou modification" }],
  "points_attention": ["Point important 1", "Point important 2"],
  "sanctions": "Sanctions applicables (emprisonnement, amende FCFA) ou null.",
  "interaction_ohada": "Comment ce texte s'articule avec l'OHADA si applicable, sinon null.",
  "jurisprudence_associee": ["Arrêt Cour Suprême CM — résumé bref"],
  "textes_lies": ["Art. Y Code pénal", "Art. Z Acte uniforme AUDCG"]
}"""
        return (
            base
            + "TYPE : Analyse d'un texte de loi, article ou acte applicable au Cameroun.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    elif query_type == "question":
        schema = """{
  "type": "question",
  "titre": "Titre de la question reformulée de façon précise",
  "domaine": "Droit du travail · Cameroun / Droit des sociétés · OHADA · Cameroun",
  "corpus_applicable": "Droit national CM / OHADA / CEMAC — préciser lequel et pourquoi",
  "reponse_directe": "Réponse directe en 1-2 phrases percutantes.",
  "etapes": [
    { "numero": 1, "titre": "Titre de l'étape", "detail": "Explication avec exigences légales CM." }
  ],
  "points_cles": ["Point juridique CM important 1", "Point juridique important 2"],
  "textes_applicables": ["Art. X Loi N°92/007 (Code du travail CM)", "Art. Y Acte uniforme OHADA"],
  "delais": "Délais légaux applicables au Cameroun si pertinents, sinon null.",
  "cout_indicatif": "Coût indicatif en FCFA si connu, sinon null.",
  "organisme_competent": "RCCM, Greffe du Tribunal, MINTSS, MINJUSTICE, Notaire, etc.",
  "specificite_anglophone": "Différence de procédure pour les régions anglophones (Common Law), ou null.",
  "avertissement": "Limites du corpus : ce qu'il faut vérifier auprès d'un praticien CM.",
  "corps": "Développement complet en markdown. **Gras** pour obligations. Tirets pour listes."
}"""
        return (
            base
            + "TYPE : Question juridique pratique ou procédurale applicable au Cameroun.\n"
            + "IMPORTANT : Indique toujours si la procédure diffère entre droit francophone et Common Law anglophone.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )

    else:  # analyse
        schema = """{
  "type": "analyse",
  "titre": "Titre de l'analyse doctrinale",
  "domaine": "Droit pénal · Cameroun / Droit des affaires · OHADA",
  "corpus_mobilise": ["Droit national CM", "OHADA", "CEMAC"],
  "principe": "Principe juridique central en 1-2 phrases.",
  "introduction": "Mise en contexte camerounais en 3-4 phrases — mentionner le dualisme si pertinent.",
  "developpement": "Analyse approfondie en markdown. **Gras** pour concepts clés.",
  "positions": [
    { "titre": "Position A", "argument": "Argument fondé sur le corpus fourni" },
    { "titre": "Position B", "argument": "Argument contraire ou nuance" }
  ],
  "jurisprudence": [
    { "ref": "Cour Suprême CM — n° / CCJA n°045/2019", "apport": "Apport de cette décision" }
  ],
  "textes_applicables": ["Art. X Constitution CM", "Art. Y Acte uniforme OHADA"],
  "conclusion": "Synthèse et prise de position motivée, valable pour le Cameroun.",
  "limites": "Limites de l'analyse et points à vérifier auprès d'un avocat camerounais."
}"""
        return (
            base
            + "TYPE : Analyse doctrinale ou question abstraite de droit camerounais.\n\n"
            + f"SCHÉMA JSON :\n{schema}\n\n"
            + f"QUESTION : {question}\n\n"
            + f"CORPUS ({n_docs} document(s)) :\n{context}\n\n"
            + "Retourne le JSON complété :"
        )


# ─── Modèles ──────────────────────────────────────────────────────────────────

class CameroonAnalyzeRequest(BaseModel):
    question: str
    context_docs: int = 6
    jurisdiction_code: str | None = None  # CM | CM.SUPREME | CEMAC | COBAC
    as_of: str | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/legal-cm/overview")
async def cameroon_overview(x_user_token: str | None = Header(default=None)):
    await _require_cameroon(x_user_token)
    conn = await _conn()
    try:
        stats = await conn.fetchrow(
            """SELECT COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE source_tier='OFFICIAL') AS official,
                      COUNT(*) FILTER (WHERE type ILIKE ANY(ARRAY['%loi%','%decret%','%ordonnance%','%arrete%','%code%','%regle%'])) AS legislation,
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
               WHERE s.jurisdiction_code LIKE 'CM%' OR s.jurisdiction_code IN ('CEMAC','COBAC')
               GROUP BY s.code ORDER BY CASE WHEN s.access_mode LIKE 'OFFICIAL%' THEN 0 ELSE 1 END,s.name"""
        )
        return {
            "country": {
                "code": "CM",
                "name": "Cameroun",
                "legal_system": "Droit mixte (civil law + common law)",
                "official_languages": ["français", "anglais"],
                "regional_law": ["OHADA", "CEMAC"],
            },
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
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(400, "Identifiant de document invalide")
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
               ORDER BY provision_number,valid_from NULLS FIRST""",
            document_id,
        )
        relations = await conn.fetch(
            """SELECT r.relation_type,r.provision_ref,r.confidence_score,r.evidence,
                      c.id,c.ref,c.titre,c.type,COALESCE(c.publication_date,c.date_decision) AS legal_date,
                      c.source_url,c.source_tier
               FROM legal_document_relations r
               JOIN legal_corpus c
                 ON c.id = CASE
                     WHEN r.source_document_id=$1::uuid THEN r.target_document_id
                     ELSE r.source_document_id
                   END
               WHERE r.source_document_id=$1::uuid OR r.target_document_id=$1::uuid
               ORDER BY legal_date""",
            document_id,
        )
        return {
            "document": dict(document),
            "versions": [dict(row) for row in provisions],
            "relations": [dict(row) for row in relations],
        }
    finally:
        await conn.close()


@router.post("/legal-cm/analyze")
async def cameroon_analyze(
    req: CameroonAnalyzeRequest,
    http_request: Request,
    x_user_token: str = Header(...),
):
    """Analyse une question de droit camerounais.

    Cherche les documents CM pertinents dans le corpus (Constitution, codes nationaux,
    OHADA, CEMAC, jurisprudence Cour Suprême), puis appelle Claude avec un prompt
    qui comprend le dualisme civil/common law camerounais.
    Quota vérifié et incrémenté avant tout appel IA.
    """
    await enforce_rate_limit(
        key=f"legal-cm-analyze:{client_ip(http_request)}", limit=20, window_seconds=3600
    )

    from baobab.api.routes.accounts import check_and_increment_analyses_quota
    quota_info = await check_and_increment_analyses_quota(x_user_token)

    # Récupérer le workspace_id pour le log
    workspace_id: str | None = None
    try:
        workspace_id = quota_info.get("workspace_id")
    except Exception:
        pass

    # ── Étape 1 : recherche documentaire CM ────────────────────────────────────
    search_req = SearchRequest(
        query=req.question,
        corpus="cm",
        country_code="CM",
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

    # Enrichir avec les textes intégraux disponibles
    import html as _html_mod

    def _clean(raw: str) -> str:
        text = _html_mod.unescape(raw or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n", text)
        return re.sub(r" {2,}", " ", text).strip()

    doc_ids = [d["id"] for d in docs if d.get("id")]
    full_texts: dict[str, str] = {}
    if doc_ids:
        try:
            conn2 = await _conn()
            try:
                rows = await conn2.fetch(
                    "SELECT id, texte_integral FROM legal_corpus WHERE id = ANY($1::uuid[])",
                    [UUID(i) for i in doc_ids],
                )
                full_texts = {str(r["id"]): _clean(r["texte_integral"] or "") for r in rows}
            finally:
                await conn2.close()
        except Exception:
            pass

    context_parts = []
    for d in docs:
        ref = d["ref"] or d["titre"] or "Document"
        body = full_texts.get(d["id"], "") or (d["resume"] or "").strip()
        context_parts.append(f"--- [{ref}] ---\n{body[:1500]}")
    context = "\n\n".join(context_parts) or "Aucun document camerounais trouvé dans le corpus."

    # ── Étape 2 : classification et appel IA ───────────────────────────────────
    query_type = _classify_cm_query(req.question)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    ai_available = bool(api_key)
    analysis: str | None = None

    if ai_available:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = _build_cm_prompt(req.question, query_type, context, len(docs))
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis = message.content[0].text
        except Exception as exc:
            analysis = f"Erreur IA : {exc}"

    fiche: dict | None = None
    if analysis:
        try:
            fiche = _json.loads(analysis)
        except Exception:
            try:
                txt = analysis.strip()
                opens = txt.count("{") - txt.count("}")
                arr_opens = txt.count("[") - txt.count("]")
                lines = txt.rsplit("\n", 1)
                if len(lines) == 2 and not lines[1].strip().endswith(("}", "]", '"', ",")):
                    txt = lines[0].rstrip().rstrip(",")
                txt += "]" * max(0, arr_opens) + "}" * max(0, opens)
                fiche = _json.loads(txt)
            except Exception:
                fiche = None

    # ── Étape 3 : log analytique (best-effort) ─────────────────────────────────
    if workspace_id:
        try:
            log_conn = await _conn()
            try:
                await log_conn.execute(
                    """INSERT INTO cm_analyze_log
                       (workspace_id, question, query_type, n_docs, ai_used)
                       VALUES ($1::uuid, $2, $3, $4, $5)""",
                    workspace_id, req.question[:2000], query_type, len(docs), ai_available,
                )
            finally:
                await log_conn.close()
        except Exception:
            pass

    return {
        "question": req.question,
        "corpus": "cm",
        "response_type": query_type,
        "jurisdiction": req.jurisdiction_code or "CM",
        "context_docs": docs,
        "analysis": analysis,
        "fiche": fiche,
        "ai_available": ai_available,
        "quota": quota_info,
    }
