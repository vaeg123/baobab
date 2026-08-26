from datetime import date

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
        corpus="all",
        query=None,
        source_scope="official",
        since_days=None,
        limit=30,
        x_user_token="valid",
    )

    assert result["results"] == []
    assert "COALESCE(source_url, '') ~* '^https?://'" in conn.sql
    assert "COALESCE(detected_at::date, created_at::date, date_decision)" in conn.sql
    assert "watch_quarantined" in conn.sql
    assert "biblio.ohada.org" in conn.sql
    assert result["methodology"]["automatic_email_notifications"] is watch.settings.watch_email_delivery_enabled


@pytest.mark.asyncio
async def test_year_precision_uses_detection_date_for_recent_period(monkeypatch):
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
        return {"plan": accounts.SubscriptionPlan.PREMIUM, "enabled_services": []}

    async def fake_conn():
        return conn

    monkeypatch.setattr(watch, "require_workspace_service", fake_workspace)
    monkeypatch.setattr(watch, "_conn", fake_conn)
    await watch.watch_feed(
        corpus="all", query=None, source_scope="official", since_days=90,
        limit=30, x_user_token="valid",
    )
    assert "EXTRACT(MONTH FROM date_decision)=1" in conn.sql
    assert "detected_at::date" in conn.sql
    assert "CURRENT_DATE - $" in conn.sql
    assert "::int" in conn.sql


@pytest.mark.parametrize(
    ("url", "tier", "code"),
    [
        ("https://www.ohada.org/journal-officiel/", "OFFICIAL", "OHADA.OFFICIAL"),
        ("https://biblio.ohada.org/notice/42", "OFFICIAL", "OHADA.BIBLIO"),
        ("https://cima-afrique.org/reglement/1", "OFFICIAL", "CIMA.OFFICIAL"),
        ("https://juricaf.org/arret/1", "INSTITUTIONAL_AGGREGATOR", "AGG.JURICAF"),
        ("https://ohadalegis.com/article/1", "SECONDARY", "PUB.OHADALEGIS"),
        ("https://example.com/document", "UNVERIFIED", None),
    ],
)
def test_source_classification_is_explicit(url, tier, code):
    source = watch.classify_source(url)
    assert source["tier"] == tier
    assert source["code"] == code
    assert source["verified"] is (tier == "OFFICIAL")


def test_source_classification_rejects_deceptive_subdomains():
    source = watch.classify_source("https://ohada.org.example.com/faux-document")
    assert source["tier"] == "UNVERIFIED"
    assert source["verified"] is False


def test_france_filter_includes_database_alias():
    assert watch.CORPUS_FILTERS["france"] == {"fr", "france"}


def test_inferred_january_first_date_is_presented_as_year_only():
    row = {
        "publication_date": None,
        "date_decision": date(2025, 1, 1),
        "legal_status": "UNKNOWN",
        "impact_level": "TO_QUALIFY",
        "impact_summary": None,
        "change_type": None,
        "editorial_status": "SOURCE_VERIFIED",
    }
    qualification = watch._document_qualification(row, {"verified": True})
    assert qualification["date_precision"] == "YEAR"
    assert qualification["display_date"] == "2025"


def test_precise_decision_date_keeps_day_precision():
    row = {
        "publication_date": None,
        "date_decision": date(2025, 3, 24),
        "legal_status": "UNKNOWN",
        "impact_level": "TO_QUALIFY",
        "impact_summary": None,
        "change_type": None,
        "editorial_status": "SOURCE_VERIFIED",
    }
    qualification = watch._document_qualification(row, {"verified": True})
    assert qualification["date_precision"] == "DAY"
    assert qualification["display_date"] == "2025-03-24"
