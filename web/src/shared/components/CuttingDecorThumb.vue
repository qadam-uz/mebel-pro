<script setup lang="ts">
import { ref } from 'vue'

import { materialSwatchStyle } from '@/shared/app/cuttingDisplay'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import Icon from '@/shared/components/AppIcon.vue'

/**
 * The decor picture on a picker row (§7.3): a thumbnail that opens the full
 * image, and **selects nothing when tapped** — the row around it is the
 * selection, this is the "what does it actually look like" escape hatch a
 * 40 px square cannot answer.
 *
 * With no image it falls back to the shared `materialSwatches` colour and stops
 * being a button: there is nothing bigger to show, and a control that opens a
 * flat colour swatch is a promise the screen does not keep.
 *
 * `AppModal` carries the lightbox rather than a hand-rolled overlay, so Escape,
 * the scrim, the focus trap and focus returned to this thumbnail all come for
 * free and behave the way every other dialog here does.
 *
 * The lightbox opens on the `sm` rendition the button beside it just drew — so
 * it is already in the browser cache and paints in the same frame as the modal —
 * and upgrades to the original behind it. `md` was the placeholder before, and
 * nothing on the page caches `md`: it bought a download of its own to show a
 * picture the row already had.
 */
const props = withDefaults(
  defineProps<{
    fileId: string | null
    /** Decor name — the lightbox title and the swatch hash (see cuttingDisplay). */
    label: string
    /** Tailwind size utility for the thumbnail box. */
    sizeClass?: string
  }>(),
  { sizeClass: 'size-10' },
)

const open = ref(false)
</script>

<template>
  <button
    v-if="fileId"
    type="button"
    class="relative shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
    :class="sizeClass"
    :title="props.label"
    :aria-label="$t('cutting.material.viewImage', { material: props.label })"
    @click.stop="open = true"
  >
    <AuthFileImage
      :file-id="fileId"
      alt=""
      class="size-full rounded-lg border border-hairline object-cover"
    />
    <!-- The expand mark rides the corner so the thumbnail reads as openable
         without a caption stealing a line from the decor name beside it. -->
    <span
      class="absolute -bottom-1 -right-1 grid size-4 place-items-center rounded-[5px] border border-hairline-strong bg-elevated text-ink-soft"
      aria-hidden="true"
    >
      <Icon name="eye" class="size-2.5" />
    </span>
  </button>
  <span
    v-else
    class="shrink-0 rounded-lg border border-hairline"
    :class="sizeClass"
    :style="materialSwatchStyle({ name: props.label })"
    aria-hidden="true"
  ></span>

  <AppModal :open="open" :title="props.label" max-width="max-w-xl" @close="open = false">
    <AuthFileImage
      v-if="fileId"
      :file-id="fileId"
      :alt="props.label"
      size="sm"
      upgrade-to="original"
      class="mx-auto block max-h-[min(calc(var(--app-vh)*0.7),36rem)] w-auto rounded-lg border border-hairline object-contain"
    />
  </AppModal>
</template>
