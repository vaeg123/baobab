"""Intégration serveur-à-serveur avec AvocAssist.

La clé d'intégration n'est jamais exposée au navigateur. Les tickets SSO sont
signés, limités à 60 secondes et ne contiennent aucun jeton permanent Baobab.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from baobab.api.routes.accounts import (
    _create_workspace_record,
    _list_workspaces,
    _public_workspace,
    _save_workspace,
)
from baobab.api.routes.legal import SearchRequest, _search_corpus_impl
from baobab.auth import constant_time_equals
from baobab.config import settings

router = APIRouter(prefix="/integrations/avocassist", tags=["avocassist-integration"])


class ProvisionRequest(BaseModel):
    organization_id: str = Field(..., min_length=10, max_length=80)
    organization_name: str = Field(..., min_length=2, max_length=180)
    owner_name: str = Field(..., min_length=2, max_length=120)
    owner_email: str = Field(..., min_length=5, max_length=180)
    territory: str = Field(default="CM", min_length=2, max_length=8)


class OrganizationRequest(BaseModel):
    organization_id: str = Field(..., min_length=10, max_length=80)


class SessionRequest(OrganizationRequest):
    user_id: str = Field(..., min_length=10, max_length=80)
    email: str = Field(..., min_length=5, max_length=180)
    display_name: str = Field(..., min_length=2, max_length=120)


class IntegratedSearchRequest(OrganizationRequest):
    query: str = Field(..., min_length=2, max_length=500)
    corpus: Literal["cima", "ohada", "ci", "all"] = "all"
    type: str | None = None
    pays: str | None = None
    domaine: str | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


def _secret() -> str:
    value = settings.avocassist_integration_secret
    if len(value) < 32:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Intégration AvocAssist non configurée.")
    return value


def _require_integration(key: str | None) -> None:
    if not constant_time_equals(key, _secret()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Clé d'intégration invalide.")


async def _workspace(organization_id: str) -> dict:
    for workspace in await _list_workspaces():
        if constant_time_equals(workspace.get("avocassist_organization_id"), organization_id):
            return workspace
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Espace Baobab non rattaché.")


def _entitlements(workspace: dict) -> dict:
    subscription_status = workspace.get("subscription_status", "free")
    active = subscription_status in {"active", "unlimited_grant"} and not workspace.get("suspended", False)
    return {
        "workspace_id": workspace["workspace_id"],
        "plan": str(workspace.get("plan", "free")),
        "subscription_status": subscription_status,
        "subscription_expires_at": workspace.get("subscription_expires_at"),
        "active": active,
        "services": workspace.get("enabled_services", []),
    }


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _ticket(payload: dict) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signed = f"{header}.{body}"
    signature = _b64(hmac.new(_secret().encode(), signed.encode(), hashlib.sha256).digest())
    return f"{signed}.{signature}"


def _verify_ticket(token: str) -> dict:
    try:
        header, body, signature = token.split(".")
        signed = f"{header}.{body}"
        expected = _b64(hmac.new(_secret().encode(), signed.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("aud") != "baobab-sso" or payload.get("exp", 0) < time.time():
            raise ValueError("expired")
        return payload
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ticket SSO invalide ou expiré.")


@router.post("/provision")
async def provision(request: ProvisionRequest, x_integration_key: str | None = Header(default=None)):
    _require_integration(x_integration_key)
    try:
        workspace = await _workspace(request.organization_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        workspace, _ = _create_workspace_record(
            owner_name=request.owner_name,
            email=request.owner_email,
            organization_name=request.organization_name,
            territory=request.territory,
            password=None,
            plan="free",
            enabled_services=[],
            provisioned_by="avocassist",
        )
        workspace["avocassist_organization_id"] = request.organization_id
        await _save_workspace(workspace)
    return {**_entitlements(workspace), "organization_name": workspace["organization_name"]}


@router.post("/entitlements")
async def entitlements(request: OrganizationRequest, x_integration_key: str | None = Header(default=None)):
    _require_integration(x_integration_key)
    return _entitlements(await _workspace(request.organization_id))


@router.post("/session")
async def session(request: SessionRequest, x_integration_key: str | None = Header(default=None)):
    _require_integration(x_integration_key)
    workspace = await _workspace(request.organization_id)
    now = int(time.time())
    token = _ticket({
        "aud": "baobab-sso", "iat": now, "exp": now + 60,
        "workspace_id": workspace["workspace_id"], "external_user_id": request.user_id,
        "email": request.email, "display_name": request.display_name,
    })
    return {"url": f"{settings.app_url}/?sso_ticket={token}", "expires_in": 60}


@router.post("/session/exchange")
async def exchange_session(body: dict):
    payload = _verify_ticket(str(body.get("ticket", "")))
    workspace = next((item for item in await _list_workspaces() if item["workspace_id"] == payload["workspace_id"]), None)
    if not workspace or workspace.get("suspended"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Espace Baobab indisponible.")
    return {"role": "client", "token": workspace["user_token"], "workspace": await _public_workspace(workspace)}


@router.post("/legal/search")
async def integrated_search(request: IntegratedSearchRequest, x_integration_key: str | None = Header(default=None)):
    _require_integration(x_integration_key)
    workspace = await _workspace(request.organization_id)
    entitlement = _entitlements(workspace)
    if not entitlement["active"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, {"code": "subscription_required", **entitlement})
    return await _search_corpus_impl(SearchRequest(
        query=request.query, corpus=request.corpus, type=request.type, pays=request.pays,
        domaine=request.domaine, limit=request.limit, offset=request.offset, mode="fulltext",
    ))
