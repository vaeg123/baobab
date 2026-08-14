import hashlib
import hmac
import os
import time

import jwt as pyjwt
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
            # Ancien format : 32 bytes salt + 32 bytes key, 260k iterations implicites
            salt, key = data[:32], data[32:]
            iterations = 260_000
        elif len(data) == 68:
            # Nouveau format : 4 bytes iter (little-endian) + 32 bytes salt + 32 bytes key
            iterations = int.from_bytes(data[:4], "little")
            salt, key = data[4:36], data[36:]
        else:
            return False
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(key, new_key)
    except Exception:
        return False


def constant_time_equals(candidate: str | None, expected: str | None) -> bool:
    """
    Compare deux secrets (tokens, clés admin...) en temps constant.

    Ne jamais comparer un secret avec `==`/`!=` : le temps de réponse
    d'une comparaison naïve dépend de la position du premier octet
    différent, ce qui peut permettre à un attaquant de reconstituer le
    secret octet par octet (timing attack). `hmac.compare_digest` est
    conçu pour être insensible à ce type d'analyse.
    """
    if not candidate or not expected:
        return False
    return hmac.compare_digest(candidate.encode(), expected.encode())


def create_superadmin_jwt(email: str, secret: str) -> str:
    payload = {
        "sub": "superadmin",
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def verify_superadmin_jwt(token: str, secret: str) -> dict:
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("sub") != "superadmin":
            raise ValueError("wrong subject")
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token superadmin expiré.",
        )
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token superadmin invalide ou expiré.",
        )
