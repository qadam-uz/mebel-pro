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
#   real; 4 manufacturers; 16 panels + 16 edges (each with a catalog image);
#   both branches carry all 32 materials with stock; finance ledger populated.
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
# 4 · Manufacturers + 32 materials (each with a catalog image)
# ============================================================================
say "4 · Manufacturers + 16 panels + 16 edges (uploading catalog images)"

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

# Upload a swatch and echo its file_id (empty on any problem — material is then
# created without an image). One upload per material: a file attaches exactly
# once, so materials that share a decor still upload their own copy.
upload_image() { # img-basename -> file_id | ""
  local path="$ASSETS_DIR/$1" resp code
  [ -f "$path" ] || { warn "image missing: $1 (material created without image)"; return 0; }
  resp="$(curl -sS -X POST "$API/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "upload=@$path;type=image/jpeg" -w $'\n%{http_code}')" || true
  code="${resp##*$'\n'}"
  case "$code" in
    2*) printf '%s' "${resp%$'\n'*}" | jq -r .id ;;
    *)  warn "upload failed ($code) for $1"; return 0 ;;
  esac
}

# Parallel arrays (bash 3.2 has no associative arrays): decor+kind -> material id.
MAT_DECOR=(); MAT_KIND=(); MAT_ID=()
mat_id() { # decor kind -> first matching material id
  local i
  for i in "${!MAT_ID[@]}"; do
    [ "${MAT_DECOR[$i]}" = "$1" ] && [ "${MAT_KIND[$i]}" = "$2" ] && { printf '%s' "${MAT_ID[$i]}"; return; }
  done
}

# Panels:  decor|manufacturer|type|length|width|thickness|grain|color|image
PANELS='
h1145|egger|dsp|2800|2070|18|true|Sonoma eman|h1145_panel.jpg
h3734|egger|dsp|2800|2070|18|true|Yong'\''oq|h3734_panel.jpg
h1180|egger|dsp|2750|1830|16|true|Oq eman|h1180_panel.jpg
h1137|egger|dsp|2800|2070|18|true|Kulrang eman|h1137_panel.jpg
h3303|swisskrono|mdf|2800|2070|18|true|To'\''q yong'\''oq|h3303_panel.jpg
h3702|swisskrono|dsp|2750|1830|16|true|Buk|h3702_panel.jpg
h1615|swisskrono|dsp|2800|2070|25|true|Qarag'\''ay|h1615_panel.jpg
h3170|swisskrono|dsp|2800|2070|18|true|Charm eman|h3170_panel.jpg
w980|kronospan|dsp|2800|2070|18|false|Oq|w980_panel.jpg
w1100|kronospan|dsp|2750|1830|16|false|Alebastr oq|w1100_panel.jpg
u999|kronospan|dsp|2800|2070|18|false|Qora|u999_panel.jpg
u963|kronospan|dsp|2750|1830|18|false|Antrasit|u963_panel.jpg
u708|toshkent|dsp|2800|2070|18|false|Kashmir|u708_panel.jpg
u732|toshkent|mdf|2800|2070|25|false|Chang kulrang|u732_panel.jpg
u636|toshkent|dsp|2800|2070|16|false|Vanil|u636_panel.jpg
u560|toshkent|mdf|2800|2070|18|false|Ko'\''k|u560_panel.jpg
'

# Edges:  decor|manufacturer|thickness|edge_width|color|image
EDGES='
h1145|egger|2|19|Sonoma eman|h1145_edge.jpg
h3734|egger|2|19|Yong'\''oq|h3734_edge.jpg
h1180|egger|1|19|Oq eman|h1180_edge.jpg
h1137|egger|2|19|Kulrang eman|h1137_edge.jpg
h3303|swisskrono|2|19|To'\''q yong'\''oq|h3303_edge.jpg
h3702|swisskrono|1|19|Buk|h3702_edge.jpg
h1615|swisskrono|2|42|Qarag'\''ay|h1615_edge.jpg
h3170|swisskrono|2|22|Charm eman|h3170_edge.jpg
w980|kronospan|2|19|Oq|w980_edge.jpg
w1100|kronospan|1|19|Alebastr oq|w1100_edge.jpg
u999|kronospan|2|19|Qora|u999_edge.jpg
u963|kronospan|2|19|Antrasit|u963_edge.jpg
u708|toshkent|1|19|Kashmir|u708_edge.jpg
u732|toshkent|2|19|Chang kulrang|u732_edge.jpg
w980|kronospan|0.4|19|Oq|w980_edge_thin.jpg
h1145|egger|0.4|19|Sonoma eman|h1145_edge_thin.jpg
'

json_escape() { printf '%s' "$1" | jq -Rrs @json | sed 's/^"//; s/"$//'; }

n_panels=0
while IFS='|' read -r decor man type len wid thick grain color img; do
  [ -n "$decor" ] || continue
  fid="$(upload_image "$img")"
  body="$(jq -nc \
    --arg mid "$(man_for "$man")" --arg type "$type" \
    --arg thick "$thick" --arg color "$color" --arg decor "$(printf '%s' "$decor" | tr '[:lower:]' '[:upper:]')" \
    --argjson len "$len" --argjson wid "$wid" --argjson grain "$grain" \
    --arg fid "$fid" \
    '{kind:"panel",manufacturer_id:$mid,type:$type,thickness_mm:$thick,
      color:$color,decor_code:$decor,panel_length_mm:$len,panel_width_mm:$wid,
      grain_direction:$grain} + (if $fid=="" then {} else {image_file_id:$fid} end)')"
  id="$(jcall POST "$API/platform/catalog/materials" "$TOKEN" "$body" | jq -r .id)"
  MAT_DECOR+=("$decor"); MAT_KIND+=("panel"); MAT_ID+=("$id")
  n_panels=$((n_panels+1))
done <<< "$PANELS"
ok "$n_panels panels created"

n_edges=0
while IFS='|' read -r decor man thick edge_width color img; do
  [ -n "$decor" ] || continue
  fid="$(upload_image "$img")"
  body="$(jq -nc \
    --arg mid "$(man_for "$man")" --arg thick "$thick" --argjson edge_width "$edge_width" \
    --arg color "$color" --arg decor "$(printf '%s' "$decor" | tr '[:lower:]' '[:upper:]')" --arg fid "$fid" \
    '{kind:"edge",manufacturer_id:$mid,thickness_mm:$thick,
      color:$color,decor_code:$decor,edge_width_mm:$edge_width} + (if $fid=="" then {} else {image_file_id:$fid} end)')"
  id="$(jcall POST "$API/platform/catalog/materials" "$TOKEN" "$body" | jq -r .id)"
  MAT_DECOR+=("$decor"); MAT_KIND+=("edge"); MAT_ID+=("$id")
  n_edges=$((n_edges+1))
done <<< "$EDGES"
ok "$n_edges edges created"

# Named handles for the order templates.
W980_P="$(mat_id w980 panel)";  W980_E="$(mat_id w980 edge)"
U963_P="$(mat_id u963 panel)";  U963_E="$(mat_id u963 edge)"
H1145_P="$(mat_id h1145 panel)"; H1145_E="$(mat_id h1145 edge)"
H3734_P="$(mat_id h3734 panel)"; H3734_E="$(mat_id h3734 edge)"

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
  "[$(g view_dashboard "$BRANCH1_ID"),$(g manage_orders "$BRANCH1_ID"),$(g manage_catalog "$BRANCH1_ID"),$(g manage_inventory "$BRANCH1_ID")]" \
  "ManagerDemo123")"; ok "manager (Filial menejeri @ B1)"
CUTTER_ID="$(create_staff "Sardor Yo'ldoshev" "cutter" "+998911002031" "$BRANCH1_ID" \
  "[$(g view_dashboard "$BRANCH1_ID"),$(g process_production "$BRANCH1_ID")]" \
  "CutterDemo123")"; ok "cutter (Usta kesish @ B1)"
EDGER_ID="$(create_staff "Jamshid Rahimov" "edger" "+998911002032" "$BRANCH1_ID" \
  "[$(g process_production "$BRANCH1_ID"),$(g process_production "$BRANCH2_ID")]" \
  "EdgerDemo123")"; ok "edger (Usta kromka @ B1 + B2)"
USTA2_ID="$(create_staff "Bekzod Tursunov" "usta2" "+998911002033" "$BRANCH2_ID" \
  "[$(g view_dashboard "$BRANCH2_ID"),$(g process_production "$BRANCH2_ID"),$(g manage_inventory "$BRANCH2_ID")]" \
  "Usta2Demo123")"; ok "usta2 (Yunusobod ustasi @ B2, home @ B2)"
ACCOUNTANT_ID="$(create_staff "Nigora Saidova" "accountant" "+998911002034" "$BRANCH1_ID" \
  "[$(g manage_finance "$BRANCH1_ID"),$(g manage_finance "$BRANCH2_ID"),$(g view_finance_reports "$BRANCH1_ID"),$(g view_finance_reports "$BRANCH2_ID")]" \
  "HisobchiDemo123")"; ok "accountant (Hisobchi @ B1 + B2)"

# ============================================================================
# 8 · Suppliers + branch carry (all 32 on both branches) + stock-ins
# ============================================================================
say "8 · Suppliers, then carry all 32 materials on both branches with stock"
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

carry() { # branch_id material_id price_tiyin min_stock
  jcall POST "$API/workshop/branches/$1/materials" "$OWNER_TOKEN" \
    "{\"material_id\":\"$2\",\"price_tiyin\":$3,\"min_stock\":$4}" >/dev/null
}
stockin() { # branch_id material_id quantity supplier_id unit_price_tiyin
  jcall POST "$API/workshop/branches/$1/stock-in" "$OWNER_TOKEN" \
    "{\"material_id\":\"$2\",\"quantity\":$3,\"unit_price_tiyin\":$5,\"supplier_id\":\"$4\",\"note\":\"Demo boshlang'ich zaxira\"}" >/dev/null
}

# Two materials that no order touches, planted below min_stock for the low-stock UI.
LOWSTOCK="u636 u560"
is_lowstock() { case " $LOWSTOCK " in *" $1 "*) return 0;; *) return 1;; esac; }

idx=0
for i in "${!MAT_ID[@]}"; do
  mid="${MAT_ID[$i]}"; kind="${MAT_KIND[$i]}"; decor="${MAT_DECOR[$i]}"
  sup="${SUPPLIERS[$((idx % 4))]}"
  if [ "$kind" = panel ]; then
    p1=$(( 30000000 + idx*400000 )); p2=$(( p1 + 1500000 ))   # even → safe for qty-2 parts
    # Purchase (kirim) price ≈ 85% of the branch's sale price — realistic margin.
    b1=$(( p1 * 85 / 100 )); b2=$(( p2 * 85 / 100 ))
    if is_lowstock "$decor"; then
      carry "$BRANCH1_ID" "$mid" "$p1" 60; stockin "$BRANCH1_ID" "$mid" 8 "$sup" "$b1"
      carry "$BRANCH2_ID" "$mid" "$p2" 60; stockin "$BRANCH2_ID" "$mid" 6 "$sup" "$b2"
    else
      q=$(( 45 + idx*4 ))
      carry "$BRANCH1_ID" "$mid" "$p1" 5; stockin "$BRANCH1_ID" "$mid" "$q" "$sup" "$b1"
      carry "$BRANCH2_ID" "$mid" "$p2" 5; stockin "$BRANCH2_ID" "$mid" $(( q + 12 )) "$sup" "$b2"
    fi
  else
    e1=$(( 900 + idx*40 )); e2=$(( e1 + 120 ))   # tiyin per mm
    be1=$(( e1 * 85 / 100 )); be2=$(( e2 * 85 / 100 ))        # kirim per metre
    q=$(( 180000 + idx*8000 ))
    carry "$BRANCH1_ID" "$mid" "$e1" 20000; stockin "$BRANCH1_ID" "$mid" "$q" "$sup" "$be1"
    carry "$BRANCH2_ID" "$mid" "$e2" 20000; stockin "$BRANCH2_ID" "$mid" $(( q + 40000 )) "$sup" "$be2"
  fi
  idx=$((idx+1))
done
ok "64 branch-material rows carried and stocked (2 planted low-stock: Vanil, Fjord Ko'k)"

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
parts_for() { case "$1" in
  bookshelf)      tmpl_bookshelf "$W980_P"  "$W980_E";;
  wardrobe)       tmpl_wardrobe  "$U963_P"  "$U963_E";;
  kitchen_oak)    tmpl_kitchen   "$H1145_P" "$H1145_E";;
  kitchen_walnut) tmpl_kitchen   "$H3734_P" "$H3734_E";;
esac; }

DRAFT_ID=""
make_draft() { # client_token branch_id template optimize(0/1)
  DRAFT_ID="$(jcall POST "$API/client/cutting-drafts" "$1" | jq -r .id)"
  jcall PATCH "$API/client/cutting-drafts/$DRAFT_ID" "$1" \
    "{\"preferred_branch_id\":\"$2\",\"parts_snapshot\":$(parts_for "$3")}" >/dev/null
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
make_draft "$DILSHOD_TOKEN" "$BRANCH1_ID" kitchen_oak 1; ok "draft (optimized)"
make_draft "$DILSHOD_TOKEN" "$BRANCH2_ID" wardrobe    0; ok "draft (not optimized)"

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

  make_draft "$tok" "$bid" "$tmpl" 1
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

  32 materials (with images) · both branches stocked · 9 orders (every status)
  · finance ledger populated · full credential list is in this file's header.

  Rebuild anytime with:  bash deploy/seed-demo.sh --reset
SUMMARY
