#!/usr/bin/env bash
# deploy.sh — roll the prod stack to one commit: pull that commit's prebuilt
# images, migrate as a separate gated step, then swap the containers.
#
# .github/workflows/deploy.yml runs it over SSH: after every green push to
# main (ci.yml calls that workflow), or by hand from the Actions tab — a
# redeploy or a rollback. Also runnable on the box as the deploy user, with a
# token (see GitHub credentials below):
#
#   ssh deploy@<server>
#   cd /opt/mebel-pro
#   bash deploy/scripts/deploy.sh                    # origin/main
#   DEPLOY_REF=<sha> bash deploy/scripts/deploy.sh   # a specific commit
#
# Nothing is built here. For every commit whose CI went green on main — only
# those commits are deployable — CI publishes ghcr.io/qadam-uz/mebel-pro-
# {backend,web}:<full sha> and ghcr.io/qadam-uz/mebel-pro-edge:<content tag>
# (scripts/edge-tag.sh: an unchanged edge keeps its tag, so its container keeps
# running). This script pulls exactly the images of the commit it resets to.
#
# GitHub credentials. The repo and its GHCR packages are private, and the box
# stores no GitHub credential. A deploy from Actions brings the deploy job's
# own GITHUB_TOKEN (contents: read + packages: read; it expires with the job)
# as DEPLOY_GITHUB_TOKEN, plus DEPLOY_GITHUB_ACTOR, the registry username.
# That one token serves exactly two calls: the git fetch (an inline credential
# helper reads it from the environment — never in argv or .git/config) and
# the image pull (docker login into a throwaway DOCKER_CONFIG, deleted right
# after the pull — never ~/.docker). Without DEPLOY_GITHUB_TOKEN both run
# anonymously, as they did while the repo was public. So a manual run needs a
# token first — a classic PAT with repo + read:packages (GHCR takes no
# fine-grained PAT), typed blind so it stays out of the shell history:
#
#   read -rs DEPLOY_GITHUB_TOKEN && export DEPLOY_GITHUB_TOKEN DEPLOY_GITHUB_ACTOR=<github user>
#   DEPLOY_REF=<sha> bash deploy/scripts/deploy.sh; unset DEPLOY_GITHUB_TOKEN
#
# Never echo the token, and never `set -x` this script: the log would carry it.
#
# Rollback — redeploy the last good commit WITHOUT migrations. From Actions:
# Deploy → Run workflow, ref = the last good sha, skip_migrations ticked. Here:
#
#   DEPLOY_REF=<last good sha> SKIP_MIGRATIONS=1 bash deploy/scripts/deploy.sh
#
# Old code can't `alembic upgrade head` against a database already at a newer
# revision (it doesn't know that revision), so the step must be skipped; old
# code running on the newer schema is safe only because every migration is
# expand → contract — compatible with the release before it
# (docs/architecture.md). Roll back only to a commit whose deploy.sh already
# logs in with DEPLOY_GITHUB_TOKEN: an older one pulls anonymously, which the
# private packages refuse (and older still builds on the box).
#
# Idempotent: re-running it for the deployed commit changes nothing.
#
# Required on the server:
#   - The repo cloned over https at $APP_DIR (default /opt/mebel-pro), owned
#     by the deploy user, no credential stored (the one-time clone of the
#     private repo: deploy/AGENTS.md → First-time setup).
#   - $APP_DIR/deploy/.env from deploy/.env.prod.example, every {{change-me}}
#     filled, chmod 600. Its IMAGE_TAG and EDGE_IMAGE_TAG lines are managed by
#     this script.
#   - The deploy user in the `docker` group.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mebel-pro}"
cd "$APP_DIR"

# Bind to a known git ref so a force-push race doesn't deploy something the
# operator didn't expect. CI passes the SHA via DEPLOY_REF; manual runs
# default to origin/main.
DEPLOY_REF="${DEPLOY_REF:-origin/main}"

# Exported, so they survive the re-exec below: the fetch uses the token
# before it, the pull after it.
export DEPLOY_GITHUB_TOKEN="${DEPLOY_GITHUB_TOKEN:-}" DEPLOY_GITHUB_ACTOR="${DEPLOY_GITHUB_ACTOR:-}"
if [ -n "$DEPLOY_GITHUB_TOKEN" ] && [ -z "$DEPLOY_GITHUB_ACTOR" ]; then
    echo "ERROR: DEPLOY_GITHUB_TOKEN is set but DEPLOY_GITHUB_ACTOR isn't — export the GitHub user" >&2
    echo "       the token belongs to (the GHCR username) too. Nothing was changed." >&2
    exit 1
fi

# git, authenticated with DEPLOY_GITHUB_TOKEN when there is one. The single
# quotes are the point: `${DEPLOY_GITHUB_TOKEN}` reaches git as text, and the
# helper's own shell expands it from the environment when GitHub asks — the
# token is in no process's argv and never in .git/config. `credential.helper=`
# first empties the helper list, so no configured helper stores it either, and
# GIT_TERMINAL_PROMPT=0 turns a refused token into an error, not a prompt.
# Without a token: plain git, anonymous, exactly as before.
git_with_token() {
    if [ -n "$DEPLOY_GITHUB_TOKEN" ]; then
        # shellcheck disable=SC2016  # expanded by the helper's shell, on purpose
        GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
            -c 'credential.helper=!f() { echo username=x-access-token; echo "password=${DEPLOY_GITHUB_TOKEN}"; }; f' \
            "$@"
    else
        git "$@"
    fi
}

# The fetch+reset can rewrite THIS script. Bash reads a script as it runs,
# so continuing past the reset could splice old and new lines — and a fix to
# the deploy flow would only take effect one deploy late. Do the reset, then
# re-exec the freshly-checked-out script exactly once (guarded so it can't
# loop); the re-exec'd run skips this block and proceeds with the new code.
#
# So this block always runs the copy ALREADY on the box — which fixed the
# order of the switch to a private repo: the first deploy of this token-aware
# script had to run while the repo was still PUBLIC (its predecessor fetches
# anonymously, then re-execs into this one, which pulls with the token), and
# only after that deploy went green could the repo go private. Full order, and
# the recovery for a repo made private too early: deploy/AGENTS.md → CI / CD.
if [ -z "${DEPLOY_REEXECED:-}" ]; then
    echo "==> Fetching latest from origin"
    if ! git_with_token fetch --all --prune; then
        echo "ERROR: git fetch failed. Nothing was changed." >&2
        if [ -n "$DEPLOY_GITHUB_TOKEN" ]; then
            echo "       If GitHub refused DEPLOY_GITHUB_TOKEN: from CI the deploy job needs contents: read;" >&2
            echo "       by hand it takes a classic PAT with repo (+ read:packages for the pull)." >&2
        else
            echo "       It ran anonymously. Private repo: deploy from CI (Actions → Deploy → Run workflow)," >&2
            echo "       or for an emergency manual run export DEPLOY_GITHUB_TOKEN=<classic PAT with repo +" >&2
            echo "       read:packages> DEPLOY_GITHUB_ACTOR=<github user> (read -rs keeps it out of shell history)." >&2
        fi
        exit 1
    fi
    echo "==> Resetting to $DEPLOY_REF"
    git reset --hard "$DEPLOY_REF"

    echo "==> Re-exec'ing the deployed deploy.sh"
    export DEPLOY_REEXECED=1
    exec bash "$APP_DIR/deploy/scripts/deploy.sh" "$@"
fi

cd "$APP_DIR/deploy"

compose() { docker compose -f compose.prod.yaml "$@"; }

echo "==> Verifying deploy/.env exists"
if [ ! -f .env ]; then
    echo "ERROR: $APP_DIR/deploy/.env is missing." >&2
    echo "       Copy .env.prod.example, fill in the {{change-me}} values, chmod 600 .env, and retry." >&2
    exit 1
fi

# A leftover placeholder is worse than a crash here: postgres takes
# POSTGRES_PASSWORD only when it initialises its empty volume, so a forgotten
# {{change-me}} would silently become the permanent DB password. Comment-aware
# (the template's own header comment mentions the placeholder), and it prints
# KEY names only — never values. Same command as deploy/AGENTS.md's setup step.
echo "==> Checking deploy/.env for unfilled {{change-me}} placeholders"
unfilled="$(grep -E '^[[:space:]]*[^#[:space:]].*\{\{change-me\}\}' .env | cut -d= -f1 || true)"
if [ -n "$unfilled" ]; then
    echo "ERROR: deploy/.env still holds {{change-me}} for:" >&2
    printf '%s\n' "$unfilled" | sed 's/^/         /' >&2
    echo "       Fill them in (secrets: openssl rand -hex 32) and retry. Nothing was changed." >&2
    exit 1
fi

env_tmp="$(mktemp)"
pull_log="$(mktemp)"
docker_config=""   # the throwaway GHCR login while it exists (step 2)
trap 'rm -f "$env_tmp" "$pull_log"; if [ -n "$docker_config" ]; then rm -rf "$docker_config"; fi' EXIT

# --- 1. Pin the release ------------------------------------------------------
# backend and web are tagged with the deployed commit; the edge with its
# content tag — computed by the same script CI tags the image with. Both are
# exported, so a stray value in the caller's environment can't win (shell env
# beats .env in compose), and pinned in .env below, so every later manual
# `docker compose -f compose.prod.yaml ps|logs|exec` resolves the deployed images.
IMAGE_TAG="$(git rev-parse HEAD)"
EDGE_IMAGE_TAG="$(bash "$APP_DIR/deploy/scripts/edge-tag.sh")"
export IMAGE_TAG EDGE_IMAGE_TAG

# Catches what the placeholder check can't — a required value that is missing
# or empty (compose's `:?`, e.g. DOCS_AUTH_PASSWORD) — before .env is written.
echo "==> Validating compose.prod.yaml against deploy/.env"
if ! compose config -q; then
    echo "ERROR: compose.prod.yaml doesn't resolve with deploy/.env (message above). Nothing was changed." >&2
    exit 1
fi

# pin_env KEY=VALUE…: in .env, replace each KEY's first line in place (dropping
# duplicates) or append it; awk also guarantees a final newline. `cat >`
# rewrites .env in place, so it keeps its owner and mode 600 — `mv` would swap
# in the temp file instead. Unchanged content isn't rewritten at all.
pin_env() {
    awk -v pins="$*" '
        BEGIN {
            n = split(pins, kv, " ")
            for (i = 1; i <= n; i++) {
                key = kv[i]; sub(/=.*/, "", key)
                line[key] = kv[i]; order[i] = key
            }
        }
        {
            key = $0; sub(/=.*/, "", key)
            if (index($0, "=") && (key in line)) {
                if (!(key in seen)) print line[key]
                seen[key] = 1
                next
            }
            print
        }
        END { for (i = 1; i <= n; i++) if (!(order[i] in seen)) print line[order[i]] }
    ' .env > "$env_tmp"
    if ! cmp -s "$env_tmp" .env; then
        cat "$env_tmp" > .env
    fi
}
echo "==> Pinning IMAGE_TAG=$IMAGE_TAG EDGE_IMAGE_TAG=$EDGE_IMAGE_TAG in deploy/.env"
pin_env "IMAGE_TAG=$IMAGE_TAG" "EDGE_IMAGE_TAG=$EDGE_IMAGE_TAG"

# --- 2. Pull -----------------------------------------------------------------
# Only our own images, all fetched before anything changes — a failure here
# leaves the running stack untouched. The data-service images (postgres, minio,
# mc) are deliberately NOT pulled: compose fetches them only when missing, so a
# moved `postgres:17-alpine` can never restart the database mid-deploy. Bumping
# one is a deliberate act (deploy/AGENTS.md).
#
# The packages are private. With DEPLOY_GITHUB_TOKEN, this is the one place a
# registry credential exists: docker login — the token over stdin, never argv
# — into a throwaway DOCKER_CONFIG (mktemp -d, so 0700) that only this pull
# uses, deleted the moment it ends, and by the EXIT trap if anything fails
# first. ~/.docker is never touched. Without a token the pull is anonymous,
# exactly as before.
echo "==> Pulling images"
if [ -n "$DEPLOY_GITHUB_TOKEN" ]; then
    docker_config="$(mktemp -d)"
    # compose is a docker CLI plugin, and the CLI also looks for plugins in
    # $DOCKER_CONFIG/cli-plugins: link a per-user install in, or `docker
    # compose` doesn't exist for this pull. (rm -rf drops the link, not its
    # target.)
    plugins="${DOCKER_CONFIG:-$HOME/.docker}/cli-plugins"
    if [ -d "$plugins" ]; then
        ln -s "$plugins" "$docker_config/cli-plugins"
    fi
    echo "==> Logging in to ghcr.io as $DEPLOY_GITHUB_ACTOR (a throwaway DOCKER_CONFIG, removed after the pull)"
    if ! printf '%s\n' "$DEPLOY_GITHUB_TOKEN" |
        DOCKER_CONFIG="$docker_config" docker login ghcr.io --username "$DEPLOY_GITHUB_ACTOR" --password-stdin; then
        echo "ERROR: the GHCR login failed. Nothing was changed; the running stack is untouched." >&2
        echo "       From CI the deploy job's token needs packages: read; by hand it takes a classic PAT" >&2
        echo "       with read:packages — GHCR takes no fine-grained PATs." >&2
        exit 1
    fi
fi
# A subshell, so DOCKER_CONFIG points at the throwaway login for the pull alone.
if ! (
    if [ -n "$docker_config" ]; then export DOCKER_CONFIG="$docker_config"; fi
    compose pull backend web edge
) 2>&1 | tee "$pull_log"; then
    echo "ERROR: pulling the images failed. Nothing was changed; the running stack is untouched." >&2
    if grep -qi 'no matching manifest' "$pull_log"; then
        echo "       The images are linux/amd64 only. An arm64 server needs CI's images job on" >&2
        echo "       ubuntu-24.04-arm (see .github/workflows/ci.yml)." >&2
    elif grep -qiE 'unauthorized|denied|forbidden' "$pull_log"; then
        if [ -n "$DEPLOY_GITHUB_TOKEN" ]; then
            echo "       GHCR refused DEPLOY_GITHUB_TOKEN for a package: each one must let this repo's workflows" >&2
            echo "       read it — inherited from the repo, or Package settings → Manage Actions access" >&2
            echo "       (deploy/AGENTS.md → First-time setup)." >&2
        else
            echo "       GHCR refused an anonymous pull: the packages are private. Deploy from CI (Actions →" >&2
            echo "       Deploy → Run workflow), or for an emergency manual run export DEPLOY_GITHUB_TOKEN=<classic" >&2
            echo "       PAT with repo + read:packages> DEPLOY_GITHUB_ACTOR=<github user>. Stale ghcr.io creds" >&2
            echo "       in ~/.docker fail the same way (docker logout ghcr.io)." >&2
        fi
    elif grep -qiE 'not found|manifest unknown' "$pull_log"; then
        echo "       No images for $IMAGE_TAG / $EDGE_IMAGE_TAG. CI publishes them only for commits whose" >&2
        echo "       CI went green on main — wait for that run, or deploy a commit that has them." >&2
    fi
    exit 1
fi
# The credential's job is done: drop the login and the token now, not at exit.
if [ -n "$docker_config" ]; then
    rm -rf "$docker_config"
    docker_config=""
fi
unset DEPLOY_GITHUB_TOKEN

# --- 3. Data services --------------------------------------------------------
# A no-op when they're up and unchanged. On a fresh box compose pulls their
# images here (missing only). They're recreated only when this commit changed
# their definition in compose.prod.yaml (a new pinned tag, a new env value) —
# a few seconds' blip for the still-serving backend; the data stays in the
# volumes.
echo "==> Starting data services (postgres, minio)"
if ! compose up -d --wait --wait-timeout 120 postgres minio; then
    echo "ERROR: postgres/minio didn't become healthy within 120s. Recent logs:" >&2
    compose logs --tail=40 postgres minio >&2 || true
    exit 1
fi

echo "==> Ensuring the MinIO bucket exists"
compose run --rm --no-deps createbuckets

# --- 4. Migrations, gated ----------------------------------------------------
# A one-off container from the NEW backend image; the OLD backend keeps serving
# throughout. A failure stops the deploy right here: the previous release keeps
# running untouched, and Postgres's transactional DDL rolls the failed migration
# back (statements a migration runs in an `autocommit_block()` excepted — keep
# those additive). Serving old code on the newly migrated schema is safe only
# because migrations are expand → contract: each one must work with the release
# that's still running (docs/architecture.md → Current stage).
if [ "${SKIP_MIGRATIONS:-}" = "1" ]; then
    echo "==> SKIP_MIGRATIONS=1: not migrating (rollback)"
else
    echo "==> Running database migrations (the current release keeps serving)"
    if ! compose run --rm --no-deps backend alembic upgrade head; then
        echo "ERROR: the migration failed; stopped before touching the serving containers." >&2
        echo "       The previous release is still live. Fix the migration and deploy again —" >&2
        echo "       or, rolling back to an older commit (\"Can't locate revision\"), re-run with skip_migrations" >&2
        echo "       ticked (SKIP_MIGRATIONS=1 by hand)." >&2
        exit 1
    fi
fi

# --- 5. Swap -----------------------------------------------------------------
# Recreates what changed — backend and web every time (per-commit tags), the
# edge only when its content tag moved — and waits until every service is
# running and every healthcheck passes. createbuckets stays out: its profile
# isn't active. The Caddyfile's retry window covers backend and web while
# they're recreated; an edge restart (a Caddyfile change) is a ~1–2 s gap no
# retry covers — the host nginx answers 502 meanwhile.
echo "==> Swapping in $IMAGE_TAG"
if ! compose up -d --wait --wait-timeout 120 --remove-orphans; then
    echo "ERROR: the stack didn't come up healthy within 120s. Recent backend logs:" >&2
    compose logs --tail=80 backend >&2 || true
    echo "       To roll back: Actions → Deploy → Run workflow, ref=<last good sha>, skip_migrations ticked." >&2
    exit 1
fi

# --- 6. Telegram webhook (non-fatal) -----------------------------------------
# Idempotent: points the bot at CLIENT_APP_BASE_URL's webhook route, so a
# domain move or a rotated webhook secret takes effect with the deploy. The
# release is already live — a failure here must not fail the deploy, but the
# bot gets no updates (bot sign-in breaks) until it's fixed.
echo "==> Registering the Telegram webhook"
if ! compose exec -T backend python -m app.cli telegram-webhook set; then
    echo "WARN: ============================================================================" >&2
    echo "WARN: Telegram webhook registration FAILED. The deploy itself succeeded, but the" >&2
    echo "WARN: bot receives no updates until this works. Check TELEGRAM_* and" >&2
    echo "WARN: CLIENT_APP_BASE_URL in deploy/.env, then re-run from deploy/:" >&2
    echo "WARN:   docker compose -f compose.prod.yaml exec backend python -m app.cli telegram-webhook set" >&2
    echo "WARN: ============================================================================" >&2
fi

# --- 7. Prune ----------------------------------------------------------------
# Only images CI labelled as mebel-pro's — the box is shared, so never another
# project's. Images in use by a container are kept; a rollback simply re-pulls
# from GHCR. Then the usual dangling-layer sweep.
echo "==> Pruning unused mebel-pro images"
docker image prune -af --filter "label=org.opencontainers.image.source=https://github.com/qadam-uz/mebel-pro" >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

compose ps || true
echo "==> Done: $IMAGE_TAG is live."
