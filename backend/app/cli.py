"""Backend CLI — seed the first platform operator (chicken-and-egg).

Platform users sit at the top of the hierarchy, so the very first one is
created out of band (docs/ref/features/access-management.md):

    uv run python -m app.cli seed-platform-user \
        --login admin --name "Operator" --phone +998901234567
"""

import argparse
import asyncio

from app.core.db import SessionLocal
from app.services import users as user_service


async def _seed_platform_user(login: str, name: str, phone: str, password: str | None) -> None:
    async with SessionLocal() as db:
        created = await user_service.create_platform_user(
            db, None, full_name=name, login=login, phone=phone, password=password
        )
        await db.commit()
        print("Created platform user.")
        print(f"  login:         {created.user.login}")
        print(f"  temp password: {created.temp_password}")
        print("  (must be changed on first login)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-platform-user", help="Create the first platform operator")
    seed.add_argument("--login", required=True)
    seed.add_argument("--name", required=True)
    seed.add_argument("--phone", required=True)
    seed.add_argument("--password", default=None, help="optional; auto-generated if omitted")

    args = parser.parse_args()
    if args.command == "seed-platform-user":
        asyncio.run(_seed_platform_user(args.login, args.name, args.phone, args.password))


if __name__ == "__main__":
    main()
