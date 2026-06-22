"""Live-rendered documentation site.

Serves the repository's ``docs/`` Markdown tree as HTML, rendered on every
request — no build step, no static-site generator. Mounted at ``/docs``
(outside the ``/api`` prefix, behind the HTTP Basic guard) from
:data:`Settings.DOCS_DIR` (default ``<repo>/docs``), the single source of
truth. Edit a file under ``docs/`` and refresh.
"""

from __future__ import annotations

import posixpath
import re
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Annotated
from xml.etree.ElementTree import Element

import markdown
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from markdown.extensions import Extension
from markdown.extensions.toc import TocExtension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor

from app.core.config import settings

_STATIC_DIR = Path(__file__).parent / "docs_assets"
_DEFAULT_ORDER = 1000

# --- the documentation site -------------------------------------------------


@dataclass(frozen=True)
class _Site:
    """The documentation tree: where it lives and where it mounts."""

    lang: str  # "en"
    prefix: str  # URL mount, no trailing slash — "/docs"
    settings_attr: str  # Settings field naming the root dir
    dir_label: str  # how the tree is named in chrome/errors ("docs")

    def root(self) -> Path:
        root: Path = getattr(settings, self.settings_attr)
        return root.resolve()


EN_SITE = _Site(
    lang="en",
    prefix="/docs",
    settings_attr="DOCS_DIR",
    dir_label="docs",
)

# --- HTTP Basic auth (shared with the OpenAPI UIs — see app/main.py) ---------

AUTH_REALM = "Mebel Pro docs"
_basic = HTTPBasic(realm=AUTH_REALM)
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
    headers={"WWW-Authenticate": f'Basic realm="{AUTH_REALM}"'},
)


def require_docs_auth(credentials: Annotated[HTTPBasicCredentials, Depends(_basic)]) -> None:
    """HTTP Basic guard for the docs sites and the OpenAPI UIs (same credentials)."""
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.DOCS_AUTH_USERNAME.encode("utf-8")
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), settings.DOCS_AUTH_PASSWORD.encode("utf-8")
    )
    if not (user_ok and pass_ok):
        raise _UNAUTHORIZED


# --- frontmatter -------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_ORDER_RE = re.compile(r"^order:\s*(\d+)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.MULTILINE)
_UPDATED_RE = re.compile(r"^updated:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class _Meta:
    title: str | None = None
    order: int = _DEFAULT_ORDER
    status: str | None = None
    updated: str | None = None


def _split_frontmatter(text: str) -> tuple[_Meta, str]:
    """Return (parsed frontmatter, body). Frontmatter is a forgiving subset of YAML."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return _Meta(), text
    block, body = m.group(1), text[m.end() :]

    def _one(rx: re.Pattern[str]) -> str | None:
        found = rx.search(block)
        return (found.group(1).strip().strip("'\"") or None) if found else None

    order_m = _ORDER_RE.search(block)
    return (
        _Meta(
            title=_one(_TITLE_RE),
            order=int(order_m.group(1)) if order_m else _DEFAULT_ORDER,
            status=_one(_STATUS_RE),
            updated=_one(_UPDATED_RE),
        ),
        body,
    )


def _humanize(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("-", " ").replace("_", " ")).strip().title() or name


# --- filesystem helpers ------------------------------------------------------


def _resolve(site: _Site, rel: str) -> Path | None:
    """Resolve a request path inside the site's root, or ``None`` if it escapes."""
    root = site.root()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def _read_meta(path: Path) -> _Meta:
    try:
        meta, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return _Meta()
    return meta


def _is_hidden(path: Path) -> bool:
    return path.name.startswith((".", "_"))


# --- navigation tree ---------------------------------------------------------


@dataclass
class NavItem:
    title: str
    order: int
    url: str | None = None  # set for pages; None for folders
    rel: str = ""  # docs-relative path ("spec/vision.md" or "spec/decisions")
    children: list[NavItem] = field(default_factory=list)

    @property
    def is_folder(self) -> bool:
        return self.url is None


def build_nav(site: _Site) -> list[NavItem]:
    root = site.root()
    if not root.is_dir():
        return []

    def walk(directory: Path) -> list[NavItem]:
        is_root = directory == root
        items: list[NavItem] = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if _is_hidden(child):
                continue
            if child.is_dir():
                kids = walk(child)
                if not kids:
                    continue
                items.append(
                    NavItem(
                        title=_humanize(child.name),
                        order=min(k.order for k in kids),
                        rel=child.relative_to(root).as_posix(),
                        children=kids,
                    )
                )
            elif child.suffix == ".md":
                # README.md is never a nav entry. index.md is the Getting-Started
                # landing at the docs root and earns a sidebar entry there; the
                # docs skill forbids index.md anywhere else, but if one slips in
                # we still hide it (the folder's overview is enough).
                name = child.name.lower()
                if name == "readme.md":
                    continue
                if name == "index.md" and not is_root:
                    continue
                rel = child.relative_to(root).as_posix()
                meta = _read_meta(child)
                url = site.prefix if name == "index.md" else f"{site.prefix}/" + rel[: -len(".md")]
                items.append(
                    NavItem(
                        title=meta.title or _humanize(child.stem),
                        order=meta.order,
                        url=url,
                        rel=rel,
                    )
                )
        # Files first, then folders — so the canon at docs/ sits above ref/ in
        # the sidebar even when ref/'s deepest order overlaps with a canon file.
        items.sort(key=lambda i: (1 if i.is_folder else 0, i.order, i.title.lower()))
        return items

    return walk(root)


def _nav_contains(item: NavItem, cur_rel: str) -> bool:
    return bool(item.rel) and (cur_rel == item.rel or cur_rel.startswith(item.rel + "/"))


def _render_nav(items: list[NavItem], cur_rel: str) -> str:
    if not items:
        return ""
    out = ["<ul>"]
    for it in items:
        if it.is_folder:
            open_attr = " open" if _nav_contains(it, cur_rel) else ""
            out.append(
                f'<li class="nav-folder"><details{open_attr}>'
                f"<summary>{escape(it.title)}</summary>"
                f"{_render_nav(it.children, cur_rel)}"
                "</details></li>"
            )
        else:
            cls = ' class="active"' if it.rel == cur_rel else ""
            out.append(f'<li><a href="{escape(it.url or "#")}"{cls}>{escape(it.title)}</a></li>')
    out.append("</ul>")
    return "".join(out)


# --- markdown rendering ------------------------------------------------------


class _RelLinkTreeprocessor(Treeprocessor):
    """Rewrite in-repo Markdown links/images so they resolve under the site mount.

    ``[x](scope.md)`` on ``/docs/spec/vision`` becomes ``/docs/spec/scope``;
    image ``src``\\ s point at their byte route. Absolute URLs, anchors,
    ``mailto:``/``tel:``, and links that climb out of the tree are left
    untouched.
    """

    def __init__(self, md: markdown.Markdown, cur_rel: str, prefix: str) -> None:
        super().__init__(md)
        self._cur_dir = posixpath.dirname(cur_rel)
        self._prefix = prefix

    def run(self, root: Element) -> None:
        for el in root.iter():
            if el.tag == "a":
                href = el.get("href")
                if href is not None and (new := self._rewrite(href, strip_md=True)) is not None:
                    el.set("href", new)
            elif el.tag == "img":
                src = el.get("src")
                if src is not None and (new := self._rewrite(src, strip_md=False)) is not None:
                    el.set("src", new)

    def _rewrite(self, url: str, *, strip_md: bool) -> str | None:
        if not url or "://" in url or url.startswith(("#", "/", "mailto:", "tel:")):
            return None
        base, _, frag = url.partition("#")
        path, _, query = base.partition("?")
        if not path:
            return None
        resolved = posixpath.normpath(posixpath.join(self._cur_dir, path)).lstrip("./")
        if resolved == ".." or resolved.startswith("../"):
            return None  # escapes the docs root — leave the link untouched
        if strip_md and resolved.endswith(".md"):
            resolved = resolved[: -len(".md")]
        out = f"{self._prefix}/" + resolved
        if query:
            out += "?" + query
        if "#" in url:
            out += "#" + frag
        return out


class _RelLinkExtension(Extension):
    def __init__(self, cur_rel: str, prefix: str) -> None:
        super().__init__()
        self._cur_rel = cur_rel
        self._prefix = prefix

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(
            _RelLinkTreeprocessor(md, self._cur_rel, self._prefix), "docs_rellinks", 3
        )


class _MermaidPreprocessor(Preprocessor):
    """Lift fenced ``mermaid`` blocks out of Markdown processing entirely.

    A ```` ```mermaid ```` fence is replaced before ``fenced_code`` sees it
    with a raw ``<pre class="mermaid">…</pre>`` HTML block, which the Mermaid JS
    picks up on load and renders as inline SVG.
    """

    _FENCE_RE = re.compile(
        r"^( {0,3})(`{3,}|~{3,})[ \t]*mermaid[ \t]*\n(.*?)\n\1\2[ \t]*$",
        re.DOTALL | re.MULTILINE,
    )

    def run(self, lines: list[str]) -> list[str]:
        text = "\n".join(lines)

        def replace(m: re.Match[str]) -> str:
            source = m.group(3)
            return f'\n<pre class="mermaid">{escape(source, quote=False)}</pre>\n'

        return self._FENCE_RE.sub(replace, text).split("\n")


class _MermaidExtension(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        # Run *before* fenced_code (priority 25) so the mermaid block never enters
        # the code-block pipeline. md_in_html (priority 30) then leaves the raw
        # <pre class="mermaid"> alone.
        md.preprocessors.register(_MermaidPreprocessor(md), "docs_mermaid", 27)


def render_markdown(text: str, cur_rel: str, prefix: str) -> tuple[str, _Meta, str, str]:
    """Render a Markdown document → (title, frontmatter, HTML body, on-this-page HTML)."""
    meta, body = _split_frontmatter(text)
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "sane_lists",
            "attr_list",
            "def_list",
            "footnotes",
            "abbr",
            "md_in_html",
            TocExtension(permalink="#", toc_depth="2-4"),
            _RelLinkExtension(cur_rel, prefix),
            _MermaidExtension(),
        ],
        output_format="html",
        tab_length=2,
    )
    html = md.convert(body)
    toc_html = _toc_html(getattr(md, "toc_tokens", []))
    title = meta.title or _humanize(Path(cur_rel).stem or "Documentation")
    return title, meta, html, toc_html


def _toc_html(tokens: list[dict[str, object]]) -> str:
    """Build the right-rail "On this page" list from Markdown's TOC tokens (h2-h3).

    ``name`` from the TOC extension is already HTML-escaped heading text, so it
    goes in verbatim; ``id`` is a slug (escaped here only out of caution).
    """

    def render(items: list[dict[str, object]], depth: int) -> str:
        if not items or depth > 2:
            return ""
        parts: list[str] = []
        for it in items:
            tid, name = str(it.get("id", "")), str(it.get("name", ""))
            if not tid:
                continue
            children = it.get("children")
            kids = render(children if isinstance(children, list) else [], depth + 1)
            parts.append(f'<li><a href="#{escape(tid)}">{name}</a>{kids}</li>')
        return f"<ul>{''.join(parts)}</ul>" if parts else ""

    return render(tokens, 1)


# --- page shell --------------------------------------------------------------


@lru_cache(maxsize=1)
def _styles() -> str:
    return (_STATIC_DIR / "style.css").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _scripts() -> str:
    return (_STATIC_DIR / "docs.js").read_text(encoding="utf-8")


def _breadcrumbs(site: _Site, cur_rel: str) -> str:
    root_crumb = f'<a href="{site.prefix}">{escape(site.dir_label)}</a>'
    if not cur_rel:
        return ""
    parts = cur_rel.split("/")
    out = [root_crumb]
    acc = ""
    for i, part in enumerate(parts):
        acc = f"{acc}/{part}" if acc else part
        label = escape(_humanize(part[: -len(".md")] if part.endswith(".md") else part))
        out.append(
            label if i == len(parts) - 1 else f'<a href="{site.prefix}/{escape(acc)}">{label}</a>'
        )
    return ' <span style="opacity:.5">/</span> '.join(out)


def _meta_badges(meta: _Meta | None) -> str:
    if not meta or not (meta.status or meta.updated):
        return ""
    bits: list[str] = []
    if meta.status:
        bits.append(f'<span class="s-{escape(meta.status.lower())}">{escape(meta.status)}</span>')
    if meta.updated:
        bits.append(f"<span>updated {escape(meta.updated)}</span>")
    return f'<div class="doc-meta">{"".join(bits)}</div>'


_FONTS_HREF = (
    "https://fonts.googleapis.com/css2"
    "?family=Cinzel:wght@400;500;600&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap"
)


def _brand_html(site: _Site) -> str:
    return (
        f'<a class="brand" href="{site.prefix}">'
        '<span class="flank">&#8212;</span>Mebel&nbsp;Pro<span class="flank">&#8212;</span></a>'
    )


def _footer_html(site: _Site) -> str:
    return (
        f'<footer class="foot">Rendered live from <code>{escape(site.dir_label)}/</code> &#8212; '
        "no build step. Edit the file and refresh.</footer>"
    )


def _page(
    site: _Site,
    *,
    title: str,
    content: str,
    cur_rel: str,
    meta: _Meta | None = None,
    toc_html: str = "",
) -> str:
    nav_html = _render_nav(build_nav(site), cur_rel) or "<p class='nav-empty'>No docs found.</p>"
    crumbs = _breadcrumbs(site, cur_rel)
    crumbs_html = f'<nav class="crumbs" aria-label="Breadcrumb">{crumbs}</nav>' if crumbs else ""
    page_title = (
        "Mebel Pro · Documentation" if title == "Documentation" else f"{title} · Mebel Pro docs"
    )
    aside = (
        '<aside class="toc" aria-label="On this page">'
        '<div class="toc-h">On this page</div>'
        '<a class="toc-top" href="#">&#8593;&nbsp;Top</a>'
        f"{toc_html}</aside>"
        if toc_html
        else ""
    )
    shell_cls = "shell" if toc_html else "shell no-toc"
    mermaid_html = (
        '<script type="module">'
        'import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";'
        'mermaid.initialize({ startOnLoad: true, theme: "default", securityLevel: "loose" });'
        "</script>"
        if 'class="mermaid"' in content
        else ""
    )
    return f"""<!doctype html>
<html lang="{escape(site.lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{escape(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{_FONTS_HREF}">
<style>{_styles()}</style>
</head>
<body>
<input type="checkbox" id="nav-toggle" hidden>
<header class="topbar">
  <label class="burger" for="nav-toggle" aria-label="Toggle navigation">&#9776;</label>
  {_brand_html(site)}
  <a class="api-link" href="/api-docs">API&nbsp;reference&nbsp;&#8599;</a>
</header>
<div class="{shell_cls}">
  <nav class="side" aria-label="Documentation">{nav_html}</nav>
  <main>
    <div class="page">
      {crumbs_html}
      {_meta_badges(meta)}
      <article>{content}</article>
      {_footer_html(site)}
    </div>
  </main>
  {aside}
</div>
<script>{_scripts()}</script>
{mermaid_html}
</body>
</html>"""


# --- routes ------------------------------------------------------------------


def _render_doc_file(site: _Site, path: Path) -> HTMLResponse:
    rel = path.relative_to(site.root()).as_posix()
    title, meta, html, toc_html = render_markdown(
        path.read_text(encoding="utf-8"), rel, site.prefix
    )
    return HTMLResponse(
        _page(site, title=title, content=html, cur_rel=rel, meta=meta, toc_html=toc_html)
    )


def _dir_entry(site: _Site, label: str, path_suffix: str, mono: str) -> str:
    return (
        f'<li><a href="{site.prefix}/{escape(path_suffix)}">'
        f'<span class="t">{escape(label)}</span>'
        f'<span class="d">{escape(mono)}</span></a></li>'
    )


def _find_in_nav(items: list[NavItem], rel: str) -> NavItem | None:
    for it in items:
        if it.rel == rel:
            return it
        if it.is_folder and rel.startswith(it.rel + "/"):
            return _find_in_nav(it.children, rel)
    return None


def _render_folder(site: _Site, path: Path) -> HTMLResponse:
    # Render the folder index from the same NavItem tree the sidebar uses, so the
    # body's listing matches the sidebar's order (frontmatter `order`, then title)
    # rather than alphabetical-by-filename.
    root = site.root()
    rel = path.relative_to(root).as_posix() if path != root else ""
    nav_root = build_nav(site)
    items: list[NavItem] = nav_root if not rel else []
    if rel:
        folder = _find_in_nav(nav_root, rel)
        if folder and folder.is_folder:
            items = folder.children
    entries: list[str] = []
    for it in items:
        if it.is_folder:
            entries.append(_dir_entry(site, f"{it.title}/", it.rel, f"{it.rel}/"))
        else:
            path_suffix = it.rel[: -len(".md")] if it.rel.endswith(".md") else it.rel
            entries.append(_dir_entry(site, it.title, path_suffix, it.rel))
    title = _humanize(path.name) if rel else "Documentation"
    listing = "".join(entries) or "<li>Empty.</li>"
    body = f'<h1>{escape(title)}</h1><ul class="dir-index">{listing}</ul>'
    return HTMLResponse(_page(site, title=title, content=body, cur_rel=rel))


def _docs_home(site: _Site) -> HTMLResponse:
    root = site.root()
    if not root.is_dir():
        body = (
            f"<h1>Documentation</h1><p>No <code>{escape(site.dir_label)}/</code> directory at "
            f"<code>{escape(str(root))}</code>. Set "
            f"<code>{escape(site.settings_attr)}</code> to point at it.</p>"
        )
        return HTMLResponse(
            _page(site, title="Documentation", content=body, cur_rel=""), status_code=404
        )
    for name in ("index.md", "README.md"):
        f = root / name
        if f.is_file():
            return _render_doc_file(site, f)
    return _render_folder(site, root)


def _docs_page(site: _Site, doc_path: str) -> Response:
    doc_path = doc_path.strip("/")
    if not doc_path:
        return _docs_home(site)
    target = _resolve(site, doc_path)
    # Anything that doesn't resolve to a real file/folder — a stale link, a
    # typo, a `..`-escape — sends the reader to this site's home rather than
    # dead-ending.
    if target is None:
        return RedirectResponse(site.prefix, status_code=status.HTTP_302_FOUND)

    # An exact file: an asset, or an explicit `.md` link.
    if target.is_file():
        return _render_doc_file(site, target) if target.suffix == ".md" else FileResponse(target)

    # An extension-less Markdown page, or a folder (with an optional index file).
    md_file = target.with_suffix(".md")
    if md_file.is_file():
        return _render_doc_file(site, md_file)
    if target.is_dir():
        for name in ("index.md", "README.md"):
            f = target / name
            if f.is_file():
                return _render_doc_file(site, f)
        return _render_folder(site, target)

    return RedirectResponse(site.prefix, status_code=status.HTTP_302_FOUND)


def _make_router(site: _Site) -> APIRouter:
    """Build the home and catch-all routes for one docs site."""
    r = APIRouter(tags=["docs"], dependencies=[Depends(require_docs_auth)])

    @r.get(site.prefix, response_class=HTMLResponse, include_in_schema=False)
    async def docs_home() -> HTMLResponse:
        return _docs_home(site)

    @r.get(f"{site.prefix}/{{doc_path:path}}", response_class=HTMLResponse, include_in_schema=False)
    async def docs_page(doc_path: str) -> Response:
        return _docs_page(site, doc_path)

    return r


# One mount: the English docs at /docs (the single source of truth).
routers: list[APIRouter] = [_make_router(EN_SITE)]
