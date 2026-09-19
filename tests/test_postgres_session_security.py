"""Optional integration test restricted to a disposable local security database."""
import os
import json
from baobab.auth import hash_password, verify_password
from urllib.parse import urlparse
from unittest.mock import AsyncMock
import asyncpg
import pytest
from baobab import sessions
from baobab.api.routes import accounts

@pytest.mark.asyncio
async def test_sessions_survive_worker_restart_and_revoke_in_postgres(monkeypatch):
    url = os.getenv("BAOBAB_SECURITY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated local PostgreSQL security database not configured")
    parsed = urlparse(url)
    assert parsed.hostname in ("localhost", "127.0.0.1")
    assert parsed.path.startswith("/baobab_security_test_")
    async def connect():
        return await asyncpg.connect(url)
    monkeypatch.setattr(accounts, "_connect_db", connect)
    monkeypatch.setattr(accounts, "_use_database", lambda: True)
    workspace = {"workspace_id": "synthetic-session-test", "user_password_hash": "synthetic-hash", "user_token": "synthetic-seed"}
    monkeypatch.setattr(accounts, "_load_workspace", AsyncMock(return_value=workspace))
    monkeypatch.setattr(sessions, "_ready", False)
    token = await sessions.issue(workspace, "client")
    sessions._LOCAL.clear()
    assert (await sessions.resolve(token))[1] == "client"
    conn = await connect()
    try:
        row = await conn.fetchrow("SELECT * FROM account_sessions WHERE token_hash=$1", sessions.digest(token))
        assert token not in str(dict(row))
        await sessions.revoke(token)
        assert await sessions.resolve(token) is None
        expiring = await sessions.issue(workspace, "client")
        await conn.execute("UPDATE account_sessions SET expires_at=NOW()-INTERVAL '1 second' WHERE token_hash=$1", sessions.digest(expiring))
        assert await sessions.resolve(expiring) is None
        reset = await sessions.issue(workspace, "client")
        workspace["user_password_hash"] = "new-credentials"
        assert await sessions.resolve(reset) is None
        await conn.execute("CREATE TABLE IF NOT EXISTS account_workspaces (workspace_id TEXT PRIMARY KEY, data JSONB NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW())")
        workspace.update(user_password_hash=hash_password("User-original-123"), admin_password_hash=hash_password("Admin-original-123"))
        await conn.execute("INSERT INTO account_workspaces(workspace_id,data) VALUES($1,$2::jsonb) ON CONFLICT (workspace_id) DO UPDATE SET data=EXCLUDED.data", workspace["workspace_id"], json.dumps(workspace))
        async def load_workspace(workspace_id):
            value = await conn.fetchval("SELECT data FROM account_workspaces WHERE workspace_id=$1", workspace_id)
            return json.loads(value) if isinstance(value, str) else value
        monkeypatch.setattr(accounts, "_load_workspace", load_workspace)
        current = await sessions.issue(workspace, "client")
        result = await accounts.client_change_password(accounts.ChangePassword(current_password="User-original-123", new_password="User-new-456"), x_access_token=current)
        updated = await load_workspace(workspace["workspace_id"])
        assert updated["admin_password_hash"] == workspace["admin_password_hash"]
        assert verify_password("User-new-456", updated["user_password_hash"])
        assert await sessions.resolve(current) is None
        assert await sessions.resolve(result["token"]) is not None
        await conn.execute("DELETE FROM account_workspaces WHERE workspace_id=$1", workspace["workspace_id"])

    finally:
        await conn.execute("DELETE FROM account_sessions WHERE workspace_id=$1", workspace["workspace_id"])
        await conn.close()
