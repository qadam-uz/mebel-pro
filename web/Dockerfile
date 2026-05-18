# syntax=docker/dockerfile:1

# --- build -------------------------------------------------------------------
FROM node:22-slim AS build

# pnpm via corepack (version pinned by package.json "packageManager").
RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build

# --- runtime: static files served by nginx -----------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA-aware server block (HTML5 history fallback).
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# --- TEMPORARY: static design-prototype gallery ------------------------------
# Bake web/prototypes/ into the image so it is served at
# admin.<domain>/prototypes (see the /prototypes/ block in nginx.conf).
# REMOVE this line and that nginx block once a design system is chosen and
# committed to web/DESIGN.md.
COPY prototypes /usr/share/nginx/html/prototypes
# --- end TEMPORARY -----------------------------------------------------------

EXPOSE 80
