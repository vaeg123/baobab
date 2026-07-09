"""
Routes API soumissions utilisateur — documents légaux à valider.

POST   /api/v1/submissions              — soumettre un document (PDF ou texte)
GET    /api/v1/submissions              — liste des soumissions [admin]
GET    /api/v1/submissions/{id}         — détail d'une soumission [admin]
PATCH  /api/v1/submissions/{id}/approve — approuver + intégrer au corpus [admin]
PATCH  /api/v1/submissions/{id}/reject  — rejeter [admin]
GET    /api/v1/submissions/stats        — statistiques soumissions [admin]
"""

import io
import json
import os
from datetime import datetime, timezone
from typing import Literal

import asyncpg
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(tags=["submissions"])

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://baobab:baobab@localhost:5432/baobab")
ADMIN_KEY = os.environ.get("BAOBAB_ADMIN_KEY", "")

CORPUS_VALUES = {"cima", "ohada", "ci"}
TYPE_VALUES = {
    "arret_ccja", "decision_crca", "decision_tca", "acte_uniforme",
    "loi", "doctrine", "these", "synthese", "autre",
}


# ─── Auth admin ───────────────────────────────────────────────────────────────

def _require_admin(x_admin_key: str | None):
    if not ADMIN_KEY:
        raise HTTPException(503, "BAOBAB_ADMIN_KEY non configurée sur le serveur")
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Clé admin invalide")


# ─── DB helper ────────────────────────────────────────────────────────────────

async def _conn():
    return await asyncpg.connect(DATABASE_URL)


# ─── Extraction PDF ───────────────────────────────────────────────────────────

def _extract_pdf_text(data: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = pdf.pages[:20]
            text = "\n".join(p.extract_text() or "" for p in pages)
            return text[:80000].strip()
    except Exception as exc:
        raise HTTPException(422, f"Impossible de lire le PDF : {exc}")


# ─── Analyse IA ───────────────────────────────────────────────────────────────

_IA_PROMPT = """Tu es un expert en droit africain (CIMA, OHADA, droit ivoirien).
Analyse le document juridique ci-dessous et retourne UNIQUEMENT un objet JSON valide avec ces champs :

{
  "titre": "titre officiel du document",
  "ref": "référence/numéro (ex: Arrêt N°012/2024)",
  "date_str": "date en format YYYY-MM-DD si trouvée, sinon chaîne brute",
  "juridiction": "juridiction émettrice (ex: CCJA, CRCA, TCA Abidjan)",
  "pays": "pays concerné",
  "parties": {"demandeur": "...", "defenseur": "..."},
  "domaine": "domaine juridique principal",
  "mots_cles": ["mot1", "mot2", ...],
  "resume": "résumé factuel en 3-5 phrases",
  "articles_cites": ["AU OHADA art. X", ...],
  "sanction": "solution/dispositif prononcé si applicable",
  "is_legal_document": true ou false,
  "score_confiance": 0.0 à 1.0,
  "note_ia": "remarques sur la qualité ou des anomalies détectées"
}

CORPUS DÉCLARÉ : {corpus}
TYPE DÉCLARÉ : {type}

DOCUMENT (extrait) :
{texte}

Retourne uniquement le JSON, sans markdown, sans commentaire."""


async def _analyze_with_claude(texte: str, corpus: str, doc_type: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic()
        snippet = texte[:12000]
        prompt = _IA_PROMPT.format(corpus=corpus, type=doc_type, texte=snippet)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Nettoyer si enveloppé dans des backticks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"is_legal_document": True, "score_confiance": 0.5, "note_ia": "Parsing JSON échoué"}
    except Exception as exc:
        return {"is_legal_document": True, "score_confiance": 0.5, "note_ia": str(exc)}


# ─── Modèles ──────────────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    # Permet à l'admin de corriger les métadonnées IA avant intégration
    ref: str | None = None
    titre: str | None = None
    date_str: str | None = None
    juridiction: str | None = None
    pays: str | None = None
    domaine: str | None = None
    mots_cles: list[str] | None = None
    resume: str | None = None
    articles_cites: list[str] | None = None
    sanction: str | None = None
    review_note: str | None = None


class RejectRequest(BaseModel):
    review_note: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/submissions", status_code=201)
async def submit_document(
    corpus: str = Form(..., description="cima | ohada | ci"),
    type: str = Form("autre"),
    titre_user: str = Form(""),
    date_str: str = Form(""),
    notes: str = Form(""),
    submitter_name: str = Form(""),
    submitter_email: str = Form(""),
    texte_colle: str = Form("", description="Texte collé directement si pas de PDF"),
    file: UploadFile | None = File(None),
):
    """
    Soumettre un document juridique pour intégration au corpus BAOBAB.
    Accepte un PDF (extraction automatique) ou un texte collé.
    Une analyse IA est lancée automatiquement. Statut initial : pending.
    """
    if corpus not in CORPUS_VALUES:
        raise HTTPException(422, f"corpus doit être : {', '.join(CORPUS_VALUES)}")

    # Extraction du texte
    texte = ""
    if file and file.filename:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(422, "Seuls les fichiers PDF sont acceptés")
        data = await file.read()
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "PDF trop volumineux (max 20 Mo)")
        texte = _extract_pdf_text(data)
    elif texte_colle.strip():
        texte = texte_colle.strip()[:80000]
    else:
        raise HTTPException(422, "Fournissez un fichier PDF ou du texte collé")

    if len(texte) < 100:
        raise HTTPException(422, "Texte extrait insuffisant (moins de 100 caractères)")

    # Analyse IA
    meta_ia = await _analyze_with_claude(texte, corpus, type)
    score = float(meta_ia.get("score_confiance", 0.5))

    # Insertion en base
    conn = await _conn()
    try:
        sub_id = await conn.fetchval(
            """INSERT INTO submissions
               (corpus, type, titre_user, date_str, notes,
                submitter_name, submitter_email,
                texte_integral, metadata_ia, score_confiance)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
               RETURNING id""",
            corpus, type, titre_user, date_str, notes,
            submitter_name, submitter_email,
            texte, json.dumps(meta_ia, ensure_ascii=False), score,
        )
    finally:
        await conn.close()

    return {
        "id": str(sub_id),
        "statut": "pending",
        "score_confiance": score,
        "is_legal_document": meta_ia.get("is_legal_document", True),
        "titre_detecte": meta_ia.get("titre") or titre_user,
        "ref_detectee": meta_ia.get("ref"),
        "message": "Document soumis. Il sera examiné par l'équipe BAOBAB avant intégration.",
    }


@router.get("/submissions")
async def list_submissions(
    statut: Literal["pending", "approved", "rejected", "all"] = "pending",
    corpus: str | None = None,
    limit: int = 50,
    offset: int = 0,
    x_admin_key: str | None = Header(None),
):
    """[Admin] Liste des soumissions avec filtres."""
    _require_admin(x_admin_key)

    conn = await _conn()
    try:
        conditions = ["1=1"]
        params: list = []
        p = 1

        if statut != "all":
            conditions.append(f"statut = ${p}"); params.append(statut); p += 1
        if corpus:
            conditions.append(f"corpus = ${p}"); params.append(corpus); p += 1

        where = " AND ".join(conditions)
        rows = await conn.fetch(
            f"""SELECT id, corpus, type, titre_user, date_str,
                       submitter_name, submitter_email,
                       score_confiance, statut, reviewed_at, corpus_id,
                       created_at,
                       metadata_ia->>'titre' AS titre_ia,
                       metadata_ia->>'ref' AS ref_ia,
                       metadata_ia->>'domaine' AS domaine_ia,
                       metadata_ia->>'is_legal_document' AS is_legal,
                       metadata_ia->>'note_ia' AS note_ia
                FROM submissions
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${p} OFFSET ${p+1}""",
            *params, limit, offset,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM submissions WHERE {where}", *params)

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": str(r["id"]),
                    "corpus": r["corpus"],
                    "type": r["type"],
                    "titre": r["titre_ia"] or r["titre_user"] or "",
                    "ref": r["ref_ia"] or "",
                    "domaine": r["domaine_ia"] or "",
                    "is_legal_document": r["is_legal"] != "false",
                    "score_confiance": r["score_confiance"],
                    "submitter": r["submitter_name"] or r["submitter_email"] or "anonyme",
                    "statut": r["statut"],
                    "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None,
                    "corpus_id": str(r["corpus_id"]) if r["corpus_id"] else None,
                    "created_at": str(r["created_at"]),
                    "note_ia": r["note_ia"] or "",
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/submissions/stats")
async def submissions_stats(x_admin_key: str | None = Header(None)):
    """[Admin] Statistiques des soumissions."""
    _require_admin(x_admin_key)
    conn = await _conn()
    try:
        by_statut = await conn.fetch(
            "SELECT statut, COUNT(*) as n FROM submissions GROUP BY statut"
        )
        by_corpus = await conn.fetch(
            "SELECT corpus, statut, COUNT(*) as n FROM submissions GROUP BY corpus, statut ORDER BY corpus"
        )
        avg_score = await conn.fetchval(
            "SELECT AVG(score_confiance) FROM submissions WHERE statut='pending'"
        )
        return {
            "by_statut": {r["statut"]: r["n"] for r in by_statut},
            "by_corpus": [{"corpus": r["corpus"], "statut": r["statut"], "count": r["n"]} for r in by_corpus],
            "avg_score_pending": round(float(avg_score or 0), 2),
        }
    finally:
        await conn.close()


@router.get("/submissions/{sub_id}")
async def get_submission(sub_id: str, x_admin_key: str | None = Header(None)):
    """[Admin] Détail complet d'une soumission (texte + métadonnées IA)."""
    _require_admin(x_admin_key)
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT * FROM submissions WHERE id = $1", sub_id)
        if not row:
            raise HTTPException(404, f"Soumission {sub_id} introuvable")
        return {
            "id": str(row["id"]),
            "corpus": row["corpus"],
            "type": row["type"],
            "titre_user": row["titre_user"],
            "date_str": row["date_str"],
            "notes": row["notes"],
            "submitter_name": row["submitter_name"],
            "submitter_email": row["submitter_email"],
            "texte_integral": row["texte_integral"],
            "metadata_ia": json.loads(row["metadata_ia"] or "{}"),
            "score_confiance": row["score_confiance"],
            "statut": row["statut"],
            "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] else None,
            "review_note": row["review_note"],
            "corpus_id": str(row["corpus_id"]) if row["corpus_id"] else None,
            "created_at": str(row["created_at"]),
        }
    finally:
        await conn.close()


@router.patch("/submissions/{sub_id}/approve")
async def approve_submission(
    sub_id: str,
    req: ApproveRequest,
    x_admin_key: str | None = Header(None),
):
    """
    [Admin] Approuver une soumission et l'intégrer dans legal_corpus.
    Les champs de ApproveRequest permettent de corriger les métadonnées IA.
    """
    _require_admin(x_admin_key)
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT * FROM submissions WHERE id = $1", sub_id)
        if not row:
            raise HTTPException(404, f"Soumission {sub_id} introuvable")
        if row["statut"] == "approved":
            raise HTTPException(409, "Soumission déjà approuvée")

        meta = json.loads(row["metadata_ia"] or "{}")

        # Champs finaux = corrections admin ou fallback IA ou fallback user
        def pick(admin_val, ia_key, user_val=""):
            return admin_val if admin_val is not None else (meta.get(ia_key) or user_val or "")

        titre      = pick(req.titre, "titre", row["titre_user"])
        ref        = pick(req.ref, "ref")
        date_str   = pick(req.date_str, "date_str", row["date_str"])
        juridiction = pick(req.juridiction, "juridiction")
        pays       = pick(req.pays, "pays")
        domaine    = pick(req.domaine, "domaine")
        resume     = pick(req.resume, "resume")
        sanction   = pick(req.sanction, "sanction")
        mots_cles  = req.mots_cles if req.mots_cles is not None else meta.get("mots_cles", [])
        arts_cites = req.articles_cites if req.articles_cites is not None else meta.get("articles_cites", [])
        parties    = meta.get("parties", {})

        # Parse date
        from baobab.pipeline.ingest_corpus import parse_date
        date_dec = parse_date(date_str)

        corpus_id = await conn.fetchval(
            """INSERT INTO legal_corpus
               (ref, type, corpus, juridiction, titre, date_decision,
                parties, pays, domaine, resume, texte_integral,
                mots_cles, sanction, articles_cites,
                metadata)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
               RETURNING id""",
            ref, row["type"], row["corpus"], juridiction, titre, date_dec,
            json.dumps(parties, ensure_ascii=False), pays, domaine, resume,
            row["texte_integral"],
            mots_cles, sanction, arts_cites,
            json.dumps({"source": "submission", "submission_id": sub_id, "submitter": row["submitter_email"]},
                       ensure_ascii=False),
        )

        await conn.execute(
            """UPDATE submissions
               SET statut='approved', reviewed_at=$1, review_note=$2, corpus_id=$3
               WHERE id=$4""",
            datetime.now(timezone.utc), req.review_note, corpus_id, sub_id,
        )

        return {
            "id": sub_id,
            "statut": "approved",
            "corpus_id": str(corpus_id),
            "message": f"Document intégré dans legal_corpus (id={corpus_id})",
        }
    finally:
        await conn.close()


@router.patch("/submissions/{sub_id}/reject")
async def reject_submission(
    sub_id: str,
    req: RejectRequest,
    x_admin_key: str | None = Header(None),
):
    """[Admin] Rejeter une soumission avec un motif."""
    _require_admin(x_admin_key)
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT id, statut FROM submissions WHERE id = $1", sub_id)
        if not row:
            raise HTTPException(404, f"Soumission {sub_id} introuvable")
        if row["statut"] == "rejected":
            raise HTTPException(409, "Soumission déjà rejetée")

        await conn.execute(
            """UPDATE submissions
               SET statut='rejected', reviewed_at=$1, review_note=$2
               WHERE id=$3""",
            datetime.now(timezone.utc), req.review_note, sub_id,
        )
        return {"id": sub_id, "statut": "rejected"}
    finally:
        await conn.close()
