"""
Limitation de débit (rate limiting) par fenêtre fixe.

BAOBAB est déployé en fonctions serverless (Vercel — voir vercel.json).
Chaque requête peut atterrir sur une instance différente : un compteur en
mémoire locale (dict Python) serait inefficace en production car non
partagé entre instances. On utilise donc PostgreSQL comme état partagé
dès qu'une vraie base est configurée (même logique que `_use_database()`
dans accounts.py), avec repli en mémoire locale pour le développement
sans dépendance externe.

Usage :
    from baobab.rate_limit import enforce_rate_limit

    @router.post("/endpoint-sensible")
    async def handler(request: Request):
        await enforce_rate_limit(
            key=f"submissions:{client_ip(request)}",
            limit=10,
            window_seconds=3600,
        )
        ...

Limite connue : les lignes anciennes ne sont pas purgées automatiquement
en mode PostgreSQL. Pour un usage en production à fort trafic, prévoir un
job de nettoyage périodique (ou une table avec TTL applicatif) sur
`rate_limit_counters`.
"""

import time

import asyncpg
from fastapi import HTTPException, status

from baobab.config import settings

_TABLE_READY = False

# Repli mémoire locale : uniquement pertinent en développement (une seule
# instance de processus). Ne PAS s'y fier en production multi-instance.
_LOCAL_COUNTERS: dict[tuple[str, int], int] = {}


def _use_database() -> bool:
    """Même heuristique que baobab.api.routes.accounts._use_database,
    dupliquée ici pour éviter un import circulaire (accounts.py importe
    ce module pour le throttling du login)."""
    return "localhost" not in settings.database_url


def _normalize_database_url(database_url: str) -> str:
    """Convertit l'URL SQLAlchemy async en URL utilisable par asyncpg brut."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(_normalize_database_url(settings.database_url), statement_cache_size=0)


async def _ensure_table(conn: asyncpg.Connection) -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limit_counters (
            bucket_key TEXT NOT NULL,
            window_start TIMESTAMPTZ NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (bucket_key, window_start)
        )
        """
    )
    _TABLE_READY = True


async def _increment_postgres(key: str, window_seconds: int) -> int:
    conn = await _connect()
    try:
        await _ensure_table(conn)
        row = await conn.fetchrow(
            """
            INSERT INTO rate_limit_counters (bucket_key, window_start, request_count)
            VALUES ($1, to_timestamp(floor(extract(epoch FROM now()) / $2) * $2), 1)
            ON CONFLICT (bucket_key, window_start)
            DO UPDATE SET request_count = rate_limit_counters.request_count + 1
            RETURNING request_count
            """,
            key,
            window_seconds,
        )
        return row["request_count"]
    finally:
        await conn.close()


def _increment_local(key: str, window_seconds: int) -> int:
    window_start = int(time.time() // window_seconds)
    bucket = (key, window_start)
    _LOCAL_COUNTERS[bucket] = _LOCAL_COUNTERS.get(bucket, 0) + 1
    # Ménage grossier : borne la taille du dict pour un process long-lived.
    if len(_LOCAL_COUNTERS) > 10_000:
        _LOCAL_COUNTERS.clear()
    return _LOCAL_COUNTERS[bucket]


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """
    Incrémente le compteur pour `key` sur la fenêtre temporelle courante.

    Lève HTTPException 429 si `limit` est dépassé sur la fenêtre en cours.
    Fenêtre fixe (pas glissante) : simple, prévisible, suffisant pour se
    protéger d'un abus automatisé grossier (spam, scraping, brute force).

    Persistance PostgreSQL si une vraie base est configurée (nécessaire
    en production multi-instance) ; repli en mémoire locale sinon, pour
    ne jamais bloquer le développement local faute de base disponible.
    """
    try:
        if _use_database():
            count = await _increment_postgres(key, window_seconds)
        else:
            count = _increment_local(key, window_seconds)
    except (OSError, asyncpg.PostgresError):
        # Un rate limiter qui plante ne doit jamais rendre l'application
        # indisponible : on se dégrade en mémoire locale plutôt que de
        # renvoyer une 500 sur un endpoint métier par ailleurs valide.
        count = _increment_local(key, window_seconds)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Trop de requêtes. Limite : {limit} par {window_seconds}s. "
                "Réessayez plus tard."
            ),
        )


def client_ip(request) -> str:
    """
    Extrait l'IP cliente en tenant compte d'un éventuel proxy inverse
    (Vercel transmet X-Forwarded-For). Ne fait confiance qu'au premier
    élément de la liste, le plus proche du load balancer de la plateforme.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
