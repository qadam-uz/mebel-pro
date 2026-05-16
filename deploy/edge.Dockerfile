# syntax=docker/dockerfile:1

# The edge reverse proxy, with the Caddyfile baked in so it is part of the
# immutable deploy artifact. A bind-mounted config file's *contents* are
# invisible to `docker compose up -d` (it only recreates a container when the
# service definition changes), so a mounted Caddyfile left Caddy serving a
# stale in-memory config after every config-only change. Baking it means
# `compose up -d --build` rebuilds this image whenever the Caddyfile changes,
# Compose sees a new image, and the edge is recreated deterministically.
#
# Per-environment values (BASE_DOMAIN, ACME_EMAIL) stay as runtime env on the
# service — Caddy substitutes them when it loads the config, so the same image
# works across environments.
FROM caddy:2.8-alpine
COPY Caddyfile /etc/caddy/Caddyfile
