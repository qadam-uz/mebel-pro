from app.api.deps import AccountReadyPrincipal, Principal, get_session
from app.main import create_app
from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


class SensitivePayload(BaseModel):
    password: int


async def test_trace_header_is_returned(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/healthz", headers={"X-Trace-ID": "trace-test"})

    assert resp.status_code == 200
    assert resp.headers["X-Trace-ID"] == "trace-test"


async def test_missing_access_token_uses_structured_error(db_session: AsyncSession) -> None:
    app = create_app()

    async def _override() -> AsyncSession:
        return db_session

    @app.get("/api/v1/test/whoami")
    async def whoami(_: Principal) -> dict[str, str]:
        return {"ok": "true"}

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/test/whoami", headers={"X-Trace-ID": "trace-auth"})
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.headers["X-Trace-ID"] == "trace-auth"
    assert resp.json() == {
        "code": "missing_access_token",
        "message": "Authentication required",
        "trace_id": "trace-auth",
    }


async def test_validation_errors_do_not_echo_sensitive_inputs() -> None:
    app = create_app()

    @app.post("/api/v1/test/validate")
    async def validate_payload(_: SensitivePayload) -> dict[str, str]:
        return {"ok": "true"}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/test/validate",
            json={"password": "Secret123"},
            headers={"X-Trace-ID": "trace-validation"},
        )

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"
    assert "input" not in resp.text
    assert "Secret123" not in resp.text


async def test_access_token_resolves_principal_through_route(db_session: AsyncSession) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    app = create_app()

    async def _override() -> AsyncSession:
        return db_session

    @app.get("/api/v1/test/whoami")
    async def whoami(principal: Principal) -> dict[str, str]:
        return {
            "principal_type": principal.principal_type.value,
            "principal_id": str(principal.principal_id),
            "trace_id": principal.trace_id,
        }

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/test/whoami",
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "X-Trace-ID": "trace-auth",
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {
        "principal_type": "workshop_user",
        "principal_id": str(owner.id),
        "trace_id": "trace-auth",
    }


async def test_account_ready_dependency_blocks_password_reset_required(
    db_session: AsyncSession,
) -> None:
    user = await seed_platform_user(db_session, login="needs-reset", password="Admin123")
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=user.id,
    )
    app = create_app()

    async def _override() -> AsyncSession:
        return db_session

    @app.get("/api/v1/test/ready")
    async def ready(_: AccountReadyPrincipal) -> dict[str, str]:
        return {"ok": "true"}

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        blocked = await ac.get(
            "/api/v1/test/ready",
            headers={"Authorization": f"Bearer {tokens.access_token}"},
        )
        user.password_reset_required = False
        allowed = await ac.get(
            "/api/v1/test/ready",
            headers={"Authorization": f"Bearer {tokens.access_token}"},
        )
    app.dependency_overrides.clear()

    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_reset_required"
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": "true"}


async def test_unexpected_errors_return_generic_public_body() -> None:
    app = create_app()

    @app.get("/api/v1/test/boom")
    async def boom() -> None:
        raise RuntimeError("password=secret")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/test/boom", headers={"X-Trace-ID": "trace-boom"})

    assert resp.status_code == 500
    assert resp.headers["X-Trace-ID"] == "trace-boom"
    assert resp.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "trace_id": "trace-boom",
    }
    assert "secret" not in resp.text
