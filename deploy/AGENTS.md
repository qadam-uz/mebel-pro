# Deploy — `mebel-pro/deploy`

Docker Compose definitions and deploy scripts for running the whole stack.
Run `docker compose` commands **from this directory** (`deploy/`) — build
contexts are `../backend` and `../web`, and env is read from `deploy/.env`
(copy `.env.dev.example`).

Two **standalone** compose files — not an overlay pair. Each is a complete
stack on its own; pick whichever matches the environment.

| File                | Stack |
| ------------------- | ----- |
| `compose.yaml`      | **Dev**, self-contained. `postgres` (17-alpine, named volume), `minio` (S3-compatible, named volume) + `createbuckets` (one-shot `mc` that creates the bucket then exits), `backend` (source-mounted, `fastapi dev` autoreload, the repo's `docs/` bind-mounted at `/docs`), `web` (Vite dev server on `node:22-slim`, HMR). Ports published on the host: 5432, 9000/9001 (MinIO API + console), 8000, 5173. |
| `compose.prod.yaml` | **Prod**, self-contained. No local data services — backend joins the external `infra-net` Docker network and reaches the shared `postgres` + `minio` services by name. `backend` runs the built image (alembic upgrade on start), `web` is the built SPA served by nginx, and a **Caddy edge** (built from `edge.Dockerfile`, Caddyfile baked in) is the only published service (80 / 443 / 443-UDP; auto-HTTPS per host). Edge subdomain routing (apex/`app.*`/`workshop.*`/`admin.*`) is owned by [`docs/architecture.md`](../docs/architecture.md) → Topology; `Caddyfile` is the implementation. Includes per-service log rotation and resource caps. Bucket creation is **not** done here — provision the `MINIO_BUCKET` on the shared MinIO once via its console / `mc`. |
| `Caddyfile`         | Edge reverse-proxy config. **Baked into the edge image**, not mounted — a config change ships as a new image, so `up -d --build` recreates the edge deterministically (a bind-mounted file's contents are invisible to Compose and would strand Caddy on a stale in-memory config). |
| `edge.Dockerfile`   | Two lines: `FROM caddy:2.8-alpine` + `COPY Caddyfile`. Build context is this `deploy/` dir, scoped by `.dockerignore` to just the Caddyfile. Per-env values (`BASE_DOMAIN`, `ACME_EMAIL`) stay runtime env — Caddy substitutes them at load. |
| `scripts/deploy.sh` | What CI runs on the server over SSH: `git fetch` + `git reset --hard $DEPLOY_REF`, then **re-exec the freshly-checked-out script once** (so a fix to the deploy flow applies the same deploy, not the next) → verify `deploy/.env` and `infra-net` exist → `docker compose -f compose.prod.yaml up -d --build --remove-orphans` → wait for backend healthcheck → prune dangling images. Idempotent; runnable manually too. |
| `.env.dev.example`  | Dev env contract — ready-to-use defaults. Copy to `.env` for `compose.yaml`. |
| `.env.prod.example` | Prod env contract — same shape, secrets as `{{change-me}}`. Copy to `.env` for `compose.prod.yaml`. |

> The `web` *container* still has its own minimal nginx config (`../web/nginx.conf`, SPA history fallback) — it's purely a static file server behind the edge and never touches TLS. `deploy/Caddyfile` is the **edge** in front of everything; that's the one that terminates HTTPS and auto-renews the certificate.

## Why no overlay

`compose.prod.yaml` doesn't extend `compose.yaml` — the two are fully separate stacks. Reasons: prod doesn't run a local `postgres`/`minio` at all (the VPS provides them on `infra-net`), so an overlay would mostly be deletions; and the dev/prod commands are unambiguous when you read either file in isolation. Keep service names and env-var names consistent across both so the contract for `backend` and `web` doesn't drift.

## Commands

```bash
cp .env.dev.example .env                               # first time

# Dev — full stack with hot reload
docker compose up --build
docker compose up -d postgres minio createbuckets   # just the data services (e.g. to run backend/web on the host)
docker compose logs -f backend
docker compose down                                 # add -v to also drop volumes

# Validate the merged config
docker compose config
docker compose -f compose.prod.yaml config

# Prod — local smoke test of the prod stack (needs the `infra-net` network)
docker network create infra-net   # once, if missing
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml logs -f edge   # Caddy logs (cert provisioning, access)
docker compose -f compose.prod.yaml down

# DB migrations inside the running backend container
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "..."
```

Ports in dev: web `http://localhost:5173`, API `http://localhost:8000` (and via Vite's proxy at `:5173/api`), live docs `http://localhost:8000/docs`, Postgres `localhost:5432`, MinIO API `localhost:9000` + console `http://localhost:9001` (login `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`). In prod: only the Caddy edge, on 80 and 443 (HTTP/3 on 443/udp).

## CI / CD

`.github/workflows/ci.yml`:

1. **Verify** — runs on every PR and every push to `main`. Three parallel jobs (`verify-backend`, `verify-web`, `verify-e2e`) that run the per-directory check gates owned by the repo `AGENTS.md`. `verify-e2e` runs `pnpm typecheck` and the full Playwright suite; the Playwright config boots Postgres/MinIO via Compose, migrates the FastAPI backend, starts Vite, and tears the data services down afterward.
2. **Docker-build smoke** — builds the backend + web images so we know they still compile. No registry push.
3. **Deploy** — only on push to `main`, only after every other job is green. SSHes to the VPS and runs `DEPLOY_REF=<sha> bash /opt/mebel-pro/deploy/scripts/deploy.sh`. No registry, no rsync — the server does its own `git pull` + `docker compose up --build`.

GitHub config (Settings → Secrets and variables → Actions):

- `secrets.DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY` — required (the key is a passphrase-less PEM private key for a user that's in the `docker` group; default `mebel`).
- `secrets.DEPLOY_SSH_PORT` — optional (default `22`).

The repository must be cloned at `/opt/mebel-pro` on the VPS — see the bootstrap below.

## First-time setup on the VPS

The VPS is already provisioned for other projects: Docker Engine + Compose v2 are installed, the shared `postgres` and `minio` are running on the external `infra-net` Docker network, and the host is reachable on 80 + 443. What's left for mebel-pro is one-time, manual:

```bash
# As a user in the `docker` group (used by CI too — the SSH key in
# secrets.DEPLOY_SSH_KEY belongs to this user):
sudo mkdir -p /opt/mebel-pro && sudo chown "$USER" /opt/mebel-pro
git clone https://github.com/qadam-uz/mebel-pro.git /opt/mebel-pro

cp /opt/mebel-pro/deploy/.env.prod.example /opt/mebel-pro/deploy/.env
$EDITOR /opt/mebel-pro/deploy/.env
chmod 600 /opt/mebel-pro/deploy/.env
#   Set: POSTGRES_USER/PASSWORD/DB    — credentials of a DB on the shared Postgres
#                                        (provision the DB + user once via psql
#                                        on the infra-net postgres container)
#        MINIO_ACCESS_KEY_ID / MINIO_SECRET_ACCESS_KEY / MINIO_BUCKET
#                                      — an access key + bucket on the shared MinIO
#                                        (create them once via the MinIO console
#                                        or `mc`; the bucket isn't auto-created)
#        BACKEND_CORS_ORIGINS=[]       — same-origin via the edge
#        DOCS_AUTH_USERNAME / DOCS_AUTH_PASSWORD  — gates admin.<domain>/docs
#        BASE_DOMAIN=mebel-pro.uz · ACME_EMAIL=ops@…

# First deploy:
bash /opt/mebel-pro/deploy/scripts/deploy.sh
```

Pre-reqs that `deploy.sh` will refuse to run without: `deploy/.env` exists on the server, the `infra-net` Docker network exists. Also implicit: the host is reachable on 80 + 443 and DNS for the apex AND `app.*` / `workshop.*` / `admin.*` points at this box (so Caddy can obtain certificates).

`deploy/.env` is **not** committed and is **not** pulled by the deploy script — it lives only on the server. The first prod `up` provisions four Let's Encrypt certificates (apex + three subdomains); they live in the `caddy-data` volume and renew automatically — don't delete that volume.

## Conventions / gotchas

- Always `cd deploy/` before `docker compose …` (relative build contexts + `.env` discovery).
- The two compose files are **independent stacks**. Don't try `-f compose.yaml -f compose.prod.yaml` — that's the old overlay shape we deliberately moved away from.
- `.env` is gitignored; `.env.dev.example` / `.env.prod.example` are the contract. Keep them in sync with each other, and mirror backend-relevant vars with `backend/.env.dev.example` + `backend/.env.prod.example`.
- In prod, postgres/minio creds in `deploy/.env` are credentials **on the shared infra**, not credentials we provision. The DB and the MinIO access key must already exist on those shared services before deploy.
- The `backend` image runs `alembic upgrade head` on start (see `../backend/Dockerfile` CMD); fresh DBs get the schema automatically. A failed migration crash-loops the new container; `deploy.sh`'s healthcheck wait will fail and the script exits non-zero.
- The prod stack does **not** create the MinIO bucket — provision it once on the shared MinIO (console or `mc`) before the first deploy; the dev stack still has a `createbuckets` one-shot for local convenience.
- Don't bind-mount over the backend's `/app/.venv` (the `backend-venv` named volume preserves the image's venv when source is mounted in dev).
- New deployable service? Add it to both compose files; in prod give it `expose` (not `ports`) and route it through the edge in the Caddyfile.
- Don't revert the prod edge to `image: caddy + bind-mount Caddyfile`. `compose up -d` won't recreate a container for a bind-mounted file's content change, so Caddy would silently keep stale config after every Caddyfile edit. Keep it baked via `edge.Dockerfile`.
- Auto-HTTPS needs the edge reachable on **80 and 443** from the internet — don't remap those ports if you want Caddy to manage certificates.
- Pin image tags (`postgres:17-alpine`, `minio/minio:RELEASE.…`, `minio/mc:RELEASE.…`, `caddy:2.8-alpine`, `nginx:1.27-alpine`, `node:22-slim`) — don't use `latest`. MinIO uses date-stamped `RELEASE.<timestamp>Z` tags; bump them deliberately.
