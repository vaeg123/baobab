"""Rafraîchit un Acte OHADA depuis une copie institutionnelle contrôlée."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json

import fitz
import httpx

from baobab.api.routes.accounts import _connect_db
from baobab.pipeline.build_ohada_provisions import extract_articles, identity_matches

ACT_SOURCES = {
    "AUSCGIE-2014": {
        "pdf_url": "https://biblio.ohada.org/pmb/opac_css/doc_num.php?explnum_id=2032",
        "source_url": "https://www.ohada.org/droit-des-societes-commerciales-et-du-gie/",
        "required_articles": {"260", "309", "311", "385", "389", "414", "702", "920"},
        "minimum_characters": 500_000,
        "minimum_articles": 900,
    },
}


def extract_pdf_text(content: bytes) -> tuple[str, int]:
    with fitz.open(stream=content, filetype="pdf") as document:
        return "\n".join(page.get_text() for page in document).strip(), len(document)


def validate_act(reference: str, text: str, pages: int, pdf_sha256: str) -> dict:
    source = ACT_SOURCES[reference]
    articles = extract_articles(text)
    numbers = {article["number"] for article in articles}
    missing = sorted(source["required_articles"] - numbers)
    report = {
        "ref": reference,
        "pages": pages,
        "characters": len(text),
        "articles": len(articles),
        "last_article_present": "920" in numbers,
        "identity_match": identity_matches(reference, text),
        "missing_required_articles": missing,
        "pdf_sha256": pdf_sha256,
    }
    report["accepted"] = (
        report["identity_match"]
        and len(text) >= source["minimum_characters"]
        and len(articles) >= source["minimum_articles"]
        and not missing
    )
    return report


async def refresh(reference: str, *, apply: bool) -> dict:
    source = ACT_SOURCES[reference]
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        response = await client.get(source["pdf_url"], headers={"User-Agent": "BaobabLegalResearch/1.0"})
        response.raise_for_status()
        content = response.content
    if not content.startswith(b"%PDF"):
        raise RuntimeError("La source n'a pas renvoyé un PDF")
    pdf_sha256 = hashlib.sha256(content).hexdigest()
    text, pages = await asyncio.to_thread(extract_pdf_text, content)
    report = validate_act(reference, text, pages, pdf_sha256)
    report["applied"] = False
    if not report["accepted"]:
        return report
    if apply:
        connection = await _connect_db()
        try:
            result = await connection.execute(
                """UPDATE legal_corpus
                   SET texte_integral=$2,source_url=$3,source_pdf_url=$4,updated_at=now(),
                       metadata=coalesce(metadata,'{}'::jsonb)||$5::jsonb
                   WHERE ref=$1 AND corpus='ohada' AND type='acte_uniforme'""",
                reference,
                text,
                source["source_url"],
                source["pdf_url"],
                json.dumps({
                    "text_extraction": "PYMUPDF_INSTITUTIONAL_PDF_V1",
                    "pdf_sha256": pdf_sha256,
                    "pages": pages,
                    "characters": len(text),
                    "automated_identity_check": True,
                }),
            )
        finally:
            await connection.close()
        if result != "UPDATE 1":
            raise RuntimeError(f"Mise à jour inattendue : {result}")
        report["applied"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", choices=sorted(ACT_SOURCES))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(refresh(args.reference, apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
