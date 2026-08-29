"""Contrôle en lecture seule des arrêts OHADA présents dans legal_corpus."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


async def main() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        manifest = Path(__file__).resolve().parents[2] / "data" / "raw" / "ohada_arrets.json"
        expected = json.loads(manifest.read_text(encoding="utf-8"))
        source_urls = [record["source_url"] for record in expected]
        rows = await connection.fetch(
            """
            SELECT ref, source_url, length(texte_integral) AS chars
            FROM legal_corpus
            WHERE source_url = ANY($1::text[])
            ORDER BY ref
            """,
            source_urls,
        )
        present_urls = {row["source_url"] for row in rows}
        print(f"COUNT={len(rows)}")
        print(f"WITH_TEXT={sum((row['chars'] or 0) > 0 for row in rows)}")
        print(f"MISSING={len(set(source_urls) - present_urls)}")
        official = await connection.fetchrow(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE length(texte_integral) > 0) AS with_text
            FROM legal_corpus
            WHERE source_url LIKE 'https://biblio.ohada.org/%'
            """
        )
        print(f"OFFICIAL_PLATFORM_TOTAL={official['total']}")
        print(f"OFFICIAL_PLATFORM_WITH_TEXT={official['with_text']}")
        missing = await connection.fetchrow(
            """
            SELECT count(*) FILTER (
                       WHERE coalesce(length(texte_integral), 0) = 0
                         AND coalesce(source_pdf_url, '') <> ''
                   ) AS downloadable,
                   count(*) FILTER (
                       WHERE coalesce(length(texte_integral), 0) = 0
                         AND coalesce(source_pdf_url, '') = ''
                   ) AS without_pdf
            FROM legal_corpus
            WHERE source_url LIKE 'https://biblio.ohada.org/%'
            """
        )
        print(f"MISSING_TEXT_WITH_PDF={missing['downloadable']}")
        print(f"MISSING_TEXT_WITHOUT_PDF={missing['without_pdf']}")
        jurisprudence = await connection.fetchrow(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE length(texte_integral) > 0) AS with_text
            FROM legal_corpus
            WHERE corpus = 'ohada'
              AND type = ANY($1::varchar[])
              AND source_url LIKE 'https://biblio.ohada.org/%'
            """,
            ["arret_ccja", "ordonnance_ccja", "avis_ccja"],
        )
        print(f"JURISPRUDENCE_TOTAL={jurisprudence['total']}")
        print(f"JURISPRUDENCE_WITH_TEXT={jurisprudence['with_text']}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
