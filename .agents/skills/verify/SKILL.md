---
name: verify
description: Build/launch/drive recipe for verifying Mebel Pro changes at their runtime surface (API + browser).
---

# Verifying Mebel Pro changes

## Launch (Docker dev stack, hot reload)

```bash
cd deploy && cp .env.dev.example .env && docker compose up -d --build
# API :8000 · web :5173 · Postgres :5432 · MinIO :9000
```

**Worktree gotcha:** compose reuses existing `mebel-pro-*` containers whose bind
mounts point at whichever checkout created them. From a worktree, force the
mounts onto your tree and confirm:

```bash
docker compose up -d --force-recreate backend web
docker inspect mebel-pro-backend-1 --format '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}'
```

Seed demo data (aborts safely if already seeded; credentials in the header):
`bash deploy/seed-demo.sh`

## API handle (no browser needed)

Client access token via OTP (dev code `000000`; request is rate-limited ~60s per phone):

```bash
API=http://localhost:8000/api/v1
curl -s -X POST $API/auth/client/otp/request -H 'Content-Type: application/json' -d '{"phone":"+998901112233"}'
TOKEN=$(curl -s -X POST $API/auth/client/otp/verify -H 'Content-Type: application/json' \
  -d '{"phone":"+998901112233","code":"000000","name":"Dilshod"}' | jq -r .access_token)
```

Workshop token: `POST $API/auth/workshop/login` with `{"login":"owner","password":"OwnerDemo123"}`
(field is `login`, not `username`). Auth is header-only — the SPA keeps tokens in
memory, so in-page `fetch(..., {credentials:'include'})` gets 401; mint your own token.

Useful surfaces: `GET /client/cutting-drafts/{id}`, `GET /client/cutting-results/{id}/pdf`,
`GET /client/orders/{id}/cutting/pdf`, `GET /workshop/orders/{id}/cutting/pdf`.

## Inspecting PDFs

`sips -s format png x.pdf --out x.png` rasterizes page 1 only; for page N extract
first: `uv run --with pypdf python -c "..."` (PyObjC/Quartz is not in the sandbox python).
Check embedded fonts with `strings x.pdf | grep DejaVu`.

## Browser pane gotchas

- The pane's screenshot capture goes blank after any `scroll` action; reload the
  tab to recover. To screenshot below-the-fold content without scrolling, pin the
  element via JS (`el.style.position='fixed'; top/left/width; zIndex`) and screenshot.
- The cutting editor's parts table: fill inputs via `read_page` refs + `form_input`
  (typed Tab characters land in the same field).
