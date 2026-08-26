from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from baobab.api.routes import cameroon
from baobab.api.routes.cameroon import _classify_cm_query


class FakeConnection:
    def __init__(self):
        self.fetch_sql: list[str] = []
        self.fetch_params: list[tuple] = []
        self.execute_sql: list[str] = []

    async def fetchrow(self, sql, *_params):
        if "COUNT(*) AS total" in sql:
            return {
                "total": 7, "official": 5, "legislation": 6, "case_law": 1,
                "latest_legal_date": date(2016, 7, 12), "latest_detection": None,
            }
        return None

    async def fetch(self, sql, *_params):
        self.fetch_sql.append(sql)
        self.fetch_params.append(_params)
        return []

    async def execute(self, sql, *_params):
        self.execute_sql.append(sql)

    async def close(self):
        pass


# ─── Overview ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_exposes_coverage_and_source_registry(monkeypatch):
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)

    result = await cameroon.cameroon_overview("token")

    assert result["country"]["code"] == "CM"
    assert result["country"]["legal_system"] == "Droit mixte (civil law + common law)"
    assert result["country"]["official_languages"] == ["français", "anglais"]
    assert result["coverage"]["total"] == 7
    assert any("document original" in rule for rule in result["principles"])
    assert any("legal_sources" in sql for sql in conn.fetch_sql)
    # La requête sources doit couvrir CEMAC et COBAC
    assert any("CEMAC" in sql or "COBAC" in sql for sql in conn.fetch_sql)


# ─── Timeline ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_is_country_scoped_and_temporal(monkeypatch):
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)

    result = await cameroon.cameroon_timeline(
        query="avocat", document_type="loi", from_year=1990, to_year=2026,
        limit=60, x_user_token="token",
    )

    sql = conn.fetch_sql[0]
    assert "country_code='CM'" in sql
    assert "ORDER BY legal_date DESC" in sql
    assert result == {"view": "timeline", "results": [], "total": 0}
    assert date(1990, 1, 1) in conn.fetch_params[0]
    assert date(2026, 12, 31) in conn.fetch_params[0]


@pytest.mark.asyncio
async def test_timeline_without_filters_returns_all_cm_docs(monkeypatch):
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)

    result = await cameroon.cameroon_timeline(
        query=None, document_type=None, from_year=None, to_year=None,
        limit=60, x_user_token="token",
    )

    sql = conn.fetch_sql[0]
    assert "country_code='CM'" in sql
    assert result["view"] == "timeline"


# ─── Document evolution ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_document_evolution_rejects_invalid_uuid(monkeypatch):
    async def allow(_token):
        return {"workspace_id": "ws_test"}

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)

    with pytest.raises(HTTPException) as exc:
        await cameroon.document_evolution("not-a-uuid", x_user_token="token")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_document_evolution_returns_empty_for_missing_doc(monkeypatch):
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)

    result = await cameroon.document_evolution(
        "00000000-0000-0000-0000-000000000000", x_user_token="token"
    )
    assert result == {"document": None, "versions": [], "relations": []}


# ─── Query classifier ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("question,expected", [
    ("Arrêt de la Cour Suprême n° 12/2023", "arret"),
    ("Jugement TGI Yaoundé du 15 mars 2024", "arret"),
    ("Décision COBAC n°2022-001 sur les réserves obligatoires", "arret"),
    ("Art. 134 Code pénal camerounais — corruption", "loi"),
    ("Loi N°2016/007 portant Code pénal", "loi"),
    ("Acte uniforme OHADA sur les sociétés commerciales", "loi"),
    ("Comment licencier un employé au Cameroun ?", "question"),
    ("Quels sont les délais de préavis selon le Code du travail CM ?", "question"),
    ("Quelle est la procédure d'immatriculation au RCCM à Douala ?", "question"),
    ("Analyse comparative civil law / common law camerounais", "analyse"),
    ("Impact de la décentralisation sur le droit administratif CM", "analyse"),
])
def test_classify_cm_query(question, expected):
    assert _classify_cm_query(question) == expected


# ─── Analyze endpoint ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_requires_auth_token(monkeypatch):
    """Le token est obligatoire (Header(...))."""
    from fastapi.testclient import TestClient
    from baobab.api.main import app

    client = TestClient(app)
    response = client.post("/api/v1/legal-cm/analyze", json={"question": "test"})
    # 422 : champ obligatoire manquant ou 403 : accès refusé
    assert response.status_code in (403, 422)


@pytest.mark.asyncio
async def test_analyze_searches_cm_corpus_and_logs(monkeypatch):
    """L'analyze cherche dans corpus='cm', log la requête, retourne une structure cohérente."""
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_quota(_token):
        return {"remaining": 25, "limit": 30, "workspace_id": "00000000-0000-0000-0000-000000000001"}

    async def fake_search(req):
        assert req.corpus == "cm"
        assert req.country_code == "CM"
        return {"results": [], "total": 0}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)

    import baobab.api.routes.accounts as accounts_mod
    monkeypatch.setattr(accounts_mod, "check_and_increment_analyses_quota", fake_quota)

    import baobab.api.routes.cameroon as cam_mod
    monkeypatch.setattr(cam_mod, "_search_corpus_impl", fake_search)
    monkeypatch.setattr(cam_mod, "enforce_rate_limit", AsyncMock())

    req = cameroon.CameroonAnalyzeRequest(question="Comment fonctionne la garde à vue au Cameroun ?")
    fake_request = MagicMock()
    fake_request.client = MagicMock()
    fake_request.client.host = "127.0.0.1"
    fake_request.headers = {}

    result = await cameroon.cameroon_analyze(req, fake_request, x_user_token="tok")

    assert result["corpus"] == "cm"
    assert result["response_type"] == "question"
    assert result["question"] == req.question
    assert result["jurisdiction"] == "CM"
    assert result["quota"]["remaining"] == 25
    # Le log a été tenté (INSERT INTO cm_analyze_log)
    assert any("cm_analyze_log" in sql for sql in conn.execute_sql)
