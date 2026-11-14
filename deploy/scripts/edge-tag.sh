#!/usr/bin/env bash
# edge-tag.sh — print the edge image's content-addressed tag:
#
#   edge-<first 16 hex of a sha256 over the edge's build inputs>
#
# backend and web are tagged with the commit SHA, but the edge (Caddy + the
# baked-in Caddyfile) changes rarely. A per-commit tag would make compose
# recreate it on every deploy — a 1–2 s window where the loopback port refuses
# connections and the host nginx answers 502, which no Caddy retry can cover.
# Tagged by content, an unchanged edge keeps its tag and its running container.
#
# This file is the ONLY place the formula lives: CI's images job tags (and
# skips re-pushing) the edge image with it, and deploy/scripts/deploy.sh pins
# it as EDGE_IMAGE_TAG. If the edge build starts reading another file, add it
# to INPUTS — otherwise a change to that file would never reach production.
# A newer upstream caddy:2.8-alpine is likewise picked up only when an input
# changes; bump the FROM line to roll it deliberately.
#
# Deterministic across macOS and Linux: raw file bytes, a fixed file order,
# and whichever sha256 tool the host has.
#
# Usage: bash deploy/scripts/edge-tag.sh   (from any directory)

set -euo pipefail

INPUTS=(edge.Dockerfile Caddyfile .dockerignore)   # relative to deploy/

deploy_dir="$(dirname -- "${BASH_SOURCE[0]}")/.."

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256
    else
        openssl dgst -sha256 -r
    fi | cut -d' ' -f1
}

# One "<sha256>  <name>" line per input, then a sha256 over that manifest —
# hashing each file separately keeps the boundaries unambiguous (moving bytes
# from one file into another changes the tag).
manifest=""
for name in "${INPUTS[@]}"; do
    file_hash="$(sha256 < "$deploy_dir/$name")"
    manifest+="$file_hash  $name"$'\n'
done
digest="$(printf '%s' "$manifest" | sha256)"

if [[ ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then
    echo "edge-tag.sh: unexpected sha256 output: '$digest'" >&2
    exit 1
fi
echo "edge-${digest:0:16}"
