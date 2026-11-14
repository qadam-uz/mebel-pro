# Deploy — `mebel-pro/deploy`

Docker Compose definitions and deploy scripts for running the whole stack.
Run `docker compose` commands **from this directory** (`deploy/`) — build
contexts are `../backend` and `../web`, and env is read from `deploy/.env`
(copy `.env.dev.example`).

Two **standalone** compose files — not an overlay pair; each is a complete stack on its own.
Don't try `-f compose.yaml -f compose.prod.yaml` (the old overlay shape we deliberately moved
away from). Keep service names and env-var names consistent across both so the `backend`/`web`
contract doesn't drift. The compose files, `ci.yml`, `deploy.sh`, and `seed-demo.sh` are all
heavily commented at the point of use — they are the source of truth for their own details;
this file carries only the map and the gotchas.

| File                | Stack |
| ------------------- | ----- |
| `compose.yaml`      | **Dev**, self-contained: `postgres` (17-alpine), `minio` + `createbuckets` one-shot, `backend` (source-mounted, autoreload, repo `docs/` bind-mounted, optional `cutting-engine` checkout — see gotchas), `web` (Vite dev server, HMR). Host ports: 5432, 9000/9001, 8000, 5173. |
| `compose.prod.yaml` | **Prod**, self-contained. No local data services — backend joins the external `infra-net` network and uses the shared `postgres` + `minio`. Built images; a **Caddy edge** is the only published service — `127.0.0.1:8080`, plain HTTP; the host nginx in front terminates TLS. Subdomain routing (apex / `app.*` / `workshop.*` / `admin.*`) is owned by [`docs/architecture.md`](../docs/architecture.md) → Topology; `Caddyfile` is the implementation. |
| `Caddyfile`         | Edge config, **baked into the edge image** (not bind-mounted — a mounted file's changes are invisible to `compose up`, stranding Caddy on stale config; a change ships via `up -d --build`). Plain HTTP (`auto_https off`), trusts the host nginx's `X-Forwarded-For` via the gateway. |
| `edge.Dockerfile`   | `FROM caddy:2.8-alpine` + `COPY Caddyfile`. The per-env value (`BASE_DOMAIN`) stays runtime env. |
| `nginx-host.conf.example` | **Reference copy** of the host-level nginx site (TLS via certbot, www → apex, proxy to `127.0.0.1:8080`). The live file is on the server, not deployed by this repo — keep the two in step by hand. Its header has the install order. |
| `scripts/deploy.sh` | What CI runs on the server over SSH: `git fetch` + `git reset --hard $DEPLOY_REF` (a hard reset — server-side edits are destroyed), re-exec the fresh script once, verify `deploy/.env` + `infra-net`, `compose -f compose.prod.yaml up -d --build --remove-orphans`, wait for the backend healthcheck, prune. Idempotent; runnable manually. |
| `seed-demo.sh`      | Deterministic fixed-credential demo world for the running **dev** stack. Credentials, catalog shape, and counts live in the script's own header; `--reset` wipes volumes (`down -v`) and re-seeds. Needs the **docker** backend container (execs `app.cli` inside it). |
| `seed-assets/`      | Catalog images the seed uploads; a missing file just skips that material's image. |
| `.env.dev.example` / `.env.prod.example` | The env contract — dev copy runs as-is; prod has every secret as `{{change-me}}`. |

> The `web` *container* has its own minimal nginx config (`../web/nginx.conf`, SPA history
> fallback) — a plain static server behind the edge, never touching TLS. Nothing in this
> repo's containers terminates TLS: the **host nginx** (shared with an unrelated project on
> the box) does, then hands plain HTTP to the Caddy edge on loopback.

## Commands

Day-to-day dev commands (`up --build`, data-services-only, logs, down) are in the root
`AGENTS.md` and `compose.yaml`'s own header. The ones documented nowhere else:

```bash
docker compose config                                # validate the merged dev config
docker compose -f compose.prod.yaml config           # validate prod
docker compose -f compose.prod.yaml up -d --build    # local prod smoke test (needs `docker network create infra-net` once)

# DB migrations inside the running backend container
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "..."
```

## CI / CD

`.github/workflows/ci.yml` (its header comment is the canonical description): three parallel
verify jobs run the per-directory gates owned by the root `AGENTS.md` (backend additionally
runs the infra-gated Postgres/MinIO suites; e2e boots its own stack), a docker-build smoke
job builds both images, and — **only on a green push to `main`** — the deploy job SSHes to
the VPS and runs `DEPLOY_REF=<sha> bash /opt/mebel-pro/deploy/scripts/deploy.sh` (fetch +
hard reset to the verified SHA; no registry). SSH secrets are listed in `ci.yml`'s header.

CI runs the compose data services with `--env-file .env.dev.example` **directly** — no `.env`
copy exists there — so the dev template must stay runnable as-is: a `{{placeholder}}` or a
commented-out required var added to it breaks `verify-backend` and `verify-e2e`, not just
local convenience.

## First-time setup on the VPS

One-time, in this order (repo at `/opt/mebel-pro`):

1. **Host nginx + certbot** are installed and own ports 80/443 (already true — the box's
   other project runs on them).
2. **`docker network create infra-net`**, with the shared `postgres` and `minio` containers
   attached to it. The backend resolves them by those bare names, so they must be **unique on
   `infra-net`** — no other project's container named or aliased `postgres`/`minio` may join
   it, or Docker resolves to whichever answers. Provision the DB/user and the MinIO key +
   bucket by hand (prod never auto-creates the bucket).
3. **DNS**: A records for the apex, `www`, `app`, `workshop`, `admin` → the box.
4. **`deploy/.env`** from `.env.prod.example` with **every** `{{change-me}}` filled (the
   backend refuses to boot in prod with `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, or
   `TELEGRAM_LOGIN_CODE_PEPPER` empty — a missed one crash-loops the first deploy, fail-safe).
5. **Certificate + nginx site**: follow `nginx-host.conf.example`'s header —
   `certbot certonly --nginx` for all five names, then install the file into
   `sites-available`/`sites-enabled`, `nginx -t`, reload.
6. **Deploy** (`deploy.sh`, or a push to `main`). `deploy.sh` refuses to run without
   `deploy/.env` and `infra-net`, and prints the fix for each.

## Conventions / gotchas

- Always `cd deploy/` before `docker compose …` (relative build contexts + `.env` discovery).
- **The dev stack is one shared instance per machine.** `compose.yaml` pins
  `name: mebel-pro`, so every checkout **and every git worktree** drives the same containers
  and volumes: containers keep bind mounts pointing at whichever tree created them
  (`--force-recreate` to re-point — see the verify skill), and `seed-demo.sh --reset` from
  any checkout wipes the shared volumes under a parallel session. Isolation needs
  `COMPOSE_PROJECT_NAME` + a ports override.
- `.env` is gitignored; the two `*.example` files are the contract. Keep them in sync with
  each other and with `backend/.env.{dev,prod}.example`.
- In prod, postgres/minio creds in `deploy/.env` are credentials **on the shared infra**, not
  something this stack provisions.
- The `backend` image runs `alembic upgrade head` on start; fresh DBs get the schema
  automatically. A failed migration crash-loops the container and `deploy.sh`'s healthcheck
  wait exits non-zero. The `Caddyfile`'s `lb_try_duration 30s` retry blocks exist **because**
  of that migrate-then-bind window — every deploy has seconds where the upstream refuses
  connections, and removing the retry turns each merge to `main` into user-facing 502s. Not
  tuning; don't strip it in a "simplify the Caddyfile" pass.
- Backend Python deps live in the image's **system interpreter** (no venv), so the dev source
  bind-mount can't shadow them — the tradeoff: a `pyproject.toml`/`uv.lock` change reaches
  the container **only via `docker compose up --build`**, a restart is not enough. Don't
  reintroduce the venv-in-a-named-volume shape: named volumes seed from the image only when
  empty, so every dep bump strands existing machines on a stale venv.
- The dev `web` container installs deps into a named volume at container start — a `pnpm add`
  done on the host is **invisible inside it** (Vite import-resolution errors) until
  `docker compose restart web` re-runs the install.
- **`cutting-engine` is the one dep the dev stack can override from a checkout.**
  `CUTTING_ENGINE_SRC` (default `../../cutting-engine`) is bind-mounted read-only with its
  `src/` first on `PYTHONPATH` and on `--reload-dir`, so engine edits apply on save; the
  wheel pinned in `backend/uv.lock` takes over when nothing is mounted and stays the single
  source of truth for what ships. **Dev only** — prod has no such mount, and a locally
  stamped `cutting-engine/…` version on a result reads the checkout, so don't compare local
  stamps against prod.
- New deployable service? Add it to both compose files; in prod give it `expose` (not
  `ports`), route it through the edge in the Caddyfile — and give it a **project-unique
  network alias** (the Caddyfile proxies to `mebel-web:80`, not `web:80`: when the edge sat
  on a shared network, a bare `web` once resolved to a *neighbour project's* container and
  every mebel-pro SPA served that project's frontend).
- Don't revert the prod edge to `image: caddy` + a bind-mounted Caddyfile — `compose up -d`
  won't recreate a container for a mounted file's content change, so Caddy silently keeps
  stale config. Keep it baked via `edge.Dockerfile`.
- **The edge publishes only `127.0.0.1:8080`, plain HTTP.** The host nginx owns 80/443 and
  TLS (certbot); never publish the edge on a public interface or re-enable Caddy's
  auto-HTTPS — it would fight nginx for the ports, and a public edge would let anyone forge
  `X-Forwarded-For` through the trusted gateway. The host nginx must **overwrite**
  `X-Forwarded-For` with `$remote_addr` (not append), and its `client_max_body_size` must stay
  ≥ the Caddyfile's 25 MB `request_body` cap — change them together.
- Pin image tags (`postgres:17-alpine`, `pgsty/minio:RELEASE.…`, `caddy:2.8-alpine`,
  `nginx:1.27-alpine`, `node:22-slim`); never `latest`.
- **MinIO images come from `pgsty/minio` + `pgsty/mc`** (the community fork). Upstream pulled
  `minio/minio` / `minio/mc` from Docker Hub and quay.io, so those tags no longer pull — a
  cached copy hides it locally, while CI and any fresh box fail with "pull access denied".
- **Postgres must be able to `CREATE EXTENSION pg_trgm`** — migration `e1a4c8b70d35` installs
  it for the catalog search's typo tier. `postgres:17-alpine` ships it (1.6), so the dev stack
  and the shared prod instance need nothing extra; a managed Postgres that withholds it leaves
  the search's last fallback returning no rows instead of erroring, but any *other* Postgres
  swap has to keep the contrib extensions available.
- The prod `default` subnet (`172.29.0.0/24`), `TRUSTED_PROXY_CIDRS`, and the Caddyfile's
  `trusted_proxies static 172.29.0.1/32` move **together**. The chain is client → host nginx
  (sets `X-Forwarded-For` to the client) → docker gateway `172.29.0.1` (the loopback port's
  source) → Caddy (keeps nginx's header, appends `172.29.0.1`) → backend, which takes the
  right-most hop outside the trusted CIDRs — the real client. The per-IP limits are inert
  without it (every request would key on the gateway). If the subnet collides on the VPS,
  change all three in one commit. `infra-net` must never be listed as trusted (shared with
  other projects).
