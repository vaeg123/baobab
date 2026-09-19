"""Opaque expiring sessions; only SHA-256 token fingerprints are persisted."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from baobab.auth import constant_time_equals

_LOCAL: dict[str, dict] = {}
_ready = False

def fingerprint(workspace: dict, role: str) -> str:
    prefix = "admin" if role == "admin" else "user"
    value = f"{role}:{workspace.get(prefix + '_password_hash', '')}:{workspace.get(prefix + '_token', '')}"
    return hashlib.sha256(value.encode()).hexdigest()

def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

async def _connection():
    from baobab.api.routes.accounts import _connect_db
    global _ready
    conn = await _connect_db()
    if not _ready:
        try:
            await conn.execute("""CREATE TABLE IF NOT EXISTS account_sessions (
                token_hash TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin','client')),
                credential_version TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL)""")
            await conn.execute("CREATE INDEX IF NOT EXISTS account_sessions_expiry ON account_sessions(expires_at)")
            _ready = True
        except Exception:
            await conn.close()
            raise
    return conn

async def issue(workspace: dict, role: str) -> str:
    from baobab.api.routes.accounts import _use_database
    if role not in ("admin", "client") or workspace.get("suspended"):
        raise ValueError("Session unavailable")
    token = "bbs_" + secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    record = dict(token_hash=digest(token), workspace_id=workspace["workspace_id"],
                  role=role, credential_version=fingerprint(workspace, role),
                  expires_at=now + timedelta(hours=8))
    if _use_database():
        conn = await _connection()
        try:
            await conn.execute("DELETE FROM account_sessions WHERE expires_at <= NOW()")
            await conn.execute("""INSERT INTO account_sessions
                (token_hash,workspace_id,role,credential_version,expires_at)
                VALUES ($1,$2,$3,$4,$5)""", *record.values())
        finally:
            await conn.close()
    else:
        for key in list(_LOCAL):
            if _LOCAL[key]["expires_at"] <= now:
                del _LOCAL[key]
        _LOCAL[record["token_hash"]] = record
    return token

async def resolve(token: str | None):
    from baobab.api.routes.accounts import _use_database, _load_workspace
    if not isinstance(token, str) or not token.startswith("bbs_") or len(token) > 128:
        return None
    if _use_database():
        conn = await _connection()
        try:
            record = await conn.fetchrow("SELECT * FROM account_sessions WHERE token_hash=$1 AND expires_at > NOW()", digest(token))
        finally:
            await conn.close()
    else:
        record = _LOCAL.get(digest(token))
    if not record or record["expires_at"] <= datetime.now(UTC):
        return None
    workspace = await _load_workspace(record["workspace_id"])
    if not workspace or workspace.get("suspended") or not constant_time_equals(record["credential_version"], fingerprint(workspace, record["role"])):
        return None
    return workspace, record["role"]

async def revoke(token: str | None):
    from baobab.api.routes.accounts import _use_database
    if not isinstance(token, str) or not token.startswith("bbs_"):
        return
    if _use_database():
        conn = await _connection()
        try:
            await conn.execute("DELETE FROM account_sessions WHERE token_hash=$1", digest(token))
        finally:
            await conn.close()
    else:
        _LOCAL.pop(digest(token), None)
