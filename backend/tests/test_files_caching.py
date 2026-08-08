"""Cache-revalidation contract for GET /api/v1/files/{id}.

A stored file is immutable per id, so the route serves a long-lived private
Cache-Control plus a strong ETag. Two things must never regress:

  * the headers themselves — without them every catalog thumbnail is
    re-downloaded on every navigation (a measured 2.6 MB per catalog page), and
  * the authorisation check must run *before* the 304 short-circuit, or an
    `If-None-Match` header becomes a way to confirm another tenant's file.
"""

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.support.api import InMemoryFileStorage
from app.modules.support.files import file_storage
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _owner_access_token(db: AsyncSession) -> str:
    _, _, owner = await seed_workshop_with_owner(db)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token


async def _upload(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/api/v1/files",
        headers=_auth(token),
        files={"upload": ("swatch.png", b"swatch-bytes", "image/png")},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


async def test_file_read_is_cacheable_and_revalidates_without_a_body(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    owner_token = await _owner_access_token(db_session)
    file_id = await _upload(client, owner_token)

    first = await client.get(f"/api/v1/files/{file_id}", headers=_auth(owner_token))
    etag = first.headers.get("etag", "")
    revalidated = await client.get(
        f"/api/v1/files/{file_id}",
        headers={**_auth(owner_token), "If-None-Match": etag},
    )

    assert first.status_code == 200
    assert first.content == b"swatch-bytes"
    assert first.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert etag, "a strong validator is required for revalidation to work at all"

    assert revalidated.status_code == 304
    assert revalidated.content == b""
    # The browser drops its copy without these on the 304, defeating the point.
    assert revalidated.headers["etag"] == etag
    assert revalidated.headers["cache-control"] == "private, max-age=31536000, immutable"


async def test_revalidation_does_not_bypass_the_permission_check(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A caller who may not read the file gets 403 — never 304.

    The 304 path skips the object-store read, so it is exactly the kind of
    shortcut a later refactor could lift above the authorisation call.
    """
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    owner_token = await _owner_access_token(db_session)
    file_id = await _upload(client, owner_token)

    owner_read = await client.get(f"/api/v1/files/{file_id}", headers=_auth(owner_token))
    etag = owner_read.headers["etag"]

    outsider = Client(phone="+998907777777", name="Outsider")
    db_session.add(outsider)
    await db_session.flush()
    outsider_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=outsider.id,
    )

    refused = await client.get(
        f"/api/v1/files/{file_id}",
        headers={**_auth(outsider_tokens.access_token), "If-None-Match": etag},
    )

    assert owner_read.status_code == 200
    assert refused.status_code == 403
