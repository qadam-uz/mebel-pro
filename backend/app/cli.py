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

    seed_error = subcommands.add_parser(
        "seed-error-record",
        help="Record an application error so the monitor has a row to act on (E2E).",
    )
    seed_error.add_argument("--code", required=True)
    seed_error.add_argument("--module", default="e2e")
    seed_error.add_argument("--message", default="Seeded error record for E2E")

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
    elif args.command == "seed-error-record":
        asyncio.run(_seed_error_record(code=args.code, module=args.module, message=args.message))


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


async def _seed_error_record(*, code: str, module: str, message: str) -> None:
    from app.models import import_all_models
    from app.modules.platform.api import record_application_error

    # ErrorOccurrence carries FKs to workshops / platform_users, so the full model
    # registry must be loaded before the mapper resolves those relationships.
    import_all_models()
    async with SessionLocal() as db:
        record = await record_application_error(
            db,
            code=code,
            module=module,
            message=message,
            trace_id=f"e2e-{code}",
        )
        await db.commit()
        print(json.dumps({"status": "created", "id": str(record.id), "code": record.code}))


if __name__ == "__main__":
    main()
