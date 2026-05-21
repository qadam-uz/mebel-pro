"""Auth routes — sign-in (workshop/platform/client), refresh, sessions, me."""

import uuid

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import PrincipalAllowPwChange, Session, device_info_from
from app.core.config import settings
from app.core.errors import not_found
from app.models.identity import Client, PlatformUser, WorkshopUser
from app.models.identity import Session as SessionRow
from app.schemas.auth import (
    ChangePasswordRequest,
    ClientTokenResponse,
    GrantOut,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    SessionInfo,
    TelegramLoginRequest,
    TokenResponse,
)
from app.services import auth as auth_service
from app.services import sessions as session_service

router = APIRouter()


@router.get("/telegram-config")
async def telegram_config() -> dict[str, str]:
    """Public — the bot username the client app mounts the Login Widget with."""
    return {"bot_username": settings.TELEGRAM_BOT_USERNAME}


@router.post("/platform/login", response_model=TokenResponse)
async def platform_login(body: LoginRequest, db: Session, request: Request) -> TokenResponse:
    issued = await auth_service.authenticate_platform(
        db, body.login, body.password, device_info_from(request)
    )
    return TokenResponse(access_token=issued.access_token, refresh_token=issued.refresh_token)


@router.post("/workshop/login", response_model=TokenResponse)
async def workshop_login(body: LoginRequest, db: Session, request: Request) -> TokenResponse:
    issued = await auth_service.authenticate_workshop(
        db, body.login, body.password, device_info_from(request)
    )
    return TokenResponse(access_token=issued.access_token, refresh_token=issued.refresh_token)


@router.post("/client/telegram", response_model=ClientTokenResponse)
async def client_telegram_login(
    body: TelegramLoginRequest, db: Session, request: Request
) -> ClientTokenResponse:
    result = await auth_service.authenticate_client_telegram(
        db, body.model_dump(exclude_none=True), device_info_from(request)
    )
    return ClientTokenResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        is_new=result.is_new,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest, db: Session) -> RefreshResponse:
    access_token, _ = await auth_service.refresh_tokens(db, body.refresh_token)
    return RefreshResponse(access_token=access_token)


@router.get("/me", response_model=MeResponse)
async def me(principal: PrincipalAllowPwChange, db: Session) -> MeResponse:
    if principal.is_platform_user:
        pu = await db.get(PlatformUser, principal.id)
        assert pu is not None
        return MeResponse(
            principal_type=principal.type,
            id=pu.id,
            full_name=pu.full_name,
            phone=pu.phone,
            force_password_change=pu.force_password_change,
        )
    if principal.is_workshop_user:
        wu = await db.get(WorkshopUser, principal.id)
        assert wu is not None
        return MeResponse(
            principal_type=principal.type,
            id=wu.id,
            full_name=wu.full_name,
            phone=wu.phone,
            force_password_change=wu.force_password_change,
            workshop_id=wu.workshop_id,
            is_owner=wu.is_owner,
            home_branch_id=wu.home_branch_id,
            grants=[GrantOut(permission=p, branch_id=b) for (p, b) in principal.grants],
        )
    cl = await db.get(Client, principal.id)
    assert cl is not None
    return MeResponse(
        principal_type=principal.type,
        id=cl.id,
        full_name=cl.first_name,
        first_name=cl.first_name,
        phone=cl.phone,
        photo_url=cl.photo_url,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, principal: PrincipalAllowPwChange, db: Session
) -> Response:
    await auth_service.change_own_password(db, principal, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: PrincipalAllowPwChange, db: Session) -> Response:
    session = await db.get(SessionRow, principal.session_id)
    if session is not None:
        await session_service.revoke(db, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(principal: PrincipalAllowPwChange, db: Session) -> Response:
    await session_service.revoke_all(db, principal.type, principal.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(principal: PrincipalAllowPwChange, db: Session) -> list[SessionInfo]:
    rows = (
        (
            await db.execute(
                select(SessionRow)
                .where(
                    SessionRow.principal_type == principal.type,
                    SessionRow.principal_id == principal.id,
                )
                .order_by(SessionRow.last_used_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        SessionInfo(
            id=r.id,
            device_info=r.device_info,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            current=(r.id == principal.session_id),
        )
        for r in rows
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID, principal: PrincipalAllowPwChange, db: Session
) -> Response:
    session = await db.get(SessionRow, session_id)
    if (
        session is None
        or session.principal_type is not principal.type
        or session.principal_id != principal.id
    ):
        raise not_found("Session not found.")
    await session_service.revoke(db, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
