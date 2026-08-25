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
