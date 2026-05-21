"""Files module — upload/download with a stubbed S3 (no network)."""

import uuid
from typing import Any

import pytest
from app.core.security import hash_password
from app.models.enums import PrincipalType
from app.models.identity import Client, PlatformUser
from app.services import files as files_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


class _FakeS3:
    """In-memory stand-in for the boto3 S3 client — never touches the network."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.store[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        data = self.store[kwargs["Key"]]

        class _Body:
            def read(self) -> bytes:
                return data

        return {"Body": _Body()}


@pytest.fixture
def fake_s3(monkeypatch: pytest.MonkeyPatch) -> _FakeS3:
    fake = _FakeS3()
    monkeypatch.setattr(files_service, "get_s3_client", lambda: fake)
    return fake


async def _client_principal(db: AsyncSession) -> Client:
    c = Client(telegram_id=42, phone="+998900000000", first_name="Aziz")
    db.add(c)
    await db.commit()
    return c


async def _platform_user(db: AsyncSession) -> PlatformUser:
    u = PlatformUser(
        login="op",
        password_hash=hash_password("Passw0rd!"),
        full_name="Op",
        phone="+998900000001",
        force_password_change=False,
    )
    db.add(u)
    await db.commit()
    return u


async def test_upload_then_download(client: AsyncClient, db_session, auth_headers, fake_s3):
    c = await _client_principal(db_session)
    headers = await auth_headers(PrincipalType.CLIENT, c.id)

    up = await client.post(
        "/api/v1/files",
        headers=headers,
        files={"upload": ("photo.png", PNG, "image/png")},
        data={"entity_type": "material"},
    )
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["storage_status"] == "stored"
    assert body["size_bytes"] == len(PNG)
    file_id = body["id"]
    assert fake_s3.store  # bytes really landed in the fake store

    down = await client.get(f"/api/v1/files/{file_id}", headers=headers)
    assert down.status_code == 200
    assert down.content == PNG


async def test_upload_rejects_bad_content_type(client, db_session, auth_headers, fake_s3):
    c = await _client_principal(db_session)
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    up = await client.post(
        "/api/v1/files",
        headers=headers,
        files={"upload": ("x.exe", b"MZ\x00\x00", "application/octet-stream")},
        data={"entity_type": "material"},
    )
    assert up.status_code == 400
    assert up.json()["code"] == "bad_content_type"


async def test_upload_rejects_too_large(client, db_session, auth_headers, fake_s3, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "MAX_UPLOAD_BYTES", 4)
    c = await _client_principal(db_session)
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    up = await client.post(
        "/api/v1/files",
        headers=headers,
        files={"upload": ("photo.png", PNG, "image/png")},
        data={"entity_type": "material"},
    )
    assert up.status_code == 400
    assert up.json()["code"] == "file_too_large"


async def test_download_scope_blocks_other_principal(client, db_session, auth_headers, fake_s3):
    """A client cannot download another client's unattached file."""
    uploader = await _client_principal(db_session)
    other = Client(telegram_id=99, phone="+998900000099", first_name="Other")
    db_session.add(other)
    await db_session.commit()

    up_headers = await auth_headers(PrincipalType.CLIENT, uploader.id)
    up = await client.post(
        "/api/v1/files",
        headers=up_headers,
        files={"upload": ("p.png", PNG, "image/png")},
    )
    file_id = up.json()["id"]

    other_headers = await auth_headers(PrincipalType.CLIENT, other.id)
    down = await client.get(f"/api/v1/files/{file_id}", headers=other_headers)
    assert down.status_code == 403


async def test_platform_user_can_download_any_file(client, db_session, auth_headers, fake_s3):
    uploader = await _client_principal(db_session)
    op = await _platform_user(db_session)
    up_headers = await auth_headers(PrincipalType.CLIENT, uploader.id)
    up = await client.post(
        "/api/v1/files",
        headers=up_headers,
        files={"upload": ("p.png", PNG, "image/png")},
    )
    file_id = up.json()["id"]
    op_headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)
    down = await client.get(f"/api/v1/files/{file_id}", headers=op_headers)
    assert down.status_code == 200


async def test_attach_replace_detach_helpers(db_session, fake_s3):
    from app.core.principal import Principal

    c = await _client_principal(db_session)
    principal = Principal(type=PrincipalType.CLIENT, id=c.id, session_id=uuid.uuid4())

    f1 = await files_service.upload_file(
        db_session,
        principal=principal,
        data=PNG,
        original_name="a.png",
        content_type="image/png",
    )
    f2 = await files_service.upload_file(
        db_session,
        principal=principal,
        data=PNG,
        original_name="b.png",
        content_type="image/png",
    )
    material_id = uuid.uuid4()

    attached = await files_service.attach_file(db_session, f1.id, "material", material_id)
    assert attached.entity_type == "material"
    assert attached.entity_id == material_id

    replaced = await files_service.replace_file(
        db_session,
        old_file_id=f1.id,
        new_file_id=f2.id,
        entity_type="material",
        entity_id=material_id,
    )
    assert replaced.id == f2.id
    refreshed = await files_service.get_file(db_session, f1.id)
    assert refreshed.entity_type is None  # old detached

    detached = await files_service.detach_file(db_session, f2.id)
    assert detached.entity_type is None
