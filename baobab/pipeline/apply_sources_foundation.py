"""Applique exclusivement la migration Baobab Sources 014 puis lance l'audit."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

from baobab.pipeline.audit_corpus_foundation import run as run_audit

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "014_baobab_sources_foundation.sql"


async def main() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")
    sql = MIGRATION.read_text(encoding="utf-8")
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        async with connection.transaction():
            await connection.execute(sql)
    finally:
        await connection.close()
    report = await run_audit(apply=True)
    print(f"MIGRATION=014 APPLIED=YES SCANNED={report['scanned']} USABLE={report['usable']}")


if __name__ == "__main__":
    asyncio.run(main())
