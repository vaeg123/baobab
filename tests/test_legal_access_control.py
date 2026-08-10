"""
Tests unitaires du contrôle d'accès sur le corpus juridique et le proxy
PISTE — cf. audit sécurité : avant correctif, /legal/search,
/legal/corpus, /legal/corpus/{id} et les endpoints legal-fr/* étaient
lisibles anonymement, et /legal/analyze pouvait être appelé sans jamais
faire vérifier ni incrémenter le quota (paywall contournable).

Ces tests exercent directement les fonctions de garde (sans base de
données réelle, indisponible dans cet environnement) en simulant la
recherche de workspace par token.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from baobab.api.main import app
from baobab.api.routes import legal, legal_fr

client = TestClient(app)


@pytest.mark.asyncio
async def test_require_active_workspace_rejects_missing_token(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        await legal._require_active_workspace(None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_active_workspace_rejects_unknown_token(monkeypatch):
    async def _fake_lookup(token):
        return None

    monkeypatch.setattr(
        "baobab.api.routes.accounts._find_workspace_by_token", _fake_lookup
    )

    with pytest.raises(HTTPException) as exc_info:
        await legal._require_active_workspace("usr_unknown")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_active_workspace_rejects_suspended_account(monkeypatch):
    async def _fake_lookup(token):
        return {"workspace_id": "ws_1", "suspended": True}

    monkeypatch.setattr(
        "baobab.api.routes.accounts._find_workspace_by_token", _fake_lookup
    )

    with pytest.raises(HTTPException) as exc_info:
        await legal._require_active_workspace("usr_valid_but_suspended")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_active_workspace_accepts_valid_active_account(monkeypatch):
    expected = {"workspace_id": "ws_1", "suspended": False}

    async def _fake_lookup(token):
        return expected

    monkeypatch.setattr(
        "baobab.api.routes.accounts._find_workspace_by_token", _fake_lookup
    )

    workspace = await legal._require_active_workspace("usr_valid")
    assert workspace == expected


def test_legifrance_resource_path_rejects_traversal_attempts():
    for malicious in ["../secret", "a/../../b", "..", "foo/../bar"]:
        with pytest.raises(HTTPException) as exc_info:
            legal_fr._validate_resource(malicious)
        assert exc_info.value.status_code == 422


def test_legifrance_resource_path_rejects_unexpected_characters():
    for malicious in ["LEGIARTI123?x=1", "code;DROP TABLE", "a b", "<script>"]:
        with pytest.raises(HTTPException):
            legal_fr._validate_resource(malicious)


def test_legifrance_resource_path_accepts_legitimate_identifiers():
    for valid in ["LEGIARTI000006419305", "code/LEGITEXT000006070721", "loi-2024-01"]:
        assert legal_fr._validate_resource(valid) == valid


# ─── Tests d'intégration HTTP (échouent avant tout accès DB) ────────────────


def test_legal_analyze_requires_x_user_token_header():
    """
    x_user_token est désormais un en-tête HTTP obligatoire : FastAPI
    rejette la requête (422) avant même d'atteindre le handler, donc
    avant tout accès base de données ou appel payant à l'API Claude.
    """
    response = client.post(
        "/api/v1/legal/analyze",
        json={"question": "Quel est le delai de declaration d'un sinistre CIMA ?"},
    )
    assert response.status_code == 422


def test_legal_search_rejects_anonymous_access():
    response = client.post(
        "/api/v1/legal/search",
        json={"query": "sinistre incendie"},
    )
    assert response.status_code == 401


def test_legal_corpus_listing_rejects_anonymous_access():
    response = client.get("/api/v1/legal/corpus")
    assert response.status_code == 401


def test_legal_corpus_document_rejects_anonymous_access():
    response = client.get("/api/v1/legal/corpus/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


def test_legal_fr_judilibre_search_rejects_anonymous_access():
    response = client.post(
        "/api/v1/legal-fr/judilibre/search",
        json={"query": "responsabilite civile"},
    )
    assert response.status_code == 401


def test_legal_fr_legifrance_consult_rejects_anonymous_access():
    response = client.post(
        "/api/v1/legal-fr/legifrance/consult/LEGIARTI000006419305",
        json={},
    )
    assert response.status_code == 401
