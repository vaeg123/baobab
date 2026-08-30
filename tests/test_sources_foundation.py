import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from baobab.api.routes import sources


def test_source_update_rejects_unknown_rights_and_agreement_status():
    with pytest.raises(ValidationError):
        sources.SourceUpdate(display_rights="MAYBE")
    with pytest.raises(ValidationError):
        sources.SourceUpdate(agreement_status="SIGNED_SOMEHOW")


def test_institutional_deposit_requires_safe_provenance_fields():
    deposit = sources.InstitutionalDocumentDeposit(
        source_code="OHADA.CCJA",
        external_document_id="CCJA-2026-001",
        official_identifier="001/2026",
        title="Arrêt CCJA numéro 001/2026",
        document_type="arret_ccja",
        country_code="CM",
        original_uri="sftp://institution/batch/document.pdf",
        original_sha256="a" * 64,
    )
    assert deposit.language_code == "fr"
    assert deposit.signature_status == "NOT_PROVIDED"

    with pytest.raises(ValidationError):
        sources.InstitutionalDocumentDeposit(
            source_code="ohada bad",
            external_document_id="1",
            title="Document officiel",
            document_type="arret",
        )
    with pytest.raises(ValidationError):
        sources.InstitutionalDocumentDeposit(
            source_code="OHADA.CCJA",
            external_document_id="1",
            title="Document officiel",
            document_type="arret",
            original_uri="file:///private/document.pdf",
        )


@pytest.mark.asyncio
async def test_sources_overview_rejects_anonymous_access():
    with pytest.raises(HTTPException) as exc:
        await sources.sources_overview(None)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_deposit_rejects_anonymous_access_before_database_use():
    request = sources.InstitutionalDocumentDeposit(
        source_code="OHADA.CCJA",
        external_document_id="CCJA-2026-001",
        title="Arrêt officiel",
        document_type="arret_ccja",
    )
    with pytest.raises(HTTPException) as exc:
        await sources.deposit_institutional_document(request, None)
    assert exc.value.status_code == 403
