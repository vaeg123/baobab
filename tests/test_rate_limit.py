"""
Tests unitaires pour les helpers de `baobab.rate_limit` qui ne
nécessitent pas de connexion PostgreSQL.

`enforce_rate_limit` lui-même (persistance du compteur en base) n'est
pas couvert ici : aucune instance PostgreSQL n'est disponible dans cet
environnement de test. Voir tests/conftest.py::postgres_available.
"""

from baobab.rate_limit import client_ip


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, headers: dict, host: str | None = "203.0.113.5"):
        self.headers = headers
        self.client = _FakeClient(host) if host else None


def test_client_ip_prefers_x_forwarded_for_first_entry():
    request = _FakeRequest({"x-forwarded-for": "198.51.100.7, 10.0.0.1, 10.0.0.2"})
    assert client_ip(request) == "198.51.100.7"


def test_client_ip_falls_back_to_direct_connection():
    request = _FakeRequest({}, host="203.0.113.5")
    assert client_ip(request) == "203.0.113.5"


def test_client_ip_handles_missing_client():
    request = _FakeRequest({}, host=None)
    assert client_ip(request) == "unknown"
