"""
Vérifie que les emails transactionnels échappent les champs utilisateur
(protection contre l'injection HTML dans le rendu email — cf. audit
sécurité) et que le BCC n'est plus ajouté automatiquement vers une
boîte tierce sur les emails contenant un secret (mot de passe temporaire,
token d'accès).
"""

import pytest

from baobab import notifications


def test_esc_neutralizes_html_and_script_tags():
    malicious = '<img src=x onerror=alert(1)>"Cabinet" \'Test\''
    escaped = notifications.esc(malicious)

    assert "<img" not in escaped
    assert "onerror" not in escaped or "&" in escaped  # doit être neutralisé
    assert "&lt;img" in escaped
    assert "&quot;" in escaped or "&#x27;" in escaped


def test_esc_handles_none_and_non_string_values():
    assert notifications.esc(None) == ""
    assert notifications.esc(42) == "42"


@pytest.mark.asyncio
async def test_workspace_created_email_escapes_organization_name(monkeypatch):
    captured = {}

    async def _fake_send(to, subject, html, *, bcc=None):
        captured["to"] = to
        captured["subject"] = subject
        captured["html"] = html
        captured["bcc"] = bcc
        return True

    monkeypatch.setattr(notifications, "_send", _fake_send)

    workspace = {
        "owner_name": '<script>alert("owner")</script>',
        "organization_name": '<img src=x onerror=alert("org")>',
        "email": "client@example.com",
        "territory": "CI",
        "workspace_id": "ws_test123",
    }

    await notifications.notify_user_workspace_created(workspace, clear_password="TempPass123")

    assert "<script>alert" not in captured["html"]
    assert "<img src=x onerror" not in captured["html"]
    assert "&lt;script&gt;" in captured["html"]

    # Aucun BCC ne doit être ajouté sur un email contenant un mot de
    # passe temporaire en clair.
    assert captured["bcc"] is None


@pytest.mark.asyncio
async def test_admin_alert_skipped_when_admin_email_not_configured(monkeypatch):
    monkeypatch.setattr(notifications, "ADMIN_EMAIL", "")

    called = False

    async def _fake_send(*args, **kwargs):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(notifications, "_send", _fake_send)

    workspace = {
        "owner_name": "Test",
        "organization_name": "Test SARL",
        "email": "test@example.com",
        "territory": "CI",
        "workspace_id": "ws_abc",
    }
    result = await notifications.notify_admin_new_workspace(workspace)

    assert result is False
    assert called is False
