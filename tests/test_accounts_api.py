import pytest
from fastapi.testclient import TestClient

from baobab.api.main import app
from baobab.api.routes.accounts import _normalize_database_url
from baobab.api.routes import accounts
from tests.conftest import postgres_available

client = TestClient(app)


@pytest.mark.asyncio
async def test_workspace_lookup_accepts_admin_token(monkeypatch):
    workspace = {
        "workspace_id": "ws_admin_service_access",
        "user_token": "usr_service_access",
        "admin_token": "adm_service_access",
    }

    async def list_workspaces():
        return [workspace]

    monkeypatch.setattr(accounts, "_list_workspaces", list_workspaces)

    assert await accounts._find_workspace_by_token("adm_service_access") == workspace
    assert await accounts._find_workspace_by_token("usr_service_access") == workspace
    assert await accounts._find_workspace_by_token("adm_wrong") is None


def _bootstrap_and_login_superadmin(email: str, password: str = "SuperSecret123!") -> str:
    """Crée (si besoin) le compte superadmin et renvoie un JWT valide."""
    setup_response = client.post(
        "/api/v1/superadmin/setup",
        json={
            "email": email,
            "password": password,
            "bootstrap_token": "test-superadmin-bootstrap-token-not-for-prod",
        },
    )
    if setup_response.status_code == 201:
        return setup_response.json()["token"]

    # Compte déjà bootstrapé par un test précédent : on se connecte.
    login_response = client.post(
        "/api/v1/superadmin/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["token"]


def test_neon_database_url_normalization_removes_unsupported_channel_binding():
    url = "postgresql://user:pass@example.neon.tech/db?sslmode=require&channel_binding=require"

    normalized = _normalize_database_url(url)

    assert "sslmode=require" in normalized
    assert "channel_binding" not in normalized


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


@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL requis pour le compte superadmin")
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

    # La confirmation de paiement est une opération privilégiée : elle
    # exige désormais un Bearer JWT superadmin (cf. audit sécurité).
    token = _bootstrap_and_login_superadmin("super-checkout@example.com")
    confirm_response = client.post(
        f"/api/v1/accounts/payments/{payment['payment_id']}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert confirm_response.status_code == 200
    activated = confirm_response.json()["workspace"]
    assert activated["plan"] == "premium"
    assert activated["subscription_status"] == "active"
    assert activated["subscription_expires_at"] is not None


def test_confirm_payment_rejects_anonymous_caller():
    """Sans le fix, cette route n'était protégée par aucune vérification cohérente à l'usage."""
    response = client.post("/api/v1/accounts/payments/pay_doesnotexist/confirm")
    assert response.status_code == 403


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


# ─── Correctifs de sécurité : IDOR sur GET /workspaces/{id} ──────────────────


def test_get_workspace_requires_a_valid_access_token():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Fanta Traore",
            "email": "fanta@example.com",
            "organization_name": "Traore & Associes",
            "territory": "CI",
        },
    ).json()

    # Sans token : avant le correctif, le simple workspace_id suffisait
    # à lire nom, email et statut d'abonnement du client (IDOR).
    anonymous_response = client.get(f"/api/v1/accounts/workspaces/{workspace['workspace_id']}")
    assert anonymous_response.status_code == 401

    wrong_token_response = client.get(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}",
        headers={"X-Access-Token": "usr_not_the_right_token"},
    )
    assert wrong_token_response.status_code == 401

    authorized_response = client.get(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}",
        headers={"X-Access-Token": workspace["user_token"]},
    )
    assert authorized_response.status_code == 200
    assert authorized_response.json()["organization_name"] == "Traore & Associes"

    admin_response = client.get(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}",
        headers={"X-Access-Token": workspace["admin_token"]},
    )
    assert admin_response.status_code == 200


def test_workspace_admin_can_update_organization_name():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Administrateur VG",
            "email": "admin-vg@example.com",
            "organization_name": "VG",
            "territory": "CI",
        },
    ).json()

    unauthorized = client.patch(
        f"/api/v1/accounts/admin/workspaces/{workspace['workspace_id']}",
        headers={"X-Admin-Token": "adm_invalide"},
        json={"organization_name": "VG Conseil"},
    )
    assert unauthorized.status_code == 403

    response = client.patch(
        f"/api/v1/accounts/admin/workspaces/{workspace['workspace_id']}",
        headers={"X-Admin-Token": workspace["admin_token"]},
        json={"organization_name": "VG Conseil"},
    )
    assert response.status_code == 200
    assert response.json()["organization_name"] == "VG Conseil"

    blank_name = client.patch(
        f"/api/v1/accounts/admin/workspaces/{workspace['workspace_id']}",
        headers={"X-Admin-Token": workspace["admin_token"]},
        json={"organization_name": "  "},
    )
    assert blank_name.status_code == 422


def test_internal_requests_listing_requires_access_token():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Ibrahim Sow",
            "email": "ibrahim@example.com",
            "organization_name": "Sow Legal",
            "territory": "CI",
        },
    ).json()
    client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={"subject": "Confidentiel", "message": "Contenu prive du client."},
    )

    anonymous_response = client.get(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests"
    )
    assert anonymous_response.status_code == 401

    authorized_response = client.get(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        headers={"X-Access-Token": workspace["user_token"]},
    )
    assert authorized_response.status_code == 200
    assert len(authorized_response.json()["requests"]) == 1


# ─── Correctifs de sécurité : authentification email + mot de passe ─────────


def test_login_with_email_and_password_returns_correct_role():
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Mariam Diallo",
            "email": "mariam@example.com",
            "organization_name": "Diallo Conseil",
            "territory": "CI",
            "password": "MotDePasseSolide42!",
        },
    ).json()

    admin_login = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "mariam@example.com", "password": "MotDePasseSolide42!"},
    )
    assert admin_login.status_code == 200
    assert admin_login.json()["role"] == "admin"
    assert admin_login.json()["workspace"]["workspace_id"] == workspace["workspace_id"]

    wrong_password = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "mariam@example.com", "password": "mauvais-mot-de-passe"},
    )
    assert wrong_password.status_code == 403


def test_login_rejects_token_used_as_password():
    """
    Avant le correctif, si le hash de mot de passe était absent, le
    code acceptait `password == token` comme authentification valide.
    Ce test garantit qu'un token connu (renvoyé en clair par l'API à la
    création) ne permet plus de se connecter comme s'il s'agissait du
    mot de passe.
    """
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Yves Kone",
            "email": "yves@example.com",
            "organization_name": "Kone SARL",
            "territory": "CI",
        },
    ).json()

    response = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "yves@example.com", "password": workspace["admin_token"]},
    )
    assert response.status_code == 403


def test_login_does_not_leak_suspended_status_before_password_is_verified():
    """
    Avant le correctif, un compte suspendu renvoyait un message distinct
    ("Ce compte est suspendu") avant même la vérification du mot de
    passe, ce qui permettait d'énumérer les emails valides (ch. 23 du
    livre). Avec un mauvais mot de passe, l'erreur doit rester générique.
    """
    workspace = client.post(
        "/api/v1/accounts/workspaces",
        json={
            "owner_name": "Compte Suspendu",
            "email": "suspendu@example.com",
            "organization_name": "Suspendu SARL",
            "territory": "CI",
            "password": "MotDePasseSolide42!",
        },
    ).json()

    # On simule la suspension directement dans le stockage en mémoire
    # utilisé par les tests (pas de DB Postgres disponible ici).
    from baobab.api.routes import accounts as accounts_module

    accounts_module.WORKSPACES[workspace["workspace_id"]]["suspended"] = True

    wrong_password_response = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "suspendu@example.com", "password": "mot-de-passe-invalide"},
    )
    assert wrong_password_response.status_code == 403
    assert wrong_password_response.json()["detail"] == "Email ou mot de passe incorrect."

    correct_password_response = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "suspendu@example.com", "password": "MotDePasseSolide42!"},
    )
    assert correct_password_response.status_code == 403
    assert "suspendu" in correct_password_response.json()["detail"].lower()


# ─── Correctifs de sécurité : superadmin (JWT) ───────────────────────────────


def test_superadmin_endpoints_reject_missing_or_malformed_authorization():
    no_header = client.get("/api/v1/accounts/superadmin/overview")
    assert no_header.status_code == 403

    malformed = client.get(
        "/api/v1/accounts/superadmin/overview",
        headers={"Authorization": "NotBearer sometoken"},
    )
    assert malformed.status_code == 403

    invalid_jwt = client.get(
        "/api/v1/accounts/superadmin/overview",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert invalid_jwt.status_code == 403


def test_superadmin_setup_rejects_wrong_bootstrap_token():
    response = client.post(
        "/api/v1/superadmin/setup",
        json={
            "email": "attacker@example.com",
            "password": "TryToBecomeAdmin123!",
            "bootstrap_token": "baobab-superadmin-dev",  # ancienne valeur par défaut
        },
    )
    # 403 (mauvais token) ou 409 (compte déjà créé par un autre test) :
    # jamais 201, dans tous les cas.
    assert response.status_code in (403, 409)


@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL requis pour le compte superadmin")
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

    token = _bootstrap_and_login_superadmin("super-overview@example.com")
    client.post(
        f"/api/v1/accounts/payments/{checkout['payment_id']}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )

    overview_response = client.get(
        "/api/v1/accounts/superadmin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["workspaces_count"] >= 1
    assert overview["confirmed_revenue_xof"] >= 5000


@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL requis pour le compte superadmin")
def test_superadmin_can_provision_custom_workspace_with_unlimited_access():
    token = _bootstrap_and_login_superadmin("super-provision@example.com")

    create_response = client.post(
        "/api/v1/accounts/superadmin/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "owner_name": "Client VIP",
            "email": "client-vip@example.com",
            "organization_name": "Client VIP Holding",
            "territory": "CI",
            "admin_name": "Admin VIP",
            "admin_email": "admin-vip@example.com",
            "grant_unlimited_access": True,
            "enabled_services": ["all_verticals", "alerts", "internal_requests"],
            "branding": {
                "display_name": "Espace Client VIP",
                "primary_color": "#1A6B4A",
                "welcome_message": "Bienvenue dans votre espace juridique dedie.",
            },
        },
    )

    assert create_response.status_code == 201
    workspace = create_response.json()
    assert workspace["plan"] == "premium"
    assert workspace["subscription_status"] == "unlimited_grant"
    assert workspace["billing_override"] is True
    assert workspace["subscription_expires_at"] is None
    assert workspace["admin_name"] == "Admin VIP"
    assert workspace["admin_email"] == "admin-vip@example.com"
    assert workspace["branding"]["display_name"] == "Espace Client VIP"
    assert workspace["admin_token"].startswith("adm_")
    assert workspace["user_token"].startswith("usr_")

    temp_password = workspace["_temp_password"]

    client_login = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "client-vip@example.com", "password": temp_password},
    )
    assert client_login.status_code == 200
    assert client_login.json()["role"] == "client"
    assert client_login.json()["workspace"]["workspace_id"] == workspace["workspace_id"]
    assert client_login.json()["workspace"]["admin_token"] is None
    assert client_login.json()["workspace"]["user_token"] is None

    admin_login = client.post(
        "/api/v1/accounts/access/login",
        json={"email": "admin-vip@example.com", "password": temp_password},
    )
    assert admin_login.status_code == 200
    assert admin_login.json()["role"] == "admin"

    first_request = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Demande illimitee 1",
            "message": "Premiere demande depuis un espace accorde par superadmin.",
        },
    )
    second_request = client.post(
        f"/api/v1/accounts/workspaces/{workspace['workspace_id']}/internal-requests",
        json={
            "subject": "Demande illimitee 2",
            "message": "Deuxieme demande sans paiement ni blocage de quota.",
        },
    )

    assert first_request.status_code == 201
    assert second_request.status_code == 201


@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL requis pour le compte superadmin")
def test_superadmin_can_customize_workspace_and_regenerate_admin_token():
    token = _bootstrap_and_login_superadmin("super-customize@example.com")

    workspace = client.post(
        "/api/v1/accounts/superadmin/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "owner_name": "Client Modifiable",
            "email": "modifiable@example.com",
            "organization_name": "Client Modifiable SA",
            "territory": "CI",
            "admin_name": "Ancien Admin",
            "admin_email": "ancien-admin@example.com",
        },
    ).json()
    old_token = workspace["admin_token"]

    update_response = client.patch(
        f"/api/v1/accounts/superadmin/workspaces/{workspace['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "organization_name": "Client Personnalise SA",
            "admin_name": "Nouvel Admin",
            "admin_email": "nouvel-admin@example.com",
            "enabled_services": ["cima", "ohada", "support"],
            "branding": {
                "display_name": "Portail Client Personnalise",
                "primary_color": "#C9A84C",
            },
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["organization_name"] == "Client Personnalise SA"
    assert updated["admin_name"] == "Nouvel Admin"
    assert updated["admin_email"] == "nouvel-admin@example.com"
    assert updated["enabled_services"] == ["cima", "ohada", "support"]
    assert updated["branding"]["display_name"] == "Portail Client Personnalise"

    token_response = client.post(
        f"/api/v1/accounts/superadmin/workspaces/{workspace['workspace_id']}/admin-token",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert token_response.status_code == 200
    new_token = token_response.json()["admin_token"]
    assert new_token.startswith("adm_")
    assert new_token != old_token
