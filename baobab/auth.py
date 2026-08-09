import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, status

JWT_EXPIRY_HOURS = 8


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return (salt + key).hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        data = bytes.fromhex(stored)
        salt, key = data[:32], data[32:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return hmac.compare_digest(key, new_key)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)


def _sign(signing_input: str, secret: str) -> str:
    return _b64url_encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    )


def create_superadmin_jwt(email: str, secret: str) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "sub": "superadmin",
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
    }).encode())
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input, secret)}"


def verify_superadmin_jwt(token: str, secret: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("bad token structure")
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"
        expected = _sign(signing_input, secret)
        if not hmac.compare_digest(sig_b64, expected):
            raise ValueError("invalid signature")
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("sub") != "superadmin":
            raise ValueError("wrong subject")
        if payload.get("exp", 0) < time.time():
            raise ValueError("token expired")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token superadmin invalide ou expiré.",
        )
