"""The bot side of client sign-in: one update in, one reply out.

Copy is **Uzbek-only** in v1 — the bot has no reliable locale channel, matching
the server-rendered-documents rule in `docs/architecture.md`. Every outbound
send here is best-effort: a Bot API hiccup must not roll back a handshake the
browser's poll is about to redeem, so send failures are logged and swallowed
while the state change still commits with the webhook's 2xx.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.core.errors import APIError
from app.core.telegram import TelegramApiError, answer_callback_query, send_message
from app.models.enums import TelegramLoginTokenStatus, UserStatus
from app.modules.access.clients import find_or_create_client
from app.modules.access.contracts import Client, TelegramLoginToken
from app.modules.access.telegram_login import (
    ADVANCEABLE_STATUSES,
    confirm_login_token,
    decline_login_token,
    find_awaiting_contact_token,
    find_login_token,
    issue_login_code,
)

logger = get_logger(__name__)

# Uzbekistan is UTC+5 year-round — the confirm message names a wall-clock time
# the client can recognize, not a UTC one.
TASHKENT_OFFSET = timedelta(hours=5)
MAX_CLIENT_NAME = 80

CONFIRM_PREFIX = "confirm:"
DECLINE_PREFIX = "decline:"
LOGIN_CODE_ACTION = "login_code"

HELP_TEXT = (
    "MebelPro botiga xush kelibsiz.\n\n"
    "Saytga kirish uchun kirish sahifasidagi QR kodni skanerlang yoki "
    '"Telegram orqali kirish" tugmasini bosing.\n\n'
    "QR ni skanerlay olmasangiz, quyidagi tugma orqali kirish kodini oling."
)
EXPIRED_TEXT = "Muddat tugadi. Saytdagi QR ni yangilang."
CONFIRMED_TEXT = "Tasdiqlandi. Saytga qayting."
DECLINED_TEXT = "Kirish bekor qilindi."
BLOCKED_TEXT = "Hisobingiz bloklangan. Ustaxona bilan bog'laning."
ASK_CONTACT_TEXT = "Davom etish uchun telefon raqamingizni ulashing — quyidagi tugmani bosing."
FOREIGN_CONTACT_TEXT = "Iltimos, faqat o'z raqamingizni ulashing."
UNSUPPORTED_PHONE_TEXT = "Hozircha faqat O'zbekiston raqamlari (+998) qo'llab-quvvatlanadi."
CODE_TEXT = "Kirish kodi: {code}\n\n5 daqiqa amal qiladi. Kodni saytdagi maydonga kiriting."

_CONTACT_KEYBOARD: dict[str, Any] = {
    "keyboard": [[{"text": "📱 Raqamni ulashish", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
_CODE_KEYBOARD: dict[str, Any] = {
    "inline_keyboard": [[{"text": "Kirish kodi", "callback_data": LOGIN_CODE_ACTION}]]
}


def _confirm_keyboard(token_id: uuid.UUID) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Tasdiqlash", "callback_data": f"{CONFIRM_PREFIX}{token_id}"},
                {"text": "Bekor qilish", "callback_data": f"{DECLINE_PREFIX}{token_id}"},
            ]
        ]
    }


async def handle_update(
    db: AsyncSession,
    update: dict[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    """Route one Telegram update. Unknown update kinds are ignored."""
    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    message = update.get("message")
    callback = update.get("callback_query")
    if isinstance(message, dict):
        await _handle_message(db, message, now=current)
    elif isinstance(callback, dict):
        await _handle_callback(db, callback, now=current)


async def _handle_message(db: AsyncSession, message: dict[str, Any], *, now: datetime) -> None:
    sender_id = _sender_id(message.get("from"))
    if sender_id is None:
        return
    chat_id = _chat_id(message, sender_id)
    contact = message.get("contact")
    if isinstance(contact, dict):
        await _handle_contact(
            db,
            contact=contact,
            sender=message.get("from") or {},
            sender_id=sender_id,
            chat_id=chat_id,
            now=now,
        )
        return
    text = message.get("text")
    if isinstance(text, str) and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        await _handle_start(
            db,
            token=parts[1].strip() if len(parts) > 1 else None,
            sender_id=sender_id,
            chat_id=chat_id,
            now=now,
        )
        return
    await _reply(chat_id, HELP_TEXT, reply_markup=_CODE_KEYBOARD)


async def _handle_start(
    db: AsyncSession,
    *,
    token: str | None,
    sender_id: int,
    chat_id: int,
    now: datetime,
) -> None:
    # Pressing Start un-blocks the bot by definition, so any earlier 403 is stale.
    await _clear_unreachable(db, sender_id=sender_id)
    if not token:
        await _reply(chat_id, HELP_TEXT, reply_markup=_CODE_KEYBOARD)
        return
    row = await find_login_token(db, token=token)
    if row is None or not _is_open(row, now=now):
        await _reply(chat_id, EXPIRED_TEXT, reply_markup=_CODE_KEYBOARD)
        return
    row.telegram_user_id = sender_id
    row.status = TelegramLoginTokenStatus.STARTED
    await db.flush()
    client = await _client_by_telegram_id(db, sender_id)
    if client is not None and client.status is not UserStatus.ACTIVE:
        decline_login_token(row, now=now)
        await db.flush()
        await _reply(chat_id, BLOCKED_TEXT)
        return
    # The confirm comes first for known and unknown accounts alike — the
    # exists/new branch is only revealed after a verified contact, so the
    # conversation is never an account-existence oracle.
    await _reply(chat_id, _confirm_prompt(row), reply_markup=_confirm_keyboard(row.id))


async def _handle_callback(db: AsyncSession, callback: dict[str, Any], *, now: datetime) -> None:
    sender_id = _sender_id(callback.get("from"))
    if sender_id is None:
        return
    message = callback.get("message")
    chat_id = _chat_id(message, sender_id) if isinstance(message, dict) else sender_id
    callback_id = callback.get("id")
    if isinstance(callback_id, str):
        await _acknowledge(callback_id)
    data = callback.get("data")
    if not isinstance(data, str):
        return
    if data == LOGIN_CODE_ACTION:
        await _start_code_flow(db, sender_id=sender_id, chat_id=chat_id, now=now)
        return
    for prefix, decision in ((CONFIRM_PREFIX, True), (DECLINE_PREFIX, False)):
        if data.startswith(prefix):
            token_id = _parse_uuid(data[len(prefix) :])
            if token_id is not None:
                await _resolve_confirmation(
                    db,
                    token_id=token_id,
                    confirmed=decision,
                    sender_id=sender_id,
                    chat_id=chat_id,
                    now=now,
                )
            return


async def _resolve_confirmation(
    db: AsyncSession,
    *,
    token_id: uuid.UUID,
    confirmed: bool,
    sender_id: int,
    chat_id: int,
    now: datetime,
) -> None:
    row = await db.get(TelegramLoginToken, token_id)
    # The token must belong to the chat that answered: a leaked callback id from
    # another account must not advance somebody else's handshake.
    if row is None or row.telegram_user_id != sender_id or not _is_open(row, now=now):
        await _reply(chat_id, EXPIRED_TEXT, reply_markup=_CODE_KEYBOARD)
        return
    if not confirmed:
        decline_login_token(row, now=now)
        await db.flush()
        await _reply(chat_id, DECLINED_TEXT)
        return
    client = await _client_by_telegram_id(db, sender_id)
    if client is None:
        # Unknown account — ask for the Telegram-verified number before binding.
        row.status = TelegramLoginTokenStatus.AWAITING_CONTACT
        await db.flush()
        await _reply(chat_id, ASK_CONTACT_TEXT, reply_markup=_CONTACT_KEYBOARD)
        return
    if client.status is not UserStatus.ACTIVE:
        decline_login_token(row, now=now)
        await db.flush()
        await _reply(chat_id, BLOCKED_TEXT)
        return
    confirm_login_token(row, client=client, now=now)
    await db.flush()
    await _reply(chat_id, CONFIRMED_TEXT)


async def _start_code_flow(
    db: AsyncSession,
    *,
    sender_id: int,
    chat_id: int,
    now: datetime,
) -> None:
    client = await _client_by_telegram_id(db, sender_id)
    if client is None:
        # Same identification as the deep-link path; the contact handler picks
        # the flow back up and issues the code once the number is verified.
        await _reply(chat_id, ASK_CONTACT_TEXT, reply_markup=_CONTACT_KEYBOARD)
        return
    if client.status is not UserStatus.ACTIVE:
        await _reply(chat_id, BLOCKED_TEXT)
        return
    code = await issue_login_code(db, client=client, now=now)
    await _reply(chat_id, CODE_TEXT.format(code=code))


async def _handle_contact(
    db: AsyncSession,
    *,
    contact: dict[str, Any],
    sender: dict[str, Any],
    sender_id: int,
    chat_id: int,
    now: datetime,
) -> None:
    # Only the sender's *own* contact proves possession of the number; a
    # forwarded or hand-picked one proves nothing.
    if contact.get("user_id") != sender_id:
        await _reply(chat_id, FOREIGN_CONTACT_TEXT, reply_markup=_CONTACT_KEYBOARD)
        return
    phone = _normalize_contact_phone(contact.get("phone_number"))
    if phone is None:
        await _reply(chat_id, UNSUPPORTED_PHONE_TEXT)
        return
    token = await find_awaiting_contact_token(db, telegram_user_id=sender_id, now=now)
    try:
        resolution = await find_or_create_client(
            db,
            phone=phone,
            name=_profile_name(sender, phone=phone),
        )
    except APIError as exc:
        if exc.code != "account_blocked":
            raise
        if token is not None:
            decline_login_token(token, now=now)
            await db.flush()
        await _reply(chat_id, BLOCKED_TEXT)
        return
    if resolution is None:
        raise RuntimeError("contact registration produced no client despite a name")
    await _link_telegram_account(db, client=resolution.client, telegram_user_id=sender_id)
    if token is not None:
        confirm_login_token(token, client=resolution.client, now=now)
        await db.flush()
        await _reply(chat_id, CONFIRMED_TEXT)
        return
    code = await issue_login_code(db, client=resolution.client, now=now)
    await _reply(chat_id, CODE_TEXT.format(code=code))


async def _link_telegram_account(
    db: AsyncSession,
    *,
    client: Client,
    telegram_user_id: int,
) -> None:
    """Bind this Telegram account to this client, relinking if either moved.

    A fresh Telegram-verified contact always wins: possession of the number is
    the identity. The account is unbound from any other client row first — the
    id is unique — and the client's own stale link is overwritten.
    """
    previous = (
        await db.scalars(
            select(Client).where(
                Client.telegram_user_id == telegram_user_id,
                Client.id != client.id,
            )
        )
    ).all()
    for row in previous:
        row.telegram_user_id = None
    if previous:
        await db.flush()
    client.telegram_user_id = telegram_user_id
    client.telegram_unreachable_at = None
    await db.flush()


async def _clear_unreachable(db: AsyncSession, *, sender_id: int) -> None:
    client = await _client_by_telegram_id(db, sender_id)
    if client is not None and client.telegram_unreachable_at is not None:
        client.telegram_unreachable_at = None
        await db.flush()


async def _client_by_telegram_id(db: AsyncSession, telegram_user_id: int) -> Client | None:
    client: Client | None = await db.scalar(
        select(Client).where(Client.telegram_user_id == telegram_user_id)
    )
    return client


def _is_open(row: TelegramLoginToken, *, now: datetime) -> bool:
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return row.status in ADVANCEABLE_STATUSES and expires_at > now


def _confirm_prompt(row: TelegramLoginToken) -> str:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    local_time = (created_at + TASHKENT_OFFSET).strftime("%H:%M")
    return (
        f"MebelPro saytiga kirish — {_device_label(row.device_info)}, {local_time}. Tasdiqlaysizmi?"
    )


def _device_label(device_info: dict[str, Any]) -> str:
    """A short, recognizable device name for the confirm message.

    This is the only mitigation against being lured into scanning someone
    else's QR, so it must read as a device the client either recognizes or
    doesn't — not as a user-agent string.
    """
    user_agent = device_info.get("user_agent")
    if not isinstance(user_agent, str):
        return "Brauzer"
    known = (
        ("iPhone", "iPhone"),
        ("iPad", "iPad"),
        ("Android", "Android"),
        ("Windows", "Windows"),
        ("Macintosh", "Mac"),
        ("Mac OS", "Mac"),
        ("Linux", "Linux"),
    )
    for needle, label in known:
        if needle in user_agent:
            return label
    return "Brauzer"


def _profile_name(sender: dict[str, Any], *, phone: str) -> str:
    """Registration name, prefilled from the Telegram profile, trimmed to 80."""
    parts = [sender.get(key) for key in ("first_name", "last_name")]
    name = " ".join(str(part).strip() for part in parts if isinstance(part, str) and part.strip())
    name = " ".join(name.split())[:MAX_CLIENT_NAME].strip()
    # Telegram always carries a first name, but never trust it to be non-empty.
    return name or phone


def _normalize_contact_phone(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    digits = "".join(character for character in raw if character.isdigit())
    candidate = f"+{digits}"
    if len(digits) != 12 or not digits.startswith("998"):
        return None
    return candidate


def _sender_id(sender: object) -> int | None:
    if not isinstance(sender, dict):
        return None
    value = sender.get("id")
    # bool is an int subclass; a bot id never is one, so reject it explicitly.
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _chat_id(message: dict[str, Any], fallback: int) -> int:
    chat = message.get("chat")
    if isinstance(chat, dict):
        value = chat.get("id")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return fallback


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def _reply(chat_id: int, text: str, *, reply_markup: dict[str, Any] | None = None) -> None:
    try:
        await send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    except TelegramApiError as exc:
        logger.warning("telegram_bot_reply_failed", chat_id=chat_id, error=str(exc))


async def _acknowledge(callback_query_id: str) -> None:
    try:
        await answer_callback_query(callback_query_id=callback_query_id)
    except TelegramApiError as exc:
        logger.warning("telegram_bot_callback_ack_failed", error=str(exc))
