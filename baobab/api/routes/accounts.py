import json
import logging
import os
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from baobab.auth import constant_time_equals, hash_password, verify_password, verify_superadmin_jwt
from baobab.config import settings
from baobab.rate_limit import client_ip, enforce_rate_limit
from baobab import notifications

router = APIRouter(tags=["accounts"])


class SubscriptionPlan(StrEnum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class PaymentProvider(StrEnum):
    ORANGE_MONEY = "orange_money"
    MTN_MONEY = "mtn_money"
    WAVE = "wave"


PLAN_CATALOG = {
    SubscriptionPlan.FREE: {
        "name": "Espace gratuit",
        "monthly_price_xof": 0,
        "currency": "XOF",
        "internal_request_quota": 1,
        "analyses_daily_limit": 5,
        "services": ["workspace", "one_internal_request", "legal_search"],
        "included_packs": ["discovery"],
    },
    SubscriptionPlan.BASIC: {
        "name": "Professionnel",
        "monthly_price_xof": 5000,
        "currency": "XOF",
        "internal_request_quota": None,
        "analyses_daily_limit": 30,
        "services": [
            "workspace", "internal_requests", "legal_dashboards", "alerts",
            "legal_search", "legal_fr", "eu", "echr",
        ],
        "included_packs": ["france", "europe"],
    },
    SubscriptionPlan.PREMIUM: {
        "name": "Cabinet & Équipe",
        "monthly_price_xof": 10000,
        "currency": "XOF",
        "internal_request_quota": None,
        "analyses_daily_limit": None,  # illimité
        "services": [
            "workspace",
            "internal_requests",
            "legal_dashboards",
            "alerts",
            "all_verticals",
            "priority_support",
        ],
        "included_packs": ["france", "europe", "ohada", "cima", "bceao_uemoa", "international"],
    },
}


LEGAL_PACK_CATALOG = {
    "france": {
        "name": "France",
        "description": "Législation et jurisprudence françaises via Légifrance et Judilibre.",
        "services": ["legal_fr"],
        "jurisdictions": ["FR"],
    },
    "europe": {
        "name": "Europe & CEDH",
        "description": "Droit de l'Union européenne et jurisprudence de la CEDH.",
        "services": ["eu", "echr"],
        "jurisdictions": ["EU", "ECHR"],
    },
    "ohada": {
        "name": "OHADA",
        "description": "Droit des affaires OHADA, actes uniformes et jurisprudence CCJA.",
        "services": ["ohada"],
        "jurisdictions": ["OHADA", "CCJA"],
    },
    "cima": {
        "name": "CIMA",
        "description": "Droit des assurances CIMA et cascades de gestion des sinistres.",
        "services": ["cima"],
        "jurisdictions": ["CIMA", "CRCA"],
    },
    "bceao_uemoa": {
        "name": "BCEAO & UEMOA",
        "description": "Banque, finance, KYC, LCB/FT et conformité prudentielle.",
        "services": ["bceao"],
        "jurisdictions": ["BCEAO", "UEMOA"],
    },
    "international": {
        "name": "Droit international",
        "description": "Sources et juridictions internationales, séparées des droits nationaux.",
        "services": ["international"],
        "jurisdictions": ["ICJ", "ICC"],
    },
}


def _workspace_legal_packs(workspace: dict) -> list[str]:
    plan = workspace.get("plan", SubscriptionPlan.FREE)
    plan_details = PLAN_CATALOG.get(plan, PLAN_CATALOG[SubscriptionPlan.FREE])
    services = set(plan_details["services"]) | set(workspace.get("enabled_services") or [])
    if "all_verticals" in services:
        return list(LEGAL_PACK_CATALOG)
    return [
        code for code, pack in LEGAL_PACK_CATALOG.items()
        if services.intersection(pack["services"])
    ]

WORKSPACES: dict[str, dict] = {}
INTERNAL_REQUESTS: dict[str, dict] = {}
PAYMENTS: dict[str, dict] = {}
DB_INITIALIZED = False


def _json_dump(value: dict) -> str:
    return json.dumps(value, default=str)


def _json_load(value) -> dict:
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


class WorkspaceCreate(BaseModel):
    owner_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=180)
    organization_name: str = Field(..., min_length=2, max_length=180)
    territory: str = Field(default="CI", min_length=2, max_length=8)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class InternalRequestCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=160)
    message: str = Field(..., min_length=10, max_length=2000)


class SubscriptionCheckoutCreate(BaseModel):
    plan: SubscriptionPlan
    provider: PaymentProvider
    phone_number: str = Field(..., min_length=8, max_length=32)


class InternalRequestUpdate(BaseModel):
    status: str = Field(..., pattern="^(submitted|in_review|approved|rejected|closed)$")
    admin_note: str | None = Field(default=None, max_length=2000)


class EmailPasswordLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePassword(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class WorkspaceBranding(BaseModel):
    display_name: str | None = Field(default=None, max_length=180)
    primary_color: str | None = Field(default=None, max_length=32)
    logo_url: str | None = Field(default=None, max_length=500)
    welcome_message: str | None = Field(default=None, max_length=500)


class SuperadminWorkspaceCreate(BaseModel):
    owner_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=180)
    organization_name: str = Field(..., min_length=2, max_length=180)
    territory: str = Field(default="CI", min_length=2, max_length=8)
    plan: str = Field(default="unlimited")
    user_name: str | None = Field(default=None, min_length=2, max_length=120)
    user_email: str | None = Field(default=None, min_length=5, max_length=180)
    admin_name: str | None = Field(default=None, min_length=2, max_length=120)
    admin_email: str | None = Field(default=None, min_length=5, max_length=180)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    enabled_services: list[str] = Field(
        default_factory=list
    )
    branding: WorkspaceBranding = Field(default_factory=WorkspaceBranding)


class SuperadminWorkspaceUpdate(BaseModel):
    owner_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=180)
    organization_name: str | None = Field(default=None, min_length=2, max_length=180)
    user_name: str | None = Field(default=None, min_length=2, max_length=120)
    user_email: str | None = Field(default=None, min_length=5, max_length=180)
    admin_name: str | None = Field(default=None, min_length=2, max_length=120)
    admin_email: str | None = Field(default=None, min_length=5, max_length=180)
    grant_unlimited_access: bool | None = None
    enabled_services: list[str] | None = None
    branding: WorkspaceBranding | None = None
    plan: str | None = None
    subscription_status: str | None = None
    subscription_expires_at: str | None = None
    suspended: bool | None = None


def _require_superadmin(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bearer token superadmin requis.",
        )
    verify_superadmin_jwt(authorization[7:], settings.jwt_secret)


def _normalize_database_url(database_url: str) -> str:
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parts = urlsplit(database_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"channel_binding"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _database_url() -> str:
    return _normalize_database_url(settings.database_url)


def _use_database() -> bool:
    override = os.getenv("BAOBAB_STORAGE_BACKEND")
    if override:
        return override.lower() == "postgres"
    return "localhost" not in settings.database_url


async def _connect_db():
    try:
        return await asyncpg.connect(_database_url(), statement_cache_size=0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {exc.__class__.__name__}",
        ) from exc


async def _ensure_db() -> None:
    global DB_INITIALIZED
    if DB_INITIALIZED or not _use_database():
        return
    conn = await _connect_db()
    try:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS account_workspaces (
                workspace_id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS account_internal_requests (
                request_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS account_payments (
                payment_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_account_requests_workspace
                ON account_internal_requests (workspace_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_account_payments_workspace
                ON account_payments (workspace_id)
            """,
        ]
        for statement in statements:
            await conn.execute(statement)
        DB_INITIALIZED = True
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database initialization failed: {exc.__class__.__name__}",
        ) from exc
    finally:
        await conn.close()


async def _save_workspace(workspace: dict) -> None:
    if not _use_database():
        WORKSPACES[workspace["workspace_id"]] = workspace
        return
    await _ensure_db()
    conn = await _connect_db()
    try:
        await conn.execute(
            """
            INSERT INTO account_workspaces (workspace_id, data)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (workspace_id)
            DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
            """,
            workspace["workspace_id"],
            _json_dump(workspace),
        )
    finally:
        await conn.close()


async def _save_internal_request(item: dict) -> None:
    if not _use_database():
        INTERNAL_REQUESTS[item["request_id"]] = item
        return
    await _ensure_db()
    conn = await _connect_db()
    try:
        await conn.execute(
            """
            INSERT INTO account_internal_requests (request_id, workspace_id, data)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (request_id)
            DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
            """,
            item["request_id"],
            item["workspace_id"],
            _json_dump(item),
        )
    finally:
        await conn.close()


async def _save_payment(payment: dict) -> None:
    if not _use_database():
        PAYMENTS[payment["payment_id"]] = payment
        return
    await _ensure_db()
    conn = await _connect_db()
    try:
        await conn.execute(
            """
            INSERT INTO account_payments (payment_id, workspace_id, data)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (payment_id)
            DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
            """,
            payment["payment_id"],
            payment["workspace_id"],
            _json_dump(payment),
        )
    finally:
        await conn.close()


async def _delete_workspace(workspace_id: str) -> None:
    if not _use_database():
        WORKSPACES.pop(workspace_id, None)
        return
    await _ensure_db()
    conn = await _connect_db()
    try:
        await conn.execute(
            "DELETE FROM account_workspaces WHERE workspace_id = $1", workspace_id
        )
    finally:
        await conn.close()


async def _load_workspace(workspace_id: str) -> dict | None:
    if not _use_database():
        return WORKSPACES.get(workspace_id)
    await _ensure_db()
    conn = await _connect_db()
    try:
        row = await conn.fetchrow(
            "SELECT data FROM account_workspaces WHERE workspace_id = $1",
            workspace_id,
        )
        return _json_load(row["data"]) if row else None
    finally:
        await conn.close()


async def _list_workspaces() -> list[dict]:
    if not _use_database():
        return list(WORKSPACES.values())
    await _ensure_db()
    conn = await _connect_db()
    try:
        rows = await conn.fetch("SELECT data FROM account_workspaces ORDER BY created_at")
        return [_json_load(row["data"]) for row in rows]
    finally:
        await conn.close()


async def _load_internal_request(request_id: str) -> dict | None:
    if not _use_database():
        return INTERNAL_REQUESTS.get(request_id)
    await _ensure_db()
    conn = await _connect_db()
    try:
        row = await conn.fetchrow(
            "SELECT data FROM account_internal_requests WHERE request_id = $1",
            request_id,
        )
        return _json_load(row["data"]) if row else None
    finally:
        await conn.close()


async def _list_internal_requests(workspace_id: str | None = None) -> list[dict]:
    if not _use_database():
        return [
            request
            for request in INTERNAL_REQUESTS.values()
            if workspace_id is None or request["workspace_id"] == workspace_id
        ]
    await _ensure_db()
    conn = await _connect_db()
    try:
        if workspace_id:
            rows = await conn.fetch(
                "SELECT data FROM account_internal_requests WHERE workspace_id = $1 ORDER BY created_at",
                workspace_id,
            )
        else:
            rows = await conn.fetch("SELECT data FROM account_internal_requests ORDER BY created_at")
        return [_json_load(row["data"]) for row in rows]
    finally:
        await conn.close()


async def _load_payment(payment_id: str) -> dict | None:
    if not _use_database():
        return PAYMENTS.get(payment_id)
    await _ensure_db()
    conn = await _connect_db()
    try:
        row = await conn.fetchrow("SELECT data FROM account_payments WHERE payment_id = $1", payment_id)
        return _json_load(row["data"]) if row else None
    finally:
        await conn.close()


async def _list_payments() -> list[dict]:
    if not _use_database():
        return list(PAYMENTS.values())
    await _ensure_db()
    conn = await _connect_db()
    try:
        rows = await conn.fetch("SELECT data FROM account_payments ORDER BY created_at")
        return [_json_load(row["data"]) for row in rows]
    finally:
        await conn.close()


async def _require_workspace_admin(workspace_id: str, x_admin_token: str | None) -> dict:
    workspace = await _get_workspace(workspace_id)
    if not constant_time_equals(x_admin_token, workspace.get("admin_token")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace admin token required",
        )
    return workspace


async def _require_workspace_access(workspace_id: str, access_token: str | None) -> dict:
    """
    Autorise la lecture d'un workspace à quiconque présente son token
    admin OU son token utilisateur (les deux donnent accès en lecture ;
    seul le token admin donne des droits d'écriture, vérifiés ailleurs).

    Sans ce contrôle, connaître/deviner un workspace_id suffisait à lire
    les données personnelles du client (IDOR — cf. audit sécurité).
    """
    workspace = await _get_workspace(workspace_id)
    is_admin = constant_time_equals(access_token, workspace.get("admin_token"))
    is_user = constant_time_equals(access_token, workspace.get("user_token"))
    if not (is_admin or is_user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'accès au workspace requis.",
        )
    return workspace


async def _public_workspace(workspace: dict) -> dict:
    requests = await _list_internal_requests(workspace["workspace_id"])
    plan = workspace["plan"]
    plan_details = PLAN_CATALOG.get(plan, PLAN_CATALOG[SubscriptionPlan.PREMIUM])
    return {
        **workspace,
        "admin_token": None,
        "user_token": None,
        "plan_details": plan_details,
        "legal_packs": _workspace_legal_packs(workspace),
        "internal_requests_used": len(requests),
    }


async def _admin_workspace(workspace: dict) -> dict:
    return {
        **await _public_workspace(workspace),
        "admin_token": workspace.get("admin_token"),
        "user_token": workspace.get("user_token"),
    }


def _generate_temp_password() -> str:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14))


def _create_workspace_record(
    owner_name: str,
    email: str,
    organization_name: str,
    territory: str,
    user_name: str | None = None,
    user_email: str | None = None,
    admin_name: str | None = None,
    admin_email: str | None = None,
    password: str | None = None,
    plan: str = "free",
    enabled_services: list[str] | None = None,
    branding: WorkspaceBranding | None = None,
    provisioned_by: str = "self_service",
) -> tuple[dict, str]:
    """Returns (workspace_dict, clear_password). clear_password is None if the user chose their own."""
    now = datetime.now(UTC)
    is_temporary = password is None
    clear_password = _generate_temp_password() if is_temporary else None
    effective_password = clear_password if is_temporary else password

    grant_unlimited = plan == "unlimited"
    effective_plan = SubscriptionPlan.PREMIUM if grant_unlimited else plan
    sub_status = "unlimited_grant" if grant_unlimited else ("free" if plan == "free" else "active")
    sub_expires = None if grant_unlimited or plan == "free" else (
        datetime.now(UTC) + timedelta(days=30)
    ).isoformat()

    workspace = {
        "workspace_id": f"ws_{uuid4().hex[:12]}",
        "owner_name": owner_name,
        "email": email.lower(),
        "organization_name": organization_name,
        "territory": territory.upper(),
        "user_name": user_name or owner_name,
        "user_email": (user_email or email).lower(),
        "user_token": f"usr_{uuid4().hex}",
        "user_password_hash": hash_password(effective_password),
        "admin_name": admin_name or owner_name,
        "admin_email": (admin_email or email).lower(),
        "admin_token": f"adm_{uuid4().hex}",
        "admin_password_hash": hash_password(effective_password),
        "plan": effective_plan,
        "subscription_status": sub_status,
        "subscription_expires_at": sub_expires,
        "billing_override": grant_unlimited,
        "enabled_services": enabled_services or [],
        "branding": (branding or WorkspaceBranding()).model_dump(),
        "provisioned_by": provisioned_by,
        "password_is_temporary": is_temporary,
        "created_at": now.isoformat(),
    }
    return workspace, clear_password


async def _get_workspace(workspace_id: str) -> dict:
    workspace = await _load_workspace(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


async def _find_workspace_by_token(user_token: str | None) -> dict | None:
    """Trouve un workspace par son user_token (comparaison temps constant)."""
    if not user_token:
        return None
    for ws in await _list_workspaces():
        if constant_time_equals(user_token, ws.get("user_token")):
            return ws
    return None


async def check_and_increment_analyses_quota(user_token: str) -> dict:
    """
    Vérifie le quota d'analyses du workspace et l'incrémente.
    Retourne {"allowed": bool, "used": int, "limit": int|None, "remaining": int|None}.
    Lève HTTPException 429 si quota dépassé.
    """
    workspace = await require_workspace_service(user_token, "legal_search")

    plan = workspace.get("plan", SubscriptionPlan.FREE)
    limit = PLAN_CATALOG[plan]["analyses_daily_limit"]

    today = datetime.now(UTC).date().isoformat()
    reset_date = workspace.get("analyses_reset_date")
    used = workspace.get("analyses_today", 0)

    # Remise à zéro si nouveau jour
    if reset_date != today:
        used = 0
        workspace["analyses_reset_date"] = today

    # Vérification quota
    if limit is not None and used >= limit:
        plan_name = PLAN_CATALOG[plan]["name"]
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "quota_exceeded",
                "message": (
                    f"Quota journalier atteint ({used}/{limit} analyses). "
                    f"Plan actuel : {plan_name}."
                ),
                "used": used,
                "limit": limit,
                "plan": plan,
                "upgrade_plans": {
                    "basic": {"name": "Professionnel", "price_xof": 5000, "limit_daily": 30},
                    "premium": {"name": "Cabinet & Équipe", "price_xof": 10000, "limit_daily": "illimité"},
                },
            },
        )

    # Incrément
    workspace["analyses_today"] = used + 1
    workspace["analyses_reset_date"] = today
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)

    remaining = (limit - used - 1) if limit is not None else None
    return {
        "allowed": True,
        "used": used + 1,
        "limit": limit,
        "remaining": remaining,
        "plan": plan,
    }


async def require_workspace_service(user_token: str | None, service: str) -> dict:
    """Contrôle côté serveur qu'un espace actif possède le service demandé."""
    if not user_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Connexion requise pour utiliser ce service.",
        )

    workspace = await _find_workspace_by_token(user_token)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session utilisateur invalide ou expirée.",
        )
    if workspace.get("suspended"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet espace est suspendu.",
        )

    subscription_status = workspace.get("subscription_status", "free")
    if subscription_status not in {"free", "active", "unlimited_grant"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet abonnement n'est pas actif.",
        )
    expires_at = workspace.get("subscription_expires_at")
    if subscription_status == "active" and expires_at:
        try:
            expiration = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Invalid subscription expiry for workspace %s", workspace.get("workspace_id"))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La date d'expiration de cet abonnement est invalide.",
            )
        if expiration <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cet abonnement a expiré. Renouvelez-le pour continuer.",
            )

    plan = workspace.get("plan", SubscriptionPlan.FREE)
    plan_details = PLAN_CATALOG.get(plan, PLAN_CATALOG[SubscriptionPlan.FREE])
    entitled_services = set(plan_details["services"]) | set(workspace.get("enabled_services") or [])
    if service not in entitled_services and "all_verticals" not in entitled_services:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Ce service n'est pas inclus dans votre abonnement.",
                "service": service,
                "current_plan": str(plan),
                "upgrade_required": True,
            },
        )
    return workspace


@router.get("/plans")
async def list_plans():
    return {
        "plans": [
            {"plan": plan, **details}
            for plan, details in PLAN_CATALOG.items()
        ],
        "payment_providers": [provider.value for provider in PaymentProvider],
        "legal_packs": [
            {"code": code, **details}
            for code, details in LEGAL_PACK_CATALOG.items()
        ],
    }


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(request: WorkspaceCreate, http_request: Request):
    await enforce_rate_limit(
        key=f"create_workspace:{client_ip(http_request)}", limit=5, window_seconds=86400
    )
    workspace, clear_password = _create_workspace_record(
        owner_name=request.owner_name,
        email=request.email,
        organization_name=request.organization_name,
        territory=request.territory,
        password=request.password,
    )
    await _save_workspace(workspace)
    await notifications.notify_user_workspace_created(workspace, clear_password)
    await notifications.notify_admin_new_workspace(workspace)
    return await _admin_workspace(workspace)


@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    x_access_token: str | None = Header(default=None),
):
    """
    Renvoie les informations du workspace (sans les tokens).

    Nécessite le token admin ou le token utilisateur du workspace : le
    workspace_id seul (48 bits d'entropie, potentiellement visible dans
    des logs, emails ou URLs partagées) ne suffit plus à consulter les
    coordonnées et le statut d'abonnement du client (IDOR corrigé —
    cf. audit sécurité).
    """
    workspace = await _require_workspace_access(workspace_id, x_access_token)
    return await _public_workspace(workspace)


@router.post(
    "/workspaces/{workspace_id}/internal-requests",
    status_code=status.HTTP_201_CREATED,
)
async def create_internal_request(
    workspace_id: str,
    request: InternalRequestCreate,
    x_access_token: str | None = Header(default=None),
):
    workspace = await _require_workspace_access(workspace_id, x_access_token)
    workspace_requests = await _list_internal_requests(workspace_id)
    quota = PLAN_CATALOG[workspace["plan"]]["internal_request_quota"]
    if quota is not None and len(workspace_requests) >= quota:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Quota gratuit atteint. Passez à Professionnel ou Cabinet & Équipe.",
        )

    request_id = f"req_{uuid4().hex[:12]}"
    item = {
        "request_id": request_id,
        "workspace_id": workspace_id,
        "subject": request.subject,
        "message": request.message,
        "status": "submitted",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await _save_internal_request(item)
    return item


@router.get("/workspaces/{workspace_id}/internal-requests")
async def list_internal_requests(
    workspace_id: str,
    x_access_token: str | None = Header(default=None),
):
    """Nécessite un token du workspace (le contenu des demandes est privé)."""
    await _require_workspace_access(workspace_id, x_access_token)
    return {"requests": await _list_internal_requests(workspace_id)}


_GENERIC_LOGIN_ERROR = "Email ou mot de passe incorrect."


@router.post("/access/login")
async def access_login(request: EmailPasswordLogin, http_request: Request):
    # Anti brute-force / anti énumération : throttling par IP avant toute
    # lecture en base. Cf. livre "Web Application Security", ch. 23 et 32.
    await enforce_rate_limit(
        key=f"login:{client_ip(http_request)}", limit=20, window_seconds=300
    )

    email = request.email.strip().lower()
    for workspace in await _list_workspaces():
        is_admin = workspace.get("admin_email") == email
        is_user = workspace.get("user_email") == email
        if not is_admin and not is_user:
            continue

        # NB : aucun repli sur le token en guise de mot de passe. Un
        # workspace créé via `_create_workspace_record` a toujours un
        # hash de mot de passe ; un repli "password == token" mélangerait
        # un identifiant porteur (renvoyé en clair par l'API) avec un
        # secret d'authentification, ce qui est une faille en soi si les
        # deux venaient à être confondus par un intégrateur.
        #
        # L'état "suspendu" n'est révélé qu'APRÈS validation du mot de
        # passe : sinon, un attaquant sans le bon mot de passe pourrait
        # déduire qu'un email existe et est suspendu (énumération de
        # comptes, cf. ch. 23 du livre).
        if is_admin:
            stored = workspace.get("admin_password_hash")
            if stored and verify_password(request.password, stored):
                if workspace.get("suspended"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Ce compte est suspendu. Contactez l'administrateur BAOBAB.",
                    )
                logger.info("Login success: %s role=%s", email, "admin")
                return {
                    "role": "admin",
                    "token": workspace["admin_token"],
                    "workspace": await _admin_workspace(workspace),
                    "password_is_temporary": workspace.get("password_is_temporary", False),
                    "message": "Workspace admin access granted",
                }
        if is_user:
            stored = workspace.get("user_password_hash")
            if stored and verify_password(request.password, stored):
                if workspace.get("suspended"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Ce compte est suspendu. Contactez l'administrateur BAOBAB.",
                    )
                logger.info("Login success: %s role=%s", email, "client")
                return {
                    "role": "client",
                    "token": workspace["user_token"],
                    "workspace": await _public_workspace(workspace),
                    "password_is_temporary": workspace.get("password_is_temporary", False),
                    "message": "Client workspace access granted",
                }

    logger.warning("Login failed for email=%s from ip=%s", email, client_ip(http_request))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_GENERIC_LOGIN_ERROR,
    )


@router.post("/admin/change-password")
async def admin_change_password(
    request: ChangePassword,
    x_admin_token: str | None = Header(default=None),
):
    if not x_admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token admin requis.")
    for workspace in await _list_workspaces():
        if constant_time_equals(x_admin_token, workspace.get("admin_token")):
            stored = workspace.get("admin_password_hash")
            if not stored or not verify_password(request.current_password, stored):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mot de passe actuel incorrect.")
            workspace["admin_password_hash"] = hash_password(request.new_password)
            workspace["password_is_temporary"] = False
            await _save_workspace(workspace)
            logger.info("Password changed for workspace %s", workspace["workspace_id"])
            return {"message": "Mot de passe modifié avec succès."}
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token invalide.")


@router.post("/client/change-password")
async def client_change_password(
    request: ChangePassword,
    x_access_token: str | None = Header(default=None),
):
    if not x_access_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token requis.")
    workspace = await _find_workspace_by_token(x_access_token)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token invalide.")
    stored = workspace.get("user_password_hash")
    if not stored or not verify_password(request.current_password, stored):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mot de passe actuel incorrect.")
    workspace["user_password_hash"] = hash_password(request.new_password)
    workspace["admin_password_hash"] = hash_password(request.new_password)
    workspace["password_is_temporary"] = False
    await _save_workspace(workspace)
    logger.info("Password changed for workspace %s", workspace["workspace_id"])
    return {"message": "Mot de passe modifié avec succès."}


@router.get("/admin/workspaces/{workspace_id}")
async def get_admin_workspace(
    workspace_id: str,
    x_admin_token: str | None = Header(default=None),
):
    workspace = await _require_workspace_admin(workspace_id, x_admin_token)
    return await _admin_workspace(workspace)


@router.get("/admin/workspaces/{workspace_id}/internal-requests")
async def list_admin_internal_requests(
    workspace_id: str,
    x_admin_token: str | None = Header(default=None),
):
    await _require_workspace_admin(workspace_id, x_admin_token)
    return {"requests": await _list_internal_requests(workspace_id)}


@router.patch("/admin/internal-requests/{request_id}")
async def update_admin_internal_request(
    request_id: str,
    request: InternalRequestUpdate,
    x_admin_token: str | None = Header(default=None),
):
    item = await _load_internal_request(request_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internal request not found",
        )
    await _require_workspace_admin(item["workspace_id"], x_admin_token)
    item["status"] = request.status
    item["admin_note"] = request.admin_note
    item["updated_at"] = datetime.now(UTC).isoformat()
    await _save_internal_request(item)
    return item


@router.get("/superadmin/overview")
async def get_superadmin_overview(
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    workspaces = await _list_workspaces()
    requests = await _list_internal_requests()
    payments = await _list_payments()
    active_subscriptions = [
        workspace
        for workspace in workspaces
        if workspace["subscription_status"] == "active"
    ]
    pending_requests = [
        request
        for request in requests
        if request["status"] in {"submitted", "in_review"}
    ]
    confirmed_payments = [
        payment
        for payment in payments
        if payment["status"] == "confirmed"
    ]
    return {
        "workspaces_count": len(workspaces),
        "active_subscriptions_count": len(active_subscriptions),
        "pending_internal_requests_count": len(pending_requests),
        "confirmed_revenue_xof": sum(payment["amount_xof"] for payment in confirmed_payments),
        "plans": {
            plan.value: sum(1 for workspace in workspaces if workspace["plan"] == plan)
            for plan in SubscriptionPlan
        },
    }


@router.get("/superadmin/workspaces")
async def list_superadmin_workspaces(
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    return {"workspaces": [await _admin_workspace(workspace) for workspace in await _list_workspaces()]}


@router.post("/superadmin/workspaces", status_code=status.HTTP_201_CREATED)
async def create_superadmin_workspace(
    request: SuperadminWorkspaceCreate,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    workspace, clear_password = _create_workspace_record(
        owner_name=request.owner_name,
        email=request.email,
        organization_name=request.organization_name,
        territory=request.territory,
        user_name=request.user_name,
        user_email=request.user_email,
        admin_name=request.admin_name,
        admin_email=request.admin_email,
        password=request.password,
        plan=request.plan,
        enabled_services=request.enabled_services,
        branding=request.branding,
        provisioned_by="superadmin",
    )
    await _save_workspace(workspace)
    await notifications.notify_superadmin_workspace_created(workspace, clear_password)
    await notifications.notify_admin_new_workspace(workspace)
    result = await _admin_workspace(workspace)
    result["_temp_password"] = clear_password
    return result


@router.patch("/superadmin/workspaces/{workspace_id}")
async def update_superadmin_workspace(
    workspace_id: str,
    request: SuperadminWorkspaceUpdate,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    workspace = await _get_workspace(workspace_id)
    updates = request.model_dump(exclude_unset=True)

    for field in ["owner_name", "organization_name", "user_name", "admin_name"]:
        if field in updates and updates[field] is not None:
            workspace[field] = updates[field]
    for field in ["email", "user_email", "admin_email"]:
        if field in updates and updates[field] is not None:
            workspace[field] = updates[field].lower()
    if "enabled_services" in updates and updates["enabled_services"] is not None:
        workspace["enabled_services"] = updates["enabled_services"]
    if "branding" in updates and updates["branding"] is not None:
        workspace["branding"] = updates["branding"]
    if updates.get("grant_unlimited_access") is True:
        workspace["plan"] = SubscriptionPlan.PREMIUM
        workspace["subscription_status"] = "unlimited_grant"
        workspace["subscription_expires_at"] = None
        workspace["billing_override"] = True
    elif updates.get("grant_unlimited_access") is False and workspace["billing_override"]:
        workspace["plan"] = SubscriptionPlan.FREE
        workspace["subscription_status"] = "free"
        workspace["billing_override"] = False
    if updates.get("plan") is not None:
        raw_plan = updates["plan"]
        workspace["plan"] = SubscriptionPlan.PREMIUM if raw_plan == "unlimited" else raw_plan
    if updates.get("subscription_status") is not None:
        workspace["subscription_status"] = updates["subscription_status"]
    if "subscription_expires_at" in updates:
        workspace["subscription_expires_at"] = updates["subscription_expires_at"]
    if updates.get("suspended") is not None:
        workspace["suspended"] = updates["suspended"]

    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.delete("/superadmin/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_superadmin_workspace(
    workspace_id: str,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    await _get_workspace(workspace_id)
    await _delete_workspace(workspace_id)


@router.post("/superadmin/workspaces/{workspace_id}/reset-password")
async def reset_workspace_passwords(
    workspace_id: str,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    workspace = await _get_workspace(workspace_id)
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    new_admin_pwd = "".join(secrets.choice(alphabet) for _ in range(12))
    new_user_pwd = "".join(secrets.choice(alphabet) for _ in range(12))
    workspace["admin_password_hash"] = hash_password(new_admin_pwd)
    workspace["user_password_hash"] = hash_password(new_user_pwd)
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)
    return {
        "admin_email": workspace.get("admin_email"),
        "admin_password": new_admin_pwd,
        "user_email": workspace.get("user_email"),
        "user_password": new_user_pwd,
    }


@router.post("/superadmin/workspaces/{workspace_id}/admin-token")
async def regenerate_superadmin_workspace_admin_token(
    workspace_id: str,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    workspace = await _get_workspace(workspace_id)
    workspace["admin_token"] = f"adm_{uuid4().hex}"
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.get("/superadmin/internal-requests")
async def list_superadmin_internal_requests(
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    return {"requests": await _list_internal_requests()}


@router.get("/superadmin/payments")
async def list_superadmin_payments(
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    return {"payments": await _list_payments()}


@router.post("/workspaces/{workspace_id}/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout(
    workspace_id: str,
    request: SubscriptionCheckoutCreate,
    http_request: Request,
    x_access_token: str | None = Header(default=None),
):
    await enforce_rate_limit(
        key=f"checkout:{client_ip(http_request)}", limit=10, window_seconds=3600
    )
    workspace = await _require_workspace_access(workspace_id, x_access_token)
    if request.plan == SubscriptionPlan.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan does not require payment.",
        )

    payment_id = f"pay_{uuid4().hex[:12]}"
    payment = {
        "payment_id": payment_id,
        "workspace_id": workspace["workspace_id"],
        "plan": request.plan,
        "provider": request.provider,
        "phone_number": request.phone_number,
        "amount_xof": PLAN_CATALOG[request.plan]["monthly_price_xof"],
        "currency": "XOF",
        "billing_period": "monthly",
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "provider_reference": f"BAOBAB-{uuid4().hex[:10].upper()}",
    }
    await _save_payment(payment)
    await notifications.notify_admin_payment_pending(payment, workspace)
    return {
        **payment,
        "message": (
            "Demande d'abonnement enregistrée. "
            "L'administrateur BAOBAB va vérifier votre paiement et activer votre accès sous 24h."
        ),
    }


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(
    payment_id: str,
    authorization: str | None = Header(default=None),
):
    _require_superadmin(authorization)
    payment = await _load_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    if payment["status"] == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment already confirmed.",
        )
    workspace = await _get_workspace(payment["workspace_id"])
    payment["status"] = "confirmed"
    payment["confirmed_at"] = datetime.now(UTC).isoformat()
    workspace["plan"] = payment["plan"]
    workspace["subscription_status"] = "active"
    workspace["subscription_expires_at"] = (
        datetime.now(UTC) + timedelta(days=30)
    ).isoformat()
    await _save_payment(payment)
    await _save_workspace(workspace)
    await notifications.notify_user_payment_confirmed(payment, workspace)
    return {
        "payment": payment,
        "workspace": await _public_workspace(workspace),
    }
