"""Client identity helpers shared by OTP login and staff walk-in resolve."""

import re
from dataclasses import dataclass

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.enums import UserStatus
from app.modules.access.contracts import Client

PHONE_RE = re.compile(r"^\+998\d{9}$")


def normalize_uz_phone(phone: str) -> str:
    normalized = phone.strip()
    if not PHONE_RE.fullmatch(normalized):
        raise APIError("invalid_phone", "Invalid phone", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


def normalize_client_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = " ".join(name.strip().split())
    if not normalized:
        return None
    if len(normalized) > 80:
        raise APIError("name_required", "Name is required", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


@dataclass(frozen=True)
class ClientResolution:
    client: Client
    created: bool


async def find_or_create_client(
    db: AsyncSession,
    *,
    phone: str,
    name: str | None,
) -> ClientResolution | None:
    """Find the client owning ``phone``, else create one named ``name``.

    This is the single lookup-else-create path for client identity — OTP
    verification and the workshop walk-in resolve both go through it. Returns
    ``None`` when no client exists and no usable name was provided, so callers
    decide whether to prompt for registration (OTP) or reject
    (``client_name_required``). A matched client with a non-active status
    raises the same ``account_blocked`` error shape OTP verification uses.
    """
    normalized_phone = normalize_uz_phone(phone)
    client = await db.scalar(select(Client).where(Client.phone == normalized_phone))
    if client is not None:
        if client.status is not UserStatus.ACTIVE:
            raise APIError(
                "account_blocked",
                "Account is blocked",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return ClientResolution(client=client, created=False)
    client_name = normalize_client_name(name)
    if client_name is None:
        return None
    client = Client(phone=normalized_phone, name=client_name, status=UserStatus.ACTIVE)
    db.add(client)
    await db.flush()
    return ClientResolution(client=client, created=True)
