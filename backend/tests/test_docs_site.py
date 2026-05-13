"""Tests for the live-rendered docs site (`/docs`), its HTTP Basic guard, and
the relocated + protected OpenAPI UIs."""

from pathlib import Path

import pytest
from app.core.config import settings
from httpx import AsyncClient

AUTH = (settings.DOCS_AUTH_USERNAME, settings.DOCS_AUTH_PASSWORD)


@pytest.fixture
def docs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "docs"
    (root / "spec").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "index.md").write_text("# Home\n\nWelcome. See [the vision](spec/vision.md).\n")
    (root / "spec" / "vision.md").write_text(
        "---\ntitle: Product Vision\nstatus: stable\nupdated: 2026-05-11\norder: 10\n---\n\n"
        "# Vision\n\nBack to [scope](scope.md) and the [home page](../index.md).\n\n"
        "External: <https://example.com> stays put.\n\n"
        "## Why\n\nReasons.\n\n### Detail\n\nMore.\n\n## How\n\nSteps.\n\n"
        "```python\nprint('hi')\n```\n"
    )
    (root / "spec" / "scope.md").write_text("---\ntitle: Scope\norder: 20\n---\n\n# Scope\n")
    (root / "assets" / "diagram.txt").write_text("hello-asset")
    monkeypatch.setattr(settings, "DOCS_DIR", root)
    return root


# --- auth -------------------------------------------------------------------


async def test_docs_and_openapi_require_basic_auth(client: AsyncClient, docs_dir: Path) -> None:
    guarded = ("/docs", "/docs/spec/vision", "/docs/assets/diagram.txt", "/api-docs", "/api-redoc")
    for url in guarded:
        r = await client.get(url)
        assert r.status_code == 401, url
        assert "basic" in r.headers.get("www-authenticate", "").lower(), url
    # the OpenAPI schema is guarded too
    assert (await client.get("/api/v1/openapi.json")).status_code == 401
    # wrong credentials → still 401
    assert (await client.get("/docs", auth=("nope", "nope"))).status_code == 401
    # health endpoints stay open (used by container healthchecks)
    assert (await client.get("/api/v1/healthz")).status_code == 200


# --- the docs site ----------------------------------------------------------


async def test_docs_home_renders_index(client: AsyncClient, docs_dir: Path) -> None:
    resp = await client.get("/docs", auth=AUTH)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert "<h1" in body and "Home" in body
    # Sidebar lists the spec folder and its pages by frontmatter title.
    assert "Product Vision" in body
    assert ">Spec<" in body  # humanized folder label in the nav


async def test_markdown_page_link_rewriting_and_toc(client: AsyncClient, docs_dir: Path) -> None:
    resp = await client.get("/docs/spec/vision", auth=AUTH)
    assert resp.status_code == 200
    body = resp.text
    assert "Product Vision · Mebel Pro docs" in body
    assert "stable" in body and "updated 2026-05-11" in body
    # Sibling and parent .md links rewritten under /docs, with .md stripped.
    assert 'href="/docs/spec/scope"' in body
    assert 'href="/docs/index"' in body
    # External links untouched.
    assert 'href="https://example.com"' in body
    # Active nav item marked; code highlighting present.
    assert 'class="active"' in body
    assert ".highlight" in body
    # "On this page" rail built from the document's headings.
    assert 'class="toc"' in body and "On this page" in body
    assert 'href="#why"' in body and 'href="#how"' in body and 'href="#detail"' in body


async def test_extensionless_and_explicit_md_resolve_same(
    client: AsyncClient, docs_dir: Path
) -> None:
    a = await client.get("/docs/spec/scope", auth=AUTH)
    b = await client.get("/docs/spec/scope.md", auth=AUTH)
    assert a.status_code == b.status_code == 200
    assert "Scope" in a.text


async def test_folder_index_listing(client: AsyncClient, docs_dir: Path) -> None:
    resp = await client.get("/docs/spec", auth=AUTH)
    assert resp.status_code == 200
    assert 'href="/docs/spec/vision"' in resp.text
    assert "dir-index" in resp.text


async def test_non_markdown_files_served_raw(client: AsyncClient, docs_dir: Path) -> None:
    resp = await client.get("/docs/assets/diagram.txt", auth=AUTH)
    assert resp.status_code == 200
    assert resp.text == "hello-asset"


async def test_missing_doc_redirects_to_docs_home(client: AsyncClient, docs_dir: Path) -> None:
    # Stale or mistyped paths under /docs send the reader home rather than 404ing.
    resp = await client.get("/docs/spec/nope", auth=AUTH)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/docs"


async def test_path_traversal_redirects_to_docs_home(client: AsyncClient, docs_dir: Path) -> None:
    # %2e%2e decodes to ".." inside the path param; must not escape the docs root —
    # we redirect to the home instead of serving anything from outside it.
    resp = await client.get("/docs/%2e%2e/%2e%2e/secret", auth=AUTH)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/docs"


async def test_missing_docs_dir_yields_404(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DOCS_DIR", tmp_path / "does-not-exist")
    resp = await client.get("/docs", auth=AUTH)
    assert resp.status_code == 404
    assert "No <code>docs/</code>" in resp.text


# --- OpenAPI UIs ------------------------------------------------------------


async def test_openapi_docs_moved_to_api_docs(client: AsyncClient) -> None:
    # Swagger UI now lives at /api-docs; /docs is the documentation site.
    api_docs = await client.get("/api-docs", auth=AUTH)
    assert api_docs.status_code == 200
    assert "swagger-ui" in api_docs.text.lower()
    assert (await client.get("/api-redoc", auth=AUTH)).status_code == 200
    assert (await client.get("/api/v1/openapi.json", auth=AUTH)).status_code == 200
    # The old Swagger oauth2-redirect helper route is gone.
    assert (await client.get("/api-docs/oauth2-redirect", auth=AUTH)).status_code == 404
