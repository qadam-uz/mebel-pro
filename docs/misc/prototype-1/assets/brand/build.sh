#!/usr/bin/env bash
# Mebel Pro brand kit — regenerates every SVG master and raster export.
# Deps: rsvg-convert, ImageMagick (magick). Run from anywhere.
set -euo pipefail
B="$(cd "$(dirname "$0")" && pwd)"
SVG="$B/svg"; ICON="$B/icon"; EXP="$B/exports"
mkdir -p "$SVG" "$ICON" "$EXP"

# --- palette (verbatim from docs/misc/prototype-1/assets/app.css) ---------
RUST="#A6471F"; RUST_DEEP="#8C3814"; INK="#1A1614"; PAPER="#FAF7F2"; DARK="#1A1614"
FONT="'Source Serif 4','Charter','Iowan Old Style',Georgia,serif"

# --- symbol geometry: three nested cut panels on a 32u stock sheet -------
#  L  = full-height part   RT = right-top part   RB = hand-placed part (tilted)
SHAPES='    <rect x="2" y="2" width="11.6" height="28" rx="2.2"/>
    <rect x="16" y="2" width="14" height="12.6" rx="2.2"/>
    <rect x="16.4" y="17.4" width="13" height="12" rx="2.2" transform="rotate(-3.5 22.9 23.4)"/>'

GRAD='  <defs>
    <linearGradient id="mp-rust" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="'$RUST'"/>
      <stop offset="1" stop-color="'$RUST_DEEP'"/>
    </linearGradient>
  </defs>'

# symbol_svg <file> <fill|GRAD>
symbol_svg() {
  local f="$1" fill="$2" defs="" g="$2"
  if [ "$2" = "GRAD" ]; then defs="$GRAD"; g="url(#mp-rust)"; fi
  cat > "$f" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Mebel Pro">
  <title>Mebel Pro</title>
$defs
  <g fill="$g">
$SHAPES
  </g>
</svg>
EOF
}

# symbol fragment for embedding in lockups (nested <svg>)
sym_frag() { # <x> <y> <size> <fill|GRAD> <gradid>
  local x="$1" y="$2" s="$3" fill="$4" gid="$5" g="$4"
  if [ "$4" = "GRAD" ]; then g="url(#$gid)"; fi
  echo "  <svg x=\"$x\" y=\"$y\" width=\"$s\" height=\"$s\" viewBox=\"0 0 32 32\" overflow=\"visible\">
    <g fill=\"$g\">
$SHAPES
    </g>
  </svg>"
}

defs_for() { # emits a uniquely-id'd vertical rust gradient
  echo "  <defs><linearGradient id=\"$1\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"$RUST\"/><stop offset=\"1\" stop-color=\"$RUST_DEEP\"/></linearGradient></defs>"
}

# --- per-colorway recipe: symbolfill  wordmarkfill --------------------------
#  paper -> gradient rust symbol + ink wordmark  (on #FAF7F2)
#  dark  -> flat rust symbol     + paper wordmark (on #1A1614)
#  black -> flat ink everything  (mono)
#  white -> flat paper everything(mono)
for v in paper dark black white; do
  case $v in
    paper) sf="GRAD"; wf="$INK";;
    dark)  sf="$RUST"; wf="$PAPER";;
    black) sf="$INK";  wf="$INK";;
    white) sf="$PAPER"; wf="$PAPER";;
  esac

  symbol_svg "$SVG/symbol-$v.svg" "$sf"

  # ---- horizontal lockup : symbol + wordmark, 188x44 ----
  gid="g-h-$v"; defs=""; [ "$sf" = "GRAD" ] && defs="$(defs_for "$gid")"
  {
    echo "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 196 44\" role=\"img\" aria-label=\"Mebel Pro\">"
    echo "  <title>Mebel Pro</title>"
    [ -n "$defs" ] && echo "$defs"
    sym_frag 3 6 32 "$sf" "$gid"
    echo "  <text x=\"50\" y=\"30\" font-family=\"$FONT\" font-size=\"25\" font-weight=\"600\" letter-spacing=\"-0.25\" fill=\"$wf\">Mebel Pro</text>"
    echo "</svg>"
  } > "$SVG/lockup-h-$v.svg"

  # ---- stacked lockup : symbol over wordmark, 132x104 ----
  gid="g-s-$v"; defs=""; [ "$sf" = "GRAD" ] && defs="$(defs_for "$gid")"
  {
    echo "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 132 104\" role=\"img\" aria-label=\"Mebel Pro\">"
    echo "  <title>Mebel Pro</title>"
    [ -n "$defs" ] && echo "$defs"
    sym_frag 44 6 44 "$sf" "$gid"
    echo "  <text x=\"66\" y=\"86\" text-anchor=\"middle\" font-family=\"$FONT\" font-size=\"23\" font-weight=\"600\" letter-spacing=\"-0.23\" fill=\"$wf\">Mebel Pro</text>"
    echo "</svg>"
  } > "$SVG/lockup-stacked-$v.svg"

  # ---- wordmark only : 178x40 ----
  {
    echo "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 178 40\" role=\"img\" aria-label=\"Mebel Pro\">"
    echo "  <title>Mebel Pro</title>"
    echo "  <text x=\"2\" y=\"29\" font-family=\"$FONT\" font-size=\"28\" font-weight=\"600\" letter-spacing=\"-0.28\" fill=\"$wf\">Mebel Pro</text>"
    echo "</svg>"
  } > "$SVG/wordmark-$v.svg"
done

# --- app-icon family : rust ground, mark knocked out in paper, FLAT ------
# tile content scaled into a clear-space-safe inner box.
tile_body() { # <inset_translate> <scale> <rx>
  cat <<EOF
  <rect width="32" height="32" rx="$3" fill="$RUST"/>
  <g fill="$PAPER" transform="translate($1,$1) scale($2)">
$SHAPES
  </g>
EOF
}
# rounded app tile (favicon / apple-touch / android any): inset to 6..26
cat > "$ICON/icon-tile.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Mebel Pro">
  <title>Mebel Pro</title>
$(tile_body 4.571 0.7143 7)
</svg>
EOF
cp "$ICON/icon-tile.svg" "$ICON/favicon.svg"
# maskable: full-bleed (no radius), mark inside 50% safe zone
cat > "$ICON/maskable.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Mebel Pro">
  <title>Mebel Pro</title>
$(tile_body 6.857 0.5714 0)
</svg>
EOF

# --- raster exports ----------------------------------------------------
png() { rsvg-convert -w "$3" -h "$3" "$1" -o "$2"; }      # transparent
pngbg() { rsvg-convert -w "$3" -h "$3" -b "$4" "$1" -o "$2"; }

# favicons / app icons (geometry only -> pixel-exact, font-independent)
for s in 16 32 48; do png "$ICON/favicon.svg" "$EXP/favicon-$s.png" "$s"; done
png "$ICON/icon-tile.svg" "$EXP/apple-touch-icon-180.png" 180
png "$ICON/icon-tile.svg" "$EXP/icon-192.png" 192
png "$ICON/icon-tile.svg" "$EXP/icon-512.png" 512
png "$ICON/maskable.svg"  "$EXP/maskable-192.png" 192
png "$ICON/maskable.svg"  "$EXP/maskable-512.png" 512
magick "$EXP/favicon-16.png" "$EXP/favicon-32.png" "$EXP/favicon-48.png" "$EXP/favicon.ico"

# symbol rasters (each colorway, 512)
pngbg "$SVG/symbol-paper.svg" "$EXP/symbol-paper-512.png" 512 "$PAPER"
pngbg "$SVG/symbol-dark.svg"  "$EXP/symbol-dark-512.png"  512 "$DARK"
png   "$SVG/symbol-black.svg" "$EXP/symbol-black-512.png" 512
png   "$SVG/symbol-white.svg" "$EXP/symbol-white-512.png" 512

# convenience lockup rasters (uses an installed serif fallback if Source
# Serif 4 is absent; the .svg is the master — it carries the correct stack)
rsvg-convert -h 240 -b "$PAPER" "$SVG/lockup-h-paper.svg" -o "$EXP/lockup-h-paper-x.png"
rsvg-convert -h 240 -b "$DARK"  "$SVG/lockup-h-dark.svg"  -o "$EXP/lockup-h-dark-x.png"

echo "brand kit built -> $B"
