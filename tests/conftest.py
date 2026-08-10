"""
Configuration partagée des tests.

IMPORTANT : `baobab.config.settings` est un singleton instancié à l'import
du module. Les variables d'environnement nécessaires aux tests (jeton de
bootstrap superadmin, clé admin...) doivent donc être positionnées ICI,
avant que quoi que ce soit n'importe `baobab.*`, faute de quoi les tests
verraient les valeurs par défaut vides et échoueraient avec 503.
"""

import asyncio
import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("BAOBAB_SUPERADMIN_TOKEN", "test-superadmin-bootstrap-token-not-for-prod")
os.environ.setdefault("BAOBAB_ADMIN_KEY", "test-admin-key-not-for-prod-0123456789")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-prod-0123456789abcdef")


def postgres_available() -> bool:
    """
    Certains flux (compte superadmin, corpus juridique, soumissions)
    exigent une vraie base PostgreSQL — pas de repli en mémoire. Les
    tests qui en dépendent se `skip` proprement si aucune base n'est
    joignable, plutôt que d'échouer bruyamment dans un environnement
    sans `docker compose up -d` (cf. README du projet).
    """
    import asyncpg

    async def _try_connect() -> bool:
        try:
            conn = await asyncpg.connect(
                "postgresql://baobab:baobab@localhost:5432/baobab", timeout=2
            )
            await conn.close()
            return True
        except Exception:  # noqa: BLE001 — simple probe de disponibilité
            return False

    try:
        return asyncio.run(_try_connect())
    except Exception:  # noqa: BLE001 — idem
        return False
