"""Backend maintenance CLI.

Run with:

    uv run python -m app.cli seed-platform-user --login admin --password Admin123
"""

import argparse
import asyncio
import json
from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.modules.access.contracts import PlatformUser


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)

    seed = subcommands.add_parser("seed-platform-user")
    seed.add_argument("--login", required=True)
    seed.add_argument("--password", required=True)
    seed.add_argument("--full-name", default="Platform Admin")
    seed.add_argument("--phone", default="+998901234567")
    seed.add_argument(
        "--no-password-reset-required",
        action="store_true",
        help="Create the user without forcing a first-login password change.",
    )

    args = parser.parse_args(argv)
    if args.command == "seed-platform-user":
        asyncio.run(
            _seed_platform_user(
                login=args.login,
                password=args.password,
                full_name=args.full_name,
                phone=args.phone,
                password_reset_required=not args.no_password_reset_required,
            )
        )


async def _seed_platform_user(
    *,
    login: str,
    password: str,
    full_name: str,
    phone: str,
    password_reset_required: bool,
) -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(
            select(PlatformUser).where(func.lower(PlatformUser.login) == login.strip().lower())
        )
        if existing is not None:
            print(
                json.dumps(
                    {
                        "status": "exists",
                        "id": str(existing.id),
                        "login": existing.login,
                    }
                )
            )
            return

        user = PlatformUser(
            login=login.strip(),
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            phone=phone.strip(),
            password_reset_required=password_reset_required,
        )
        db.add(user)
        await db.commit()
        print(
            json.dumps(
                {
                    "status": "created",
                    "id": str(user.id),
                    "login": user.login,
                    "password_reset_required": user.password_reset_required,
                }
            )
        )


if __name__ == "__main__":
    main()
