from fastapi.testclient import TestClient

from baobab.api.main import app


client = TestClient(app)


def test_free_workspace_can_submit_one_internal_request_then_must_upgrade():
    workspace_response = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Awa Kouassi",
            "email": "awa@example.com",
            "organization_name": "Cabinet Awa",
            "territory": "ci",
        },
    )

    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    assert workspace["plan"] == "free"
    assert workspace["subscription_status"] == "free"
    assert workspace["plan_details"]["monthly_price_xof"] == 0

    request_response = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Analyse contrat",
            "message": "Je souhaite une analyse interne de ce nouveau dossier.",
        },
    )

    assert request_response.status_code == 201
    assert request_response.json()["status"] == "submitted"

    blocked_response = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Deuxieme demande",
            "message": "Cette demande doit etre bloquee avec l'offre gratuite.",
        },
    )

    assert blocked_response.status_code == 402


def test_paid_checkout_activates_monthly_subscription():
    workspace_response = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Koffi Mensah",
            "email": "koffi@example.com",
            "organization_name": "Mensah Consulting",
            "territory": "CI",
        },
    )
    workspace = workspace_response.json()

    checkout_response = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/checkout",
        json={
            "plan": "premium",
            "provider": "wave",
            "phone_number": "+2250700000000",
        },
    )

    assert checkout_response.status_code == 201
    payment = checkout_response.json()
    assert payment["amount_xof"] == 10000
    assert payment["billing_period"] == "monthly"
    assert payment["status"] == "pending"

    confirm_response = client.post(
        f"/api/v1/accounts/payments/{payment['payment_id']}/confirm"
    )

    assert confirm_response.status_code == 200
    activated = confirm_response.json()["workspace"]
    assert activated["plan"] == "premium"
    assert activated["subscription_status"] == "active"
    assert activated["subscription_expires_at"] is not None


def test_plan_catalog_contains_basic_premium_and_mobile_money_providers():
    response = client.get("/api/v1/accounts/plans")

    assert response.status_code == 200
    body = response.json()
    prices = {plan["plan"]: plan["monthly_price_xof"] for plan in body["plans"]}
    assert prices["basic"] == 5000
    assert prices["premium"] == 10000
    assert {"orange_money", "mtn_money", "wave"} <= set(body["payment_providers"])
