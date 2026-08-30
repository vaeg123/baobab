"""Calcule les empreintes du texte normalisé sans modifier le contenu juridique."""

from __future__ import annotations

import asyncio
import hashlib
import os

import asyncpg
from dotenv import load_dotenv


async def main() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        rows = await connection.fetch(
            """
            SELECT id,texte_integral FROM legal_corpus
            WHERE content_checksum IS NULL AND coalesce(texte_integral,'')<>''
            """
        )
        values = [
            (hashlib.sha256(row["texte_integral"].encode("utf-8")).hexdigest(), row["id"])
            for row in rows
        ]
        if values:
            async with connection.transaction():
                await connection.executemany(
                    "UPDATE legal_corpus SET content_checksum=$1,updated_at=NOW() WHERE id=$2",
                    values,
                )
                await connection.execute(
                    """
                    UPDATE legal_documents d
                    SET normalized_text=c.texte_integral,
                        normalized_sha256=c.content_checksum,
                        updated_at=NOW()
                    FROM legal_corpus c WHERE d.legacy_corpus_id=c.id
                    """
                )
        print(f"CHECKSUMS_ADDED={len(values)}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
