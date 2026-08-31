# Backend — `mebel-pro/backend`

FastAPI service. Async end-to-end: `asyncio` + `asyncpg` + SQLAlchemy 2.0 ORM,
migrations via Alembic, settings via `pydantic-settings`. Managed with **uv**.

## Toolchain

| Concern        | Tool                                                  |
| -------------- | ----------------------------------------------------- |
| Runtime        | Python **3.12** (`.python-version`)                   |
| Package / venv | **uv** (`pyproject.toml` + `uv.lock`)                 |
| Web framework  | FastAPI (`fastapi[standard]` → uvicorn, CLI)          |
| ORM            | SQLAlchemy 2.0 (async, typed `Mapped[...]`)           |
| DB driver      | asyncpg (Postgres); aiosqlite in tests                |
| Object store   | MinIO / S3-compatible, via **boto3** (`support` module) |
| Migrations     | Alembic (async env, autogenerate)                     |
| Settings       | pydantic-settings (`app/core/config.py`)              |
| Lint + format  | **ruff** (one tool for both)                          |
| Types          | **mypy** (`strict`)                                   |
| Tests          | pytest + pytest-asyncio + httpx (`ASGITransport`)     |
| Logging        | structlog                                             |

## Commands

Run everything through `uv run` (no manual venv activation needed).

```bash
uv sync                                  # install/refresh deps from uv.lock
uv add <pkg>            / uv add --dev <pkg>

uv run fastapi dev app/main.py            # dev server, autoreload, :8000

uv run pytest                             # full suite + coverage (single file first while iterating)

uv run ruff check . --fix                 # lint (autofix)
uv run ruff format .                       # format
uv run mypy app                            # type check

uv run alembic revision --autogenerate -m "add products"
uv run alembic upgrade head

uv run python -m app.cli                  # maintenance CLI: seed-platform-user · seed-error-record · backfill-image-variants
```

Run from `backend/` — `Settings` reads `.env` relative to the **CWD**, so a server started
from the repo root silently loads no env file (`TELEGRAM_LOGIN_DEV_MODE` reverts to `false` —
client sign-in then needs a real bot — and `DEBUG` to `false`). With `DEBUG=true`, `app.cli` shares stdout with SQLAlchemy echo
logs — when piping to `jq`, grep for the line starting with `{` first.

Pre-push gate (canonical copy in the root `AGENTS.md`): `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`.

## Layout

```
backend/
  pyproject.toml          # deps, ruff/mypy/pytest config (single source)
  uv.lock                 # pinned, committed
  alembic.ini             # script_location = app/migrations; URL injected at runtime
  app/
    main.py               # create_app(): trace middleware, error handlers, lifespan (starts the platform scheduler task)
    cli.py                # the maintenance CLI behind `uv run python -m app.cli`
    docs_site.py          # serves the repo's docs/ as HTML at /docs; exports `require_docs_auth`
    docs_assets/          # docs-site theme + scroll-spy JS
    core/                 # config.py (Settings) · db.py · errors.py (APIError + handlers) · logging.py (structlog)
                          #   trace.py (trace-ID middleware) · principal.py (AuthenticatedPrincipal, grants)
                          #   security.py (argon2) · telegram.py (Bot API client) · pdf.py + fonts/ (reportlab, DejaVu)
                          #   search_fold.py · material_label.py
    api/
      deps.py             # DI aliases: `Session` (function-scoped — commit completes before the response) + the auth
                          #   surface (get_current_principal, Principal, AccountReadyPrincipal, has_permission)
      router.py           # api_router; mounts module-owned routers
      routes/             # meta-only routes (health.py); no domain route implementations
    models/               # shared infra only: Base + mixins (base.py), shared enums (enums.py),
                          #   import_all_models() registry (__init__.py) — NO domain model files
    schemas/              # shared schema bases only (APIModel in common.py)
    modules/              # domain modules — access, catalog, client_portal, cutting, finance,
                          #   inventory, platform, sales, support, workshop
    services/             # retired layer-first package; keep empty, do not add domain files
    migrations/           # Alembic: env.py (async), script.py.mako, versions/
  tests/                  # conftest.py (in-memory sqlite + httpx client w/ get_session override),
                          #   factories.py, fixtures/, test_*.py
  Dockerfile              # multi-stage; compiles a pinned PackingSolver from source (sha256-checked);
                          #   uv installs deps into the system interpreter (no venv); non-root;
                          #   CMD runs `alembic upgrade head` then uvicorn
  .env.dev.example        # local non-Docker env — copy to `.env` (Compose uses deploy/.env instead)
  .env.prod.example       # same shape, secrets as {{change-me}}
```

File inventories drift — `ls` a directory before trusting any list here.

Subsystem pointers (all born module-first; each lives where the roster says):

- **Auth/authz** — bearer-token sessions, client sign-in through the Telegram bot
  (deep-link handshake + fallback code; budgets in `Settings.TELEGRAM_LOGIN_*`), login IP
  throttle, argon2 hashing; the `access` module owns it (auth.py, authz.py, sessions.py,
  login_throttle.py, client_ip.py, telegram_login.py, telegram_bot.py, telegram_routes.py)
  with the principal/permission types in `core/principal.py` and the DI surface in
  `api/deps.py`.
- **Telegram Bot API** — one thin httpx client in `core/telegram.py`, shared by the two
  modules that talk to the bot: `access` drives the sign-in conversation (webhook in,
  replies out), `support` delivers client order notifications (`telegram_delivery.py`,
  best-effort after the request transaction commits).
- **Files & images** — the `support` module owns object storage (files.py, files_routes.py)
  and sm/md image renditions (image_variants.py, Pillow); notifications live here too.
- **Cutting** — `cutting-engine` (pinned wheel; the dev compose stack can override it from
  a sibling checkout — see `deploy/AGENTS.md`) plus a PackingSolver binary built in the
  Dockerfile; cut-file import parsers under `modules/cutting/imports/`.
- **PDFs** — reportlab through `core/pdf.py` (bundled DejaVu fonts); cutting documents and
  finance statements render server-side and are never stored.

## Conventions

- **Async only.** Route handlers `async def`; DB access via the injected `AsyncSession`. Never call blocking I/O in a handler — offload with `anyio.to_thread` if unavoidable.
- **Sessions** come from the `Session` dependency in `app/api/deps.py`. `get_session` commits on success, rolls back on exception. Don't create engines/sessions ad hoc outside `app/core/db.py` (tests are the exception).
- **Models**: domain ORM classes live in `app/modules/<module>/models.py`
  using typed `Mapped[...]` / `mapped_column(...)` style (SQLAlchemy 2.0).
  Inherit `Base`; compose `UUIDPrimaryKey` / `Timestamped` mixins as needed.
  `app/models/base.py` and `app/models/enums.py` are shared
  infrastructure/value definitions. Layer-first domain model files under
  `app/models/` must not be reintroduced. Every new module-owned model class
  must be listed in `app/models/__init__.py`'s `import_all_models()` registry
  or Alembic won't see it.
- **Migrations**: never edit a DB by hand. `alembic revision --autogenerate -m "..."`, review the generated file (autogenerate misses some things — enum changes, server defaults, renames), then `alembic upgrade head`. Migrations are auto-formatted by ruff via a post-write hook.
- **Schemas vs models**: ORM objects never cross the API boundary — convert to a
  module-owned Pydantic schema (`app/modules/<module>/schemas.py`, or a named
  `*_schemas.py` split). Response schemas extend `APIModel`
  (`from_attributes=True`). `app/schemas/common.py` holds only shared schema
  bases/meta responses; layer-first domain schema files under `app/schemas/`
  must not be reintroduced.
- **Routes thin, modules fat**: domain route implementations live with their
  owning module as `app/modules/<module>/routes.py` or a named `*_routes.py`
  split. `app/api/router.py` only mounts routers; `app/api/routes/` is
  meta-only (`health.py`). Routes parse input, call module public APIs, and
  shape the response with module-owned schemas.
- **Module boundaries**: the backend is module-first — see the module map in
  [`docs/architecture.md`](../docs/architecture.md). A module exposes public
  use cases from `api.py` and public cross-module types from `contracts.py`.
  Code in one module calls another module only through `app.modules.<name>.api`
  or `app.modules.<name>.contracts`; it must not import another module's private
  `service.py` helpers or private `models.py` file. Cross-module behavior goes
  through `api.py`; same-transaction SQL composition may import an owning
  module's explicitly exported persistence classes from `contracts.py`.
- **No layer-first domain files**: `app/services/` is retired and kept empty.
  Domain files under `app/models/` or `app/schemas/` are also retired. Add
  domain code under `app/modules/<module>/`; the boundary test enforces this.
- **Config**: add new settings to `Settings` in `app/core/config.py` with a default following the repo's Convention-over-Configuration rule (non-security → leans dev, security → leans prod/locked; secrets have no default). Surface each in all four templates — `.env.dev.example` + `.env.prod.example` here and in `deploy/`. Read config via the `settings` singleton.
- **Errors**: raise `APIError(code, message, status_code=…, details=…)` from
  `app/core/errors.py` for client-facing failures — **not** `fastapi.HTTPException` (no
  module file uses it). Registered handlers shape every error into the envelope
  `{code, message, trace_id[, details]}`; let unexpected errors propagate — they 500 with a
  structured log and a record in the platform error monitor.
- **API prefix**: everything under `settings.API_V1_PREFIX` (`/api/v1`). `GET /api/v1/healthz` (liveness) and `/readyz` (DB-check) already exist.
- **Built-in pages**: `/docs` serves the project's `docs/` Markdown tree rendered live (`app/docs_site.py`; directory = `settings.DOCS_DIR`, default `<repo>/docs`; no build step — edit a file and refresh `:8000/docs`). The OpenAPI UIs moved to **`/api-docs`** (Swagger) and `/api-redoc` (ReDoc); the schema stays at `/api/v1/openapi.json`. **All four are behind HTTP Basic** with the same credentials — `settings.DOCS_AUTH_USERNAME` / `DOCS_AUTH_PASSWORD` (dev default `docs`/`docs`; change in any non-local deploy). Health endpoints (`/api/v1/healthz`, `/readyz`) stay open.
- **Lint/type clean** is required: `ruff check`, `ruff format --check`, `mypy app` must all pass. Prefer fixing over `# noqa` / `# type: ignore`; when you must suppress, scope it to the line with a reason.

## Database / object store / running locally

- Postgres is expected on `localhost:5432` (db `mebel`, user/pass `mebel/mebel`) and MinIO on `localhost:9000` (key/secret `mebel/mebel-secret`, bucket `mebel`) — `cd deploy && docker compose up -d postgres minio createbuckets` brings up both (the `createbuckets` one-shot creates the bucket and exits). A host Postgres already on :5432 shadows the container for every `localhost` DSN — see the root `AGENTS.md` traps.
- Then `uv run alembic upgrade head` and `uv run fastapi dev app/main.py`. The MinIO endpoint / access key / bucket come from `MINIO_*` in `.env` (defaults already point at the local MinIO).
- Tests need **no** database and **no** object store — they use in-memory SQLite and should stub/fake S3. Point `DATABASE_URL` at a real Postgres to run the suite against it. Two infra-gated suites are skipped by default and run in CI against the Compose data services: `POSTGRES_CONCURRENCY=1` (+ a throwaway Postgres `DATABASE_URL` — the test drops/recreates all tables) and `MINIO_CONTRACT=1` (needs the local MinIO). A gated test must keep an executing home in CI — see the **testing-practices** skill.

## Adding a feature (typical flow)

1. `app/modules/<module>/models.py` → model; add its module to
   `app/models/__init__.py`'s `import_all_models()` registry.
2. `uv run alembic revision --autogenerate -m "add <thing>"`; review; `alembic upgrade head`.
3. `app/modules/<module>/contracts.py` → explicitly export any persistence shapes
   another module must compose in SQL.
4. `app/modules/<module>/schemas.py` → request/response Pydantic models.
5. `app/modules/<module>/service.py` (or a smaller private file) → logic.
6. `app/modules/<module>/api.py` → public functions/classes exported to routes
   and other modules.
7. `app/modules/<module>/routes.py` (or a named `*_routes.py`) → router;
   register it in `app/api/router.py`.
8. `tests/test_<thing>.py` → cover the routes and meaningful module contracts.
9. `ruff check --fix . && ruff format . && mypy app && pytest`.
