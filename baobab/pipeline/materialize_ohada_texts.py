"""Matérialise durablement le texte OHADA et un manifeste de provenance.

La base reste la source opérationnelle. Cette commande produit un artefact
versionnable afin qu'un prochain intervenant puisse auditer le corpus sans
devoir deviner comment le texte a été obtenu.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path

from baobab.api.routes.accounts import _connect_db
from baobab.pipeline.build_ohada_provisions import extract_articles, identity_matches

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "processed" / "ohada_texts"
MANIFEST = OUTPUT_DIR / "manifest.json"


def safe_name(reference: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", reference).strip("-")


def quality(reference: str, text: str) -> dict:
    return {
        "characters": len(text),
        "articles": len(extract_articles(text)),
        "identity_match": identity_matches(reference, text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


async def materialize() -> dict:
    connection = await _connect_db()
    try:
        rows = await connection.fetch(
            """SELECT ref,titre,publication_date,date_decision,source_url,source_pdf_url,
                      texte_integral,metadata
               FROM legal_corpus
               WHERE corpus='ohada' AND type='acte_uniforme'
                 AND coalesce(texte_integral,'')<>'' ORDER BY ref"""
        )
    finally:
        await connection.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for row in rows:
        raw_text = (row["texte_integral"] or "").replace("\r\n", "\n")
        text = "\n".join(line.rstrip() for line in raw_text.splitlines()).strip() + "\n"
        metrics = quality(row["ref"], text)
        target = OUTPUT_DIR / f"{safe_name(row['ref'])}.txt"
        target.write_text(text, encoding="utf-8", newline="\n")
        records.append({
            "ref": row["ref"],
            "title": row["titre"],
            "legal_date": str(row["publication_date"] or row["date_decision"] or ""),
            "source_url": row["source_url"],
            "source_pdf_url": row["source_pdf_url"],
            "text_file": target.relative_to(ROOT).as_posix(),
            "materialization_method": "DATABASE_CANONICAL_TEXT_EXPORT_V1",
            "verification_status": "AUTOMATED_TO_REVIEW",
            **metrics,
        })
    payload = {
        "schema_version": 1,
        "corpus": "ohada",
        "documents": records,
        "summary": {
            "documents": len(records),
            "identity_matches": sum(record["identity_match"] for record in records),
            "articles": sum(record["articles"] for record in records),
        },
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload["summary"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(asyncio.run(materialize()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
