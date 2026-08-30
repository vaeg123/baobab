"""Applique la qualification A–F des sources camerounaises."""

from __future__ import annotations

import asyncio
from pathlib import Path

from baobab.api.routes.accounts import _connect_db

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "017_cameroon_source_authority.sql"


async def main() -> None:
    connection = await _connect_db()
    try:
        await connection.execute(MIGRATION.read_text(encoding="utf-8"))
        rows = await connection.fetch(
            """SELECT authority_grade,count(*) AS count FROM legal_sources
               GROUP BY authority_grade ORDER BY authority_grade"""
        )
        print(" ".join(f"GRADE_{row['authority_grade']}={row['count']}" for row in rows))
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
