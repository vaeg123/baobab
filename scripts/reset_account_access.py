"""Reset a BAOBAB account password by email in the configured PostgreSQL database."""

import argparse
import asyncio
import json
import secrets
import string
from pathlib import Path

import asyncpg
from dotenv import dotenv_values

from baobab.auth import hash_password

ROOT = Path(__file__).resolve().parents[1]


def strong_password(length: int = 18) -> str:
    groups = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%&*+-_"]
    chars = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


async def reset(email: str, env_file: Path) -> tuple[str, list[str]]:
    config = dotenv_values(env_file)
    database_url = str(config.get("DATABASE_URL") or "").replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    if not database_url:
        raise ValueError("DATABASE_URL absente du fichier d'environnement.")

    normalized_email = email.strip().lower()
    new_password = strong_password()
    password_hash = hash_password(new_password)
    updated: list[str] = []
    connection = await asyncpg.connect(database_url, ssl="require", statement_cache_size=0)
    try:
        async with connection.transaction():
            superadmin = await connection.fetchrow(
                "SELECT id FROM account_superadmins WHERE lower(email) = $1", normalized_email
            )
            if superadmin:
                await connection.execute(
                    "UPDATE account_superadmins SET password_hash = $1 WHERE id = $2",
                    password_hash,
                    superadmin["id"],
                )
                updated.append("superadmin")

            rows = await connection.fetch(
                """
                SELECT workspace_id, data
                FROM account_workspaces
                WHERE lower(coalesce(data->>'email', '')) = $1
                   OR lower(coalesce(data->>'admin_email', '')) = $1
                   OR lower(coalesce(data->>'user_email', '')) = $1
                """,
                normalized_email,
            )
            for row in rows:
                data = dict(row["data"]) if not isinstance(row["data"], str) else json.loads(row["data"])
                if normalized_email in {
                    str(data.get("email", "")).lower(),
                    str(data.get("admin_email", "")).lower(),
                }:
                    data["admin_password_hash"] = password_hash
                    updated.append(f"workspace-admin:{row['workspace_id']}")
                if normalized_email in {
                    str(data.get("email", "")).lower(),
                    str(data.get("user_email", "")).lower(),
                }:
                    data["user_password_hash"] = password_hash
                    updated.append(f"workspace-user:{row['workspace_id']}")
                data["password_is_temporary"] = True
                await connection.execute(
                    "UPDATE account_workspaces SET data = $1::jsonb, updated_at = NOW() WHERE workspace_id = $2",
                    json.dumps(data),
                    row["workspace_id"],
                )

            if not updated:
                raise LookupError("Aucun compte ne correspond à cette adresse.")
    finally:
        await connection.close()
    return new_password, updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.local")
    args = parser.parse_args()
    password, roles = asyncio.run(reset(args.email, args.env_file))
    print(f"Accès mis à jour pour : {args.email.lower()}")
    print(f"Profils concernés : {', '.join(roles)}")
    print(f"Nouveau mot de passe temporaire : {password}")


if __name__ == "__main__":
    main()
