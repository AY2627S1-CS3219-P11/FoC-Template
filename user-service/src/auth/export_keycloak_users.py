"""Read application users and prepare an explicit Keycloak import; never import automatically."""

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
import secrets

from sqlalchemy.ext.asyncio import async_sessionmaker

from auth.repository import list_identity_import_users
from common.db import get_engine


def build_import(users):
    exported = []
    passwords = []
    for user in users:
        password = "ResetA1-" + secrets.token_urlsafe(24)
        exported.append({
            "id": str(user.id), "username": user.username, "email": str(user.email),
            "enabled": True, "realmRoles": [str(user.user_role)],
            "credentials": [{"type": "password", "value": password, "temporary": True}],
            "requiredActions": ["UPDATE_PASSWORD"],
        })
        passwords.append({"user_id": str(user.id), "email": str(user.email), "temporary_password": password})
    return {"ifResourceExists": "FAIL", "users": exported}, passwords


async def export(output: Path):
    engine = get_engine()
    try:
        async with async_sessionmaker(engine)() as session:
            users = await list_identity_import_users(session)
        realm, passwords = build_import(users)
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(output, 0o700)
        # Exclusive creation prevents overwriting a previous credential handoff.
        with (output / "foc-users.json").open("x") as file:
            os.chmod(file.name, 0o600)
            json.dump(realm, file, indent=2)
        with (output / "temporary-passwords.csv").open("x", newline="") as file:
            os.chmod(file.name, 0o600)
            writer = csv.DictWriter(file, fieldnames=["user_id", "email", "temporary_password"])
            writer.writeheader()
            writer.writerows(passwords)
        print(f"Prepared {len(users)} users with preserved UUIDs in {output}. No Keycloak changes made.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(export(args.output))
