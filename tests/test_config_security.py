"""
Vérifie que la configuration refuse de démarrer en production avec des
secrets par défaut ou trop faibles — cf. audit sécurité : plusieurs
secrets (JWT_SECRET, BAOBAB_SUPERADMIN_TOKEN...) avaient des valeurs de
repli connues publiquement, exploitables si l'opérateur oubliait de les
surcharger en déploiement.

Les variables d'environnement sont manipulées via `monkeypatch.setenv`
plutôt que passées comme kwargs au constructeur : `superadmin_bootstrap_token`
et `admin_key` utilisent un `validation_alias` (BAOBAB_SUPERADMIN_TOKEN,
BAOBAB_ADMIN_KEY) qui ne serait pas honoré par un kwarg portant le nom
du champ Python — passer par l'environnement reproduit fidèlement le
comportement réel en déploiement.
"""

import pytest

from baobab.config import Settings

_STRONG = "x" * 40


def _set_all_strong_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", _STRONG)
    monkeypatch.setenv("JWT_SECRET", _STRONG)
    monkeypatch.setenv("BAOBAB_SUPERADMIN_TOKEN", _STRONG)
    monkeypatch.setenv("BAOBAB_ADMIN_KEY", _STRONG)


def test_development_environment_accepts_default_secrets():
    settings = Settings(environment="development")
    assert settings.is_production is False


def test_production_rejects_default_secret_key(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key")

    with pytest.raises(ValueError, match="secret_key"):
        Settings(environment="production")


def test_production_rejects_default_jwt_secret(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "dev-jwt-secret-change-me")

    with pytest.raises(ValueError, match="jwt_secret"):
        Settings(environment="production")


def test_production_rejects_missing_superadmin_bootstrap_token(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv("BAOBAB_SUPERADMIN_TOKEN", "")

    with pytest.raises(ValueError, match="superadmin_bootstrap_token"):
        Settings(environment="production")


def test_production_rejects_short_secrets(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "trop-court")

    with pytest.raises(ValueError, match="minimum requis"):
        Settings(environment="production")


def test_production_rejects_wildcard_cors(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValueError, match="cors_allowed_origins"):
        Settings(environment="production")


def test_production_accepts_strong_unique_secrets(monkeypatch):
    _set_all_strong_secrets(monkeypatch)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com"
    )

    settings = Settings(environment="production")

    assert settings.is_production is True
    assert settings.cors_origins_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
