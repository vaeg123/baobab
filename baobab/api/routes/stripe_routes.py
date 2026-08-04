"""
Stripe integration — checkout sessions et webhooks.

POST /api/v1/stripe/checkout/{workspace_id}   — crée une session Stripe Checkout
POST /api/v1/stripe/webhook                   — reçoit les événements Stripe
"""

import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from baobab.config import settings
from baobab import notifications
from baobab.api.routes.accounts import (
    SubscriptionPlan,
    PLAN_CATALOG,
    _get_workspace,
    _save_workspace,
    _load_workspace,
    _save_payment,
)
from datetime import UTC, datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stripe"])

PLAN_PRICES_XOF = {
    SubscriptionPlan.BASIC: 5_000,
    SubscriptionPlan.PREMIUM: 10_000,
}


def _stripe_client() -> stripe.StripeClient:
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe non configuré sur ce serveur.",
        )
    return stripe.StripeClient(settings.stripe_secret_key)


class CheckoutRequest(BaseModel):
    plan: SubscriptionPlan


@router.post("/stripe/checkout/{workspace_id}", status_code=status.HTTP_201_CREATED)
async def create_stripe_checkout(workspace_id: str, request: CheckoutRequest):
    if request.plan == SubscriptionPlan.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le plan gratuit ne nécessite pas de paiement.",
        )

    workspace = await _get_workspace(workspace_id)
    client = _stripe_client()

    amount = PLAN_PRICES_XOF[request.plan]
    plan_name = PLAN_CATALOG[request.plan]["name"]
    currency = settings.stripe_currency
    app_url = settings.app_url

    session = client.v1.checkout.sessions.create({
        "payment_method_types": ["card"],
        "line_items": [{
            "price_data": {
                "currency": currency,
                "product_data": {
                    "name": f"BAOBAB {plan_name}",
                    "description": f"Abonnement mensuel BAOBAB {plan_name} — Legal OS for Africa",
                },
                "unit_amount": amount,
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        "mode": "subscription",
        "success_url": f"{app_url}?payment=success&workspace_id={workspace_id}",
        "cancel_url": f"{app_url}?payment=cancelled",
        "customer_email": workspace["email"],
        "metadata": {
            "workspace_id": workspace_id,
            "plan": request.plan,
        },
    })

    # Enregistrer le paiement en statut pending
    payment = {
        "payment_id": f"pay_{uuid4().hex[:12]}",
        "workspace_id": workspace_id,
        "plan": request.plan,
        "provider": "stripe",
        "phone_number": "",
        "amount_xof": amount,
        "currency": currency.upper(),
        "billing_period": "monthly",
        "status": "pending",
        "stripe_session_id": session.id,
        "created_at": datetime.now(UTC).isoformat(),
        "provider_reference": session.id,
    }
    await _save_payment(payment)
    await notifications.notify_admin_payment_pending(payment, workspace)

    return {"url": session.url, "session_id": session.id}


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
):
    payload = await request.body()

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Webhook secret non configuré.")

    client = _stripe_client()
    try:
        event = client.construct_event(
            payload, stripe_signature or "", settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Signature Stripe invalide.")

    event_type = event["type"]
    logger.info("Stripe event reçu : %s", event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(event["data"]["object"])

    return {"ok": True}


async def _handle_checkout_completed(session: dict) -> None:
    workspace_id = (session.get("metadata") or {}).get("workspace_id")
    plan = (session.get("metadata") or {}).get("plan")
    if not workspace_id or not plan:
        logger.warning("Stripe session sans metadata workspace_id/plan : %s", session.get("id"))
        return

    workspace = await _load_workspace(workspace_id)
    if not workspace:
        logger.error("Workspace introuvable pour Stripe session %s", session.get("id"))
        return

    workspace["plan"] = plan
    workspace["subscription_status"] = "active"
    workspace["subscription_expires_at"] = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    workspace["stripe_customer_id"] = session.get("customer")
    workspace["stripe_subscription_id"] = session.get("subscription")
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    await _save_workspace(workspace)

    payment_stub = {
        "payment_id": session.get("id", ""),
        "plan": plan,
        "provider_reference": session.get("id", ""),
        "amount_xof": PLAN_PRICES_XOF.get(plan, 0),
    }
    await notifications.notify_user_payment_confirmed(payment_stub, workspace)
    logger.info("Workspace %s activé en plan %s via Stripe", workspace_id, plan)


async def _handle_subscription_deleted(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    from baobab.api.routes.accounts import _list_workspaces
    for ws in await _list_workspaces():
        if ws.get("stripe_customer_id") == customer_id:
            ws["plan"] = SubscriptionPlan.FREE
            ws["subscription_status"] = "free"
            ws["subscription_expires_at"] = None
            ws["updated_at"] = datetime.now(UTC).isoformat()
            await _save_workspace(ws)
            logger.info("Workspace %s repassé en FREE (subscription annulée)", ws["workspace_id"])
            break
