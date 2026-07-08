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


def test_workspace_admin_can_manage_own_internal_requests():
    workspace_response = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Admin Local",
            "email": "admin-local@example.com",
            "organization_name": "Admin Local SARL",
            "territory": "CI",
        },
    )
    workspace = workspace_response.json()
    admin_token = workspace["admin_token"]

    login_response = client.post(
        "/api/v1/accounts/admin/login",
        json={"admin_token": admin_token},
    )
    assert login_response.status_code == 200
    assert login_response.json()["workspace_id"] == workspace["workspace_id"]

    request_response = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Demande admin",
            "message": "Cette demande sera traitee depuis l'espace admin.",
        },
    )
    internal_request = request_response.json()

    update_response = client.patch(
        f"/api/v1/accounts/admin/internal-requests/{internal_request['request_id']}",
        headers={"X-Admin-Token": admin_token},
        json={
            "status": "in_review",
            "admin_note": "Pris en charge par l'administrateur de l'espace.",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "in_review"
    assert updated["admin_note"] == "Pris en charge par l'administrateur de l'espace."


def test_workspace_admin_cannot_manage_another_workspace_request():
    first_workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Premier Admin",
            "email": "premier@example.com",
            "organization_name": "Premier SARL",
            "territory": "CI",
        },
    ).json()
    second_workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Second Admin",
            "email": "second@example.com",
            "organization_name": "Second SARL",
            "territory": "CI",
        },
    ).json()

    request_response = client.post(
        f"/api/v1/accounts/workspaces/{first_workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Demande protegee",
            "message": "Cette demande appartient au premier espace.",
        },
    )
    internal_request = request_response.json()

    forbidden_response = client.patch(
        f"/api/v1/accounts/admin/internal-requests/{internal_request['request_id']}",
        headers={"X-Admin-Token": second_workspace["admin_token"]},
        json={"status": "closed", "admin_note": "Tentative interdite."},
    )

    assert forbidden_response.status_code == 403


def test_superadmin_can_see_platform_overview():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Super Admin Test",
            "email": "super-admin-test@example.com",
            "organization_name": "Super Admin Test SARL",
            "territory": "CI",
        },
    ).json()
    checkout = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/checkout",
        json={
            "plan": "basic",
            "provider": "orange_money",
            "phone_number": "+2250500000000",
        },
    ).json()
    client.post(f"/api/v1/accounts/payments/{checkout['payment_id']}/confirm")

    forbidden_response = client.get("/api/v1/accounts/superadmin/overview")
    assert forbidden_response.status_code == 403

    overview_response = client.get(
        "/api/v1/accounts/superadmin/overview",
        headers={"X-Superadmin-Token": "baobab-superadmin-dev"},
    )

    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["workspaces_count"] >= 1
    assert overview["confirmed_revenue_xof"] >= 5000


def test_access_code_routes_to_admin_or_superadmin_space():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Code Admin",
            "email": "code-admin@example.com",
            "organization_name": "Code Admin SARL",
            "territory": "CI",
        },
    ).json()

    admin_access = client.post(
        "/api/v1/accounts/access/login",
        json={"access_code": workspace["admin_token"]},
    )

    assert admin_access.status_code == 200
    assert admin_access.json()["role"] == "admin"
    assert admin_access.json()["workspace"]["workspace_id"] == workspace["workspace_id"]

    superadmin_access = client.post(
        "/api/v1/accounts/access/login",
        json={"access_code": "baobab-superadmin-dev"},
    )

    assert superadmin_access.status_code == 200
    assert superadmin_access.json()["role"] == "superadmin"

    invalid_access = client.post(
        "/api/v1/accounts/access/login",
        json={"access_code": "invalid-access-code"},
    )

    assert invalid_access.status_code == 403
