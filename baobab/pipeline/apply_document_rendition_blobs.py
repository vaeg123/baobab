"""Applique le coffre binaire initial des copies documentaires."""

from __future__ import annotations

import asyncio
from pathlib import Path

from baobab.api.routes.accounts import _connect_db

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "020_document_rendition_blobs.sql"


async def main() -> None:
    connection = await _connect_db()
    try:
        await connection.execute(MIGRATION.read_text(encoding="utf-8"))
        print("MIGRATION=020 APPLIED=YES")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
