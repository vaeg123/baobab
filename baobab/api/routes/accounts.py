import json
import os
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from baobab.config import settings

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
        "services": ["workspace", "one_internal_request"],
    },
    SubscriptionPlan.BASIC: {
        "name": "Basic",
        "monthly_price_xof": 5000,
        "currency": "XOF",
        "internal_request_quota": None,
        "services": ["workspace", "internal_requests", "legal_dashboards", "alerts"],
    },
    SubscriptionPlan.PREMIUM: {
        "name": "Premium",
        "monthly_price_xof": 10000,
        "currency": "XOF",
        "internal_request_quota": None,
        "services": [
            "workspace",
            "internal_requests",
            "legal_dashboards",
            "alerts",
            "all_verticals",
            "priority_support",
        ],
    },
}

WORKSPACES: dict[str, dict] = {}
INTERNAL_REQUESTS: dict[str, dict] = {}
PAYMENTS: dict[str, dict] = {}
SUPERADMIN_TOKEN = os.getenv("BAOBAB_SUPERADMIN_TOKEN", "baobab-superadmin-dev")
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


class AdminLogin(BaseModel):
    admin_token: str = Field(..., min_length=12, max_length=80)


class AccessLogin(BaseModel):
    access_code: str = Field(..., min_length=12, max_length=80)


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
    user_name: str | None = Field(default=None, min_length=2, max_length=120)
    user_email: str | None = Field(default=None, min_length=5, max_length=180)
    admin_name: str = Field(..., min_length=2, max_length=120)
    admin_email: str = Field(..., min_length=5, max_length=180)
    grant_unlimited_access: bool = True
    enabled_services: list[str] = Field(
        default_factory=lambda: ["all_verticals", "alerts", "internal_requests", "priority_support"]
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


def _require_superadmin(x_superadmin_token: str | None) -> None:
    if x_superadmin_token != SUPERADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin token required",
        )


def _database_url() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _use_database() -> bool:
    override = os.getenv("BAOBAB_STORAGE_BACKEND")
    if override:
        return override.lower() == "postgres"
    return "localhost" not in settings.database_url


async def _connect_db():
    return await asyncpg.connect(_database_url(), statement_cache_size=0)


async def _ensure_db() -> None:
    global DB_INITIALIZED
    if DB_INITIALIZED or not _use_database():
        return
    conn = await _connect_db()
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_workspaces (
                workspace_id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS account_internal_requests (
                request_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS account_payments (
                payment_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_account_requests_workspace
                ON account_internal_requests (workspace_id);
            CREATE INDEX IF NOT EXISTS idx_account_payments_workspace
                ON account_payments (workspace_id);
            """
        )
        DB_INITIALIZED = True
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
    if x_admin_token != workspace["admin_token"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace admin token required",
        )
    return workspace


async def _public_workspace(workspace: dict) -> dict:
    requests = await _list_internal_requests(workspace["workspace_id"])
    return {
        **workspace,
        "admin_token": None,
        "user_token": None,
        "plan_details": PLAN_CATALOG[workspace["plan"]],
        "internal_requests_used": len(requests),
    }


async def _admin_workspace(workspace: dict) -> dict:
    return {
        **await _public_workspace(workspace),
        "admin_token": workspace["admin_token"],
        "user_token": workspace["user_token"],
    }


def _create_workspace_record(
    owner_name: str,
    email: str,
    organization_name: str,
    territory: str,
    user_name: str | None = None,
    user_email: str | None = None,
    admin_name: str | None = None,
    admin_email: str | None = None,
    grant_unlimited_access: bool = False,
    enabled_services: list[str] | None = None,
    branding: WorkspaceBranding | None = None,
    provisioned_by: str = "self_service",
) -> dict:
    now = datetime.now(UTC)
    workspace = {
        "workspace_id": f"ws_{uuid4().hex[:12]}",
        "owner_name": owner_name,
        "email": email.lower(),
        "organization_name": organization_name,
        "territory": territory.upper(),
        "user_name": user_name or owner_name,
        "user_email": (user_email or email).lower(),
        "user_token": f"usr_{uuid4().hex}",
        "admin_name": admin_name or owner_name,
        "admin_email": (admin_email or email).lower(),
        "admin_token": f"adm_{uuid4().hex}",
        "plan": SubscriptionPlan.PREMIUM if grant_unlimited_access else SubscriptionPlan.FREE,
        "subscription_status": "unlimited_grant" if grant_unlimited_access else "free",
        "subscription_expires_at": None,
        "billing_override": grant_unlimited_access,
        "enabled_services": enabled_services or [],
        "branding": (branding or WorkspaceBranding()).model_dump(),
        "provisioned_by": provisioned_by,
        "created_at": now.isoformat(),
    }
    return workspace


async def _get_workspace(workspace_id: str) -> dict:
    workspace = await _load_workspace(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
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
    }


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(request: WorkspaceCreate):
    workspace = _create_workspace_record(
        owner_name=request.owner_name,
        email=request.email,
        organization_name=request.organization_name,
        territory=request.territory,
    )
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    return await _public_workspace(await _get_workspace(workspace_id))


@router.post(
    "/workspaces/{workspace_id}/internal-requests",
    status_code=status.HTTP_201_CREATED,
)
async def create_internal_request(workspace_id: str, request: InternalRequestCreate):
    workspace = await _get_workspace(workspace_id)
    workspace_requests = await _list_internal_requests(workspace_id)
    quota = PLAN_CATALOG[workspace["plan"]]["internal_request_quota"]
    if quota is not None and len(workspace_requests) >= quota:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Free workspace quota reached. Upgrade to Basic or Premium.",
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
async def list_internal_requests(workspace_id: str):
    await _get_workspace(workspace_id)
    return {"requests": await _list_internal_requests(workspace_id)}


@router.post("/admin/login")
async def admin_login(request: AdminLogin):
    for workspace in await _list_workspaces():
        if workspace["admin_token"] == request.admin_token:
            return await _admin_workspace(workspace)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid admin token",
    )


@router.post("/access/login")
async def access_login(request: AccessLogin):
    if request.access_code == SUPERADMIN_TOKEN:
        return {
            "role": "superadmin",
            "token": request.access_code,
            "message": "Superadmin access granted",
        }

    for workspace in await _list_workspaces():
        if workspace.get("user_token") == request.access_code:
            return {
                "role": "client",
                "token": request.access_code,
                "workspace": await _public_workspace(workspace),
                "message": "Client workspace access granted",
            }
        if workspace["admin_token"] == request.access_code:
            return {
                "role": "admin",
                "token": request.access_code,
                "workspace": await _admin_workspace(workspace),
                "message": "Workspace admin access granted",
            }

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid access code",
    )


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
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
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
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
    return {"workspaces": [await _admin_workspace(workspace) for workspace in await _list_workspaces()]}


@router.post("/superadmin/workspaces", status_code=status.HTTP_201_CREATED)
async def create_superadmin_workspace(
    request: SuperadminWorkspaceCreate,
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
    workspace = _create_workspace_record(
        owner_name=request.owner_name,
        email=request.email,
        organization_name=request.organization_name,
        territory=request.territory,
        user_name=request.user_name,
        user_email=request.user_email,
        admin_name=request.admin_name,
        admin_email=request.admin_email,
        grant_unlimited_access=request.grant_unlimited_access,
        enabled_services=request.enabled_services,
        branding=request.branding,
        provisioned_by="superadmin",
    )
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.patch("/superadmin/workspaces/{workspace_id}")
async def update_superadmin_workspace(
    workspace_id: str,
    request: SuperadminWorkspaceUpdate,
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
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

    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.post("/superadmin/workspaces/{workspace_id}/admin-token")
async def regenerate_superadmin_workspace_admin_token(
    workspace_id: str,
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
    workspace = await _get_workspace(workspace_id)
    workspace["admin_token"] = f"adm_{uuid4().hex}"
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)
    return await _admin_workspace(workspace)


@router.get("/superadmin/internal-requests")
async def list_superadmin_internal_requests(
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
    return {"requests": await _list_internal_requests()}


@router.get("/superadmin/payments")
async def list_superadmin_payments(
    x_superadmin_token: str | None = Header(default=None),
):
    _require_superadmin(x_superadmin_token)
    return {"payments": await _list_payments()}


@router.post("/workspaces/{workspace_id}/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout(workspace_id: str, request: SubscriptionCheckoutCreate):
    workspace = await _get_workspace(workspace_id)
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
    return {
        **payment,
        "message": "Payment initialized. Provider confirmation must activate the subscription.",
    }


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(payment_id: str):
    payment = await _load_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
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
    return {
        "payment": payment,
        "workspace": await _public_workspace(workspace),
    }
