#!/usr/bin/env bash
#
# ============================================================================
#  Mebel Pro — presentation demo seed
# ============================================================================
#
# Builds ONE deterministic, presentable demo world that lights up every page of
# all three SPAs (client · workshop · superadmin). Fixed credentials, fixed
# content — hand this to a presenter and it looks the same every time.
#
# Everything is created through the public REST API (curl + jq), exactly as a
# real operator would, except the very first platform admin, which is seeded via
# the idempotent `app.cli` command (no API exists to bootstrap the first admin).
#
# ─── USAGE ──────────────────────────────────────────────────────────────────
#   Dev stack must be up first (from deploy/):  docker compose up -d --build
#
#   bash deploy/seed-demo.sh            # seed a fresh stack (aborts if already seeded)
#   bash deploy/seed-demo.sh --reset    # wipe volumes, restart the stack, then seed
#
#   The platform's no-delete invariant means there is no in-place re-seed: to
#   rebuild the demo, always use --reset (it runs `docker compose down -v`).
#
# ─── DEMO CREDENTIALS (all passwords are ready to use — no forced change) ─────
#
#   SUPERADMIN SPA  (admin.<host> / :5173 → superadmin)
#     admin        / AdminDemo123      platform admin (full access)
#     operator     / —                 extra platform user, left on a temp
#                                       password (shows the "reset required"
#                                       state on the Platform-users page)
#
#   WORKSHOP SPA  (workshop.<host>)   — workshop "Mebel Master", 2 branches:
#                                        B1 Chilonzor filiali · B2 Yunusobod filiali
#     owner        / OwnerDemo123      owner (full workshop access, both branches)
#     manager      / ManagerDemo123    Filial menejeri  — dashboard, orders,
#                                                          catalog, inventory @ B1
#     cutter       / CutterDemo123     Usta (kesish)    — dashboard, production @ B1
#     edger        / EdgerDemo123      Usta (kromka)    — production @ B1 AND @ B2
#     usta2        / Usta2Demo123      Yunusobod ustasi — dashboard, production,
#                                                          inventory @ B2 (home @ B2)
#     accountant   / HisobchiDemo123   Hisobchi         — finance + reports @ B1+B2
#
#   CLIENT SPA  (app.<host>)          — OTP login, dev code 000000:
#     +998901112233  Dilshod          6 orders (new→ready) + 2 saved drafts
#     +998901234455  Aziza            3 orders (completed ×2, cancelled)
#
#   Also: 2 skeleton workshops (Atlas Mebel, Nur Mebel) so the admin list looks
#   real; 4 manufacturers; 30 platform dekorlar (16 panel-shaped + 14 kromka),
#   each with a catalog image; both branches carry 34 branch-material formats
#   each, with stock; finance ledger populated.
#
# ─── CATALOG SHAPE (post-reshape) ────────────────────────────────────────────
#
#   A *dekor* is platform-owned identity only — manufacturer, tur, kod, nomi,
#   photo, grain. It has no thickness, no size and no price, because a platform
#   operator cannot know what a workshop's supplier actually sells.
#
#   A *branch material* is one dekor in one concrete format, carried by one
#   branch: qalinlik + (uzunlik×eni | kromka_eni) + price + min_stock. THAT is
#   the id every stock row, cutting panel and order item points at — and it is
#   per branch, so B1's id for "Oq 2800×2070×18" is not B2's.
#
#   The demo leans on that fan-out on purpose, so the new screens have data:
#     · h1145 / w980 kromka are ONE dekor each, carried at two thicknesses
#       (2 mm and 0.4 mm) — under the old model those were 4 separate materials.
#     · h1145 panel is carried at 18 mm AND 16 mm, and the 16 mm row is attached
#       with NO price → price_tiyin 0 → the "narx yo'q" state on the workshop
#       catalog, and excluded from client-facing listings.
#     · w980 panel is carried at the standard 2800×2070 AND at 2620×1830, so the
#       "Nostandart o'lcham" grouping is not empty.
#
#   NOTE: the workshop owner shows as full-name "owner" with B1's phone — the API
#   provisions the owner from its login and forbids editing the owner record, so
#   there is no way to give it a nicer display name. The customer-facing name is
#   the workshop itself ("Mebel Master").
#
# Requires: docker (compose v2), curl, jq. Run against the DEV stack only.
# ============================================================================

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API="${API:-http://localhost:8000/api/v1}"
READYZ="${READYZ:-http://localhost:8000/api/v1/readyz}"
ASSETS_DIR="$SCRIPT_DIR/seed-assets/materials"
OTP_CODE="000000"

# Credentials (see header). Temp passwords are used once during seeding, then
# changed to the documented finals so the finals are ready to use immediately.
ADMIN_LOGIN="admin";     ADMIN_PW="AdminDemo123"
OPERATOR_LOGIN="operator"; OPERATOR_TEMP="OperatorTmp123"   # left un-changed on purpose
OWNER_LOGIN="owner";     OWNER_TEMP="OwnerTmp123";   OWNER_PW="OwnerDemo123"
STAFF_TEMP="StaffTmp123"

DILSHOD_PHONE="+998901112233"; DILSHOD_NAME="Dilshod"
AZIZA_PHONE="+998901234455";   AZIZA_NAME="Aziza"

B1_PHONE="+998712001212"   # Chilonzor filiali
B2_PHONE="+998712007878"   # Yunusobod filiali

RESET=0
[ "${1-}" = "--reset" ] && RESET=1

# ─── Pretty output ───────────────────────────────────────────────────────────
say()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
info() { printf '   \033[0;90m%s\033[0m\n' "$*"; }
ok()   { printf '   \033[0;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '   \033[0;33m! %s\033[0m\n' "$*" >&2; }
die()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ─── HTTP helpers ────────────────────────────────────────────────────────────
HTTP_CODE=""; HTTP_BODY=""
_req() { # method url token [json-body]
  local method="$1" url="$2" token="$3" body="${4-}" resp
  resp="$(curl -sS -X "$method" "$url" \
    -H 'Content-Type: application/json' \
    ${token:+-H "Authorization: Bearer $token"} \
    ${body:+--data "$body"} \
    -w $'\n%{http_code}')" || true
  HTTP_CODE="${resp##*$'\n'}"
  HTTP_BODY="${resp%$'\n'*}"
}

jcall() { # method url token [json-body] -> prints response body, dies on non-2xx
  _req "$1" "$2" "$3" "${4-}"
  case "$HTTP_CODE" in
    2*) printf '%s' "$HTTP_BODY" ;;
    *)  printf '%s' "$HTTP_BODY" >&2
        die "HTTP ${HTTP_CODE:-ERR} on $1 $2" ;;
  esac
}

dc() { ( cd "$SCRIPT_DIR" && docker compose "$@" ); }

# `compose.yaml` hardcodes `name: mebel-pro`, and COMPOSE_PROJECT_NAME overrides
# it — so without that variable set, a checkout *anywhere* (including a git
# worktree) drives the one shared stack. Two sessions running in parallel then
# seed, reset and migrate each other's database without either noticing. Say
# which project this run will touch, so that is a visible choice and not a
# silent one; `--reset` gets a louder warning because it destroys volumes.
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-mebel-pro}"
if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
  info "Compose project: ${COMPOSE_PROJECT} (isolated via COMPOSE_PROJECT_NAME)"
else
  info "Compose project: ${COMPOSE_PROJECT} — the shared default."
  info "  Working on a branch alongside another session? Re-run with"
  info "  COMPOSE_PROJECT_NAME=<something-unique> and a ports override."
fi

# ─── Preflight ───────────────────────────────────────────────────────────────
command -v curl >/dev/null || die "curl is required"
command -v jq   >/dev/null || die "jq is required"
command -v docker >/dev/null || die "docker is required"

if [ "$RESET" = 1 ]; then
  say "Reset: wiping volumes and restarting the dev stack"
  dc down -v
  dc up -d --build
fi

say "Waiting for the API to become ready ($READYZ)"
ready=0
for _ in $(seq 1 90); do
  if curl -sf "$READYZ" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || die "API not ready after 90s. Is the dev stack up? (cd deploy && docker compose up -d)"
ok "API is ready"

# ============================================================================
# 1 · Platform admin (CLI) + abort-if-already-seeded guard
# ============================================================================
say "1 · Seed platform admin '$ADMIN_LOGIN' (idempotent CLI)"
ADMIN_RESULT="$(dc exec -T backend python -m app.cli seed-platform-user \
  --login "$ADMIN_LOGIN" --password "$ADMIN_PW" \
  --full-name "Platforma administratori" --phone "+998712000001" \
  --no-password-reset-required)"
# The CLI prints a one-line JSON result, but with DEBUG=true (the dev default)
# SQLAlchemy echo logs share stdout — the JSON is the only line starting with '{'.
ADMIN_STATUS="$(printf '%s\n' "$ADMIN_RESULT" | grep '^{' | jq -r '.status' 2>/dev/null | tail -1)"
if [ "$ADMIN_STATUS" = exists ]; then
  die "This stack is already seeded (admin '$ADMIN_LOGIN' exists).
     The platform has no delete path, so re-seeding in place would collide.
     Rebuild the demo world with:  bash deploy/seed-demo.sh --reset"
fi
ok "admin created"

# ============================================================================
# 2 · Platform login
# ============================================================================
say "2 · Platform login"
TOKEN="$(jcall POST "$API/auth/platform/login" "" \
  "{\"login\":\"$ADMIN_LOGIN\",\"password\":\"$ADMIN_PW\"}" | jq -r .access_token)"
[ -n "$TOKEN" ] && [ "$TOKEN" != null ] || die "platform login failed"
ok "token acquired"

# ============================================================================
# 3 · Extra platform operator (left on a temp password, on purpose)
# ============================================================================
say "3 · Extra platform user '$OPERATOR_LOGIN' (temp password — shows reset-required state)"
jcall POST "$API/platform/users" "$TOKEN" \
  "{\"full_name\":\"Nazorat operatori\",\"login\":\"$OPERATOR_LOGIN\",\"phone\":\"+998712000002\",\"temp_password\":\"$OPERATOR_TEMP\"}" >/dev/null
ok "operator created"

# ============================================================================
# 4 · Manufacturers + 30 dekorlar (each with a catalog image)
# ============================================================================
say "4 · Manufacturers + 16 panel dekorlar + 14 kromka dekorlar (uploading images)"

man_id() { # name country -> id
  jcall POST "$API/platform/catalog/manufacturers" "$TOKEN" \
    "{\"name\":\"$1\",\"country\":\"$2\"}" | jq -r .id
}
MAN_EGGER="$(man_id "Egger" "AT")"
MAN_SWISS="$(man_id "Swiss Krono" "PL")"
MAN_KRONO="$(man_id "Kronospan" "UA")"
MAN_TOSH="$(man_id "Toshkent Plita" "UZ")"
man_for() { case "$1" in
  egger) echo "$MAN_EGGER";; swisskrono) echo "$MAN_SWISS";;
  kronospan) echo "$MAN_KRONO";; toshkent) echo "$MAN_TOSH";; esac; }

# Upload a swatch and echo its file_id (empty on any problem — the dekor is then
# created without an image). One upload per dekor: a file attaches exactly once,
# and one photo now serves every format of that dekor. Two committed swatches
# (`w980_edge_thin.jpg`, `h1145_edge_thin.jpg`) are therefore no longer uploaded
# — the 0.4 mm tape is a *format* of the same dekor as the 2 mm one, not its own
# catalog entry.
upload_image() { # img-basename -> file_id | ""
  local path="$ASSETS_DIR/$1" resp code
  [ -f "$path" ] || { warn "image missing: $1 (dekor created without image)"; return 0; }
  resp="$(curl -sS -X POST "$API/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "upload=@$path;type=image/jpeg" -w $'\n%{http_code}')" || true
  code="${resp##*$'\n'}"
  case "$code" in
    2*) printf '%s' "${resp%$'\n'*}" | jq -r .id ;;
    *)  warn "upload failed ($code) for $1"; return 0 ;;
  esac
}

# Parallel arrays (bash 3.2 has no associative arrays). Two maps, deliberately:
#
#   DEKOR_*  key "<decor>|<shape>"                   -> platform dekor id
#   BM_*     key "<branch>|<decor>|<shape>|<format>" -> branch_material id
#
# The second one MUST be branch-keyed. A dekor is one platform row shared by
# everyone, but the format a branch carries is its own row with its own id, and
# that id is what stock-ins, cutting parts and order items reference. Reusing
# B1's ids on B2 would silently move every B2 order onto B1's shelves.
#
# `shape` is `panel` or `kromka` — the coarse split the templates care about,
# not the dekor's `tur` (which is ldsp/mdf/... and varies per decor).
# `format` is the literal spec string from the tables below: `LxWxT` for panels,
# `TxW` for kromka.
DEKOR_KEY=(); DEKOR_ID=(); DEKOR_FMT=()
put_dekor() { DEKOR_KEY+=("$1"); DEKOR_ID+=("$2"); DEKOR_FMT+=("$3"); }

BM_KEY=(); BM_ID=()
put_bm() { BM_KEY+=("$1"); BM_ID+=("$2"); }
bm_id() { # "<branch>|<decor>|<shape>|<format>" -> branch_material id
  local i
  for i in "${!BM_KEY[@]}"; do
    [ "${BM_KEY[$i]}" = "$1" ] && { printf '%s' "${BM_ID[$i]}"; return; }
  done
}

# Panel dekorlar:  decor|manufacturer|tur|tolali|nomi|image|formats
#   formats: comma-separated `uzunlik x eni x qalinlik`; a leading `~` attaches
#   that format with NO price (price_tiyin 0 — the "narx yo'q" state).
#   `tur` is the real substrate now: the old `type=dsp` rows were LDSP boards all
#   along (the label already rendered them "LDSP"), so they seed as `ldsp`.
PANEL_DEKORLAR='
h1145|egger|ldsp|true|Sonoma eman|h1145_panel.jpg|2800x2070x18,~2800x2070x16
h3734|egger|ldsp|true|Yong'\''oq|h3734_panel.jpg|2800x2070x18
h1180|egger|ldsp|true|Oq eman|h1180_panel.jpg|2750x1830x16
h1137|egger|ldsp|true|Kulrang eman|h1137_panel.jpg|2800x2070x18
h3303|swisskrono|mdf|true|To'\''q yong'\''oq|h3303_panel.jpg|2800x2070x18
h3702|swisskrono|ldsp|true|Buk|h3702_panel.jpg|2750x1830x16
h1615|swisskrono|ldsp|true|Qarag'\''ay|h1615_panel.jpg|2800x2070x25
h3170|swisskrono|ldsp|true|Charm eman|h3170_panel.jpg|2800x2070x18
w980|kronospan|ldsp|false|Oq|w980_panel.jpg|2800x2070x18,2620x1830x18
w1100|kronospan|ldsp|false|Alebastr oq|w1100_panel.jpg|2750x1830x16
u999|kronospan|ldsp|false|Qora|u999_panel.jpg|2800x2070x18
u963|kronospan|ldsp|false|Antrasit|u963_panel.jpg|2750x1830x18
u708|toshkent|ldsp|false|Kashmir|u708_panel.jpg|2800x2070x18
u732|toshkent|mdf|false|Chang kulrang|u732_panel.jpg|2800x2070x25
u636|toshkent|ldsp|false|Vanil|u636_panel.jpg|2800x2070x16
u560|toshkent|mdf|false|Ko'\''k|u560_panel.jpg|2800x2070x18
'

# Kromka dekorlar:  decor|manufacturer|nomi|image|formats
#   formats: comma-separated `qalinlik x kromka_eni`. h1145 and w980 carry two
#   thicknesses of the SAME dekor — the old catalog had to spend a second
#   material (and a second swatch) on each of them.
KROMKA_DEKORLAR='
h1145|egger|Sonoma eman|h1145_edge.jpg|2x19,0.4x19
h3734|egger|Yong'\''oq|h3734_edge.jpg|2x19
h1180|egger|Oq eman|h1180_edge.jpg|1x19
h1137|egger|Kulrang eman|h1137_edge.jpg|2x19
h3303|swisskrono|To'\''q yong'\''oq|h3303_edge.jpg|2x19
h3702|swisskrono|Buk|h3702_edge.jpg|1x19
h1615|swisskrono|Qarag'\''ay|h1615_edge.jpg|2x42
h3170|swisskrono|Charm eman|h3170_edge.jpg|2x22
w980|kronospan|Oq|w980_edge.jpg|2x19,0.4x19
w1100|kronospan|Alebastr oq|w1100_edge.jpg|1x19
u999|kronospan|Qora|u999_edge.jpg|2x19
u963|kronospan|Antrasit|u963_edge.jpg|2x19
u708|toshkent|Kashmir|u708_edge.jpg|1x19
u732|toshkent|Chang kulrang|u732_edge.jpg|2x19
'

create_dekor() { # manufacturer tur kod nomi tolali file_id -> dekor id
  jcall POST "$API/platform/catalog/dekorlar" "$TOKEN" "$(jq -nc \
    --arg mid "$(man_for "$1")" --arg tur "$2" --arg kod "$3" --arg nomi "$4" \
    --argjson tolali "$5" --arg fid "$6" \
    '{manufacturer_id:$mid,tur:$tur,kod:$kod,nomi:$nomi,tolali:$tolali}
     + (if $fid=="" then {} else {image_file_id:$fid} end)')" | jq -r .id
}

n_panel_dekor=0
while IFS='|' read -r decor man tur tolali nomi img formats; do
  [ -n "$decor" ] || continue
  id="$(create_dekor "$man" "$tur" "$(printf '%s' "$decor" | tr '[:lower:]' '[:upper:]')" \
        "$nomi" "$tolali" "$(upload_image "$img")")"
  put_dekor "$decor|panel" "$id" "$formats"
  n_panel_dekor=$((n_panel_dekor+1))
done <<< "$PANEL_DEKORLAR"
ok "$n_panel_dekor panel dekorlar created"

n_kromka_dekor=0
while IFS='|' read -r decor man nomi img formats; do
  [ -n "$decor" ] || continue
  id="$(create_dekor "$man" kromka "$(printf '%s' "$decor" | tr '[:lower:]' '[:upper:]')" \
        "$nomi" false "$(upload_image "$img")")"
  put_dekor "$decor|kromka" "$id" "$formats"
  n_kromka_dekor=$((n_kromka_dekor+1))
done <<< "$KROMKA_DEKORLAR"
ok "$n_kromka_dekor kromka dekorlar created"

# ============================================================================
# 5 · Provision "Mebel Master" + owner ready + 2nd branch
# ============================================================================
say "5 · Provision workshop 'Mebel Master' + owner + 2 branches"
PROV="$(jcall POST "$API/platform/workshops" "$TOKEN" "$(jq -nc \
  --arg b1phone "$B1_PHONE" --arg owner "$OWNER_LOGIN" --arg temp "$OWNER_TEMP" \
  '{workshop:{name:"Mebel Master"},
    branch:{name:"Chilonzor filiali",address:"Toshkent, Chilonzor tumani, Bunyodkor ko‘chasi 12",phone:$b1phone},
    owner:{login:$owner},temp_password:$temp}')")"
WORKSHOP_ID="$(printf '%s' "$PROV" | jq -r .workshop.id)"
BRANCH1_ID="$(printf '%s'  "$PROV" | jq -r .branch.id)"
[ -n "$BRANCH1_ID" ] && [ "$BRANCH1_ID" != null ] || die "workshop provision failed"

# Owner first login → change temp to final (token stays valid after the change).
OWNER_TOKEN="$(jcall POST "$API/auth/workshop/login" "" \
  "{\"login\":\"$OWNER_LOGIN\",\"password\":\"$OWNER_TEMP\"}" | jq -r .access_token)"
jcall POST "$API/auth/password/change" "$OWNER_TOKEN" \
  "{\"current_password\":\"$OWNER_TEMP\",\"new_password\":\"$OWNER_PW\"}" >/dev/null
ok "owner ready ($OWNER_LOGIN / $OWNER_PW)"

BRANCH2_ID="$(jcall POST "$API/workshop/branches" "$OWNER_TOKEN" "$(jq -nc \
  --arg b2phone "$B2_PHONE" \
  '{name:"Yunusobod filiali",address:"Toshkent, Yunusobod tumani, Amir Temur ko‘chasi 108",phone:$b2phone}')" | jq -r .id)"
ok "branch 2 created (Yunusobod filiali)"

branch_id_for() { case "$1" in B1) echo "$BRANCH1_ID";; B2) echo "$BRANCH2_ID";; esac; }

# ============================================================================
# 6 · Branch pricing (both branches — required before any order is placed)
# ============================================================================
say "6 · Branch pricing"
jcall PUT "$API/workshop/branches/$BRANCH1_ID/pricing" "$OWNER_TOKEN" \
  '{"cutting_rate_tiyin":50000,"edge_banding_rate_tiyin":20000}' >/dev/null
jcall PUT "$API/workshop/branches/$BRANCH2_ID/pricing" "$OWNER_TOKEN" \
  '{"cutting_rate_tiyin":60000,"edge_banding_rate_tiyin":25000}' >/dev/null
ok "pricing set on B1 and B2"

# B1 keeps the platform defaults (kerf 4 / trim 5, set at creation). B2 gets
# visibly different cutting settings so the per-branch feature is checkable by
# hand — the same parts on B1 vs B2 must yield a different fit/waste result.
jcall PATCH "$API/workshop/branches/$BRANCH2_ID" "$OWNER_TOKEN" \
  '{"kerf_mm":3,"edge_trim_mm":12}' >/dev/null
ok "cutting settings: B1 kerf 4mm/trim 5mm (default), B2 kerf 3mm/trim 12mm"

# ============================================================================
# 7 · Staff (create → first login → change temp to final)
# ============================================================================
say "7 · 5 staff with distinct per-branch permission matrices"
g() { printf '{"permission":"%s","branch_id":"%s"}' "$1" "$2"; }

create_staff() { # full_name login phone home_branch grants_json final_pw -> echoes user id
  local resp uid
  resp="$(jcall POST "$API/workshop/users" "$OWNER_TOKEN" "$(jq -nc \
    --arg fn "$1" --arg login "$2" --arg phone "$3" --arg home "$4" \
    --argjson grants "$5" --arg temp "$STAFF_TEMP" \
    '{full_name:$fn,phone:$phone,login:$login,home_branch_id:$home,grants:$grants,temp_password:$temp}')")"
  uid="$(printf '%s' "$resp" | jq -r .user.id)"
  local tok
  tok="$(jcall POST "$API/auth/workshop/login" "" \
    "{\"login\":\"$2\",\"password\":\"$STAFF_TEMP\"}" | jq -r .access_token)"
  jcall POST "$API/auth/password/change" "$tok" \
    "{\"current_password\":\"$STAFF_TEMP\",\"new_password\":\"$6\"}" >/dev/null
  printf '%s' "$uid"
}

MANAGER_ID="$(create_staff "Alisher Karimov" "manager" "+998911002030" "$BRANCH1_ID" \
  "[$(g view_orders "$BRANCH1_ID"),$(g manage_orders "$BRANCH1_ID"),$(g manage_catalog "$BRANCH1_ID"),$(g manage_inventory "$BRANCH1_ID")]" \
  "ManagerDemo123")"; ok "manager (Filial menejeri @ B1)"
CUTTER_ID="$(create_staff "Sardor Yo'ldoshev" "cutter" "+998911002031" "$BRANCH1_ID" \
  "[$(g view_orders "$BRANCH1_ID"),$(g process_production "$BRANCH1_ID")]" \
  "CutterDemo123")"; ok "cutter (Usta kesish @ B1)"
EDGER_ID="$(create_staff "Jamshid Rahimov" "edger" "+998911002032" "$BRANCH1_ID" \
  "[$(g process_production "$BRANCH1_ID"),$(g process_production "$BRANCH2_ID")]" \
  "EdgerDemo123")"; ok "edger (Usta kromka @ B1 + B2)"
USTA2_ID="$(create_staff "Bekzod Tursunov" "usta2" "+998911002033" "$BRANCH2_ID" \
  "[$(g view_orders "$BRANCH2_ID"),$(g process_production "$BRANCH2_ID"),$(g manage_inventory "$BRANCH2_ID")]" \
  "Usta2Demo123")"; ok "usta2 (Yunusobod ustasi @ B2, home @ B2)"
ACCOUNTANT_ID="$(create_staff "Nigora Saidova" "accountant" "+998911002034" "$BRANCH1_ID" \
  "[$(g manage_finance "$BRANCH1_ID"),$(g manage_finance "$BRANCH2_ID"),$(g view_finance_reports "$BRANCH1_ID"),$(g view_finance_reports "$BRANCH2_ID")]" \
  "HisobchiDemo123")"; ok "accountant (Hisobchi @ B1 + B2)"

# ============================================================================
# 8 · Suppliers + branch attach (every dekor, every format, both branches) + stock
# ============================================================================
say "8 · Suppliers, then attach every dekor format on both branches with stock"
# Create suppliers once (workshop-scoped); reuse their ids on every stock-in so
# we don't spawn a duplicate supplier row per stock-in.
sup_id() { # name phone -> id
  jcall POST "$API/workshop/branches/$BRANCH1_ID/suppliers" "$OWNER_TOKEN" \
    "{\"name\":\"$1\",\"phone\":\"$2\"}" | jq -r .id
}
SUP1="$(sup_id "Egger Rasmiy Distribyutor" "+998712300010")"
SUP2="$(sup_id "Kronospan Osiyo" "+998712300020")"
SUP3="$(sup_id "Toshkent Plita Zavodi" "+998712300030")"
SUP4="$(sup_id "Mebel Furnitura Savdo" "+998712300040")"
SUPPLIERS=("$SUP1" "$SUP2" "$SUP3" "$SUP4")
ok "4 suppliers created"

# One dekor + every o'lcham the branch carries of it, in a single all-or-nothing
# attach — the real flow the workshop UI drives. The endpoint takes a LIST of
# dekorlar (the UI attaches many at once); seeding one per call keeps the price
# tables below readable, and the wire shape is identical either way.
attach() { # branch_id dekor_id formats_json -> response body
  jcall POST "$API/workshop/branches/$1/materials" "$OWNER_TOKEN" \
    "$(jq -nc --arg d "$2" --argjson f "$3" '{items:[{dekor_id:$d,formats:$f}]}')"
}

# `qalinlik_mm` goes over the wire as a STRING: it is a Decimal server-side, and
# 0.4 as a JSON float is the one value in this file that a float round-trip could
# nudge. Everything else is an integer.
format_json() { # qalinlik uzunlik eni kromka_eni price min_stock   ("" = omit the field)
  local out="\"qalinlik_mm\":\"$1\""
  [ -n "$2" ] && out="$out,\"uzunlik_mm\":$2"
  [ -n "$3" ] && out="$out,\"eni_mm\":$3"
  [ -n "$4" ] && out="$out,\"kromka_eni_mm\":$4"
  [ -n "$5" ] && out="$out,\"price_tiyin\":$5"     # omitted → server default 0
  printf '{%s,"min_stock":%s}' "$out" "$6"
}

# Match a created row back to the format we asked for by its own numbers, not by
# list position. A mis-mapping here is invisible — every id is a plausible uuid —
# and would land B2's stock-ins and orders on B1's shelves.
pick_bm() { # response qalinlik uzunlik eni kromka_eni -> branch_material id | ""
  printf '%s' "$1" | jq -r --arg q "$2" --arg u "$3" --arg e "$4" --arg k "$5" '
    .created
    | map(select(
        ((.qalinlik_mm | tostring | tonumber) == ($q | tonumber))
        and ((.uzunlik_mm // "" | tostring) == $u)
        and ((.eni_mm // "" | tostring) == $e)
        and ((.kromka_eni_mm // "" | tostring) == $k)))
    | (.[0].id // "")'
}

stockin() { # branch_id branch_material_id quantity supplier_id unit_price_tiyin
  jcall POST "$API/workshop/branches/$1/stock-in" "$OWNER_TOKEN" \
    "{\"branch_material_id\":\"$2\",\"quantity\":$3,\"unit_price_tiyin\":$5,\"supplier_id\":\"$4\",\"note\":\"Demo boshlang'ich zaxira\"}" >/dev/null
}

# Two decors that no order touches, planted below min_stock for the low-stock UI.
LOWSTOCK="u636 u560"
is_lowstock() { case " $LOWSTOCK " in *" $1 "*) return 0;; *) return 1;; esac; }

# Sale price per format, spread over the catalog so no two rows look alike.
# Panel prices stay even so qty-2 parts divide cleanly.
panel_price()  { printf '%s' $(( 30000000 + $1*400000 + $2*900000 + $3*1500000 )); } # dekor_idx fmt_idx b2
kromka_price() { printf '%s' $(( 900 + $1*40 + $2*150 + $3*120 )); }                 # tiyin per mm

n_bm=0
for i in "${!DEKOR_KEY[@]}"; do
  key="${DEKOR_KEY[$i]}"; did="${DEKOR_ID[$i]}"
  decor="${key%%|*}"; shape="${key##*|}"
  sup="${SUPPLIERS[$((i % 4))]}"
  IFS=',' read -r -a FORMATS <<< "${DEKOR_FMT[$i]}"

  for bcode in B1 B2; do
    bid="$(branch_id_for "$bcode")"
    # B2 is the pricier, better-stocked branch — the same knob the old seed used.
    bump=0; [ "$bcode" = B2 ] && bump=1

    # Pass 1 — build the batch.
    items=""; f=0
    for spec in "${FORMATS[@]}"; do
      unpriced=0
      case "$spec" in '~'*) unpriced=1; spec="${spec#\~}";; esac
      if [ "$shape" = panel ]; then
        IFS='x' read -r len wid thick <<< "$spec"
        price="$(panel_price "$i" "$f" "$bump")"
        [ "$unpriced" = 1 ] && price=""
        mins=5; if is_lowstock "$decor"; then mins=60; fi
        item="$(format_json "$thick" "$len" "$wid" "" "$price" "$mins")"
      else
        IFS='x' read -r thick ew <<< "$spec"
        item="$(format_json "$thick" "" "" "$ew" "$(kromka_price "$i" "$f" "$bump")" 20000)"
      fi
      items="${items:+$items,}$item"
      f=$((f+1))
    done
    resp="$(attach "$bid" "$did" "[$items]")"

    # Pass 2 — remember each new id under its format key, then stock it.
    # Purchase (kirim) price ≈ 85% of the branch's sale price — realistic margin.
    f=0
    for spec in "${FORMATS[@]}"; do
      spec="${spec#\~}"
      if [ "$shape" = panel ]; then
        IFS='x' read -r len wid thick <<< "$spec"
        bmid="$(pick_bm "$resp" "$thick" "$len" "$wid" "")"
        if is_lowstock "$decor"; then qty=$(( 8 - bump*2 )); else qty=$(( 45 + i*4 + f*7 + bump*12 )); fi
        buy=$(( $(panel_price "$i" "$f" "$bump") * 85 / 100 ))
      else
        IFS='x' read -r thick ew <<< "$spec"
        bmid="$(pick_bm "$resp" "$thick" "" "" "$ew")"
        qty=$(( 180000 + i*8000 + f*5000 + bump*40000 ))
        buy=$(( $(kromka_price "$i" "$f" "$bump") * 85 / 100 ))
      fi
      [ -n "$bmid" ] || die "attach on $bcode returned no row for $decor $shape $spec"
      put_bm "$bcode|$decor|$shape|$spec" "$bmid"
      stockin "$bid" "$bmid" "$qty" "$sup" "$buy"
      n_bm=$((n_bm+1)); f=$((f+1))
    done
  done
done
ok "$n_bm branch materials attached and stocked (low-stock: Vanil, Ko'k · unpriced: Sonoma eman 16 mm)"

# ============================================================================
# 9 · Skeleton workshops (so the admin list looks real)
# ============================================================================
say "9 · 2 skeleton workshops (Atlas Mebel, Nur Mebel)"
skeleton() { # name owner_login branch address phone
  jcall POST "$API/platform/workshops" "$TOKEN" "$(jq -nc \
    --arg name "$1" --arg owner "$2" --arg bn "$3" --arg addr "$4" --arg phone "$5" \
    --arg temp "SkeletonTmp123" \
    '{workshop:{name:$name},branch:{name:$bn,address:$addr,phone:$phone},
      owner:{login:$owner},temp_password:$temp}')" >/dev/null
}
skeleton "Atlas Mebel" "owner-atlas" "Sergeli filiali" "Toshkent, Sergeli tumani, Yangi Sergeli 7" "+998712400050"
skeleton "Nur Mebel"   "owner-nur"   "Olmazor filiali" "Toshkent, Olmazor tumani, Universitet ko'chasi 3" "+998712400060"
ok "2 skeleton workshops created"

# ============================================================================
# 10 · Clients (OTP login, dev code 000000)
# ============================================================================
say "10 · Client OTP logins"
client_token() { # phone name -> access token
  jcall POST "$API/auth/client/otp/request" "" "{\"phone\":\"$1\"}" >/dev/null
  jcall POST "$API/auth/client/otp/verify" "" \
    "{\"phone\":\"$1\",\"code\":\"$OTP_CODE\",\"name\":\"$2\"}" | jq -r .access_token
}
DILSHOD_TOKEN="$(client_token "$DILSHOD_PHONE" "$DILSHOD_NAME")"
AZIZA_TOKEN="$(client_token "$AZIZA_PHONE" "$AZIZA_NAME")"
ok "clients logged in (Dilshod, Aziza)"

# ─── Cutting part / template builders ────────────────────────────────────────
# The parts snapshot keeps its `material_id` key — the reshape re-pointed what it
# holds (a branch_material id now, not a platform material id) without renaming
# the key, so old snapshots and new ones stay readable by the same code.
band() { printf '{"material_id":"%s","source":"shop"}' "$1"; }
part() { # ref panel l w q top bottom left right
  printf '{"part_ref":"%s","material_id":"%s","material_source":"shop","length_mm":%s,"width_mm":%s,"quantity":%s,"edge_top":%s,"edge_bottom":%s,"edge_left":%s,"edge_right":%s}' \
    "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9"
}
tmpl_bookshelf() { # panel edge (Kitob javoni — white)
  local p="$1" e="$2" N=null
  printf '[%s,%s,%s,%s,%s]' \
    "$(part yon_chap  "$p" 600 400 1 "$(band "$e")" "$N" "$(band "$e")" "$N")" \
    "$(part yon_ong   "$p" 600 400 1 "$(band "$e")" "$N" "$N" "$(band "$e")")" \
    "$(part tokcha_1  "$p" 564 380 2 "$(band "$e")" "$N" "$N" "$N")" \
    "$(part tokcha_2  "$p" 564 380 1 "$(band "$e")" "$N" "$N" "$N")" \
    "$(part orqa      "$p" 580 596 1 "$N" "$N" "$N" "$N")"
}
tmpl_wardrobe() { # panel edge (Shkaf eshiklari — anthracite, full edge)
  local p="$1" e="$2" N=null
  printf '[%s,%s,%s,%s]' \
    "$(part eshik_chap "$p" 700 396 1 "$(band "$e")" "$(band "$e")" "$(band "$e")" "$(band "$e")")" \
    "$(part eshik_ong  "$p" 700 396 1 "$(band "$e")" "$(band "$e")" "$(band "$e")" "$(band "$e")")" \
    "$(part tortma     "$p" 700 180 1 "$(band "$e")" "$(band "$e")" "$N" "$N")" \
    "$(part tokcha     "$p" 760 480 1 "$N" "$N" "$N" "$N")"
}
tmpl_kitchen() { # panel edge (Oshxona stoli — top with full edge)
  local p="$1" e="$2" N=null
  printf '[%s,%s,%s,%s]' \
    "$(part stol_usti "$p" 900 600 1 "$(band "$e")" "$(band "$e")" "$(band "$e")" "$(band "$e")")" \
    "$(part oyoq_chap "$p" 560 500 1 "$(band "$e")" "$N" "$N" "$N")" \
    "$(part oyoq_ong  "$p" 560 500 1 "$(band "$e")" "$N" "$N" "$N")" \
    "$(part boglam    "$p" 820 250 1 "$(band "$e")" "$N" "$N" "$N")"
}
# A template now resolves per branch: the ids it puts in the parts snapshot are
# branch materials, and a draft may only reference the ones its own branch
# carries. Every template picks the 18 mm / 2 mm standard formats.
parts_for() { # template branch_code
  local p e
  case "$1" in
    bookshelf)      p="$(bm_id "$2|w980|panel|2800x2070x18")";  e="$(bm_id "$2|w980|kromka|2x19")";;
    wardrobe)       p="$(bm_id "$2|u963|panel|2750x1830x18")";  e="$(bm_id "$2|u963|kromka|2x19")";;
    kitchen_oak)    p="$(bm_id "$2|h1145|panel|2800x2070x18")"; e="$(bm_id "$2|h1145|kromka|2x19")";;
    kitchen_walnut) p="$(bm_id "$2|h3734|panel|2800x2070x18")"; e="$(bm_id "$2|h3734|kromka|2x19")";;
    *) die "unknown template: $1" ;;
  esac
  [ -n "$p" ] && [ -n "$e" ] || die "template $1 has no branch material on $2"
  case "$1" in
    bookshelf) tmpl_bookshelf "$p" "$e";;
    wardrobe)  tmpl_wardrobe  "$p" "$e";;
    *)         tmpl_kitchen   "$p" "$e";;
  esac
}

DRAFT_ID=""
make_draft() { # client_token branch_code template optimize(0/1)
  DRAFT_ID="$(jcall POST "$API/client/cutting-drafts" "$1" | jq -r .id)"
  jcall PATCH "$API/client/cutting-drafts/$DRAFT_ID" "$1" \
    "{\"preferred_branch_id\":\"$(branch_id_for "$2")\",\"parts_snapshot\":$(parts_for "$3" "$2")}" >/dev/null
  [ "$4" = 1 ] && jcall POST "$API/client/cutting-drafts/$DRAFT_ID/optimize" "$1" >/dev/null
  return 0
}

ORDER_ID=""; VERSION=""; ORDER_TOTAL=""
place_order() { # client_token branch_id name phone note
  local resp
  resp="$(jcall POST "$API/client/orders" "$1" "$(jq -nc \
    --arg d "$DRAFT_ID" --arg b "$2" --arg n "$3" --arg p "$4" --arg note "$5" \
    '{draft_id:$d,branch_id:$b,contact_name:$n,contact_phone:$p,note_client:$note}')")"
  ORDER_ID="$(printf '%s' "$resp" | jq -r .id)"
  VERSION="$(printf '%s' "$resp" | jq -r .version)"
  ORDER_TOTAL="$(printf '%s' "$resp" | jq -r .total_tiyin)"
}
ws_step() { # order_id endpoint [extra_kv]
  local resp
  resp="$(jcall POST "$API/workshop/orders/$1/$2" "$OWNER_TOKEN" "{\"version\":$VERSION${3:+,$3}}")"
  VERSION="$(printf '%s' "$resp" | jq -r .version)"
}
advance_to() { # order_id target cutter_id edger_id
  local oid="$1" target="$2" cut="$3" edg="$4"
  [ "$target" = new ] && return 0
  ws_step "$oid" approve
  # Assignment is metadata (no status change): a `confirmed` demo order is left
  # assigned-but-unstarted, so it sits queued in the master's Ishlarim station.
  ws_step "$oid" assign "\"cutter_user_id\":\"$cut\",\"edger_user_id\":\"$edg\""
  [ "$target" = confirmed ] && return 0
  ws_step "$oid" start-cutting    # confirmed → cutting (the worker's Boshlash)
  [ "$target" = cutting ] && return 0
  ws_step "$oid" cutting-done
  # The edge_banding demo order shows a started kromka job (the edger's hero card).
  [ "$target" = edge_banding ] && { ws_step "$oid" start-banding; return 0; }
  ws_step "$oid" banding-done
  [ "$target" = ready ] && return 0
  ws_step "$oid" mark-collected   # ready → completed
  return 0
}
# A finance date N days ago, CLAMPED to the first of the current month. The
# finance list/summary default to the current calendar month, so entries dated
# before the 1st would be hidden until the user widens the date filter — this
# keeps the whole ledger visible by default while still spreading dates when the
# month is far enough along. Portable (jq only): never produces a future date.
fin_date() { # days_ago -> YYYY-MM-DD (>= first of this month)
  # Pure epoch arithmetic — no gmtime-array indexing, whose element order differs
  # across jq builds. midnight = epoch floored to the UTC day; first-of-month is
  # (day-of-month - 1) days before that.
  jq -rn --argjson n "$1" '
    (now|floor) as $now
    | ($now - ($now % 86400)) as $midnight
    | (now|gmtime|strftime("%d")|tonumber) as $dom
    | ($midnight - (($dom - 1) * 86400)) as $first_of_month
    | ([$midnight - ($n * 86400), $first_of_month] | max)
    | gmtime | strftime("%Y-%m-%d")'
}
record_income() { # order_id amount method days_ago
  jcall POST "$API/workshop/finance/income" "$OWNER_TOKEN" \
    "{\"type\":\"order_payment\",\"order_id\":\"$1\",\"amount_tiyin\":$2,\"method\":\"$3\",\"received_on\":\"$(fin_date "$4")\",\"note\":\"Buyurtma to'lovi\"}" >/dev/null
}

# ============================================================================
# 11 · Standalone client drafts (Dilshod) — never ordered, so they persist
# ============================================================================
say "11 · 2 saved cutting drafts for Dilshod (1 optimized, 1 not)"
make_draft "$DILSHOD_TOKEN" B1 kitchen_oak 1; ok "draft (optimized)"
make_draft "$DILSHOD_TOKEN" B2 wardrobe    0; ok "draft (not optimized)"

# ============================================================================
# 12 · 9 orders across both branches, driven to every status
# ============================================================================
say "12 · 9 orders covering every status on both branches"
# client|name|phone|branch|status|template|pay|days_ago|note
ORDERS='
DILSHOD|Dilshod|+998901112233|B1|new|bookshelf|none|0|Yangi buyurtma, tasdiqlanishini kutmoqda
DILSHOD|Dilshod|+998901112233|B1|confirmed|wardrobe|none|1|Tasdiqlandi, navbatda
DILSHOD|Dilshod|+998901112233|B1|cutting|kitchen_oak|none|2|Hozir kesilmoqda
DILSHOD|Dilshod|+998901112233|B2|edge_banding|bookshelf|none|3|Kromka yopishtirilmoqda
DILSHOD|Dilshod|+998901112233|B1|ready|wardrobe|partial_cash|1|Olib ketishga tayyor
DILSHOD|Dilshod|+998901112233|B2|ready|kitchen_walnut|full_bank|2|Tayyor, to'\''liq to'\''langan
AZIZA|Aziza|+998901234455|B1|completed|bookshelf|full_cash|6|Topshirilgan buyurtma
AZIZA|Aziza|+998901234455|B2|completed|wardrobe|full_bank|8|Topshirilgan buyurtma
AZIZA|Aziza|+998901234455|B1|cancelled|kitchen_oak|none|4|Rejadan qaytdim
'

while IFS='|' read -r cli name phone branch status tmpl pay dago note; do
  [ -n "$cli" ] || continue
  case "$cli" in DILSHOD) tok="$DILSHOD_TOKEN";; AZIZA) tok="$AZIZA_TOKEN";; esac
  bid="$(branch_id_for "$branch")"
  if [ "$branch" = B2 ]; then cut="$USTA2_ID"; edg="$USTA2_ID"; else cut="$CUTTER_ID"; edg="$EDGER_ID"; fi

  make_draft "$tok" "$branch" "$tmpl" 1
  place_order "$tok" "$bid" "$name" "$phone" "$note"

  if [ "$status" = cancelled ]; then
    jcall POST "$API/client/orders/$ORDER_ID/cancel" "$tok" \
      "{\"version\":$VERSION,\"reason\":\"Reja o'zgardi\"}" >/dev/null
  else
    advance_to "$ORDER_ID" "$status" "$cut" "$edg"
  fi

  case "$pay" in
    partial_cash) record_income "$ORDER_ID" "$(( ORDER_TOTAL * 60 / 100 ))" cash "$dago";;
    full_cash)    record_income "$ORDER_ID" "$ORDER_TOTAL" cash "$dago";;
    full_bank)    record_income "$ORDER_ID" "$ORDER_TOTAL" bank_transfer "$dago";;
  esac
  ok "$name · $branch · $status${pay:+ · $pay}"
done <<< "$ORDERS"

# ============================================================================
# 13 · Expenses (spread across categories, branches, and the last 30 days)
# ============================================================================
say "13 · Workshop expenses"
# category|branch(-=workshop-wide)|amount_tiyin|days_ago|description|vendor
EXPENSES='
rent|B1|500000000|28|Chilonzor filiali ijara haqi|Toshkent Ko'\''chmas Mulk
rent|B2|420000000|27|Yunusobod filiali ijara haqi|Amir Temur Biznes Markaz
utilities|B1|85000000|20|Elektr va suv|Hududgaz
utilities|B2|72000000|19|Elektr va suv|Hududgaz
raw_materials|B1|1200000000|15|LDSP plitalar partiyasi|Egger Rasmiy Distribyutor
supplies|B2|45000000|12|Kromka va furnitura|Mebel Furnitura Savdo
transport|-|60000000|10|Yetkazib berish xizmati|Express Logistika
equipment|B1|350000000|22|Forma kesish dastgohi ehtiyot qismlari|CNC Servis
marketing|-|90000000|8|Instagram reklama kampaniyasi|SMM Agentlik
salary|B1|800000000|5|Ustalar oyligi|-
taxes_and_fees|-|210000000|3|Soliq to'\''lovlari|-
'
n_exp=0
while IFS='|' read -r cat branch amount dago desc vendor; do
  [ -n "$cat" ] || continue
  bid=""; [ "$branch" != - ] && bid="$(branch_id_for "$branch")"
  on="$(fin_date "$dago")"
  body="$(jq -nc --arg cat "$cat" --argjson amt "$amount" --arg on "$on" \
    --arg desc "$desc" --arg vendor "$vendor" --arg bid "$bid" \
    '{category:$cat, amount_tiyin:$amt, incurred_on:$on, description:$desc}
     + (if $bid == "" then {} else {branch_id:$bid} end)
     + (if $vendor == "-" or $vendor == "" then {} else {vendor:$vendor} end)')"
  jcall POST "$API/workshop/finance/expenses" "$OWNER_TOKEN" "$body" >/dev/null
  n_exp=$((n_exp+1))
done <<< "$EXPENSES"
ok "$n_exp expenses recorded"

# ============================================================================
# 14 · Seeded error record (populates the admin error monitor)
# ============================================================================
say "14 · Seed one platform error record (error monitor)"
dc exec -T backend python -m app.cli seed-error-record \
  --code "cutting.optimize.timeout" --module "cutting" \
  --message "Optimizatsiya vaqti tugadi (demo yozuvi)" >/dev/null
ok "error record seeded"

# ============================================================================
# 15 · Summary
# ============================================================================
cat <<SUMMARY

$(printf '\033[1;32m')╔══════════════════════════════════════════════════════════════════════╗
║  ✅  Demo world ready — "Mebel Master" + 2 skeleton workshops         ║
╚══════════════════════════════════════════════════════════════════════╝$(printf '\033[0m')

  SUPERADMIN   admin / AdminDemo123   (operator: temp password, reset-required)
  WORKSHOP     owner / OwnerDemo123
               manager / ManagerDemo123     cutter / CutterDemo123
               edger / EdgerDemo123         usta2 / Usta2Demo123
               accountant / HisobchiDemo123
  CLIENT       $DILSHOD_PHONE (Dilshod) · $AZIZA_PHONE (Aziza) · OTP $OTP_CODE

  30 dekorlar (with images) · $n_bm branch materials across both branches, all
  stocked · 9 orders (every status) · finance ledger populated · full credential
  list is in this file's header.

  Rebuild anytime with:  bash deploy/seed-demo.sh --reset
SUMMARY
