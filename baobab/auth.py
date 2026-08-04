import jwt
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException, status

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 8


def create_superadmin_jwt(email: str, secret: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode({
        "sub": "superadmin",
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }, secret, algorithm=JWT_ALGORITHM)


def verify_superadmin_jwt(token: str, secret: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        if payload.get("sub") != "superadmin":
            raise ValueError
        return payload
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token superadmin invalide ou expiré.",
        )
