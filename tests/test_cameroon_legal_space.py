from datetime import date

import pytest

from baobab.api.routes import cameroon


class FakeConnection:
    def __init__(self):
        self.fetch_sql: list[str] = []
        self.fetch_params: list[tuple] = []

    async def fetchrow(self, sql, *_params):
        if "COUNT(*) AS total" in sql:
            return {"total": 0, "official": 0, "legislation": 0, "case_law": 0,
                    "latest_legal_date": None, "latest_detection": None}
        return None

    async def fetch(self, sql, *_params):
        self.fetch_sql.append(sql)
        self.fetch_params.append(_params)
        return []

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_overview_exposes_real_coverage_and_source_registry(monkeypatch):
    conn = FakeConnection()

    async def allow(_token):
        return {"workspace_id": "ws_test"}

    async def fake_conn():
        return conn

    monkeypatch.setattr(cameroon, "_require_cameroon", allow)
    monkeypatch.setattr(cameroon, "_conn", fake_conn)
    result = await cameroon.cameroon_overview("token")
    assert result["country"]["code"] == "CM"
    assert result["coverage"]["total"] == 0
    assert any("document original" in rule for rule in result["principles"])
    assert any("legal_sources" in sql for sql in conn.fetch_sql)


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
