import pytest
from fastapi import HTTPException

from baobab.api.routes import accounts, watch


def test_basic_workspace_watch_is_limited_to_included_packs():
    workspace = {
        "plan": accounts.SubscriptionPlan.BASIC,
        "enabled_services": [],
    }
    allowed = watch._allowed_corpora(workspace)
    assert {"fr", "france", "eu", "cedh", "echr"} <= allowed
    assert "ohada" not in allowed


def test_explicit_pack_grant_extends_watch_scope():
    workspace = {
        "plan": accounts.SubscriptionPlan.BASIC,
        "enabled_services": ["ohada"],
    }
    assert "ohada" in watch._allowed_corpora(workspace)


def test_watch_rejects_corpus_outside_workspace_packs():
    workspace = {
        "plan": accounts.SubscriptionPlan.BASIC,
        "enabled_services": [],
    }
    with pytest.raises(HTTPException) as exc:
        watch._validate_requested_corpus(workspace, "cima")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_watch_feed_rejects_anonymous_access():
    with pytest.raises(HTTPException) as exc:
        await watch.watch_feed(x_user_token=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_watch_feed_only_queries_verified_non_quarantined_sources(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.sql = ""

        async def fetch(self, sql, *_params):
            self.sql = sql
            return []

        async def close(self):
            pass

    conn = FakeConnection()

    async def fake_workspace(_token, _service):
        return {
            "plan": accounts.SubscriptionPlan.BASIC,
            "enabled_services": [],
        }

    async def fake_conn():
        return conn

    monkeypatch.setattr(watch, "require_workspace_service", fake_workspace)
    monkeypatch.setattr(watch, "_conn", fake_conn)

    result = await watch.watch_feed(
        corpus="all", query=None, limit=30, x_user_token="valid"
    )

    assert result["results"] == []
    assert "COALESCE(source_url, '') ~* '^https?://'" in conn.sql
    assert "watch_quarantined" in conn.sql
