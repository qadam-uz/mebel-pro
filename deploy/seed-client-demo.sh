#!/usr/bin/env bash
#
# Seed the running DEV stack with a FULL client demo so every client-SPA page has
# content in every state: cutting drafts (optimised + not), and orders in each
# status (new / confirmed / cutting / edge_banding / ready / completed /
# cancelled).
#
# It first provisions a fresh workshop + branch + catalog (panels/edges, pricing,
# branch carry + stock) like seed-dev-data.sh, then logs in as a CLIENT over OTP
# (dev code 000000) and drives drafts → orders → workshop production transitions
# entirely through the public API.
#
# Usage (from repo root, dev stack up via `cd deploy && docker compose up -d`):
#   bash deploy/seed-client-demo.sh
#   CLIENT_PHONE=+998901112233 CLIENT_NAME=Dilshod bash deploy/seed-client-demo.sh
#
# Defaults target the dev "Dilshod" client (+998901112233) so the data shows up
# for the account the dev preview is usually logged in as. Re-running adds a fresh
# workshop + a fresh batch of drafts/orders each time. Requires: curl, jq.
set -euo pipefail

API="${API:-http://localhost:8000/api/v1}"
COMPOSE=(docker compose --project-directory deploy -f deploy/compose.yaml)
ADMIN_LOGIN="${ADMIN_LOGIN:-dev-admin}"
ADMIN_PW="${ADMIN_PW:-AdminPass123}"
OWNER_TEMP_PW="OwnerTemp123"
OWNER_READY_PW="OwnerReady123"
CLIENT_PHONE="${CLIENT_PHONE:-+998901112233}"
CLIENT_NAME="${CLIENT_NAME:-Dilshod}"
OTP_CODE="${OTP_CODE:-000000}"
SUFFIX="$(date +%s)"

say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
info() { printf '   \033[0;90m%s\033[0m\n' "$*"; }

jcall() { # method url token json -> response body
  local method="$1" url="$2" token="$3" body="${4:-}"
  curl -fsS -X "$method" "$url" \
    -H 'Content-Type: application/json' \
    ${token:+-H "Authorization: Bearer $token"} \
    ${body:+-d "$body"}
}

# ---------------------------------------------------------------------------
# 1. Platform admin + workshop + branch + owner
# ---------------------------------------------------------------------------
say "1/8 Seed platform admin ($ADMIN_LOGIN) — idempotent"
"${COMPOSE[@]}" exec -T backend python -m app.cli seed-platform-user \
  --login "$ADMIN_LOGIN" --password "$ADMIN_PW" \
  --full-name "Dev Admin" --phone "+998900000001" \
  --no-password-reset-required

say "2/8 Platform login"
TOKEN="$(jcall POST "$API/auth/platform/login" "" \
  "{\"login\":\"$ADMIN_LOGIN\",\"password\":\"$ADMIN_PW\"}" | jq -r .access_token)"
[ -n "$TOKEN" ] && [ "$TOKEN" != null ] || { echo "platform login failed"; exit 1; }

say "3/8 Create workshop + branch + owner (demo-ws-$SUFFIX)"
WS_CODE="demo-ws-$SUFFIX"
OWNER_LOGIN="demo-owner-$SUFFIX"
WORKING_HOURS='{"monday":{"open":"09:00","close":"18:00"},"tuesday":{"open":"09:00","close":"18:00"},"wednesday":{"open":"09:00","close":"18:00"},"thursday":{"open":"09:00","close":"18:00"},"friday":{"open":"09:00","close":"18:00"},"saturday":{"open":"10:00","close":"16:00"},"sunday":{"open":null,"close":null}}'
WS_JSON="$(jcall POST "$API/platform/workshops" "$TOKEN" "$(cat <<JSON
{"workshop":{"name":"Demo Mebel $SUFFIX","code":"$WS_CODE","phone":"+99890${SUFFIX:0:7}","address":"Toshkent, Yunusobod"},
 "branch":{"name":"Markaziy filial","address":"Toshkent, Chilonzor 12","phone":"+99891${SUFFIX:0:7}","latitude":"41.2995","longitude":"69.2401","working_hours":$WORKING_HOURS},
 "owner":{"full_name":"Demo Owner","login":"$OWNER_LOGIN","phone":"+99893${SUFFIX:0:7}"},
 "temp_password":"$OWNER_TEMP_PW"}
JSON
)")"
BRANCH_ID="$(echo "$WS_JSON" | jq -r '.branch.id')"
[ -n "$BRANCH_ID" ] && [ "$BRANCH_ID" != null ] || { echo "workshop create failed: $WS_JSON"; exit 1; }
info "branch=$BRANCH_ID code=$WS_CODE"

say "4/8 Owner first login + password change + pricing"
OWNER_TOKEN="$(jcall POST "$API/auth/workshop/login" "" \
  "{\"workshop_code\":\"$WS_CODE\",\"login\":\"$OWNER_LOGIN\",\"password\":\"$OWNER_TEMP_PW\"}" | jq -r .access_token)"
jcall POST "$API/auth/password/change" "$OWNER_TOKEN" \
  "{\"current_password\":\"$OWNER_TEMP_PW\",\"new_password\":\"$OWNER_READY_PW\"}" >/dev/null
OWNER_TOKEN="$(jcall POST "$API/auth/workshop/login" "" \
  "{\"workshop_code\":\"$WS_CODE\",\"login\":\"$OWNER_LOGIN\",\"password\":\"$OWNER_READY_PW\"}" | jq -r .access_token)"
jcall PUT "$API/workshop/branches/$BRANCH_ID/pricing" "$OWNER_TOKEN" \
  '{"cutting_rate_tiyin":50000,"edge_banding_rate_tiyin":20000}' >/dev/null

# ---------------------------------------------------------------------------
# 2. Catalog: panels + edges, then branch carry + stock
# ---------------------------------------------------------------------------
say "5/8 Manufacturer + catalog materials"
MAN_ID="$(jcall POST "$API/platform/catalog/manufacturers" "$TOKEN" \
  "{\"name\":\"Egger Demo $SUFFIX\",\"country\":\"AT\"}" | jq -r .id)"

PANEL_IDS=()
EDGE_IDS=()
make_panel() { # name len wid grain color
  local id
  id="$(jcall POST "$API/platform/catalog/materials" "$TOKEN" "$(cat <<JSON
{"kind":"panel","manufacturer_id":"$MAN_ID","type":"dsp","name":"$1",
 "thickness_mm":"18","color":"$5","decor_code":"P-$SUFFIX-$RANDOM",
 "panel_length_mm":$2,"panel_width_mm":$3,"grain_direction":$4}
JSON
)" | jq -r .id)"
  PANEL_IDS+=("$id"); info "panel: $1 ($2×$3) -> ${id:0:8}"
}
make_edge() { # name thickness color
  local id
  id="$(jcall POST "$API/platform/catalog/materials" "$TOKEN" "$(cat <<JSON
{"kind":"edge","manufacturer_id":"$MAN_ID","name":"$1",
 "thickness_mm":"$2","color":"$3","decor_code":"E-$SUFFIX-$RANDOM"}
JSON
)" | jq -r .id)"
  EDGE_IDS+=("$id"); info "edge: $1 (${2}mm) -> ${id:0:8}"
}

make_panel "LDSP Oq 2750x1830"        2750 1830 false "Oq"
make_panel "LDSP Antrasit 2800x2070"  2800 2070 false "Antrasit"
make_panel "LDSP Yong'oq 2750x1830"   2750 1830 true  "Yong'oq"
make_edge  "Krom Oq 2mm"   2 "Oq"
make_edge  "Krom Antrasit 1mm" 1 "Antrasit"

say "6/8 Branch carry + stock for every material"
carry_stock() { # material_id price_tiyin stock_qty
  jcall POST "$API/workshop/branches/$BRANCH_ID/materials" "$OWNER_TOKEN" \
    "{\"material_id\":\"$1\",\"price_tiyin\":$2,\"min_stock\":2}" >/dev/null
  jcall POST "$API/workshop/branches/$BRANCH_ID/stock-in" "$OWNER_TOKEN" \
    "{\"material_id\":\"$1\",\"quantity\":$3,\"supplier\":{\"name\":\"Demo Supplier\"},\"note\":\"demo seed\"}" >/dev/null
}
# Panels are consumed by whole-panel count; edge tape is consumed in millimetres,
# so it needs a much larger stock-in (each order eats a few metres of tape).
for mid in "${PANEL_IDS[@]}"; do carry_stock "$mid" 250000 200; done    # ~2500 so'm per panel
for mid in "${EDGE_IDS[@]}";  do carry_stock "$mid" 1500 2000000; done  # 1500 tiyin/m · 2000 m

PANEL_A="${PANEL_IDS[0]}"; PANEL_B="${PANEL_IDS[1]}"
EDGE_A="${EDGE_IDS[0]}";   EDGE_B="${EDGE_IDS[1]}"

WORKER_ID="$(jcall GET "$API/workshop/orders/workers?branch_id=$BRANCH_ID" "$OWNER_TOKEN" \
  | jq -r '.[0].id')"
[ -n "$WORKER_ID" ] && [ "$WORKER_ID" != null ] || { echo "no worker found"; exit 1; }

# ---------------------------------------------------------------------------
# 3. Client login (OTP) + draft/order builders
# ---------------------------------------------------------------------------
say "7/8 Client OTP login ($CLIENT_NAME $CLIENT_PHONE)"
jcall POST "$API/auth/client/otp/request" "" "{\"phone\":\"$CLIENT_PHONE\"}" >/dev/null
CLIENT_TOKEN="$(jcall POST "$API/auth/client/otp/verify" "" \
  "{\"phone\":\"$CLIENT_PHONE\",\"code\":\"$OTP_CODE\",\"name\":\"$CLIENT_NAME\"}" | jq -r .access_token)"
[ -n "$CLIENT_TOKEN" ] && [ "$CLIENT_TOKEN" != null ] || { echo "client OTP login failed"; exit 1; }

# Three part templates → varied panel/edge layouts across drafts. Every part is
# quantity 1: the backend's per-part panel-cost split + floored unit price only
# satisfies ck_order_items_line_total_formula when panel_price is divisible by
# quantity, and 1 always divides it. Multiple distinct parts still give a rich,
# multi-placement cutting result.
band() { echo "{\"material_id\":\"$1\",\"source\":\"shop\"}"; }
part() { # ref material <dummy> l w top bottom left right
  printf '{"part_ref":"%s","material_id":"%s","material_source":"shop","length_mm":%s,"width_mm":%s,"quantity":1,"edge_top":%s,"edge_bottom":%s,"edge_left":%s,"edge_right":%s}' \
    "$1" "$2" "$4" "$5" "$6" "$7" "$8" "$9"
}
parts_for() { # template_index -> parts_snapshot JSON
  local NONE=null
  case "$(( $1 % 3 ))" in
    0)  # Bookshelf carcass in white LDSP, 2 mm edge on visible faces
      printf '[%s,%s,%s,%s,%s]\n' \
        "$(part side_l "$PANEL_A" - 600 400 "$(band "$EDGE_A")" "$NONE" "$(band "$EDGE_A")" "$NONE")" \
        "$(part side_r "$PANEL_A" - 600 400 "$(band "$EDGE_A")" "$NONE" "$NONE" "$(band "$EDGE_A")")" \
        "$(part shelf_top "$PANEL_A" - 564 380 "$(band "$EDGE_A")" "$NONE" "$NONE" "$NONE")" \
        "$(part shelf_mid "$PANEL_A" - 564 380 "$(band "$EDGE_A")" "$NONE" "$NONE" "$NONE")" \
        "$(part back "$PANEL_A" - 580 596 "$NONE" "$NONE" "$NONE" "$NONE")"
      ;;
    1)  # Wardrobe doors in anthracite, 1 mm edge all round
      printf '[%s,%s,%s,%s]\n' \
        "$(part door_l "$PANEL_B" - 700 396 "$(band "$EDGE_B")" "$(band "$EDGE_B")" "$(band "$EDGE_B")" "$(band "$EDGE_B")")" \
        "$(part door_r "$PANEL_B" - 700 396 "$(band "$EDGE_B")" "$(band "$EDGE_B")" "$(band "$EDGE_B")" "$(band "$EDGE_B")")" \
        "$(part drawer "$PANEL_B" - 700 180 "$(band "$EDGE_B")" "$(band "$EDGE_B")" "$NONE" "$NONE")" \
        "$(part shelf "$PANEL_B" - 760 480 "$NONE" "$NONE" "$NONE" "$NONE")"
      ;;
    *)  # Desk top + dividers, white LDSP with full edge on the top
      printf '[%s,%s,%s,%s]\n' \
        "$(part top "$PANEL_A" - 900 600 "$(band "$EDGE_A")" "$(band "$EDGE_A")" "$(band "$EDGE_A")" "$(band "$EDGE_A")")" \
        "$(part leg_l "$PANEL_A" - 560 500 "$(band "$EDGE_A")" "$NONE" "$NONE" "$NONE")" \
        "$(part leg_r "$PANEL_A" - 560 500 "$(band "$EDGE_A")" "$NONE" "$NONE" "$NONE")" \
        "$(part brace "$PANEL_A" - 820 250 "$(band "$EDGE_A")" "$NONE" "$NONE" "$NONE")"
      ;;
  esac
}

DRAFT_ID=""
make_draft() { # template_index optimise(0/1)
  DRAFT_ID="$(jcall POST "$API/client/cutting-drafts" "$CLIENT_TOKEN" "" | jq -r .id)"
  jcall PATCH "$API/client/cutting-drafts/$DRAFT_ID" "$CLIENT_TOKEN" \
    "{\"preferred_branch_id\":\"$BRANCH_ID\",\"parts_snapshot\":$(parts_for "$1")}" >/dev/null
  if [ "$2" = "1" ]; then
    local rid
    rid="$(jcall POST "$API/client/cutting-drafts/$DRAFT_ID/optimize" "$CLIENT_TOKEN" "" | jq -r '.results[0].id')"
    jcall POST "$API/client/cutting-drafts/$DRAFT_ID/chosen-result" "$CLIENT_TOKEN" \
      "{\"result_id\":\"$rid\"}" >/dev/null
  fi
}

ORDER_ID=""; VERSION=""
place_order() { # draft_id note
  local resp
  resp="$(jcall POST "$API/client/orders" "$CLIENT_TOKEN" \
    "{\"draft_id\":\"$1\",\"branch_id\":\"$BRANCH_ID\",\"contact_name\":\"$CLIENT_NAME\",\"contact_phone\":\"$CLIENT_PHONE\",\"note_client\":\"$2\"}")"
  ORDER_ID="$(echo "$resp" | jq -r .id)"
  VERSION="$(echo "$resp" | jq -r .version)"
}

ws_step() { # order_id path extra_json
  local resp
  resp="$(jcall POST "$API/workshop/orders/$1/$2" "$OWNER_TOKEN" "{\"version\":$VERSION${3:+,$3}}")"
  VERSION="$(echo "$resp" | jq -r .version)"
}

advance_to() { # order_id target_status
  local oid="$1" target="$2"
  case "$target" in new) return 0 ;; esac
  ws_step "$oid" approve ""
  [ "$target" = confirmed ] && return 0
  ws_step "$oid" assign "\"cutter_user_id\":\"$WORKER_ID\",\"edger_user_id\":\"$WORKER_ID\""
  [ "$target" = cutting ] && return 0
  ws_step "$oid" cutting-done ""
  [ "$target" = edge_banding ] && return 0
  ws_step "$oid" banding-done ""
  [ "$target" = ready ] && return 0
  ws_step "$oid" mark-collected ""
}

# ---------------------------------------------------------------------------
# 4. Build the demo set
# ---------------------------------------------------------------------------
say "8/8 Create client drafts + orders in every status"

# Standalone drafts (no order): one optimised, one parts-only (not optimised).
make_draft 2 1; info "draft (optimised, not ordered) -> ${DRAFT_ID:0:8}"
make_draft 0 0; info "draft (not optimised) -> ${DRAFT_ID:0:8}"

ORDER_PLAN=(
  "new|Yangi buyurtma, tasdiqlanishini kutmoqda"
  "confirmed|Tasdiqlandi, ishlab chiqarish navbatida"
  "cutting|Hozir kesilmoqda"
  "edge_banding|Krom yopishtirilmoqda"
  "ready|Olib ketishga tayyor"
  "ready|Ikkinchi tayyor buyurtma"
  "completed|Topshirilgan buyurtma"
  "cancelled|Fikrimdan qaytdim"
)

idx=0
for entry in "${ORDER_PLAN[@]}"; do
  target="${entry%%|*}"; note="${entry#*|}"
  make_draft "$idx" 1
  place_order "$DRAFT_ID" "$note"
  if [ "$target" = cancelled ]; then
    jcall POST "$API/client/orders/$ORDER_ID/cancel" "$CLIENT_TOKEN" \
      "{\"version\":$VERSION,\"reason\":\"Reja o'zgardi\"}" >/dev/null
  else
    advance_to "$ORDER_ID" "$target"
  fi
  info "order ${ORDER_ID:0:8} -> $target"
  idx=$((idx + 1))
done

cat <<DONE

✅ Done. Client "$CLIENT_NAME" ($CLIENT_PHONE) now has:
   • 2 standalone drafts (1 optimised, 1 not)
   • 8 orders covering new / confirmed / cutting / edge_banding / ready×2 / completed / cancelled
   Workshop "Demo Mebel $SUFFIX": code=$WS_CODE login=$OWNER_LOGIN password=$OWNER_READY_PW
   Log in to the client SPA with phone $CLIENT_PHONE (OTP $OTP_CODE) and refresh.
DONE
