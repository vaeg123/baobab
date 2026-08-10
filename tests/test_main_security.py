"""
Vérifie la configuration sécurité de l'application FastAPI elle-même :
CORS restreint (plus de wildcard) et documentation API masquable.
"""

from baobab.api.main import app
from baobab.config import settings


def test_cors_does_not_allow_wildcard_origin():
    cors_middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    allowed_origins = cors_middleware.kwargs["allow_origins"]

    assert "*" not in allowed_origins
    assert allowed_origins == settings.cors_origins_list


def test_docs_enabled_in_development_by_default():
    # En environnement de développement (celui des tests), la doc reste
    # utile et n'a pas besoin d'être masquée.
    if not settings.is_production:
        assert app.docs_url == "/api/docs"
        assert app.redoc_url == "/api/redoc"
