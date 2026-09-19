import pytest
from unittest.mock import AsyncMock
from baobab.api.routes import accounts
from baobab import sessions
from datetime import UTC, datetime, timedelta
from baobab.auth import hash_password, verify_password


@pytest.fixture
def workspace(monkeypatch):
    ws = dict(workspace_id="ws_security", plan="free", territory="CI",
              admin_email="admin@example.invalid", user_email="user@example.invalid",
              admin_token="synthetic-admin", user_token="synthetic-user",
              admin_password_hash=hash_password("Admin-original-123"),
              user_password_hash=hash_password("User-original-123"),
              internal_secret="must-never-be-returned", enabled_services=[])
    monkeypatch.setattr(accounts, "_list_workspaces", AsyncMock(return_value=[ws]))
    monkeypatch.setattr(accounts, "_save_workspace", AsyncMock())
    monkeypatch.setattr(accounts, "_load_workspace", AsyncMock(return_value=ws))
    monkeypatch.setattr(accounts, "_use_database", lambda: False)
    sessions._LOCAL.clear()
    monkeypatch.setattr(accounts, "_list_internal_requests", AsyncMock(return_value=[]))
    return ws


@pytest.mark.asyncio
async def test_workspace_responses_only_expose_public_fields(workspace):
    for render in (accounts._public_workspace, accounts._admin_workspace):
        result = await render(workspace)
        assert result["workspace_id"] == workspace["workspace_id"]
        assert not result.get("admin_token") and not result.get("user_token")
        assert "admin_password_hash" not in result
        assert "user_password_hash" not in result
        assert "internal_secret" not in result


@pytest.mark.asyncio
async def test_user_cannot_replace_administrator_password(workspace):
    original = workspace["admin_password_hash"]
    old_token = await sessions.issue(workspace, "client")
    result = await accounts.client_change_password(
        accounts.ChangePassword(current_password="User-original-123", new_password="User-selected-456"),
        x_access_token=old_token,
    )
    assert await sessions.resolve(old_token) is None
    assert await sessions.resolve(result["token"]) is not None
    assert workspace["admin_password_hash"] == original
    assert not verify_password("User-selected-456", workspace["admin_password_hash"])
    assert verify_password("User-selected-456", workspace["user_password_hash"])


@pytest.mark.asyncio
async def test_sessions_expire_revoke_and_reject_legacy_tokens(workspace):
    assert await sessions.resolve(workspace["user_token"]) is None
    token = await sessions.issue(workspace, "client")
    assert token not in str(sessions._LOCAL)
    assert (await sessions.resolve(token))[1] == "client"
    with pytest.raises(Exception) as failure:
        await accounts._require_workspace_admin(workspace["workspace_id"], token)
    assert failure.value.status_code == 403
    sessions._LOCAL[sessions.digest(token)]["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert await sessions.resolve(token) is None
    token = await sessions.issue(workspace, "admin")
    await sessions.revoke(token)
    assert await sessions.resolve(token) is None


@pytest.mark.asyncio
async def test_suspension_and_password_reset_revoke_existing_sessions(workspace):
    token = await sessions.issue(workspace, "admin")
    workspace["suspended"] = True
    assert await sessions.resolve(token) is None
    workspace["suspended"] = False
    workspace["admin_password_hash"] = hash_password("Reset-password-456")
    assert await sessions.resolve(token) is None


@pytest.mark.asyncio
async def test_client_session_cannot_cross_workspace(workspace):
    token = await sessions.issue(workspace, "client")
    with pytest.raises(Exception) as failure:
        await accounts._require_workspace_access("another-workspace", token)
    assert failure.value.status_code == 401
