# syntax=docker/dockerfile:1

# The edge reverse proxy, with the Caddyfile baked in so it is part of the
# immutable deploy artifact. A bind-mounted config file's *contents* are
# invisible to `docker compose up -d` (it only recreates a container when the
# service definition changes), so a mounted Caddyfile left Caddy serving a
# stale in-memory config after every config-only change. Baked, the image is
# tagged by its own content (scripts/edge-tag.sh hashes this file, the
# Caddyfile and .dockerignore): a config change yields a new tag, which a
# deploy pulls and Compose recreates the edge for — and an unchanged edge
# keeps its tag, so deploys leave it running.
#
# Per-environment values (BASE_DOMAIN) stay as runtime env on the
# service — Caddy substitutes them when it loads the config, so the same image
# works across environments.
FROM caddy:2.8-alpine
COPY Caddyfile /etc/caddy/Caddyfile
