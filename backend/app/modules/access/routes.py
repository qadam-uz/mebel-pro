"""Authentication, account, and session routes."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, Session
from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.telegram import deep_link
from app.core.trace import get_trace_id
from app.models.enums import AuthenticatedPrincipalType, WorkshopStatus
from app.modules.access.api import (
    INVALID_CREDENTIALS_CODE,
    PlainSessionTokens,
    authenticate_platform_user,
    authenticate_workshop_user,
    change_password,
    create_login_token,
    dev_confirm_login_token,
    login_throttle,
    poll_login_token,
    redeem_login_code,
    refresh_session,
    resolve_client_ip,
    revoke_for_principal,
    revoke_session,
)
from app.modules.access.contracts import Client, PlatformUser, WorkshopUser
from app.modules.access.contracts import Session as AuthSession
from app.modules.access.schemas import (
    MeResponse,
    PasswordChangeRequest,
    PermissionGrantResponse,
    PlatformLoginRequest,
    SessionResponse,
    TelegramLoginCodeRequest,
    TelegramLoginDevConfirmRequest,
    TelegramLoginPollRequest,
    TelegramLoginPollResponse,
    TelegramLoginTokenResponse,
    TokenResponse,
    WorkshopLoginRequest,
)
from app.modules.workshop.contracts import Branch, Workshop

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "mp_refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"


@router.post("/platform/login", response_model=TokenResponse)
async def platform_login(
    payload: PlatformLoginRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    ip = _request_ip(request)
    login_throttle.check(ip)
    try:
        result = await authenticate_platform_user(
            db,
            login=payload.login,
            password=payload.password,
            trace_id=get_trace_id(),
            device_info=_device_info(request),
        )
    except APIError as exc:
        _record_login_failure(ip, exc)
        raise
    _set_refresh_cookie(response, result.tokens)
    return await _token_response(db, result.tokens, result.principal)


@router.post("/workshop/login", response_model=TokenResponse)
async def workshop_login(
    payload: WorkshopLoginRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    ip = _request_ip(request)
    login_throttle.check(ip)
    try:
        result = await authenticate_workshop_user(
            db,
            login=payload.login,
            password=payload.password,
            trace_id=get_trace_id(),
            device_info=_device_info(request),
        )
    except APIError as exc:
        _record_login_failure(ip, exc)
        raise
    _set_refresh_cookie(response, result.tokens)
    return await _token_response(db, result.tokens, result.principal)


@router.post("/client/telegram/token", response_model=TelegramLoginTokenResponse)
async def client_telegram_login_token(
    request: Request,
    db: Session,
) -> TelegramLoginTokenResponse:
    issued = await create_login_token(
        db,
        request_ip=_request_ip(request),
        device_info=_device_info(request),
    )
    return TelegramLoginTokenResponse(
        token=issued.token,
        poll_secret=issued.poll_secret,
        deep_link=deep_link(issued.token),
        expires_at=issued.expires_at,
    )


@router.post(
    "/client/telegram/poll",
    response_model=TokenResponse | TelegramLoginPollResponse,
)
async def client_telegram_login_poll(
    payload: TelegramLoginPollRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse | TelegramLoginPollResponse:
    result = await poll_login_token(
        db,
        poll_secret=payload.poll_secret,
        trace_id=get_trace_id(),
        device_info=_device_info(request),
    )
    if result.login is None:
        return TelegramLoginPollResponse(status=result.status, expired=result.expired)
    _set_refresh_cookie(response, result.login.tokens)
    return await _token_response(db, result.login.tokens, result.login.principal)


@router.post("/client/telegram/code", response_model=TokenResponse)
async def client_telegram_login_code(
    payload: TelegramLoginCodeRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    login = await redeem_login_code(
        db,
        code=payload.code,
        request_ip=_request_ip(request),
        trace_id=get_trace_id(),
        device_info=_device_info(request),
    )
    _set_refresh_cookie(response, login.tokens)
    return await _token_response(db, login.tokens, login.principal)


@router.post("/client/telegram/dev-confirm", status_code=status.HTTP_204_NO_CONTENT)
async def client_telegram_dev_confirm(
    payload: TelegramLoginDevConfirmRequest,
    db: Session,
) -> None:
    """Confirm a pending token without Telegram — `TELEGRAM_LOGIN_DEV_MODE` only.

    Off by default and rejected outright in production (see `Settings`), the
    route 404s when disabled rather than advertising a sign-in bypass.
    """
    if not settings.TELEGRAM_LOGIN_DEV_MODE:
        raise APIError("not_found", "Not found", status_code=status.HTTP_404_NOT_FOUND)
    await dev_confirm_login_token(
        db,
        phone=payload.phone,
        token=payload.token,
        name=payload.name,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_login(
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token is None:
        raise APIError(
            "invalid_refresh_token",
            "Refresh session is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    tokens = await refresh_session(db, refresh_token)
    if tokens is None:
        _clear_refresh_cookie(response)
        raise APIError(
            "invalid_refresh_token",
            "Refresh session is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    session = await db.get(AuthSession, tokens.session_id)
    if session is None:
        raise APIError(
            "invalid_refresh_token",
            "Refresh session is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    from app.modules.access.api import principal_from_session

    principal = await principal_from_session(db, session, trace_id=get_trace_id())
    if principal is None:
        await revoke_session(db, session.id)
        _clear_refresh_cookie(response)
        raise APIError(
            "invalid_refresh_token",
            "Refresh session is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    _set_refresh_cookie(response, tokens)
    return await _token_response(db, tokens, principal)


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal, db: Session) -> MeResponse:
    return await _me_response(db, principal)


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def password_change(
    payload: PasswordChangeRequest,
    principal: Principal,
    db: Session,
) -> None:
    await change_password(
        db,
        principal=principal,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(principal: Principal, db: Session) -> list[SessionResponse]:
    rows = (
        await db.scalars(
            select(AuthSession)
            .where(
                AuthSession.principal_type == principal.principal_type,
                AuthSession.principal_id == principal.principal_id,
            )
            .order_by(AuthSession.created_at.desc())
        )
    ).all()
    return [_session_response(row, current_session_id=principal.session_id) for row in rows]


@router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT)
async def logout_current(
    response: Response,
    principal: Principal,
    db: Session,
) -> None:
    await revoke_session(db, principal.session_id)
    _clear_refresh_cookie(response)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def logout_everywhere(
    response: Response,
    principal: Principal,
    db: Session,
) -> None:
    await revoke_for_principal(
        db,
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
    )
    _clear_refresh_cookie(response)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    response: Response,
    principal: Principal,
    db: Session,
) -> None:
    row = await db.get(AuthSession, session_id)
    if (
        row is None
        or row.principal_type is not principal.principal_type
        or row.principal_id != principal.principal_id
    ):
        raise APIError(
            "session_not_found",
            "Session not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    await revoke_session(db, row.id)
    if row.id == principal.session_id:
        _clear_refresh_cookie(response)


async def _token_response(
    db: AsyncSession,
    tokens: PlainSessionTokens,
    principal: AuthenticatedPrincipal,
) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        access_token_expires_at=tokens.access_token_expires_at,
        me=await _me_response(db, principal),
    )


async def _me_response(db: AsyncSession, principal: AuthenticatedPrincipal) -> MeResponse:
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        user = await db.get(PlatformUser, principal.principal_id)
        if user is None:
            raise APIError(
                "invalid_access_token",
                "Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return MeResponse(
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            session_id=principal.session_id,
            password_reset_required=user.password_reset_required,
            login=user.login,
            full_name=user.full_name,
            phone=user.phone,
            status=user.status,
        )
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        client = await db.get(Client, principal.principal_id)
        if client is None:
            raise APIError(
                "invalid_access_token",
                "Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        pinned_workshop_name, pinned_branch_name = await _pinned_names(
            db, client.preferred_branch_id
        )
        return MeResponse(
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            session_id=principal.session_id,
            name=client.name,
            phone=client.phone,
            preferred_branch_id=client.preferred_branch_id,
            pinned_workshop_name=pinned_workshop_name,
            pinned_branch_name=pinned_branch_name,
            status=client.status,
        )
    workshop_user = await db.get(WorkshopUser, principal.principal_id)
    if workshop_user is None:
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    workshop = (
        await db.get(Workshop, principal.workshop_id) if principal.workshop_id is not None else None
    )
    return MeResponse(
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
        session_id=principal.session_id,
        password_reset_required=workshop_user.password_reset_required,
        workshop_id=principal.workshop_id,
        workshop_name=workshop.name if workshop is not None else None,
        is_owner=principal.is_owner,
        grants=[
            PermissionGrantResponse(permission=grant.permission, branch_id=grant.branch_id)
            for grant in sorted(
                principal.grants,
                key=lambda item: (item.branch_id.hex, item.permission.value),
            )
        ],
        login=workshop_user.login,
        full_name=workshop_user.full_name,
        phone=workshop_user.phone,
        status=workshop_user.status,
    )


async def _pinned_names(
    db: AsyncSession,
    preferred_branch_id: uuid.UUID | None,
) -> tuple[str | None, str | None]:
    """Workshop and branch names behind the client's pin — one join, no gates.

    The pin is not scope-enforced (identity.md): an `inactive` or
    `temporarily_closed` branch still names itself in the header, and nothing
    here ever clears the column. A blocked workshop is the one exception — it is
    off the platform, absent from Ustaxonalarim, and must not be named either.
    """
    if preferred_branch_id is None:
        return None, None
    row = (
        await db.execute(
            select(Workshop.name, Branch.name)
            .join(Branch, Branch.workshop_id == Workshop.id)
            .where(
                Branch.id == preferred_branch_id,
                Workshop.status == WorkshopStatus.ACTIVE,
            )
        )
    ).first()
    if row is None:
        return None, None
    return row[0], row[1]


def _session_response(row: AuthSession, *, current_session_id: uuid.UUID) -> SessionResponse:
    return SessionResponse(
        id=row.id,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        access_token_expires_at=row.access_token_expires_at,
        refresh_token_expires_at=row.refresh_token_expires_at,
        device_info=row.device_info,
        is_current=row.id == current_session_id,
    )


def _set_refresh_cookie(response: Response, tokens: PlainSessionTokens) -> None:
    max_age = int((tokens.refresh_token_expires_at - datetime.now(UTC)).total_seconds())
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens.refresh_token,
        max_age=max(max_age, 0),
        expires=tokens.refresh_token_expires_at,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def _record_login_failure(ip: str, exc: APIError) -> None:
    # Only credential misses count against the IP budget — lockout/blocked
    # responses are already throttled by the account state itself.
    if exc.code == INVALID_CREDENTIALS_CODE:
        login_throttle.record_failure(ip)


def _device_info(request: Request) -> dict[str, Any]:
    return {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    }


def _request_ip(request: Request) -> str:
    return resolve_client_ip(
        peer_host=request.client.host if request.client else None,
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        trusted_proxy_cidrs=settings.TRUSTED_PROXY_CIDRS,
    )
