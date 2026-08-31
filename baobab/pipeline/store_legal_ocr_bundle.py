"""Enregistre un original et son bundle OCR dans le coffre documentaire Neon."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from baobab.api.routes.accounts import _connect_db

MAX_BLOB_BYTES = 20 * 1024 * 1024


async def store_bundle(document_id: str, original_path: Path, bundle_dir: Path) -> dict:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    files = [
        ("ORIGINAL", None, original_path, "application/pdf", "SOURCE_ORIGINAL", None),
        ("SEARCHABLE_PDF", None, bundle_dir / manifest["searchable_pdf"]["filename"],
         "application/pdf", "TESSERACT_IMAGE_TEXT_LAYER", None),
    ]
    for page in manifest["pages"]:
        files.extend([
            ("PAGE_IMAGE", page["page"], bundle_dir / page["image"], "image/png",
             page["method"], page["confidence"]),
            ("OCR_TEXT", page["page"], bundle_dir / page["text"], "text/plain; charset=utf-8",
             page["method"], page["confidence"]),
        ])
    connection = await _connect_db()
    stored = 0
    try:
        exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM legal_documents WHERE document_id=$1::uuid)", document_id
        )
        if not exists:
            raise ValueError("Document canonique introuvable")
        async with connection.transaction():
            for kind, page, path, mime, method, confidence in files:
                content = path.read_bytes()
                if not content or len(content) > MAX_BLOB_BYTES:
                    raise ValueError(f"Rendu {path.name} vide ou supérieur à 20 Mo")
                checksum = hashlib.sha256(content).hexdigest()
                rendition_id = await connection.fetchval(
                    """INSERT INTO legal_document_renditions
                       (document_id,rendition_type,page_number,storage_uri,mime_type,sha256,
                        byte_size,extraction_method,ocr_language,ocr_confidence,review_status,metadata)
                       VALUES($1::uuid,$2,$3,'database://pending',$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
                       ON CONFLICT (document_id,rendition_type,page_number,sha256)
                       DO UPDATE SET byte_size=EXCLUDED.byte_size RETURNING rendition_id""",
                    document_id, kind, page, mime, checksum, len(content), method,
                    manifest.get("language") if kind in {"OCR_TEXT", "SEARCHABLE_PDF"} else None,
                    confidence,
                    "TO_REVIEW" if page and page_requires_review(manifest, page) else "DOCUMENT_VERIFIED",
                    json.dumps({"bundle_schema": manifest["schema"], "original_sha256": manifest["original"]["sha256"]}),
                )
                await connection.execute(
                    """INSERT INTO legal_document_rendition_blobs(rendition_id,content)
                       VALUES($1,$2) ON CONFLICT(rendition_id) DO UPDATE SET content=EXCLUDED.content""",
                    rendition_id, content,
                )
                await connection.execute(
                    "UPDATE legal_document_renditions SET storage_uri=$2 WHERE rendition_id=$1",
                    rendition_id, f"database://renditions/{rendition_id}",
                )
                stored += 1
        return {"document_id": document_id, "renditions_stored": stored}
    finally:
        await connection.close()


def page_requires_review(manifest: dict, page_number: int) -> bool:
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), {})
    return bool(page.get("requires_review", True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_id")
    parser.add_argument("original", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(store_bundle(args.document_id, args.original, args.bundle)), indent=2))


if __name__ == "__main__":
    main()
