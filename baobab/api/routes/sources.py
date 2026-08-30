"""Baobab Sources — registre, provenance et dépôts institutionnels."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from baobab.api.routes.accounts import _connect_db, _use_database
from baobab.api.routes.superadmin_auth import _auth_superadmin

router = APIRouter(tags=["sources"])

RIGHTS_VALUES = {"UNKNOWN", "PROHIBITED", "LINK_ONLY", "AUTHORIZED", "PUBLIC_LICENSE"}
AGREEMENT_VALUES = {"TO_REVIEW", "CONTACTED", "NEGOTIATING", "ACTIVE", "EXPIRED", "TERMINATED"}


class SourceUpdate(BaseModel):
    institution_name: str | None = Field(default=None, max_length=250)
    authority_type: str | None = Field(default=None, max_length=50)
    acquisition_channel: str | None = Field(default=None, max_length=50)
    agreement_reference: str | None = Field(default=None, max_length=250)
    agreement_status: str | None = None
    agreement_review_due_at: date | None = None
    display_rights: str | None = None
    indexing_rights: str | None = None
    analysis_rights: str | None = None
    expected_frequency: str | None = Field(default=None, max_length=40)
    technical_format: str | None = Field(default=None, max_length=80)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=250)
    coverage_scope: dict[str, Any] | None = None
    enabled: bool | None = None

    @field_validator("agreement_status")
    @classmethod
    def validate_agreement(cls, value: str | None) -> str | None:
        if value is not None and value not in AGREEMENT_VALUES:
            raise ValueError("Statut de convention non reconnu")
        return value

    @field_validator("display_rights", "indexing_rights", "analysis_rights")
    @classmethod
    def validate_rights(cls, value: str | None) -> str | None:
        if value is not None and value not in RIGHTS_VALUES:
            raise ValueError("Niveau de droit non reconnu")
        return value


class InstitutionalDocumentDeposit(BaseModel):
    source_code: str = Field(..., pattern=r"^[A-Z0-9._-]{2,60}$")
    external_batch_id: str | None = Field(default=None, max_length=250)
    external_document_id: str = Field(..., min_length=1, max_length=250)
    official_identifier: str | None = Field(default=None, max_length=250)
    title: str = Field(..., min_length=3, max_length=1000)
    document_type: str = Field(..., min_length=2, max_length=60)
    jurisdiction_code: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    language_code: str = Field(default="fr", pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    publication_date: date | None = None
    effective_from: date | None = None
    source_url: str | None = Field(default=None, max_length=4000)
    original_uri: str | None = Field(default=None, max_length=4000)
    original_filename: str | None = Field(default=None, max_length=500)
    original_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    signature_status: Literal["NOT_PROVIDED", "PROVIDED", "VERIFIED", "INVALID"] = "NOT_PROVIDED"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_url", "original_uri")
    @classmethod
    def validate_uri(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "sftp://", "storage://")):
            raise ValueError("URI autorisée : HTTPS, SFTP ou stockage interne")
        return value


def _require_database() -> None:
    if not _use_database():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base documentaire indisponible")


@router.get("/sources/overview")
async def sources_overview(authorization: str | None = Header(default=None)):
    _auth_superadmin(authorization)
    _require_database()
    conn = await _connect_db()
    try:
        summary = await conn.fetchrow(
            """
            SELECT count(*) AS total_sources,
                   count(*) FILTER (WHERE enabled) AS enabled_sources,
                   count(*) FILTER (WHERE agreement_status='ACTIVE') AS active_agreements,
                   count(*) FILTER (WHERE license_review_required OR agreement_status='TO_REVIEW') AS rights_to_review
            FROM legal_sources
            """
        )
        documents = await conn.fetchrow(
            """
            SELECT count(*) AS canonical_documents,
                   count(*) FILTER (WHERE validation_level IN ('SOURCE_VERIFIED','EDITORIALLY_VALIDATED')) AS verified_documents,
                   count(*) FILTER (WHERE original_sha256 IS NOT NULL) AS originals_hashed,
                   count(*) FILTER (WHERE editorial_status='TO_REVIEW') AS editorial_backlog
            FROM legal_documents
            """
        )
        acquisitions = await conn.fetchrow(
            """
            SELECT count(*) AS total_acquisitions,
                   count(*) FILTER (WHERE processing_status='RECEIVED') AS pending_processing,
                   count(*) FILTER (WHERE rights_status='TO_REVIEW') AS pending_rights
            FROM legal_source_acquisitions
            """
        )
        return {"sources": dict(summary), "documents": dict(documents), "acquisitions": dict(acquisitions)}
    finally:
        await conn.close()


@router.get("/sources")
async def list_sources(authorization: str | None = Header(default=None)):
    _auth_superadmin(authorization)
    _require_database()
    conn = await _connect_db()
    try:
        rows = await conn.fetch(
            """
            SELECT s.*, count(d.document_id) AS canonical_documents
            FROM legal_sources s
            LEFT JOIN legal_documents d ON d.source_code=s.code
            GROUP BY s.code
            ORDER BY s.jurisdiction_code,s.code
            """
        )
        return {"results": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await conn.close()


@router.patch("/sources/{source_code}")
async def update_source(
    source_code: str,
    request: SourceUpdate,
    authorization: str | None = Header(default=None),
):
    actor = _auth_superadmin(authorization)
    _require_database()
    values = request.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucune modification fournie")
    columns = list(values)
    assignments = ",".join(f"{name}=${index + 2}" for index, name in enumerate(columns))
    conn = await _connect_db()
    try:
        row = await conn.fetchrow(
            f"UPDATE legal_sources SET {assignments},updated_at=NOW(),last_audit_at=NOW() WHERE code=$1 RETURNING *",
            source_code,
            *(values[name] for name in columns),
        )
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source inconnue")
        result = dict(row)
        result["updated_by"] = actor.get("email")
        return result
    finally:
        await conn.close()


@router.post("/institution/documents", status_code=status.HTTP_202_ACCEPTED)
async def deposit_institutional_document(
    request: InstitutionalDocumentDeposit,
    authorization: str | None = Header(default=None),
):
    actor = _auth_superadmin(authorization)
    _require_database()
    conn = await _connect_db()
    transaction = conn.transaction()
    await transaction.start()
    try:
        source = await conn.fetchrow("SELECT * FROM legal_sources WHERE code=$1 AND enabled", request.source_code)
        if not source:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source institutionnelle inconnue ou désactivée")
        existing = await conn.fetchrow(
            "SELECT document_id FROM legal_documents WHERE source_code=$1 AND official_identifier=$2",
            request.source_code,
            request.official_identifier or request.external_document_id,
        )
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "Document officiel déjà enregistré")
        rights_snapshot = {
            "display": source["display_rights"],
            "indexing": source["indexing_rights"],
            "analysis": source["analysis_rights"],
            "agreement_status": source["agreement_status"],
        }
        document_id = await conn.fetchval(
            """
            INSERT INTO legal_documents (
                source_code,jurisdiction_code,official_identifier,document_type,title,country_code,
                language_code,publication_date,effective_from,source_url,original_file_uri,
                original_sha256,rights_snapshot,metadata,validation_level
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14::jsonb,'SOURCE_RECEIVED')
            RETURNING document_id
            """,
            request.source_code, request.jurisdiction_code or source["jurisdiction_code"],
            request.official_identifier or request.external_document_id, request.document_type,
            request.title, request.country_code, request.language_code, request.publication_date,
            request.effective_from, request.source_url, request.original_uri, request.original_sha256,
            __import__("json").dumps(rights_snapshot), __import__("json").dumps(request.metadata),
        )
        acquisition_id = await conn.fetchval(
            """
            INSERT INTO legal_source_acquisitions (
                source_code,document_id,external_batch_id,external_document_id,channel,received_by,
                original_filename,original_uri,original_sha256,signature_status,integrity_status,rights_status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING acquisition_id
            """,
            request.source_code, document_id, request.external_batch_id, request.external_document_id,
            source["acquisition_channel"], actor.get("email") or "superadmin", request.original_filename,
            request.original_uri, request.original_sha256, request.signature_status,
            "HASH_RECORDED" if request.original_sha256 else "TO_VERIFY",
            "AUTHORIZED" if source["agreement_status"] == "ACTIVE" else "TO_REVIEW",
        )
        await transaction.commit()
        return {
            "document_id": str(document_id), "acquisition_id": str(acquisition_id),
            "status": "RECEIVED", "next_step": "INTEGRITY_AND_EDITORIAL_REVIEW",
        }
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await conn.close()


@router.get("/sources/audits/latest")
async def latest_corpus_audit(authorization: str | None = Header(default=None)):
    _auth_superadmin(authorization)
    _require_database()
    conn = await _connect_db()
    try:
        row = await conn.fetchrow("SELECT * FROM legal_corpus_audit_runs ORDER BY started_at DESC LIMIT 1")
        return {"audit": dict(row) if row else None}
    finally:
        await conn.close()
