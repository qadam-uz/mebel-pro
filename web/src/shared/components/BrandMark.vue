<script setup lang="ts">
/**
 * The product mark: a graphite tile with `M`, the orange cut, `P`.
 *
 * It is MARKUP rather than an `<img>` of `/favicon.svg`, because the letters are
 * Wix Madefor Display 800 and an SVG cannot carry a webfont. `/favicon.svg` is
 * the same tile with the cut alone — the form the mark takes where the letters
 * would smear (a browser tab, an app icon) — so rendering that file inside the
 * app put two different logos on one product: the workshop sidebar showed the
 * lockup while the client header, the admin sidebar and all three login screens
 * showed a bare orange bar. Every in-app mark comes from here now.
 *
 * `size` is the tile's edge in px; everything inside scales from it, so the
 * proportions hold at 24px and at 40px. The tile is decorative — the host names
 * the link it sits in.
 */
const props = withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<template>
  <span
    class="mp-brand-mark"
    aria-hidden="true"
    :style="{
      width: `${props.size}px`,
      height: `${props.size}px`,
      borderRadius: `${Math.round(props.size * 0.22)}px`,
      fontSize: `${Math.round(props.size * 0.44 * 10) / 10}px`,
      gap: `${Math.max(1, Math.round(props.size * 0.05 * 10) / 10)}px`,
    }"
  >
    <span class="mp-brand-letter">M</span>
    <span
      class="mp-brand-cut"
      :style="{
        width: `${Math.max(1.5, Math.round(props.size * 0.07 * 10) / 10)}px`,
        height: `${Math.round(props.size * 0.53)}px`,
      }"
    ></span>
    <span class="mp-brand-letter">P</span>
  </span>
</template>
