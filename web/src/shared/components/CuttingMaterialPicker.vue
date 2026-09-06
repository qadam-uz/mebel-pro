<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { decorIdentityKey, decorTitle } from '@/shared/app/cuttingGroupTape'
import { decorTypeLabel, formatMm } from '@/shared/app/materialLabel'
import { formatTiyin } from '@/shared/formatters'
import ClientChipFilter from '@/shared/components/ClientChipFilter.vue'
import CuttingBottomSheet from '@/shared/components/CuttingBottomSheet.vue'
import CuttingDecorThumb from '@/shared/components/CuttingDecorThumb.vue'
import Icon from '@/shared/components/AppIcon.vue'
import type { DecorType } from '@/shared/stores/admin'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * The client's material picker (§7.3): **decor first, format second.**
 *
 * The catalog's identity is the format (thickness × length × width) and that is
 * still what a part stores — but a client shops by colour, so the list is one
 * row per decor and the formats only appear under the decor that has more than
 * one. That split is also what makes the price honest: **the price is the
 * format's, never the decor's**, so it is printed on the row exactly when the
 * row names one concrete format, and on the format rows otherwise.
 *
 * **Two frames, one list** (§7.3): a full-height sheet on phones, and from `md`
 * up a `SearchCombobox`-shaped panel anchored to the control that opened it —
 * search field on top, decor rows under it, placed from the trigger and
 * teleported to `<body>` like every other popover here. A centred modal was the
 * wrong frame on a desktop: changing one group's board is a picker on a row,
 * not a decision that earns a scrim over the whole drawing.
 *
 * Under the search sits the **board-type filter** (decision 27b): «Barchasi»
 * plus one chip per type the branch's shelf holds, in the catalog's own
 * vocabulary. It is the one cut a client makes before colour — "I need an
 * 18 mm LDSP", not "I need something beige" — and on a phone it is the
 * difference between a list of six decors and a list of forty. The chips filter
 * **formats**, so a decor is listed only while it has one of that type and its
 * «{n} ta format» line counts only those.
 *
 * The workshop keeps its own picker in `CuttingEditorView` — this component is
 * mounted on the client path only.
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    materials: ClientCatalogMaterialOption[]
    loading: boolean
    /** The format currently on the part/group, so its row reads as chosen. */
    currentId: string | null
    search: string
    /** `Mebel Master · Yunusobod filiali katalogi · 6 ta dekor` */
    caption: string
    /**
     * The control that opened the picker. With one, `md` and up renders the
     * anchored panel and focus returns here on close; without one (or on a
     * phone) the sheet is the frame.
     */
    anchor?: HTMLElement | null
  }>(),
  { anchor: null },
)

const emit = defineEmits<{
  close: []
  'update:search': [string]
  pick: [materialId: string]
}>()

const { t } = useI18n()

interface DecorRow {
  key: string
  title: string
  imageFileId: string | null
  formats: ClientCatalogMaterialOption[]
}

// ---- the board-type filter (§27b) -----------------------------------------

const ALL = 'all'
const activeType = ref<string>(ALL)

/**
 * The types the chip row offers, remembered across the searches of **one**
 * opening.
 *
 * The search is server-side, so `materials` is the branch's catalog only while
 * the query is empty (which is how every open starts — the editor clears the
 * query on open). Deriving the chips from the current list alone would make
 * them appear and vanish under the typing hand; a set that only ever grows
 * while the sheet is open keeps the row still, and closing it forgets
 * everything, so a branch that lost a substrate is not remembered either.
 */
const typesSeen = ref<DecorType[]>([])

function absorbTypes() {
  for (const material of props.materials) {
    if (material.type && !typesSeen.value.includes(material.type))
      typesSeen.value.push(material.type)
  }
}

watch(() => props.materials, absorbTypes)

/**
 * LDSP, MDF, DSP first — the three a client meets on nine drawings out of ten,
 * in the order the shop floor names them — then whatever else the branch
 * carries, alphabetically. A fixed head means the chip a client reaches for
 * does not move when a branch adds a substrate.
 */
const TYPE_HEAD: readonly DecorType[] = ['ldsp', 'mdf', 'dsp']

const typeChips = computed(() => {
  const head = TYPE_HEAD.filter((type) => typesSeen.value.includes(type))
  const tail = typesSeen.value
    .filter((type) => !TYPE_HEAD.includes(type))
    .map((type) => ({ type, label: decorTypeLabel(type) }))
    .sort((a, b) => a.label.localeCompare(b.label))
  return [
    { value: ALL, label: t('cutting.material.typeAll') },
    ...head.map((type) => ({ value: type as string, label: decorTypeLabel(type) })),
    ...tail.map((entry) => ({ value: entry.type as string, label: entry.label })),
  ]
})

/** The formats the chips let through — the decor rows are folded from these, so
 *  the «{n} ta format» count and the expanded list are the filter's too. */
const shownMaterials = computed(() =>
  activeType.value === ALL
    ? props.materials
    : props.materials.filter((material) => material.type === activeType.value),
)

const rows = computed<DecorRow[]>(() => {
  const list: DecorRow[] = []
  const indexByKey = new Map<string, number>()
  for (const material of shownMaterials.value) {
    const key = decorIdentityKey(material)
    let row = list[indexByKey.get(key) ?? -1]
    if (!row) {
      row = { key, title: decorTitle(material), imageFileId: material.image_file_id, formats: [] }
      indexByKey.set(key, list.length)
      list.push(row)
    }
    if (!row.imageFileId && material.image_file_id) row.imageFileId = material.image_file_id
    row.formats.push(material)
  }
  return list
})

/** `18 mm · 2800×2070 mm` — the format line, in the order the canvas prints it. */
function formatLabel(material: ClientCatalogMaterialOption): string {
  const thickness = formatMm(material.thickness_mm)
  if (material.length_mm != null && material.width_mm != null) {
    return t('cutting.material.formatLine', {
      thickness,
      length: material.length_mm,
      width: material.width_mm,
    })
  }
  return `${thickness} mm`
}

function price(material: ClientCatalogMaterialOption): string {
  return formatTiyin(material.price_tiyin)
}

/**
 * A branch registers its whole format list long before it prices it, and the
 * client endpoint deliberately returns the unpriced rows (`price_unset`) so the
 * shelf reads as the shelf. What it must not do is print «0 so'm»: that is a
 * price, and a wrong one. The catalog page says the same thing here.
 */
function hasPrice(material: ClientCatalogMaterialOption): boolean {
  return !material.price_unset && material.price_tiyin > 0
}

// Which multi-format decor is expanded. A decor is not chosen until one of its
// formats is: with several formats there is no sensible default (a 16 and an
// 18 mm board are different boards), so the row opens instead of selecting.
const expandedKey = ref<string | null>(null)

/** Open the decor that already holds the current format, so its chosen radio is
 *  visible without a tap — and nothing else. */
function syncExpanded() {
  expandedKey.value =
    rows.value.find(
      (row) =>
        row.formats.length > 1 && row.formats.some((format) => format.id === props.currentId),
    )?.key ?? null
}

// Reopening starts closed, on «Barchasi», with nothing remembered from the last
// open: a chip left armed would silently hide most of the catalog next time.
watch(
  () => props.open,
  (open) => {
    if (!open) {
      expandedKey.value = null
      activeType.value = ALL
      typesSeen.value = []
      return
    }
    absorbTypes()
    syncExpanded()
  },
  { immediate: true },
)

// A narrowed list is a different list: a decor left open may now hold one
// format, or none.
watch(activeType, syncExpanded)

function onRow(row: DecorRow) {
  if (row.formats.length === 1) {
    emit('pick', row.formats[0].id)
    return
  }
  expandedKey.value = expandedKey.value === row.key ? null : row.key
}

function rowIsCurrent(row: DecorRow) {
  return row.formats.some((format) => format.id === props.currentId)
}
</script>

<template>
  <CuttingBottomSheet
    :open="open"
    :title="$t('cutting.material.pick')"
    max-width="sm:max-w-[560px]"
    :anchor="anchor"
    @close="emit('close')"
  >
    <template #pinned>
      <div class="border-b border-hairline px-4 pb-3 pt-1 sm:px-5">
        <label class="sr-only" for="cutting-material-picker-search">
          {{ $t('cutting.material.searchLabel') }}
        </label>
        <span
          class="mp-input flex items-center gap-2 focus-within:border-accent"
          :class="loading ? 'opacity-70' : ''"
        >
          <Icon name="search" class="size-4 shrink-0 text-ink-muted" />
          <input
            id="cutting-material-picker-search"
            type="search"
            class="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-ink outline-none"
            :value="search"
            :placeholder="$t('cutting.material.searchPlaceholder')"
            @input="emit('update:search', ($event.target as HTMLInputElement).value)"
          />
        </span>
        <p class="mt-2 truncate text-[12.5px] text-ink-muted">{{ caption }}</p>
        <!-- One chip per substrate the branch actually carries; with a single
             one the row would be a control with nothing to choose. -->
        <ClientChipFilter
          v-if="typeChips.length > 2"
          v-model="activeType"
          class="mt-2.5"
          :label="$t('cutting.material.typeFilter')"
          :options="typeChips"
        />
      </div>
    </template>

    <p v-if="rows.length === 0" class="px-1 py-8 text-center text-sm text-ink-muted">
      {{
        search.trim() || activeType !== 'all'
          ? $t('cutting.material.searchEmpty')
          : $t('cutting.material.emptyInBranch')
      }}
    </p>

    <div v-else class="grid gap-2">
      <!-- `min-w-0`: a grid item's `min-width: auto` is its min-content size —
           thumbnail + longest word + the nowrap price — which is wider than the
           anchored panel, so without it the rows hang off its right edge. -->
      <div
        v-for="row in rows"
        :key="row.key"
        class="min-w-0 rounded-xl border transition"
        :class="
          rowIsCurrent(row) ? 'border-accent-tint bg-accent-soft' : 'border-hairline bg-elevated'
        "
      >
        <!-- One button per decor. The thumbnail inside it is its own button
             (the lightbox), so it is a sibling in the DOM rather than a child —
             a button in a button is invalid and swallows the inner click. -->
        <div class="flex min-h-[60px] items-center gap-3 p-2 pl-3">
          <CuttingDecorThumb :file-id="row.imageFileId" :label="row.title" />
          <button
            type="button"
            class="flex min-w-0 flex-1 items-center gap-3 rounded-lg py-1 text-left"
            :aria-expanded="row.formats.length > 1 ? expandedKey === row.key : undefined"
            @click="onRow(row)"
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-bold text-ink">{{ row.title }}</span>
              <span class="mt-0.5 block text-[12.5px] text-ink-muted">
                {{
                  row.formats.length > 1
                    ? $t('cutting.material.formatCount', { n: row.formats.length })
                    : formatLabel(row.formats[0])
                }}
              </span>
            </span>
            <!-- One format → the row IS that format, so it carries its price.
                 Several → the price lives on the format rows, because there is
                 no single number this row could honestly print. -->
            <span v-if="row.formats.length === 1" class="shrink-0 text-right">
              <template v-if="hasPrice(row.formats[0])">
                <span class="block whitespace-nowrap text-sm font-bold text-ink">
                  {{ price(row.formats[0]) }}
                </span>
                <span class="mt-0.5 block text-[12.5px] text-ink-muted">
                  {{ $t('cutting.material.perSheet') }}
                </span>
              </template>
              <span v-else class="block whitespace-nowrap text-[12.5px] text-ink-muted">
                {{ $t('cutting.material.priceOnRequest') }}
              </span>
            </span>
            <Icon
              v-else
              name="chevron-down"
              class="size-4 shrink-0 text-ink-muted transition"
              :class="expandedKey === row.key ? 'rotate-180' : ''"
            />
          </button>
        </div>

        <div v-if="row.formats.length > 1 && expandedKey === row.key" class="grid gap-1.5 p-2 pt-0">
          <button
            v-for="format in row.formats"
            :key="format.id"
            type="button"
            class="flex min-h-11 items-center gap-2.5 rounded-[10px] border px-3 py-2 text-left transition hover:border-accent-tint"
            :class="
              format.id === currentId ? 'border-accent bg-elevated' : 'border-hairline bg-elevated'
            "
            :aria-pressed="format.id === currentId"
            @click="emit('pick', format.id)"
          >
            <span
              class="grid size-[18px] shrink-0 place-items-center rounded-full border bg-elevated"
              :class="
                format.id === currentId ? 'border-[5px] border-accent' : 'border-hairline-strong'
              "
              aria-hidden="true"
            ></span>
            <span class="min-w-0 flex-1 text-[13.5px] font-semibold text-ink">
              {{ formatLabel(format) }}
            </span>
            <span
              v-if="hasPrice(format)"
              class="shrink-0 whitespace-nowrap text-[13.5px] font-bold text-ink"
            >
              {{ price(format)
              }}<span class="font-normal text-ink-muted">
                {{ $t('cutting.material.perSheet') }}</span
              >
            </span>
            <span v-else class="shrink-0 whitespace-nowrap text-[12.5px] text-ink-muted">
              {{ $t('cutting.material.priceOnRequest') }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </CuttingBottomSheet>
</template>
