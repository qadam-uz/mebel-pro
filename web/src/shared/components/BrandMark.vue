<script setup lang="ts">
/**
 * The product mark: the 2026-07 cutting-map mark, revived by owner decision
 * 2026-08-31 — a cream sheet of parts on the ultramarine tile, one part in
 * wood amber.
 *
 * This component is the ONE in-app source of the mark, and it draws every
 * colour from the `--color-brand-*` theme tokens (the tile deliberately does
 * NOT follow `--color-accent` — retheming the logo with the action colour
 * was considered and rejected as too dark), so a token change in `main.css`
 * recolours the logo everywhere at once. Nothing else in the app may draw
 * the mark. The static mirrors (`public/favicon.svg` and the rasters) are
 * generated from the same tokens by `scripts/generate-brand-assets.mjs`;
 * change a token → rerun the script.
 *
 * `size` is the tile's edge in px; the geometry lives in a 32-unit viewBox,
 * so the proportions hold at 24px and at 40px. The tile is decorative — the
 * host names the link it sits in.
 */
const props = withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<template>
  <svg
    class="mp-brand-mark"
    aria-hidden="true"
    :width="props.size"
    :height="props.size"
    viewBox="0 0 32 32"
  >
    <rect width="32" height="32" rx="7" style="fill: var(--color-brand-tile)" />
    <rect x="5" y="5" width="9" height="22" rx="2" style="fill: var(--color-brand-panel)" />
    <rect x="16.5" y="5" width="10.5" height="10" rx="2" style="fill: var(--color-brand-panel)" />
    <rect x="16.5" y="17" width="10.5" height="10" rx="2" style="fill: var(--color-brand-wood)" />
  </svg>
</template>
