from baobab.pipeline.build_searchable_legal_copy import (
    configure_tesseract,
    normalize_ocr_text,
    page_requires_review,
    sha256_bytes,
)


def test_ocr_normalization_preserves_legal_characters_and_lines():
    source = "Article 1er : obligation n° 2024/017  \r\n\r\nSigné : X\x0c"
    assert normalize_ocr_text(source) == "Article 1er : obligation n° 2024/017\n\nSigné : X"


def test_low_confidence_or_empty_page_requires_review():
    assert page_requires_review("Texte court", 99) is True
    assert page_requires_review("Texte juridique suffisamment long pour être contrôlé fidèlement.", 70) is True
    assert page_requires_review("Texte juridique suffisamment long pour être contrôlé fidèlement.", 95) is False


def test_original_hash_is_deterministic():
    assert sha256_bytes(b"original") == sha256_bytes(b"original")


def test_missing_tessdata_directory_is_rejected(tmp_path):
    try:
        configure_tesseract("fra", tmp_path / "missing")
    except ValueError as exc:
        assert "tessdata" in str(exc)
    else:
        raise AssertionError("Un dossier OCR absent doit être refusé")
