import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, status

JWT_EXPIRY_HOURS = 8


def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec PBKDF2-SHA256 à 600 000 itérations.

    Format du hash (68 bytes encodés en hex) :
        - 4 bytes  : nombre d'itérations en little-endian
        - 32 bytes : sel aléatoire
        - 32 bytes : clé dérivée
    """
    iterations = 600_000
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    iter_bytes = iterations.to_bytes(4, "little")
    return (iter_bytes + salt + key).hex()


def verify_password(password: str, stored: str) -> bool:
    """
    Vérifie un mot de passe contre son hash stocké.

    Rétro-compatible avec l'ancien format (64 bytes hex = 32 salt + 32 key,
    260 000 itérations implicites) et le nouveau format (68 bytes hex = 4
    itérations + 32 salt + 32 key). La comparaison est en temps constant
    pour éviter les attaques par timing.
    """
    try:
        data = bytes.fromhex(stored)
        if len(data) == 64:
            salt, key = data[:32], data[32:]
            iterations = 260_000
        elif len(data) == 68:
            iterations = int.from_bytes(data[:4], "little")
            salt, key = data[4:36], data[36:]
        else:
            return False
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(key, new_key)
    except Exception:
        return False


def constant_time_equals(candidate: str | None, expected: str | None) -> bool:
    if not candidate or not expected:
        return False
    return hmac.compare_digest(candidate.encode(), expected.encode())


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
