"""Rendition generation and the size-aware read path.

The measured problem these exist for: a production catalog original is 2160x2160
and 1.5 MB, drawn into a 34 px swatch, fifty to a page — ~2.2 MB of transfer to
paint about 1700 px of image.
"""

import io

import pytest
from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.support.api import InMemoryFileStorage
from app.modules.support.files import file_storage
from app.modules.support.image_variants import (
    VARIANT_CONTENT_TYPE,
    ImageDecodeError,
    ImageVariant,
    resize_image,
    resolve_variant,
    variant_storage_key,
)
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def png_bytes(width: int, height: int, *, mode: str = "RGBA") -> bytes:
    image = Image.new(mode, (width, height), (120, 100, 90, 255)[: len(mode)])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_large_image_yields_both_renditions_far_smaller_than_the_source() -> None:
    source = png_bytes(2160, 2160)

    rendered = resize_image(source)

    by_name = {item.variant: item for item in rendered}
    assert set(by_name) == {ImageVariant.SM, ImageVariant.MD}
    for item in rendered:
        assert item.content_type == VARIANT_CONTENT_TYPE
        assert len(item.content) < len(source)
    assert Image.open(io.BytesIO(by_name[ImageVariant.SM].content)).size == (160, 160)
    assert Image.open(io.BytesIO(by_name[ImageVariant.MD].content)).size == (640, 640)


def test_aspect_ratio_survives_the_downscale() -> None:
    rendered = resize_image(png_bytes(2000, 1000))

    sizes = {item.variant: Image.open(io.BytesIO(item.content)).size for item in rendered}
    assert sizes[ImageVariant.SM] == (160, 80)
    assert sizes[ImageVariant.MD] == (640, 320)


def test_an_image_smaller_than_a_rendition_is_left_alone() -> None:
    """No upscales: more bytes for no more detail, and the original already fits."""
    rendered = resize_image(png_bytes(120, 120))

    assert rendered == []


def test_only_the_renditions_bigger_than_the_source_are_skipped() -> None:
    # 400 px sits between the two budgets: sm downscales, md would upscale.
    rendered = resize_image(png_bytes(400, 400))

    assert [item.variant for item in rendered] == [ImageVariant.SM]


def test_palette_images_are_converted_before_resizing() -> None:
    """`P`-mode interpolates palette indices, not colours — it must be converted."""
    palette = Image.new("P", (900, 900))
    buffer = io.BytesIO()
    palette.save(buffer, format="PNG")

    rendered = resize_image(buffer.getvalue())

    assert {item.variant for item in rendered} == {ImageVariant.SM, ImageVariant.MD}


def test_undecodable_bytes_raise_a_decode_error() -> None:
    with pytest.raises(ImageDecodeError):
        resize_image(b"this is not an image")


def test_variant_key_hangs_off_the_original_key() -> None:
    assert (
        variant_storage_key("uploads/abc/photo.png", ImageVariant.SM)
        == "uploads/abc/photo.png.sm.webp"
    )


class TestResolveVariant:
    """What a read actually serves, given what exists."""

    original = ("uploads/a/x.png", "image/png")

    def test_no_size_requested_serves_the_original(self) -> None:
        assert (
            resolve_variant(
                requested=None,
                variant_keys={"sm": "uploads/a/x.png.sm.webp"},
                original_key=self.original[0],
                original_content_type=self.original[1],
            )
            == self.original
        )

    def test_a_requested_rendition_that_exists_is_served(self) -> None:
        assert resolve_variant(
            requested=ImageVariant.SM,
            variant_keys={"sm": "uploads/a/x.png.sm.webp"},
            original_key=self.original[0],
            original_content_type=self.original[1],
        ) == ("uploads/a/x.png.sm.webp", VARIANT_CONTENT_TYPE)

    @pytest.mark.parametrize("variant_keys", [None, {}, {"md": "uploads/a/x.png.md.webp"}])
    def test_a_missing_rendition_falls_back_to_the_original(
        self, variant_keys: dict[str, str] | None
    ) -> None:
        """This fallback is why `?size=sm` is safe to ship before any backfill.

        It also covers PDFs and images too small to have renditions.
        """
        assert (
            resolve_variant(
                requested=ImageVariant.SM,
                variant_keys=variant_keys,
                original_key=self.original[0],
                original_content_type=self.original[1],
            )
            == self.original
        )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _owner_token(db: AsyncSession) -> str:
    _, _, owner = await seed_workshop_with_owner(db)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token


async def _upload_large_png(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/api/v1/files",
        headers=_auth(token),
        files={"upload": ("swatch.png", png_bytes(2160, 2160), "image/png")},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


async def test_upload_stores_renditions_and_the_route_serves_the_small_one(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    token = await _owner_token(db_session)
    file_id = await _upload_large_png(client, token)

    original = await client.get(f"/api/v1/files/{file_id}", headers=_auth(token))
    small = await client.get(f"/api/v1/files/{file_id}?size=sm", headers=_auth(token))
    medium = await client.get(f"/api/v1/files/{file_id}?size=md", headers=_auth(token))

    assert original.headers["content-type"].startswith("image/png")
    assert small.headers["content-type"].startswith(VARIANT_CONTENT_TYPE)
    assert medium.headers["content-type"].startswith(VARIANT_CONTENT_TYPE)
    # The whole point: the rendition a swatch asks for is a fraction of the source.
    assert len(small.content) < len(medium.content) < len(original.content)
    assert Image.open(io.BytesIO(small.content)).size == (160, 160)


async def test_the_etag_differs_per_size(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same URL path, different bytes per `size` — so the validator must differ.

    A shared ETag would let a cache answer a `?size=sm` request with the 1.5 MB
    original, or worse, hand the thumbnail to a caller that asked for the full
    image. This is the one correctness risk the whole feature carries.
    """
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    token = await _owner_token(db_session)
    file_id = await _upload_large_png(client, token)

    etags = {
        size: (
            await client.get(
                f"/api/v1/files/{file_id}" + (f"?size={size}" if size else ""),
                headers=_auth(token),
            )
        ).headers["etag"]
        for size in ("", "sm", "md")
    }

    assert len(set(etags.values())) == 3, etags

    # And revalidation is per-size: the small ETag must not satisfy a full read.
    full = await client.get(
        f"/api/v1/files/{file_id}",
        headers={**_auth(token), "If-None-Match": etags["sm"]},
    )
    same_size = await client.get(
        f"/api/v1/files/{file_id}?size=sm",
        headers={**_auth(token), "If-None-Match": etags["sm"]},
    )
    assert full.status_code == 200
    assert same_size.status_code == 304


async def test_a_rejected_reader_cannot_use_size_to_reach_a_rendition(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """`?size=` must not become a second, unguarded path to the bytes."""
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    token = await _owner_token(db_session)
    file_id = await _upload_large_png(client, token)

    outsider = Client(phone="+998907777777", name="Outsider")
    db_session.add(outsider)
    await db_session.flush()
    outsider_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=outsider.id,
    )

    refused = await client.get(
        f"/api/v1/files/{file_id}?size=sm",
        headers=_auth(outsider_tokens.access_token),
    )

    assert refused.status_code == 403


async def test_a_pdf_upload_gets_no_renditions_and_still_serves(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    token = await _owner_token(db_session)
    uploaded = await client.post(
        "/api/v1/files",
        headers=_auth(token),
        files={"upload": ("receipt.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    file_id = uploaded.json()["id"]

    # Asking for a rendition of a PDF returns the PDF, not an error.
    asked_for_small = await client.get(f"/api/v1/files/{file_id}?size=sm", headers=_auth(token))

    assert uploaded.status_code == 200
    # Storage keys stay server-side; the response deliberately exposes none.
    assert "variant_keys" not in uploaded.json()
    assert asked_for_small.status_code == 200
    assert asked_for_small.headers["content-type"].startswith("application/pdf")
    assert asked_for_small.content == b"%PDF-1.4 fake"


async def test_an_unreadable_image_still_uploads(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Rendition generation is best effort — it must never fail the upload.

    Otherwise one image Pillow dislikes would stop an operator attaching a photo
    at all, trading a size problem for a broken feature.
    """
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    token = await _owner_token(db_session)

    uploaded = await client.post(
        "/api/v1/files",
        headers=_auth(token),
        files={"upload": ("broken.png", b"not really a png", "image/png")},
    )

    assert uploaded.status_code == 200
    file_id = uploaded.json()["id"]
    served = await client.get(f"/api/v1/files/{file_id}?size=sm", headers=_auth(token))
    assert served.status_code == 200
    # No rendition was made, so the read falls back to exactly what was stored.
    assert served.content == b"not really a png"
