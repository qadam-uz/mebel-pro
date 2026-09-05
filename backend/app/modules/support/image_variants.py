"""Downscaled renditions of an uploaded image.

A decor photo arrives as the operator's original — measured in production at
2160x2160 and 1.5 MB — and is then drawn into a 34 px swatch. A catalog page
holds fifty of them, so the browser was fetching ~2.2 MB to paint about 1700 px
of image. These renditions exist so each screen can ask for roughly what it
draws.

Two of them, because there are two jobs:

    sm  160 px  grids, list rows, swatches (34-40 px at up to 3x DPR)
    md  640 px  upload previews and detail panes (up to ~200 px at 3x DPR)

The original is always kept, untouched, and stays what a download returns — and
it is served in answer to a `?size=` only when it is *provably* no bigger than
the rendition asked for. An image nobody has rendered yet is not that case, so
it is rendered first (see `VariantChoice.needs_render`) rather than streamed.

WebP for both renditions: it carries alpha (the PNG swatches need it) and lands
well under JPEG at the same visual quality, which is the whole point on the
connections this app runs over.

Everything here is pure and synchronous — no I/O, no ORM. `resize_image` is CPU
work, so callers run it through `anyio.to_thread`; keeping it free of async makes
that possible and makes it directly testable.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import StrEnum

from PIL import Image, UnidentifiedImageError

# Pillow refuses images whose pixel count looks like a decompression bomb, but its
# default ceiling is generous. Ours is tighter: nothing legitimate in this catalog
# approaches it, and the check runs before any allocation.
MAX_SOURCE_PIXELS = 50_000_000

WEBP_QUALITY = 82
VARIANT_CONTENT_TYPE = "image/webp"

#: Uploads that have renditions at all. Everything else (PDFs) is served as
#: stored, whatever `?size=` says.
RENDERABLE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


class ImageVariant(StrEnum):
    """Rendition names. The value is what the API accepts as `?size=`."""

    SM = "sm"
    MD = "md"


#: Longest-edge budget per rendition. Aspect ratio is always preserved.
VARIANT_MAX_EDGE: dict[ImageVariant, int] = {
    ImageVariant.SM: 160,
    ImageVariant.MD: 640,
}


class ImageDecodeError(Exception):
    """The bytes are not an image Pillow can read, or are implausibly large."""


@dataclass(frozen=True)
class RenderedVariant:
    variant: ImageVariant
    content: bytes
    content_type: str


def variant_storage_key(original_key: str, variant: ImageVariant) -> str:
    """Where a rendition lives, derived from the original's key.

    Derived rather than stored so the two can never disagree, and so a key is
    computable without reading the row.
    """
    return f"{original_key}.{variant.value}.webp"


@dataclass(frozen=True)
class VariantChoice:
    """What a read serves, and whether the renditions still have to be made."""

    key: str
    content_type: str
    #: The file is an image nothing has ever rendered — `variant_keys` is NULL,
    #: not an empty map. Serving `key` here would stream the full original into
    #: a 34 px swatch, so the read path renders and stores the renditions once
    #: before answering, and this is how it knows to.
    needs_render: bool = False


def resolve_variant(
    *,
    requested: ImageVariant | None,
    variant_keys: dict[str, str] | None,
    original_key: str,
    original_content_type: str,
) -> VariantChoice:
    """The (storage key, content type) a read should actually serve.

    Three states, and the difference between the last two is the whole point:

    * the rendition exists — serve it;
    * the file has been *processed* and this rendition legitimately does not
      exist (a PDF, or an image whose longest edge already fits the budget) —
      serve the original, which `resize_image` guarantees is no larger than
      what was asked for;
    * the file has never been processed (`variant_keys IS NULL`) — say so. The
      original here can be any size at all, so serving it is the bug decision 21
      is about: the caller renders the renditions once and stores them instead.
    """
    if requested is None:
        return VariantChoice(original_key, original_content_type)
    if variant_keys is None:
        return VariantChoice(
            original_key,
            original_content_type,
            needs_render=original_content_type in RENDERABLE_CONTENT_TYPES,
        )
    key = variant_keys.get(requested.value)
    if key is None:
        return VariantChoice(original_key, original_content_type)
    return VariantChoice(key, VARIANT_CONTENT_TYPE)


def resize_image(content: bytes) -> list[RenderedVariant]:
    """Render every rendition that would actually be smaller than the source.

    A rendition wider than the original would be an upscale: more bytes for no
    more detail. Those are skipped, and the read path falls back to the original
    for them — which is correct, because the original already *is* small.

    Raises `ImageDecodeError` for bytes Pillow cannot read. Callers treat that as
    "no renditions", never as a failed upload: the original is stored either way,
    and a catalog image that declines to downscale is a cosmetic problem, not a
    lost file.
    """
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            if width * height > MAX_SOURCE_PIXELS:
                raise ImageDecodeError(f"image too large to process: {width}x{height}")
            longest = max(width, height)
            # Frames are decoded once and reused for both renditions. `load()`
            # forces the decode inside the context manager, so the file handle is
            # closed before the resizing loop begins.
            image.load()
            source = _flatten_to_rgba(image)
            rendered: list[RenderedVariant] = []
            for variant, max_edge in VARIANT_MAX_EDGE.items():
                if longest <= max_edge:
                    continue
                rendered.append(_render(source, variant, max_edge))
            return rendered
    except ImageDecodeError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageDecodeError(str(exc)) from exc


def _flatten_to_rgba(image: Image.Image) -> Image.Image:
    """One colour mode for the resize step.

    Palette images (`P`) resize badly — the interpolation runs over palette
    indices, not colours — so they are converted first. RGBA throughout keeps
    transparency, which the edge-tape swatches rely on.
    """
    if image.mode in {"RGBA", "RGB"}:
        return image
    return image.convert("RGBA")


def _render(source: Image.Image, variant: ImageVariant, max_edge: int) -> RenderedVariant:
    resized = source.copy()
    # `thumbnail` fits inside the box and preserves aspect ratio; LANCZOS is the
    # right filter for large downscales, where a cheaper one visibly aliases.
    resized.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    resized.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=4)
    return RenderedVariant(
        variant=variant,
        content=buffer.getvalue(),
        content_type=VARIANT_CONTENT_TYPE,
    )
