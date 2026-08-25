import pytest
from fastapi import HTTPException

from baobab.api.routes import accounts


@pytest.mark.asyncio
async def test_service_requires_a_user_token():
    with pytest.raises(HTTPException) as exc:
        await accounts.require_workspace_service(None, "cima")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_free_workspace_cannot_use_specialist_vertical(monkeypatch):
    async def find_workspace(_token):
        return {"plan": accounts.SubscriptionPlan.FREE, "enabled_services": [], "suspended": False}

    monkeypatch.setattr(accounts, "_find_workspace_by_token", find_workspace)
    with pytest.raises(HTTPException) as exc:
        await accounts.require_workspace_service("usr_valid", "ohada")
    assert exc.value.status_code == 403
    assert exc.value.detail["upgrade_required"] is True


@pytest.mark.asyncio
async def test_explicit_service_grant_allows_access(monkeypatch):
    workspace = {"plan": accounts.SubscriptionPlan.FREE, "enabled_services": ["bceao"], "suspended": False}

    async def find_workspace(_token):
        return workspace

    monkeypatch.setattr(accounts, "_find_workspace_by_token", find_workspace)
    assert await accounts.require_workspace_service("usr_valid", "bceao") == workspace


@pytest.mark.asyncio
async def test_premium_all_verticals_allows_access(monkeypatch):
    workspace = {"plan": accounts.SubscriptionPlan.PREMIUM, "enabled_services": [], "suspended": False}

    async def find_workspace(_token):
        return workspace

    monkeypatch.setattr(accounts, "_find_workspace_by_token", find_workspace)
    assert await accounts.require_workspace_service("usr_valid", "cima") == workspace


@pytest.mark.asyncio
async def test_suspended_workspace_is_rejected(monkeypatch):
    async def find_workspace(_token):
        return {"plan": accounts.SubscriptionPlan.PREMIUM, "suspended": True}

    monkeypatch.setattr(accounts, "_find_workspace_by_token", find_workspace)
    with pytest.raises(HTTPException) as exc:
        await accounts.require_workspace_service("usr_valid", "cima")
    assert exc.value.status_code == 403
