"""Rattache prudemment les transcriptions OCR au texte canonique du document."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from baobab.api.routes.accounts import _connect_db


def join_ocr_pages(pages: list[tuple[int, bytes]]) -> str:
    ordered = sorted(pages, key=lambda item: item[0])
    return "\n\n".join(
        f"[Page {page}]\n{content.decode('utf-8', errors='replace').strip()}"
        for page, content in ordered if content.strip()
    ).strip()


def should_replace(current: str | None, ocr_text: str) -> bool:
    return len(ocr_text.strip()) >= 200 and len(ocr_text.strip()) > len((current or "").strip())


async def sync(manifest: Path, *, apply: bool) -> dict:
    records = json.loads(manifest.read_text(encoding="utf-8"))
    source_urls = sorted({record.get("source_url") for record in records if record.get("source_url")})
    connection = await _connect_db()
    try:
        rows = await connection.fetch(
            """SELECT d.document_id,d.legacy_corpus_id,d.normalized_text,c.texte_integral,
                      r.page_number,b.content
               FROM legal_documents d
               JOIN legal_corpus c ON c.id=d.legacy_corpus_id
               JOIN legal_document_renditions r ON r.document_id=d.document_id
               JOIN legal_document_rendition_blobs b ON b.rendition_id=r.rendition_id
               WHERE c.source_url=ANY($1::text[]) AND r.rendition_type='OCR_TEXT'
               ORDER BY d.document_id,r.page_number""",
            source_urls,
        )
        documents: dict[str, dict] = {}
        for row in rows:
            item = documents.setdefault(str(row["document_id"]), {
                "document_id": row["document_id"], "corpus_id": row["legacy_corpus_id"],
                "normalized_text": row["normalized_text"], "corpus_text": row["texte_integral"],
                "pages": [],
            })
            item["pages"].append((row["page_number"], bytes(row["content"])))

        updates = []
        for item in documents.values():
            ocr_text = join_ocr_pages(item["pages"])
            replace_canonical = should_replace(item["normalized_text"], ocr_text)
            replace_legacy = should_replace(item["corpus_text"], ocr_text)
            if replace_canonical or replace_legacy:
                updates.append((item, ocr_text, replace_canonical, replace_legacy))

        if apply:
            async with connection.transaction():
                for item, text, replace_canonical, replace_legacy in updates:
                    if replace_canonical:
                        await connection.execute(
                            """UPDATE legal_documents SET normalized_text=$2,normalized_sha256=$3,
                                      metadata=metadata || $4::jsonb,updated_at=NOW()
                               WHERE document_id=$1""",
                            item["document_id"], text, hashlib.sha256(text.encode()).hexdigest(),
                            json.dumps({"canonical_text_origin": "OCR_RENDITION", "ocr_pages": len(item["pages"])}),
                        )
                    if replace_legacy:
                        await connection.execute(
                            "UPDATE legal_corpus SET texte_integral=$2,updated_at=NOW() WHERE id=$1",
                            item["corpus_id"], text,
                        )
        return {
            "manifest_documents": len(source_urls), "documents_with_ocr": len(documents),
            "documents_updated": len(updates), "applied": apply,
        }
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(sync(args.manifest, apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
