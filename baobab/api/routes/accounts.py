from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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


def _public_workspace(workspace: dict) -> dict:
    requests = [
        request
        for request in INTERNAL_REQUESTS.values()
        if request["workspace_id"] == workspace["workspace_id"]
    ]
    return {
        **workspace,
        "plan_details": PLAN_CATALOG[workspace["plan"]],
        "internal_requests_used": len(requests),
    }


def _get_workspace(workspace_id: str) -> dict:
    workspace = WORKSPACES.get(workspace_id)
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
    workspace_id = f"ws_{uuid4().hex[:12]}"
    now = datetime.now(UTC)
    workspace = {
        "workspace_id": workspace_id,
        "owner_name": request.owner_name,
        "email": request.email.lower(),
        "organization_name": request.organization_name,
        "territory": request.territory.upper(),
        "plan": SubscriptionPlan.FREE,
        "subscription_status": "free",
        "subscription_expires_at": None,
        "created_at": now.isoformat(),
    }
    WORKSPACES[workspace_id] = workspace
    return _public_workspace(workspace)


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    return _public_workspace(_get_workspace(workspace_id))


@router.post(
    "/workspaces/{workspace_id}/internal-requests",
    status_code=status.HTTP_201_CREATED,
)
async def create_internal_request(workspace_id: str, request: InternalRequestCreate):
    workspace = _get_workspace(workspace_id)
    workspace_requests = [
        item
        for item in INTERNAL_REQUESTS.values()
        if item["workspace_id"] == workspace_id
    ]
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
    INTERNAL_REQUESTS[request_id] = item
    return item


@router.get("/workspaces/{workspace_id}/internal-requests")
async def list_internal_requests(workspace_id: str):
    _get_workspace(workspace_id)
    return {
        "requests": [
            request
            for request in INTERNAL_REQUESTS.values()
            if request["workspace_id"] == workspace_id
        ]
    }


@router.post("/workspaces/{workspace_id}/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout(workspace_id: str, request: SubscriptionCheckoutCreate):
    workspace = _get_workspace(workspace_id)
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
    PAYMENTS[payment_id] = payment
    return {
        **payment,
        "message": "Payment initialized. Provider confirmation must activate the subscription.",
    }


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(payment_id: str):
    payment = PAYMENTS.get(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    workspace = _get_workspace(payment["workspace_id"])
    payment["status"] = "confirmed"
    payment["confirmed_at"] = datetime.now(UTC).isoformat()
    workspace["plan"] = payment["plan"]
    workspace["subscription_status"] = "active"
    workspace["subscription_expires_at"] = (
        datetime.now(UTC) + timedelta(days=30)
    ).isoformat()
    return {
        "payment": payment,
        "workspace": _public_workspace(workspace),
    }
