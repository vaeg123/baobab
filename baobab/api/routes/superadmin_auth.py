from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from baobab.auth import JWT_EXPIRY_HOURS, create_superadmin_jwt, hash_password, verify_password, verify_superadmin_jwt
from baobab.config import settings
from baobab.api.routes.accounts import _connect_db, _use_database

router = APIRouter(tags=["superadmin-auth"])


async def _ensure_superadmin_table() -> None:
    if not _use_database():
        return
    conn = await _connect_db()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS account_superadmins (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_login_at TIMESTAMPTZ
            )
        """)
    finally:
        await conn.close()


def _auth_superadmin(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bearer token requis.")
    return verify_superadmin_jwt(authorization[7:], settings.jwt_secret)


class SuperadminSetup(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=8, max_length=128)
    bootstrap_token: str = Field(..., min_length=1)


class SuperadminLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=1, max_length=128)


class SuperadminChangePassword(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class SuperadminChangeEmail(BaseModel):
    new_email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/superadmin/setup", status_code=status.HTTP_201_CREATED)
async def setup_superadmin(request: SuperadminSetup):
    import os
    bootstrap_token = os.getenv("BAOBAB_SUPERADMIN_TOKEN", "baobab-superadmin-dev")
    if request.bootstrap_token != bootstrap_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de bootstrap invalide.")

    if not _use_database():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Base de données requise.")

    await _ensure_superadmin_table()
    conn = await _connect_db()
    try:
        existing = await conn.fetchrow("SELECT id FROM account_superadmins LIMIT 1")
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un compte superadmin existe déjà.")

        email = request.email.lower()
        await conn.execute(
            "INSERT INTO account_superadmins (email, password_hash) VALUES ($1, $2)",
            email, hash_password(request.password),
        )
    finally:
        await conn.close()

    token = create_superadmin_jwt(email, settings.jwt_secret)
    return {"message": "Compte superadmin créé.", "email": email, "token": token}


@router.post("/superadmin/login")
async def login_superadmin(request: SuperadminLogin):
    if not _use_database():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Base de données requise.")

    await _ensure_superadmin_table()
    conn = await _connect_db()
    try:
        email = request.email.lower()
        row = await conn.fetchrow("SELECT id, password_hash FROM account_superadmins WHERE email = $1", email)
        if not row or not verify_password(request.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email ou mot de passe incorrect.")
        await conn.execute(
            "UPDATE account_superadmins SET last_login_at = $1 WHERE id = $2",
            datetime.now(UTC), row["id"],
        )
    finally:
        await conn.close()

    token = create_superadmin_jwt(email, settings.jwt_secret)
    return {"token": token, "email": email, "expires_in_hours": JWT_EXPIRY_HOURS}


@router.get("/superadmin/me")
async def me_superadmin(authorization: str | None = Header(default=None)):
    payload = _auth_superadmin(authorization)
    return {"email": payload.get("email"), "role": "superadmin"}


@router.put("/superadmin/password")
async def change_superadmin_password(
    request: SuperadminChangePassword,
    authorization: str | None = Header(default=None),
):
    payload = _auth_superadmin(authorization)
    email = payload["email"]

    conn = await _connect_db()
    try:
        row = await conn.fetchrow("SELECT id, password_hash FROM account_superadmins WHERE email = $1", email)
        if not row or not verify_password(request.current_password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mot de passe actuel incorrect.")
        await conn.execute(
            "UPDATE account_superadmins SET password_hash = $1 WHERE id = $2",
            hash_password(request.new_password), row["id"],
        )
    finally:
        await conn.close()

    return {"message": "Mot de passe modifié avec succès."}


@router.put("/superadmin/email")
async def change_superadmin_email(
    request: SuperadminChangeEmail,
    authorization: str | None = Header(default=None),
):
    payload = _auth_superadmin(authorization)
    current_email = payload["email"]
    new_email = request.new_email.lower()

    conn = await _connect_db()
    try:
        row = await conn.fetchrow("SELECT id, password_hash FROM account_superadmins WHERE email = $1", current_email)
        if not row or not verify_password(request.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mot de passe incorrect.")
        existing = await conn.fetchrow("SELECT id FROM account_superadmins WHERE email = $1", new_email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet email est déjà utilisé.")
        await conn.execute(
            "UPDATE account_superadmins SET email = $1 WHERE id = $2",
            new_email, row["id"],
        )
    finally:
        await conn.close()

    token = create_superadmin_jwt(new_email, settings.jwt_secret)
    return {"message": "Email modifié avec succès.", "email": new_email, "token": token}
