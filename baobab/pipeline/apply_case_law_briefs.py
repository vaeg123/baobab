"""Applique la migration 015 des fiches jurisprudentielles."""

from __future__ import annotations

import asyncio
from pathlib import Path

from baobab.api.routes.accounts import _connect_db

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "015_case_law_briefs.sql"


async def main() -> None:
    connection = await _connect_db()
    try:
        await connection.execute(MIGRATION.read_text(encoding="utf-8"))
        total = await connection.fetchval("SELECT count(*) FROM legal_case_briefs")
        review = await connection.fetchval(
            "SELECT count(*) FROM legal_case_briefs WHERE editorial_status='TO_REVIEW'"
        )
        print(f"MIGRATION=015 APPLIED=YES BRIEFS={total} TO_REVIEW={review}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
