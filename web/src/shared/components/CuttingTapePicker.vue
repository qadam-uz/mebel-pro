<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { edgeSearchText } from '@/shared/app/cuttingDisplay'
import { decorTitle, type TapeDecor } from '@/shared/app/cuttingGroupTape'
import { formatMm } from '@/shared/app/materialLabel'
import { formatSom } from '@/shared/formatters'
import CuttingBottomSheet from '@/shared/components/CuttingBottomSheet.vue'
import CuttingDecorThumb from '@/shared/components/CuttingDecorThumb.vue'
import Icon from '@/shared/components/AppIcon.vue'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * «Rangi mos kromkani tanlang» (§7.2) — the client picks a tape **decor**, and
 * only a decor. The thicknesses under each row are information, priced per
 * metre so the choice can be made on colour *and* cost; which thickness a given
 * side takes is settled afterwards, on the part's own chips.
 *
 * That is the one difference from the material picker, and it is deliberate:
 * there the client picks a format and the price is the format's; here the
 * decor is the unit and every variant's price is shown at once.
 *
 * «Plita rangi» is pinned above the list because colour is judged side by side.
 * Asking someone to remember a board colour while scrolling a list of browns is
 * how a drawing gets banded in the wrong one.
 */
const props = defineProps<{
  open: boolean
  decors: TapeDecor[]
  /** The group's board, shown pinned at the top for comparison. */
  panel: ClientCatalogMaterialOption | null
  panelImageFileId: string | null
  /** The group's current tape decor key, or null while it has none. */
  currentKey: string | null
  /** `Mebel Master · Yunusobod filiali · 5 ta kromka dekori` */
  caption: string
}>()

const emit = defineEmits<{ close: []; pick: [decorKey: string] }>()

const { t } = useI18n()
const search = ref('')
// The picker commits on «Tanlash», not on tap: on a colour choice the client
// wants to compare two rows against the board strip above before committing.
const selectedKey = ref<string | null>(null)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    search.value = ''
    selectedKey.value = props.currentKey
  },
  { immediate: true },
)

const panelLabel = computed(() => (props.panel ? decorTitle(props.panel) : ''))

const rows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return props.decors.filter((decor) =>
    query
      ? decor.variants.some((variant) => edgeSearchText(variant.material).includes(query))
      : true,
  )
})

/**
 * `0.4 mm · 1 200 so'm/m` per variant — the decor's whole price card, which is
 * what makes this a decor choice rather than a format one.
 */
function variantLines(decor: TapeDecor): string[] {
  return decor.variants.map((variant) => {
    const thickness = `${formatMm(variant.material.thickness_mm)} mm`
    // An unpriced tape («0 so'm/m» would be a price, and a wrong one) — the
    // branch has the format on the shelf but has not priced it yet.
    if (variant.material.price_unset || variant.material.price_tiyin <= 0) {
      return `${thickness} · ${t('cutting.material.priceOnRequest')}`
    }
    return `${thickness} · ${formatSom(variant.material.price_tiyin)} ${t('cutting.edge.perMetre')}`
  })
}
</script>

<template>
  <!-- `raised`: this picker is opened from the «Detal» sheet as often as from
       the group line, and at the plain modal tier it lost the tie to that
       sheet and opened behind it. -->
  <CuttingBottomSheet
    :open="open"
    :title="$t('cutting.edge.pickerTitle')"
    max-width="sm:max-w-[560px]"
    raised
    @close="emit('close')"
  >
    <template #pinned>
      <div
        v-if="panel"
        class="flex items-center gap-2.5 border-b border-hairline bg-sunk px-4 py-2.5 sm:px-5"
      >
        <CuttingDecorThumb :file-id="panelImageFileId" :label="panelLabel" size-class="size-6" />
        <span class="min-w-0">
          <!-- Sentence case, not uppercase: DESIGN.md's label rule. -->
          <span class="block text-[12.5px] font-semibold text-ink-muted">{{
            $t('cutting.edge.boardColour')
          }}</span>
          <span class="block truncate text-[13px] font-bold text-ink">{{ panelLabel }}</span>
        </span>
      </div>
      <div class="border-b border-hairline px-4 pb-3 pt-3 sm:px-5">
        <label class="sr-only" for="cutting-tape-picker-search">
          {{ $t('cutting.edge.searchPlaceholder') }}
        </label>
        <span class="mp-input flex items-center gap-2 focus-within:border-accent">
          <Icon name="search" class="size-4 shrink-0 text-ink-muted" />
          <input
            id="cutting-tape-picker-search"
            v-model="search"
            type="search"
            class="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-ink outline-none"
            :placeholder="$t('cutting.edge.searchPlaceholder')"
          />
        </span>
        <p class="mt-2 truncate text-[12.5px] text-ink-muted">{{ caption }}</p>
      </div>
    </template>

    <p v-if="rows.length === 0" class="px-1 py-8 text-center text-sm text-ink-muted">
      {{ decors.length === 0 ? $t('cutting.edge.emptyInBranch') : $t('cutting.edge.noMatches') }}
    </p>

    <div v-else class="grid gap-2" role="radiogroup" :aria-label="$t('cutting.edge.pickerTitle')">
      <!-- `min-w-0`, exactly as `CuttingMaterialPicker` carries it: a grid
           item's `min-width: auto` is its min-content size — the thumbnail plus
           the decor label, which `truncate` keeps on one line — so without it
           the track sizes to the longest name and the whole list hangs off the
           right edge of a phone sheet. -->
      <div
        v-for="decor in rows"
        :key="decor.key"
        class="flex min-h-[60px] min-w-0 items-center gap-3 rounded-xl border p-2 pl-3 transition"
        :class="
          decor.key === selectedKey
            ? 'border-accent-tint bg-accent-soft'
            : 'border-hairline bg-elevated'
        "
      >
        <CuttingDecorThumb :file-id="decor.imageFileId" :label="decor.label" />
        <button
          type="button"
          role="radio"
          :aria-checked="decor.key === selectedKey"
          class="flex min-w-0 flex-1 items-center gap-3 rounded-lg py-1 text-left"
          @click="selectedKey = decor.key"
        >
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-bold text-ink">{{ decor.label }}</span>
            <span class="mt-0.5 block text-[12.5px] leading-[1.35] text-ink-muted">
              <span
                v-for="(line, index) in variantLines(decor)"
                :key="line"
                class="whitespace-nowrap"
              >
                <span v-if="index > 0"> · </span>{{ line }}
              </span>
            </span>
          </span>
          <span
            class="grid size-[18px] shrink-0 place-items-center rounded-full border bg-elevated"
            :class="
              decor.key === selectedKey ? 'border-[5px] border-accent' : 'border-hairline-strong'
            "
            aria-hidden="true"
          ></span>
        </button>
      </div>
    </div>

    <template #foot>
      <button
        type="button"
        class="mp-button mp-button-primary w-full"
        :disabled="!selectedKey"
        @click="selectedKey && emit('pick', selectedKey)"
      >
        {{ $t('cutting.edge.select') }}
      </button>
    </template>
  </CuttingBottomSheet>
</template>
