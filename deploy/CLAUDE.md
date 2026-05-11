# Deploy — `mebel-pro/deploy`

Docker Compose definitions for running the whole stack. Run `docker compose`
commands **from this directory** (`deploy/`) — build contexts are `../backend`
and `../web`, and env is read from `deploy/.env`.

Production deploys are automated: pushing to `main` runs
`.github/workflows/deploy.yml`, which rsyncs the repo to the server and runs the
prod compose stack there (see [CI deploy](#ci-deploy) below).

## Files

| File                     | Role |
| ------------------------ | ---- |
| `compose.yaml`           | Base: `postgres` (17-alpine, named volume), `minio` (S3-compatible object store, named volume, healthcheck) + `createbuckets` (one-shot `mc` that creates the bucket then exits), `backend` (builds `../backend`, migrates on start, healthcheck, talks to `postgres` + `minio`), `web` (builds `../web` → nginx serving the built SPA). |
| `compose.override.yaml`  | **Dev**, auto-loaded by plain `docker compose`. Publishes ports (5432, 9000/9001 MinIO API+console, 8000, 5173); backend source-mounted with `fastapi dev` autoreload (image venv kept via `backend-venv` volume); the repo's `../docs` is bind-mounted at `/docs` so the backend's live docs site (`:8000/docs`) reflects edits; `web` switched (`build: !reset null`) to a `node:22-slim` Vite dev server with HMR. |
| `compose.prod.yaml`      | **Prod** overlay. Adds a `caddy` **edge** (`Caddyfile`) — the only published service (80/443; auto-HTTPS when `SITE_ADDRESS` is a domain): `/api`, `/docs`, `/api-docs`, `/api-redoc` → `backend`, everything else → `web`. Bind-mounts `../docs` into `backend` so the live docs site works in prod too. Internal services (`postgres`, `minio`, `backend`, `web`) use `expose`, not `ports` — MinIO's console isn't published in prod. |
| `Caddyfile`              | Edge reverse-proxy config (mounted into the prod `edge` service). |
| `.env.example`           | Copy to `.env`. Postgres creds, `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` (also the backend's S3 access key/secret) + `S3_BUCKET`, `ENV`/`DEBUG`, `BACKEND_CORS_ORIGINS`, `DOCS_AUTH_USERNAME`/`DOCS_AUTH_PASSWORD` (HTTP Basic for `/docs` + `/api-docs`), `VITE_API_BASE_URL`, `SITE_ADDRESS`, `ACME_EMAIL`. |

> The `web` *container* still has its own minimal nginx config (`../web/nginx.conf`, SPA history fallback) — it's purely a static file server behind the edge and never touches TLS. `deploy/Caddyfile` is the **edge** in front of everything; it's the one that terminates HTTPS and auto-renews the certificate.

## Commands

```bash
cp .env.example .env                               # first time

# Dev — full stack with hot reload (base + override.yaml automatically)
docker compose up --build
docker compose up -d postgres minio createbuckets   # just the data services (e.g. to run backend/web on the host)
docker compose logs -f backend
docker compose down                                 # add -v to also drop the postgres volume

# Validate merged config
docker compose config
docker compose -f compose.yaml -f compose.prod.yaml config

# Prod — note: passing -f disables auto-loading of override.yaml
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml logs -f edge   # Caddy logs (cert provisioning, access)
docker compose -f compose.yaml -f compose.prod.yaml down

# DB migrations inside the running backend container
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "..."
```

Ports in dev: web `http://localhost:5173`, API `http://localhost:8000` (and via the Vite proxy at `:5173/api`), live docs `http://localhost:8000/docs`, Postgres `localhost:5432`, MinIO API `localhost:9000` + console `http://localhost:9001` (login with `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`). In prod: only the Caddy edge, on 80 and 443 (HTTP/3 on 443/udp).

## CI deploy

`.github/workflows/deploy.yml` runs on every push to `main` (or manual dispatch). It does **not** run any checks — verification (the per-directory check gates) is expected to have passed locally before you push. It just: rsync the repo to the server over SSH → `docker compose -f compose.yaml -f compose.prod.yaml up -d --build --remove-orphans` in `deploy/` → `docker image prune -f`.

GitHub config (Settings → Secrets and variables → Actions):

- `secrets.DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY` — required (the key is a passphrase-less PEM private key for a user that can run `docker`).
- `secrets.DEPLOY_SSH_PORT` — optional (default `22`).
- `secrets.DEPLOY_SSH_KNOWN_HOSTS` — optional but recommended (the server's SSH host key, e.g. `ssh-keyscan -H your.host`); without it the workflow trusts the key on first use.
- `vars.DEPLOY_PATH` — optional (default `/srv/mebel-pro`); the directory the repo is synced into.

One-time server bootstrap:

```bash
# On the server, as the deploy user:
sudo mkdir -p /srv/mebel-pro && sudo chown "$USER" /srv/mebel-pro     # or your DEPLOY_PATH
# (the workflow rsyncs the repo here; you don't need git on the server)
mkdir -p /srv/mebel-pro/deploy
cp /path/to/.env.example /srv/mebel-pro/deploy/.env                   # then edit it:
#   ENV=prod  DEBUG=false  POSTGRES_PASSWORD=…  MINIO_ROOT_PASSWORD=…  BACKEND_CORS_ORIGINS=…
#   DOCS_AUTH_USERNAME=…  DOCS_AUTH_PASSWORD=…   (guards /docs and /api-docs)
#   SITE_ADDRESS=mebel.example.com   ACME_EMAIL=ops@example.com
# Requirements: Docker Engine + Compose v2 plugin installed; ports 80 and 443
# open; DNS for SITE_ADDRESS pointed at this box (so Caddy can get a cert).
```

`deploy/.env` is **not** synced by the workflow (it's in the rsync excludes) — it lives only on the server. The first prod `up` provisions a Let's Encrypt certificate; it's stored in the `caddy-data` volume and renewed automatically, so don't delete that volume.

## Conventions / gotchas

- Always `cd deploy/` before `docker compose …` (relative build contexts + `.env` discovery).
- `compose.override.yaml` is for dev only and is picked up **automatically** — but *only* when you don't pass `-f`. Any `-f` flag means you must list every file explicitly.
- `.env` is gitignored; `.env.example` is the contract — keep them in sync, and mirror backend-relevant vars with `backend/.env.example`.
- The `backend` image runs `alembic upgrade head` on container start (see `../backend/Dockerfile` CMD); fresh DBs get the schema automatically. The `createbuckets` one-shot does the equivalent for MinIO (creates `S3_BUCKET` if missing, then exits — a normal `Exited (0)` is expected).
- MinIO's root user/password (`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`) double as the backend's `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` — the base compose wires them through. Set them once in `deploy/.env`; mirror the *non-secret* S3 bits (`S3_*`) in `backend/.env.example` for host-mode runs.
- Don't bind-mount over the backend's `/app/.venv` (the `backend-venv` named volume preserves the image's venv when source is mounted in dev).
- New deployable service? Add it to `compose.yaml`; give it `expose` (not `ports`) and route it through the edge in `compose.prod.yaml` + `Caddyfile`.
- Auto-HTTPS needs the edge reachable on **80 and 443** from the internet — don't remap those ports if you want Caddy to manage certificates.
- Pin image tags (`postgres:17-alpine`, `minio/minio:RELEASE.…`, `minio/mc:RELEASE.…`, `caddy:2.8-alpine`, `nginx:1.27-alpine`, `node:22-slim`) — don't use `latest`. MinIO uses date-stamped `RELEASE.<timestamp>Z` tags; bump them deliberately.
