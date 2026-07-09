"""
Connecteur PISTE — Droit français dans BAOBAB.

Routes :
  GET  /api/v1/legal-fr/status
  POST /api/v1/legal-fr/judilibre/search
  GET  /api/v1/legal-fr/judilibre/decision?id=...
  GET  /api/v1/legal-fr/judilibre/taxonomy
  POST /api/v1/legal-fr/legifrance/search
  POST /api/v1/legal-fr/legifrance/consult/{resource}

Sécurité : les credentials PISTE restent côté serveur.
"""

import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["droit-français"])

# ── Config PISTE ──────────────────────────────────────────────────────────────
PISTE_TOKEN_URL    = os.environ.get("PISTE_TOKEN_URL", "https://sandbox-oauth.piste.gouv.fr/api/oauth/token")
PISTE_CLIENT_ID    = os.environ.get("PISTE_CLIENT_ID", "")
PISTE_CLIENT_SECRET= os.environ.get("PISTE_CLIENT_SECRET", "")
PISTE_SCOPE        = os.environ.get("PISTE_SCOPE", "openid")

JUDILIBRE_BASE = os.environ.get("JUDILIBRE_API_BASE_URL", "https://sandbox-api.piste.gouv.fr/cassation/judilibre/v1.0")
LEGIFRANCE_BASE= os.environ.get("LEGIFRANCE_API_BASE_URL", "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app")

# ── Cache token en mémoire ────────────────────────────────────────────────────
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0}


async def _get_token() -> str:
    if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 60:
        return _token_cache["access_token"]

    if not PISTE_CLIENT_ID or not PISTE_CLIENT_SECRET:
        raise HTTPException(503, "PISTE non configuré (PISTE_CLIENT_ID / PISTE_CLIENT_SECRET manquants)")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                PISTE_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": PISTE_CLIENT_ID,
                    "client_secret": PISTE_CLIENT_SECRET,
                    "scope": PISTE_SCOPE,
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, f"Impossible de joindre PISTE OAuth ({PISTE_TOKEN_URL}): {exc}")

    if r.status_code != 200:
        raise HTTPException(502, f"Erreur token PISTE {r.status_code}: {r.text[:300]}")

    payload = r.json()
    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = time.time() + payload.get("expires_in", 300)
    return _token_cache["access_token"]


async def _piste_get(base: str, path: str, params: dict | None = None) -> Any:
    token = await _get_token()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{base}{path}",
                params={k: v for k, v in (params or {}).items() if v is not None},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, f"Erreur réseau PISTE GET {path}: {exc}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"PISTE GET {path} → {r.status_code}: {r.text[:300]}")
    return r.json()


async def _piste_post(base: str, path: str, body: dict) -> Any:
    token = await _get_token()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{base}{path}",
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, f"Erreur réseau PISTE POST {path}: {exc}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"PISTE POST {path} → {r.status_code}: {r.text[:300]}")
    return r.json()


# ── DTOs ──────────────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    page: int = 0
    page_size: int = 10
    type: str | None = None         # ex: "arret", "loi", "CODE"
    date_start: str | None = None   # YYYY-MM-DD
    date_end: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/legal-fr/status")
async def status():
    """Statut de la connexion PISTE — tente réellement d'obtenir un token."""
    configured = bool(PISTE_CLIENT_ID and PISTE_CLIENT_SECRET)
    token_ok = False
    token_error = None

    if configured:
        try:
            await _get_token()
            token_ok = True
        except HTTPException as exc:
            token_error = exc.detail
        except Exception as exc:
            token_error = str(exc)

    return {
        "configured": configured,
        "token_ok": token_ok,
        "token_error": token_error,
        "env": "sandbox" if "sandbox" in JUDILIBRE_BASE else "production",
        "judilibre_base": JUDILIBRE_BASE,
        "legifrance_base": LEGIFRANCE_BASE,
    }


# ─── Judilibre ───────────────────────────────────────────────────────────────

@router.post("/legal-fr/judilibre/search")
async def judilibre_search(req: SearchRequest):
    """Recherche dans Judilibre (décisions Cour de Cassation + juridictions)."""
    return await _piste_get(JUDILIBRE_BASE, "/search", {
        "query": req.query,
        "page": req.page,
        "page_size": req.page_size,
        "type": req.type,
        "date_start": req.date_start,
        "date_end": req.date_end,
    })


@router.get("/legal-fr/judilibre/decision")
async def judilibre_decision(id: str = Query(...)):
    """Texte intégral d'une décision Judilibre."""
    return await _piste_get(JUDILIBRE_BASE, "/decision", {"id": id})


@router.get("/legal-fr/judilibre/taxonomy")
async def judilibre_taxonomy():
    """Taxonomie Judilibre (juridictions, types, chambres…)."""
    return await _piste_get(JUDILIBRE_BASE, "/taxonomy")


@router.get("/legal-fr/judilibre/stats")
async def judilibre_stats():
    """Statistiques du corpus Judilibre."""
    return await _piste_get(JUDILIBRE_BASE, "/stats")


# ─── Légifrance ──────────────────────────────────────────────────────────────

@router.post("/legal-fr/legifrance/search")
async def legifrance_search(req: SearchRequest):
    """Recherche dans Légifrance (codes, lois, règlements, jurisprudence)."""
    filtres = []
    if req.type:
        filtres.append({"facette": "NATURE", "valeurs": [req.type]})
    if req.date_start:
        filtres.append({"facette": "DATE_SIGNATURE", "valeurs": [f"{req.date_start}:"]})

    return await _piste_post(LEGIFRANCE_BASE, "/search", {
        "recherche": {
            "champs": [{
                "typeChamp": "ALL",
                "criteres": [{"typeRecherche": "UN_DES_MOTS", "valeur": req.query, "operateur": "ET"}],
                "operateur": "ET",
            }],
            "filtres": filtres,
            "operateur": "ET",
            "pageNumber": req.page + 1,
            "pageSize": req.page_size,
            "sort": "PERTINENCE",
        }
    })


@router.post("/legal-fr/legifrance/consult/{resource}")
async def legifrance_consult(resource: str, body: dict):
    """Consultation d'un texte Légifrance (loi, code, article…)."""
    return await _piste_post(LEGIFRANCE_BASE, f"/consult/{resource}", body)
