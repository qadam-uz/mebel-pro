#!/usr/bin/env bash
# deploy.sh — pull the latest code and (re)start the prod stack.
#
# Designed to be invoked over SSH from CI (see .github/workflows/ci.yml's
# `deploy` job) but also runnable manually as the deploy user:
#
#   ssh mebel@<server>
#   cd /opt/mebel-pro
#   bash deploy/scripts/deploy.sh
#
# Idempotent. Uses the standalone prod compose (no overlay): the backend
# joins the existing `infra-net` Docker network to reach the shared
# `postgres` and `minio` services running on the VPS.
#
# Required (on the server):
#   - The repo is cloned at $APP_DIR (default /opt/mebel-pro).
#   - $APP_DIR/deploy/.env exists, with prod values filled in.
#   - The `infra-net` Docker network exists (`docker network create infra-net`).
#   - The deploy user is in the `docker` group.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mebel-pro}"
cd "$APP_DIR"

# Bind to a known git ref so a force-push race doesn't deploy something the
# operator didn't expect. CI passes the SHA via DEPLOY_REF; manual runs
# default to origin/main.
DEPLOY_REF="${DEPLOY_REF:-origin/main}"

# The fetch+reset can rewrite THIS script. Bash reads a script as it runs,
# so continuing past the reset could splice old and new lines — and a fix to
# the deploy flow would only take effect one deploy late. Do the reset, then
# re-exec the freshly-checked-out script exactly once (guarded so it can't
# loop); the re-exec'd run skips this block and proceeds with the new code.
if [ -z "${DEPLOY_REEXECED:-}" ]; then
    echo "==> Fetching latest from origin"
    git fetch --all --prune
    echo "==> Resetting to $DEPLOY_REF"
    git reset --hard "$DEPLOY_REF"

    echo "==> Re-exec'ing the deployed deploy.sh"
    export DEPLOY_REEXECED=1
    exec bash "$0" "$@"
fi

cd "$APP_DIR/deploy"

echo "==> Verifying deploy/.env exists"
if [ ! -f .env ]; then
    echo "ERROR: $APP_DIR/deploy/.env is missing." >&2
    echo "       Copy .env.prod.example, fill in the {{change-me}} values, chmod 600 .env, and retry." >&2
    exit 1
fi

echo "==> Verifying infra-net network exists"
if ! docker network inspect infra-net >/dev/null 2>&1; then
    echo "ERROR: external Docker network 'infra-net' is missing on this host." >&2
    echo "       Create it once:  docker network create infra-net" >&2
    echo "       (The shared postgres + minio services attach to this network.)" >&2
    exit 1
fi

# Migrations run inside the backend image at startup (alembic upgrade head;
# see ../backend/Dockerfile CMD). A botched migration crash-loops the new
# container, the healthcheck wait below fails, and this script exits non-zero.
# Recover by re-running with DEPLOY_REF pointed at the last good commit.

echo "==> Rebuilding & restarting the stack"
docker compose -f compose.prod.yaml up -d --build --remove-orphans

echo "==> Waiting for backend healthcheck"
ok=""
for i in {1..30}; do
    state="$(docker compose -f compose.prod.yaml ps --format json backend 2>/dev/null \
        | tr -d '\n' \
        | grep -o '"Health":"[^"]*"' \
        | head -1 \
        | cut -d'"' -f4 || true)"
    if [ "$state" = "healthy" ]; then
        ok="yes"
        break
    fi
    sleep 2
done

if [ -z "$ok" ]; then
    echo "ERROR: backend didn't become healthy within 60s. Recent logs:" >&2
    docker compose -f compose.prod.yaml logs --tail=80 backend >&2
    exit 1
fi

echo "==> Stack is healthy; pruning dangling images"
docker image prune -f >/dev/null 2>&1 || true

echo "==> Done."
