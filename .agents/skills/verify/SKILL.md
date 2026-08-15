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

**Two web surfaces can coexist.** The harness browser preview (`.claude/launch.json`) runs
its own host Vite on **:5199** (`--strictPort`, chosen so the docker `web` on :5173 can't
collide or get adopted); it still proxies `/api` to `localhost:8000`, so a backend must be up
(docker or host). Screenshot the port you actually launched — :5173 is the docker container's
instance, :5199 is the preview's.

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
(field is `login`, not `username`). API calls are header-only — the SPA keeps access tokens
in memory, so an in-page `fetch` of an API route without the header 401s; mint your own token
for direct API work.

## Logging the SPA in from the browser pane

Typing into the login form via automation is unreliable (v-model misses the synthetic input
on the workshop login). The recipe that works: run the login **as an in-page fetch, then
reload** — login sets an HttpOnly refresh cookie, and the app silently refreshes from it on
load:

```js
await fetch('/api/v1/auth/workshop/login', {
  method: 'POST', credentials: 'include',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({login: 'owner', password: 'OwnerDemo123'}),
})
location.reload()
```

Same shape for the client SPA via the OTP endpoints (dev code `000000`).

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
