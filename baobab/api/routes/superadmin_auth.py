import os
from datetime import UTC, datetime

import bcrypt
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from baobab.auth import JWT_EXPIRY_HOURS, create_superadmin_jwt, verify_superadmin_jwt
from baobab.config import settings
from baobab.api.routes.accounts import _connect_db, _use_database

router = APIRouter(tags=["superadmin-auth"])


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

    await _ensure_superadmin_table()

    if not _use_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données requise pour la configuration superadmin.",
        )

    conn = await _connect_db()
    try:
        existing = await conn.fetchrow(
            "SELECT id FROM account_superadmins LIMIT 1"
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte superadmin existe déjà.",
            )

        password_hash = bcrypt.hashpw(
            request.password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        email = request.email.lower()
        await conn.execute(
            """
            INSERT INTO account_superadmins (email, password_hash)
            VALUES ($1, $2)
            """,
            email,
            password_hash,
        )

        token = create_superadmin_jwt(email, settings.jwt_secret)
        return {
            "message": "Compte superadmin créé avec succès.",
            "email": email,
            "token": token,
        }
    finally:
        await conn.close()


@router.post("/superadmin/login")
async def login_superadmin(request: SuperadminLogin):
    await _ensure_superadmin_table()

    if not _use_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données requise pour l'authentification superadmin.",
        )

    conn = await _connect_db()
    try:
        email = request.email.lower()
        row = await conn.fetchrow(
            "SELECT id, email, password_hash FROM account_superadmins WHERE email = $1",
            email,
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email ou mot de passe incorrect.",
            )

        password_matches = bcrypt.checkpw(
            request.password.encode("utf-8"),
            row["password_hash"].encode("utf-8"),
        )
        if not password_matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email ou mot de passe incorrect.",
            )

        await conn.execute(
            "UPDATE account_superadmins SET last_login_at = $1 WHERE id = $2",
            datetime.now(UTC),
            row["id"],
        )

        token = create_superadmin_jwt(email, settings.jwt_secret)
        return {
            "token": token,
            "email": email,
            "expires_in_hours": JWT_EXPIRY_HOURS,
        }
    finally:
        await conn.close()


@router.get("/superadmin/me")
async def me_superadmin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bearer token superadmin requis.",
        )
    payload = verify_superadmin_jwt(authorization[7:], settings.jwt_secret)
    return {
        "email": payload.get("email"),
        "role": "superadmin",
    }
