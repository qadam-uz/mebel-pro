# Deploy — `mebel-pro/deploy`

Docker Compose definitions and deploy scripts for running the whole stack.
Run `docker compose` commands **from this directory** (`deploy/`) — dev build
contexts are `../backend` and `../web`, and env is read from `deploy/.env`
(copy `.env.dev.example`; on the server, `.env.prod.example`).

Two **standalone** compose files — not an overlay pair; each is a complete stack on its own.
Don't try `-f compose.yaml -f compose.prod.yaml` (the old overlay shape we deliberately moved
away from). Keep service names and env-var names consistent across both so the `backend`/`web`
contract doesn't drift. The compose files, `ci.yml`, `deploy.sh`, and `seed-demo.sh` are all
heavily commented at the point of use — they are the source of truth for their own details;
this file carries only the map and the gotchas.

| File                | Stack |
| ------------------- | ----- |
| `compose.yaml`      | **Dev**, self-contained: `postgres` (17-alpine), `minio` + `createbuckets` one-shot, `backend` (source-mounted, autoreload, repo `docs/` bind-mounted, optional `cutting-engine` checkout — see gotchas), `web` (Vite dev server, HMR). Host ports: 5432, 9000/9001, 8000, 5173. |
| `compose.prod.yaml` | **Prod**, self-contained: its own `postgres` + `minio` (named volumes `prod-postgres-data` / `prod-minio-data`, no published ports) and a `createbuckets` one-shot behind the `setup` profile; `backend` / `web` / `edge` are **prebuilt GHCR images** — backend and web pinned by `IMAGE_TAG` (the deployed commit SHA), the edge by `EDGE_IMAGE_TAG` (its content tag) — no `build:` anywhere, the server never builds. A **Caddy edge** is the only published service — `127.0.0.1:8080`, plain HTTP; the host nginx in front terminates TLS. Subdomain routing (apex / `my.*` / `workshop.*` / `admin.*`) is owned by [`docs/architecture.md`](../docs/architecture.md) → Topology; `Caddyfile` is the implementation. |
| `Caddyfile`         | Edge config, **baked into the edge image** (not bind-mounted — a mounted file's changes are invisible to `compose up`, stranding Caddy on stale config; a change ships as a new edge image under a new content tag). Plain HTTP (`auto_https off`), trusts the host nginx's `X-Forwarded-For` via the gateway. Every upstream goes through the `(to_backend)` / `(to_web)` snippets, which carry the deploy retry window. |
| `edge.Dockerfile`   | `FROM caddy:2.8-alpine` + `COPY Caddyfile`. The per-env value (`BASE_DOMAIN`) stays runtime env. |
| `scripts/edge-tag.sh` | Prints the edge image's **content tag** (`edge-<16 hex>`, a sha256 over `edge.Dockerfile`, `Caddyfile`, `.dockerignore`) — the only place the formula lives; CI tags the image with it and `deploy.sh` pins it as `EDGE_IMAGE_TAG`. Same bytes, same tag, so a deploy that doesn't touch the edge leaves its container running. A file the edge build starts reading must join its input list. |
| `nginx-host.conf.example` | **Reference copy** of the host-level nginx site (TLS via certbot, www → apex, proxy to `127.0.0.1:8080`). The live file is on the server, not deployed by this repo — keep the two in step by hand. Its header has the install order. |
| `scripts/deploy.sh` | What CI runs on the server over SSH: `git fetch` + `git reset --hard $DEPLOY_REF` (a hard reset — server-side edits are destroyed), re-exec the fresh script once, verify `deploy/.env` (exists, no `{{change-me}}` left, `compose config` resolves), pin `IMAGE_TAG` (= HEAD) and `EDGE_IMAGE_TAG` in it, `pull backend web edge` (never the data-service images), data services `up --wait`, `createbuckets`, migrations in a one-off container (the old backend keeps serving; `SKIP_MIGRATIONS=1` skips them for a rollback), `up -d --wait --remove-orphans`, Telegram webhook (non-fatal), prune mebel-pro's unused images. Idempotent; runnable manually. |
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
IMAGE_TAG=x EDGE_IMAGE_TAG=x docker compose -f compose.prod.yaml config -q   # validate prod (both tags required)
bash scripts/edge-tag.sh                             # the edge's content tag for this checkout

# DB migrations inside the running dev backend container
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "..."

# Prod, on the server (IMAGE_TAG / EDGE_IMAGE_TAG come from deploy/.env — deploy.sh writes them)
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs -f backend
docker compose -f compose.prod.yaml run --rm --no-deps backend alembic current        # where the DB is
docker compose -f compose.prod.yaml run --rm --no-deps backend alembic upgrade head   # migrate by hand
docker compose -f compose.prod.yaml pull postgres && docker compose -f compose.prod.yaml up -d postgres   # roll postgres:17-alpine forward (see gotchas)

# Local prod smoke test against published images. ALWAYS under its own project
# name: both files say `name: mebel-pro`, so without -p this drives (and `down -v`
# wipes) the dev stack. Needs an env file prod can boot with (the prod template,
# dummy secrets, BASE_DOMAIN=lvh.me), port 8080 and subnet 172.29.0.0/24 free,
# and a main commit whose images CI published (check it out, so the edge tag
# matches) — or images built locally with exactly those tags.
prodtest() { IMAGE_TAG=<sha> EDGE_IMAGE_TAG=$(bash scripts/edge-tag.sh) docker compose -p mebel-prodtest -f compose.prod.yaml --env-file smoke.env "$@"; }
prodtest up -d --wait postgres minio && prodtest run --rm --no-deps createbuckets
prodtest run --rm --no-deps backend alembic upgrade head && prodtest up -d --wait
curl -H 'Host: my.lvh.me' http://127.0.0.1:8080/api/v1/readyz
prodtest down -v                                     # only ever with -p mebel-prodtest
```

## CI / CD

`.github/workflows/ci.yml` (its header comment is the canonical description): three parallel
verify jobs run the per-directory gates owned by the root `AGENTS.md` (backend additionally
runs the infra-gated Postgres/MinIO suites; e2e boots its own stack). The `images` job then
builds backend, web and edge **once** — on a PR it stops there (a build smoke test); on
`main` (a push, or **Run workflow** on `main`) it also pushes them to GHCR as
`ghcr.io/qadam-uz/mebel-pro-{backend,web}:<full sha>` and
`ghcr.io/qadam-uz/mebel-pro-edge:<content tag>`. Tags are **immutable**: an image GHCR
already has under its tag is neither rebuilt nor re-pushed (a re-push repoints the tag at a
new digest, and compose would then recreate that container for nothing). Last, on `main`
only, the deploy job SSHes to the VPS and runs
`DEPLOY_REF=<sha> bash /opt/mebel-pro/deploy/scripts/deploy.sh`, which pulls exactly those
images — so only commits whose CI went green on `main` are deployable, and **Run workflow**
on `main` is a quick redeploy. The SSH secrets (incl. the optional host-key fingerprint and
how to read it) are listed in `ci.yml`'s header; they live in the `production` environment.

CI runs the compose data services with `--env-file .env.dev.example` **directly** — no `.env`
copy exists there — so the dev template must stay runnable as-is: a `{{placeholder}}` or a
commented-out required var added to it breaks `verify-backend` and `verify-e2e`, not just
local convenience.

## First-time setup on the VPS

One-time, in this order (repo at `/opt/mebel-pro`). Postgres and MinIO come up with the
stack itself — there is no shared infra to provision.

1. **Host nginx + certbot** are installed and own ports 80/443 (already true — the box's
   other project runs on them).
2. **Swap**, if the box has none (`swapon --show`) — the RAM is small and shared with
   another production app, so give the kernel somewhere to go before the OOM killer picks a
   database: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap
   /swapfile && sudo swapon /swapfile`, plus `/swapfile none swap sw 0 0` in `/etc/fstab`.
3. **A `deploy` user in the `docker` group** (`sudo adduser --disabled-password deploy &&
   sudo usermod -aG docker deploy`), with CI's public key in its
   `~/.ssh/authorized_keys`, and `/opt/mebel-pro` created and owned by it.
4. **Clone** as that user: `git clone https://github.com/qadam-uz/mebel-pro.git
   /opt/mebel-pro` — the repo is public, so no deploy key.
5. **`deploy/.env`** from `.env.prod.example`, `chmod 600`, with **every** `{{change-me}}`
   filled (`openssl rand -hex 32` for secrets). Check from `deploy/` with
   `grep -E '^[[:space:]]*[^#[:space:]].*\{\{change-me\}\}' .env | cut -d= -f1` — no output
   means done; it lists the unfilled KEYs only, never values. Not a plain
   `grep change-me .env`: the template's header comment mentions the placeholder, so that
   always matches. `deploy.sh` runs the same check and refuses to start on a hit — a missed
   `POSTGRES_PASSWORD` would otherwise become the database's permanent password (the
   postgres/minio values initialise this stack's own data services on first start). An
   *empty* `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` or `TELEGRAM_LOGIN_CODE_PEPPER`
   is caught later: the backend refuses to boot in prod, failing the deploy's health wait;
   a missing or empty required value (e.g. `DOCS_AUTH_PASSWORD`) makes `deploy.sh`'s
   `compose config` check stop it first. Leave `IMAGE_TAG` / `EDGE_IMAGE_TAG` out —
   `deploy.sh` writes them.
6. **DNS**: A records for the apex, `www`, `my`, `workshop`, `admin` → the box.
7. **Certificate + nginx site**: follow `nginx-host.conf.example`'s header —
   `certbot certonly --nginx` for all five names **with `--deploy-hook "systemctl reload
   nginx"`** (renewed certs only take effect on reload), then install the file into
   `sites-available`/`sites-enabled`, `nginx -t`, reload.
8. **GHCR packages public**, so the server pulls without credentials. A package a workflow
   creates with its `GITHUB_TOKEN` "inherits the visibility and permissions model of the
   repository where the workflow is run" ([GitHub Docs](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions)),
   so this public repo's first `main` run should create all three **public** — but other
   GitHub pages say a new package starts private, so check once after that run: the org's
   **Packages** tab shows each package's visibility, and an anonymous
   `docker pull ghcr.io/qadam-uz/mebel-pro-web:<sha>` (and the same for `-backend`, and
   `-edge:<content tag>`) must succeed. If one is private:
   package → **Package settings** → **Danger Zone** → **Change visibility** → Public
   (irreversible — fine, the code is public too). The org setting **Settings → Packages →
   Package creation** must allow public packages.
9. **GitHub secrets** in the `production` **environment** the deploy job runs in — repo
   **Settings → Environments → production → Environment secrets**, not repository secrets
   (an environment secret also overrides a repository secret of the same name):
   `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER` (`deploy`), `DEPLOY_SSH_KEY`, optional
   `DEPLOY_SSH_PORT`, and `DEPLOY_SSH_FINGERPRINT` — `ci.yml`'s header says which host key to
   read it from (the ECDSA one, not ed25519).
10. **First deploy**: as `deploy`, `bash /opt/mebel-pro/deploy/scripts/deploy.sh` (deploys
    `origin/main`, which must be a commit CI published images for), or **Actions → CI → Run
    workflow** on `main`.
11. **First platform admin**, from `deploy/`:
    `docker compose -f compose.prod.yaml exec backend python -m app.cli seed-platform-user
    --login <login> --password <throwaway>` — the first sign-in forces a password change.

## Conventions / gotchas

- Always `cd deploy/` before `docker compose …` (relative build contexts and bind mounts +
  `.env` discovery).
- **The dev stack is one shared instance per machine.** `compose.yaml` pins
  `name: mebel-pro`, so every checkout **and every git worktree** drives the same containers
  and volumes: containers keep bind mounts pointing at whichever tree created them
  (`--force-recreate` to re-point — see the verify skill), and `seed-demo.sh --reset` from
  any checkout wipes the shared volumes under a parallel session. Isolation needs
  `COMPOSE_PROJECT_NAME` + a ports override.
- `.env` is gitignored; the two `*.example` files are the contract. Keep them in sync with
  each other and with `backend/.env.{dev,prod}.example`.
- **Never `docker compose down -v` or `docker volume rm` on the server.** The database and
  the uploads live in the `mebel-pro_prod-postgres-data` / `mebel-pro_prod-minio-data` named
  volumes; they survive `up`, `pull`, `--remove-orphans`, recreation and `image prune` —
  only those two commands destroy them.
- **No backups yet.** Nothing copies the database or the uploads off the box today: losing
  the volumes or the VPS (the previous server expired and took its data with it) is
  unrecoverable. A follow-up PR adds a nightly off-box `pg_dump` + MinIO mirror; until it
  lands, take a manual dump before anything risky.
- **`POSTGRES_PASSWORD` only applies to an empty volume** — the postgres image reads it once,
  at initialisation. Changing it in `.env` later doesn't change the database's password, it
  locks the backend out: `ALTER ROLE … PASSWORD …` inside the DB first, then `.env`, then
  redeploy.
- **Prod never builds.** `compose.prod.yaml` has no `build:` key, on purpose: an on-box build
  is how the 2026-09-02 deploy died (the PackingSolver compile outran the SSH timeout), and on
  this small shared host it also courts the OOM killer. If GHCR is down, build the three
  images elsewhere with exactly the tags compose expects, from `deploy/` at the commit to ship
  — `T=$(git rev-parse HEAD) E=$(bash scripts/edge-tag.sh); docker build -t
  ghcr.io/qadam-uz/mebel-pro-backend:$T ../backend && docker build -t
  ghcr.io/qadam-uz/mebel-pro-web:$T ../web && docker build -t
  ghcr.io/qadam-uz/mebel-pro-edge:$E -f edge.Dockerfile .` — `docker save | ssh … docker
  load` them onto the box, and run `deploy.sh`'s steps after its pull by hand with
  `IMAGE_TAG=$T EDGE_IMAGE_TAG=$E` (the script's own pull would fail).
- **Migrations must work with the release that's still running** (expand → contract — add
  first, drop or rename only once no deployed code reads it; the invariant lives in
  [`docs/architecture.md`](../docs/architecture.md) → Current stage). `deploy.sh` migrates
  *before* swapping containers, so the old code serves on the new schema for the length of
  the deploy — and indefinitely after a rollback. **Rollback** =
  `DEPLOY_REF=<last good sha> SKIP_MIGRATIONS=1 bash deploy/scripts/deploy.sh` (old code
  can't `upgrade head` past a revision it doesn't know); only to commits that already have
  the pull-based `deploy.sh` — an older one builds on the box and wants `infra-net`.
- **`IMAGE_TAG` and `EDGE_IMAGE_TAG` in `deploy/.env` belong to `deploy.sh`.** It pins the
  deployed commit and the edge's content tag there on every run so manual
  `docker compose -f compose.prod.yaml …` commands resolve the running images; a hand edit is
  overwritten by the next deploy. Unset, compose refuses to start.
- **Data-service images are bumped deliberately, never by a deploy.** `deploy.sh` pulls only
  backend, web and edge; `postgres`, `minio` and `mc` are pulled by compose only when missing,
  so a moved `postgres:17-alpine` can't restart the database mid-deploy. To roll one forward,
  from `deploy/`: `docker compose -f compose.prod.yaml pull postgres && docker compose -f
  compose.prod.yaml up -d postgres` (likewise `minio`; `createbuckets` for mc) — expect a few
  seconds of DB or MinIO restart; the data stays in the volumes, and the backend's pool
  reconnects. Changing a pinned tag in `compose.prod.yaml` instead (the MinIO images) ships
  with the next deploy: the data-services step pulls the missing image and recreates that
  service then.
- The `backend` image's own CMD still runs `alembic upgrade head` before uvicorn (useful
  standalone); both compose files override it, and prod's `command:` only serves. The
  `Caddyfile`'s retry window (`lb_try_duration 30s`, in the `(to_backend)` and `(to_web)`
  snippets every route imports) exists **because** every deploy recreates the backend and web
  containers — seconds where the upstream refuses connections — and removing it turns each
  merge to `main` into user-facing 502s. Not tuning; don't strip it in a "simplify the
  Caddyfile" pass, and route any new upstream through a snippet that keeps it. The one gap
  it can't cover is the edge's own restart — ~1–2 s of refused connections on the loopback
  port, which the host nginx answers with 502. That is why the edge is tagged by content
  (`scripts/edge-tag.sh`), not by commit: it restarts only on deploys that change it.
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
  `ports`) and, if it's built from this repo, an image in CI's `images` job pinned by a
  `deploy.sh`-managed tag and added to `deploy.sh`'s `pull` list; route it through the edge
  in the Caddyfile — and give it a **project-unique
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
  `nginx:1.27-alpine`, `node:22-slim`); never `latest`. Our own images carry exactly one
  immutable tag — backend and web the full commit SHA, the edge its content tag.
- **MinIO images come from `pgsty/minio` + `pgsty/mc`** (the community fork). Upstream pulled
  `minio/minio` / `minio/mc` from Docker Hub and quay.io, so those tags no longer pull — a
  cached copy hides it locally, while CI and any fresh box fail with "pull access denied".
- **Postgres must be able to `CREATE EXTENSION pg_trgm`** — migration `e1a4c8b70d35` installs
  it for the catalog search's typo tier. `postgres:17-alpine` ships it (1.6), so the dev and
  prod stacks need nothing extra; a managed Postgres that withholds it leaves
  the search's last fallback returning no rows instead of erroring, but any *other* Postgres
  swap has to keep the contrib extensions available.
- The prod `default` subnet (`172.29.0.0/24`), `TRUSTED_PROXY_CIDRS`, and the Caddyfile's
  `trusted_proxies static 172.29.0.1/32` move **together**. The chain is client → host nginx
  (sets `X-Forwarded-For` to the client) → docker gateway `172.29.0.1` (the loopback port's
  source) → Caddy (keeps nginx's header, appends `172.29.0.1`) → backend, which takes the
  right-most hop outside the trusted CIDRs — the real client. The per-IP limits are inert
  without it (every request would key on the gateway). If the subnet collides on the VPS,
  change all three in one commit.
