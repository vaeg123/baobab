from fastapi.testclient import TestClient

from baobab.api.main import app
from baobab.api.routes import accounts
from baobab.config import settings

client = TestClient(app)
SECRET = "avocassist-integration-test-secret-0123456789"
HEADERS = {"X-Integration-Key": SECRET}
ORG_ID = "11111111-1111-4111-8111-111111111111"


def setup_function():
    accounts.WORKSPACES.clear()
    settings.avocassist_integration_secret = SECRET


def test_provision_is_idempotent_and_subscription_is_separate():
    body = {
        "organization_id": ORG_ID,
        "organization_name": "Cabinet Test",
        "owner_name": "Alice Test",
        "owner_email": "alice@example.com",
        "territory": "CM",
    }
    first = client.post("/api/v1/integrations/avocassist/provision", headers=HEADERS, json=body)
    second = client.post("/api/v1/integrations/avocassist/provision", headers=HEADERS, json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["workspace_id"] == second.json()["workspace_id"]
    assert first.json()["subscription_status"] == "free"
    assert first.json()["active"] is False


def test_sso_ticket_exchange_does_not_expose_token_in_ticket_payload():
    client.post("/api/v1/integrations/avocassist/provision", headers=HEADERS, json={
        "organization_id": ORG_ID, "organization_name": "Cabinet Test",
        "owner_name": "Alice Test", "owner_email": "alice@example.com", "territory": "CM",
    })
    response = client.post("/api/v1/integrations/avocassist/session", headers=HEADERS, json={
        "organization_id": ORG_ID, "user_id": "22222222-2222-4222-8222-222222222222",
        "email": "alice@example.com", "display_name": "Alice Test",
    })
    assert response.status_code == 200
    ticket = response.json()["url"].split("sso_ticket=", 1)[1]
    assert "usr_" not in ticket
    exchange = client.post("/api/v1/integrations/avocassist/session/exchange", json={"ticket": ticket})
    assert exchange.status_code == 200
    assert exchange.json()["role"] == "client"


def test_search_requires_paid_subscription():
    client.post("/api/v1/integrations/avocassist/provision", headers=HEADERS, json={
        "organization_id": ORG_ID, "organization_name": "Cabinet Test",
        "owner_name": "Alice Test", "owner_email": "alice@example.com", "territory": "CM",
    })
    response = client.post("/api/v1/integrations/avocassist/legal/search", headers=HEADERS, json={
        "organization_id": ORG_ID, "query": "droit des sociétés", "corpus": "ohada",
    })
    assert response.status_code == 402
