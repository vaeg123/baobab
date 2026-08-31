from pathlib import Path

import pytest
from fastapi import HTTPException

from baobab.api.routes import legal
from baobab.pipeline.store_legal_ocr_bundle import page_requires_review


def test_bundle_page_review_status_is_preserved():
    manifest = {"pages": [{"page": 1, "requires_review": False}, {"page": 2, "requires_review": True}]}
    assert page_requires_review(manifest, 1) is False
    assert page_requires_review(manifest, 2) is True
    assert page_requires_review(manifest, 3) is True


def test_blob_migration_has_hard_size_limit():
    sql = (
        Path(__file__).parents[1] / "baobab" / "db" / "migrations"
        / "020_document_rendition_blobs.sql"
    ).read_text(encoding="utf-8")
    assert "20971520" in sql
    assert "BYTEA" in sql


def test_client_distinguishes_original_searchable_pdf_and_ocr_text():
    html = (Path(__file__).parents[1] / "baobab" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Lire le PDF recherchable" in html
    assert "Voir l’original conservé" in html
    assert "Lire la transcription OCR" in html
    assert "La copie visuelle fait foi pour la lecture" in html
    assert "async function openOcrTranscription" in html


def test_superadmin_highlights_ocr_briefs_and_beginner_guide():
    html = (Path(__file__).parents[1] / "baobab" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Fiches jurisprudentielles OCR à contrôler" in html
    assert "Guide débutant" in html
    assert "Baobab pour les débutants" in html
    assert "async function loadEditorialBriefs" in html


@pytest.mark.asyncio
async def test_rendition_list_rejects_anonymous_access():
    with pytest.raises(HTTPException) as exc:
        await legal.list_document_renditions("00000000-0000-0000-0000-000000000000", None)
    assert exc.value.status_code in {401, 403}
