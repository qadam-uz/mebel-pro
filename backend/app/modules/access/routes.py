"""Authentication, account, and session routes."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, Session
from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.trace import get_trace_id
from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import (
    OtpSender,
    PlainSessionTokens,
    TelegramGatewaySender,
    authenticate_platform_user,
    authenticate_workshop_user,
    change_password,
    refresh_session,
    request_otp_code,
    resolve_client_ip,
    revoke_for_principal,
    revoke_session,
    verify_otp_code,
)
from app.modules.access.contracts import Client, PlatformUser, WorkshopUser
from app.modules.access.contracts import Session as AuthSession
from app.modules.access.schemas import (
    ClientOtpRegistrationRequiredResponse,
    ClientOtpRequest,
    ClientOtpRequestResponse,
    ClientOtpVerifyRequest,
    MeResponse,
    PasswordChangeRequest,
    PermissionGrantResponse,
    PlatformLoginRequest,
    SessionResponse,
    TokenResponse,
    WorkshopLoginRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "mp_refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"


def get_otp_sender() -> OtpSender:
    return TelegramGatewaySender(
        access_token=settings.TELEGRAM_GATEWAY_ACCESS_TOKEN,
        api_base_url=settings.TELEGRAM_GATEWAY_API_BASE_URL,
        timeout_seconds=settings.TELEGRAM_GATEWAY_TIMEOUT_SECONDS,
    )


OtpSenderDep = Annotated[OtpSender, Depends(get_otp_sender)]


@router.post("/platform/login", response_model=TokenResponse)
async def platform_login(
    payload: PlatformLoginRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    result = await authenticate_platform_user(
        db,
        login=payload.login,
        password=payload.password,
        trace_id=get_trace_id(),
        device_info=_device_info(request),
    )
    _set_refresh_cookie(response, result.tokens)
    return await _token_response(db, result.tokens, result.principal)


@router.post("/workshop/login", response_model=TokenResponse)
async def workshop_login(
    payload: WorkshopLoginRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    result = await authenticate_workshop_user(
        db,
        login=payload.login,
        password=payload.password,
        trace_id=get_trace_id(),
        device_info=_device_info(request),
    )
    _set_refresh_cookie(response, result.tokens)
    return await _token_response(db, result.tokens, result.principal)


@router.post("/client/otp/request", response_model=ClientOtpRequestResponse)
async def client_otp_request(
    payload: ClientOtpRequest,
    request: Request,
    db: Session,
    sender: OtpSenderDep,
) -> ClientOtpRequestResponse:
    result = await request_otp_code(
        db,
        phone=payload.phone,
        request_ip=_request_ip(request),
        sender=sender,
    )
    return ClientOtpRequestResponse(
        phone=result.phone,
        expires_at=result.expires_at,
        resend_after_seconds=result.resend_after_seconds,
    )


@router.post(
    "/client/otp/verify",
    response_model=TokenResponse | ClientOtpRegistrationRequiredResponse,
)
async def client_otp_verify(
    payload: ClientOtpVerifyRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse | ClientOtpRegistrationRequiredResponse:
    result = await verify_otp_code(
        db,
        phone=payload.phone,
        code=payload.code,
        name=payload.name,
        trace_id=get_trace_id(),
        device_info=_device_info(request),
    )
    if result.is_new:
        return ClientOtpRegistrationRequiredResponse()
    if result.login is None:
        raise RuntimeError("OTP verification returned no login result for existing client")
    _set_refresh_cookie(response, result.login.tokens)
    return await _token_response(db, result.login.tokens, result.login.principal)


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
        return MeResponse(
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            session_id=principal.session_id,
            name=client.name,
            phone=client.phone,
            preferred_branch_id=client.preferred_branch_id,
            status=client.status,
        )
    workshop_user = await db.get(WorkshopUser, principal.principal_id)
    if workshop_user is None:
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return MeResponse(
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
        session_id=principal.session_id,
        password_reset_required=workshop_user.password_reset_required,
        workshop_id=principal.workshop_id,
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
