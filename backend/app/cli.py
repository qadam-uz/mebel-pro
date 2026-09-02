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
from app.models.enums import FileStorageStatus
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

    backfill = subcommands.add_parser(
        "backfill-image-variants",
        help="Generate sm/md renditions for images uploaded before variants existed.",
    )
    backfill.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Rows per transaction. Smaller batches commit progress more often.",
    )
    backfill.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many images. Omit to process all remaining.",
    )

    webhook = subcommands.add_parser(
        "telegram-webhook",
        help="Register, inspect, or remove the bot's webhook with the Telegram Bot API.",
    )
    webhook.add_argument("action", choices=["set", "info", "delete"])
    webhook.add_argument(
        "--base-url",
        default=None,
        help="Public origin the webhook lives behind (default: CLIENT_APP_BASE_URL).",
    )
    webhook.add_argument(
        "--drop-pending-updates",
        action="store_true",
        help="Discard updates Telegram queued while the webhook was down.",
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
    elif args.command == "seed-error-record":
        asyncio.run(_seed_error_record(code=args.code, module=args.module, message=args.message))
    elif args.command == "backfill-image-variants":
        asyncio.run(_backfill_image_variants(batch_size=args.batch_size, limit=args.limit))
    elif args.command == "telegram-webhook":
        asyncio.run(
            _telegram_webhook(
                action=args.action,
                base_url=args.base_url,
                drop_pending_updates=args.drop_pending_updates,
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


async def _telegram_webhook(
    *,
    action: str,
    base_url: str | None,
    drop_pending_updates: bool,
) -> None:
    """Point the bot at this deployment's webhook route, inspect it, or remove it.

    Telegram keeps the registration until it is changed, so `set` is a one-time
    deploy step (re-run only when the public origin or the secret rotates).
    """
    from app.core import telegram
    from app.core.config import settings

    try:
        if action == "info":
            print(json.dumps(await telegram.call("getWebhookInfo", {})))
            return
        if action == "delete":
            await telegram.call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})
            print(json.dumps({"status": "deleted"}))
            return
        if settings.TELEGRAM_WEBHOOK_SECRET in {"", "{{change-me}}"}:
            raise SystemExit("TELEGRAM_WEBHOOK_SECRET must be set before registering the webhook")
        origin = (base_url or settings.CLIENT_APP_BASE_URL).rstrip("/")
        url = f"{origin}{settings.API_V1_PREFIX}/telegram/webhook"
        payload: dict[str, object] = {
            "url": url,
            "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
            # The conversation only consumes these two; narrowing the
            # subscription keeps unrelated update spam off the endpoint.
            "allowed_updates": ["message", "callback_query"],
        }
        if drop_pending_updates:
            payload["drop_pending_updates"] = True
        await telegram.call("setWebhook", payload)
        print(json.dumps({"status": "set", "url": url}))
    except telegram.TelegramApiError as exc:
        raise SystemExit(f"Telegram Bot API refused: {exc}") from exc


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


async def _backfill_image_variants(*, batch_size: int, limit: int | None) -> None:
    """Generate renditions for images that predate the variants column.

    Resumable and idempotent: the query only selects rows whose `variant_keys` is
    still NULL, and each batch commits on its own. Re-running after an
    interruption — or after adding a new rendition size — picks up where it left
    off. Safe to run against a live system: it only ever adds objects and fills a
    column the read path already treats as optional.
    """
    from app.models import import_all_models
    from app.modules.support.api import IMAGE_CONTENT_TYPES, build_image_variants, file_storage
    from app.modules.support.contracts import File as StoredFile

    import_all_models()
    storage = file_storage()
    processed = 0
    skipped = 0
    failed = 0

    while limit is None or processed + skipped + failed < limit:
        remaining = (
            batch_size if limit is None else min(batch_size, limit - processed - skipped - failed)
        )
        async with SessionLocal() as db:
            rows = list(
                (
                    await db.scalars(
                        select(StoredFile)
                        .where(
                            StoredFile.variant_keys.is_(None),
                            StoredFile.content_type.in_(IMAGE_CONTENT_TYPES),
                            StoredFile.storage_status == FileStorageStatus.STORED,
                        )
                        # Stable order so an interrupted run resumes predictably.
                        .order_by(StoredFile.created_at, StoredFile.id)
                        .limit(remaining)
                    )
                ).all()
            )
            if not rows:
                break
            for row in rows:
                try:
                    content = await asyncio.to_thread(storage.open, row.storage_key)
                except Exception as exc:
                    failed += 1
                    print(
                        json.dumps({"id": str(row.id), "status": "read_failed", "error": str(exc)})
                    )
                    continue
                keys = await build_image_variants(
                    storage,
                    storage_key=row.storage_key,
                    content_type=row.content_type,
                    content=content,
                )
                # An image already smaller than every rendition legitimately has
                # none. Writing `{}` marks it done so the next run skips it —
                # leaving NULL would make the backfill re-read it forever.
                row.variant_keys = keys if keys is not None else {}
                if keys:
                    processed += 1
                else:
                    skipped += 1
            await db.commit()
        print(
            json.dumps(
                {
                    "status": "progress",
                    "generated": processed,
                    "no_variants_needed": skipped,
                    "failed": failed,
                }
            )
        )

    print(
        json.dumps(
            {
                "status": "done",
                "generated": processed,
                "no_variants_needed": skipped,
                "failed": failed,
            }
        )
    )


if __name__ == "__main__":
    main()
