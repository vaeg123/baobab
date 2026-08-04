import hashlib
import hmac
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from baobab.auth import JWT_EXPIRY_HOURS, create_superadmin_jwt, verify_superadmin_jwt
from baobab.config import settings
from baobab.api.routes.accounts import _connect_db, _use_database

router = APIRouter(tags=["superadmin-auth"])


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return (salt + key).hex()


def _verify_password(password: str, stored: str) -> bool:
    data = bytes.fromhex(stored)
    salt, key = data[:32], data[32:]
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return hmac.compare_digest(key, new_key)


class SuperadminSetup(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=8, max_length=128)
    bootstrap_token: str = Field(..., min_length=1)


class SuperadminLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=1, max_length=128)


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


@router.post("/superadmin/setup", status_code=status.HTTP_201_CREATED)
async def setup_superadmin(request: SuperadminSetup):
    bootstrap_token = os.getenv("BAOBAB_SUPERADMIN_TOKEN", "baobab-superadmin-dev")
    if request.bootstrap_token != bootstrap_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de bootstrap invalide.",
        )

    if not _use_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données requise pour la configuration superadmin.",
        )

    await _ensure_superadmin_table()
    conn = await _connect_db()
    try:
        existing = await conn.fetchrow("SELECT id FROM account_superadmins LIMIT 1")
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte superadmin existe déjà. Utilisez /superadmin/login.",
            )

        email = request.email.lower()
        password_hash = _hash_password(request.password)
        await conn.execute(
            "INSERT INTO account_superadmins (email, password_hash) VALUES ($1, $2)",
            email,
            password_hash,
        )
    finally:
        await conn.close()

    token = create_superadmin_jwt(email, settings.jwt_secret)
    return {"message": "Compte superadmin créé avec succès.", "email": email, "token": token}


@router.post("/superadmin/login")
async def login_superadmin(request: SuperadminLogin):
    if not _use_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données requise pour l'authentification superadmin.",
        )

    await _ensure_superadmin_table()
    conn = await _connect_db()
    try:
        email = request.email.lower()
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM account_superadmins WHERE email = $1",
            email,
        )
        if not row or not _verify_password(request.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email ou mot de passe incorrect.",
            )
        await conn.execute(
            "UPDATE account_superadmins SET last_login_at = $1 WHERE id = $2",
            datetime.now(UTC),
            row["id"],
        )
    finally:
        await conn.close()

    token = create_superadmin_jwt(email, settings.jwt_secret)
    return {"token": token, "email": email, "expires_in_hours": JWT_EXPIRY_HOURS}


@router.get("/superadmin/me")
async def me_superadmin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bearer token requis.")
    payload = verify_superadmin_jwt(authorization[7:], settings.jwt_secret)
    return {"email": payload.get("email"), "role": "superadmin"}
