"""Apply one reviewed BAOBAB SQL migration transactionally without exposing credentials."""

import argparse
import asyncio
from pathlib import Path

import asyncpg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (ROOT / "baobab" / "db" / "migrations").resolve()


async def apply(migration: Path, env_file: Path) -> None:
    resolved = migration.resolve()
    if resolved.parent != MIGRATIONS or resolved.suffix != ".sql":
        raise ValueError("Le fichier doit être une migration SQL du dossier officiel.")
    config = dotenv_values(env_file)
    database_url = str(config.get("DATABASE_URL") or "").replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    if not database_url:
        raise ValueError("DATABASE_URL absente du fichier d'environnement.")
    connection = await asyncpg.connect(database_url, ssl="require")
    try:
        async with connection.transaction():
            await connection.execute(resolved.read_text(encoding="utf-8"))
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("migration", type=Path)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.local")
    args = parser.parse_args()
    asyncio.run(apply(args.migration, args.env_file))
    print(f"Migration appliquée : {args.migration.name}")


if __name__ == "__main__":
    main()
