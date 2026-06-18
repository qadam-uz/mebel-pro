#!/usr/bin/env bash
#
# Seed the running DEV stack with demo catalog data so the client SPA has
# panels/edges to exercise the cutting editor, quoting and ordering.
#
# It mirrors the provisioning flow the E2E suite uses (platform admin →
# workshop+branch → manufacturer → panel/edge materials → branch carry,
# pricing and stock), but against the dev database (compose `mebel`).
#
# Usage (from repo root, with `docker compose up -d` already running):
#   bash deploy/seed-dev-data.sh
#
# Re-running creates a FRESH workshop + materials each time (unique by
# timestamp); platform admin creation is idempotent. Requires: curl, jq,
# and the dev stack up (web :5173 / backend :8000).
set -euo pipefail

API="${API:-http://localhost:8000/api/v1}"
COMPOSE=(docker compose --project-directory deploy -f deploy/compose.yaml)
ADMIN_LOGIN="${ADMIN_LOGIN:-dev-admin}"
ADMIN_PW="${ADMIN_PW:-AdminPass123}"
OWNER_TEMP_PW="OwnerTemp123"
OWNER_READY_PW="OwnerReady123"
SUFFIX="$(date +%s)"

say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

jpost() { # method url token json  -> response body
  local method="$1" url="$2" token="$3" body="$4"
  curl -fsS -X "$method" "$url" \
    -H 'Content-Type: application/json' \
    ${token:+-H "Authorization: Bearer $token"} \
    -d "$body"
}

say "1/7 Seed platform admin ($ADMIN_LOGIN) — idempotent"
"${COMPOSE[@]}" exec -T backend python -m app.cli seed-platform-user \
  --login "$ADMIN_LOGIN" --password "$ADMIN_PW" \
  --full-name "Dev Admin" --phone "+998900000001" \
  --no-password-reset-required

say "2/7 Platform login"
TOKEN="$(jpost POST "$API/auth/platform/login" "" \
  "{\"login\":\"$ADMIN_LOGIN\",\"password\":\"$ADMIN_PW\"}" | jq -r .access_token)"
[ -n "$TOKEN" ] && [ "$TOKEN" != null ] || { echo "platform login failed"; exit 1; }

say "3/7 Create workshop + branch + owner (dev-ws-$SUFFIX)"
WS_CODE="dev-ws-$SUFFIX"
OWNER_LOGIN="dev-owner-$SUFFIX"
WORKING_HOURS='{"monday":{"open":"09:00","close":"18:00"},"tuesday":{"open":"09:00","close":"18:00"},"wednesday":{"open":"09:00","close":"18:00"},"thursday":{"open":"09:00","close":"18:00"},"friday":{"open":"09:00","close":"18:00"},"saturday":{"open":"10:00","close":"16:00"},"sunday":{"open":null,"close":null}}'
WS_JSON="$(jpost POST "$API/platform/workshops" "$TOKEN" "$(cat <<JSON
{"workshop":{"name":"Dev Ustaxona $SUFFIX","code":"$WS_CODE","phone":"+99890${SUFFIX:0:7}","address":"Toshkent"},
 "branch":{"name":"Markaziy filial","address":"Toshkent, Chilonzor","phone":"+99891${SUFFIX:0:7}","latitude":"41.2995","longitude":"69.2401","working_hours":$WORKING_HOURS},
 "owner":{"full_name":"Dev Owner","login":"$OWNER_LOGIN","phone":"+99893${SUFFIX:0:7}"},
 "temp_password":"$OWNER_TEMP_PW"}
JSON
)")"
BRANCH_ID="$(echo "$WS_JSON" | jq -r '.branch.id')"
[ -n "$BRANCH_ID" ] && [ "$BRANCH_ID" != null ] || { echo "workshop create failed: $WS_JSON"; exit 1; }

say "4/7 Owner first login + password change"
OWNER_TOKEN="$(jpost POST "$API/auth/workshop/login" "" \
  "{\"workshop_code\":\"$WS_CODE\",\"login\":\"$OWNER_LOGIN\",\"password\":\"$OWNER_TEMP_PW\"}" | jq -r .access_token)"
jpost POST "$API/auth/password/change" "$OWNER_TOKEN" \
  "{\"current_password\":\"$OWNER_TEMP_PW\",\"new_password\":\"$OWNER_READY_PW\"}" >/dev/null

say "5/7 Manufacturer + branch pricing"
MAN_ID="$(jpost POST "$API/platform/catalog/manufacturers" "$TOKEN" \
  "{\"name\":\"Dev Maker $SUFFIX\",\"country\":\"UZ\"}" | jq -r .id)"
jpost PUT "$API/workshop/branches/$BRANCH_ID/pricing" "$OWNER_TOKEN" \
  '{"cutting_rate_tiyin":50000,"edge_banding_rate_tiyin":20000}' >/dev/null

ALL_MATERIALS=()

make_panel() { # name len wid grain
  local id
  id="$(jpost POST "$API/platform/catalog/materials" "$TOKEN" "$(cat <<JSON
{"kind":"panel","manufacturer_id":"$MAN_ID","type":"dsp","name":"$1",
 "thickness_mm":"18","color":"$4-color","decor_code":"P-$SUFFIX-$RANDOM",
 "panel_length_mm":$2,"panel_width_mm":$3,"grain_direction":$4}
JSON
)" | jq -r .id)"
  ALL_MATERIALS+=("$id")
  echo "   panel: $1 ($2×$3, grain=$4) -> $id"
}

make_edge() { # name thickness
  local id
  id="$(jpost POST "$API/platform/catalog/materials" "$TOKEN" "$(cat <<JSON
{"kind":"edge","manufacturer_id":"$MAN_ID","name":"$1",
 "thickness_mm":"$2","color":"White","decor_code":"E-$SUFFIX-$RANDOM"}
JSON
)" | jq -r .id)"
  ALL_MATERIALS+=("$id")
  echo "   edge: $1 (${2}mm) -> $id"
}

say "6/7 Create catalog materials (4 panels + 2 edges)"
make_panel "LDSP Oq 2750x1830"          2750 1830 false
make_panel "LDSP Antrasit 2800x2070"    2800 2070 false
make_panel "LDSP Yongoq tola 2750x1830" 2750 1830 true
make_panel "Mini panel 900x600"         900  600  false
make_edge  "Krom Oq 2mm" 2
make_edge  "Krom Oq 1mm" 1

say "7/7 Branch carry + stock-in for all materials"
for mid in "${ALL_MATERIALS[@]}"; do
  jpost POST "$API/workshop/branches/$BRANCH_ID/materials" "$OWNER_TOKEN" \
    "{\"material_id\":\"$mid\",\"price_tiyin\":250000,\"min_stock\":1}" >/dev/null
  jpost POST "$API/workshop/branches/$BRANCH_ID/stock-in" "$OWNER_TOKEN" \
    "{\"material_id\":\"$mid\",\"quantity\":100,\"supplier\":{\"name\":\"Dev Supplier\"},\"note\":\"dev seed\"}" >/dev/null
done

cat <<DONE

✅ Done. Seeded workshop "Dev Ustaxona $SUFFIX" (branch $BRANCH_ID) with 4 panels + 2 edges.
   Client: refresh the cutting editor — panels now appear in "Panel materiali".
   Workshop login: code=$WS_CODE  login=$OWNER_LOGIN  password=$OWNER_READY_PW
DONE
