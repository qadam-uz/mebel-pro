<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useI18n } from 'vue-i18n'

import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { decorTypeLabel, formatMm, isTape, materialIdentityLabel } from '@/shared/app/materialLabel'
import { materialSwatchClass } from '@/shared/app/materialSwatches'
import { useRolePath } from '@/shared/app/paths'
import ClientChipFilter from '@/apps/client/components/ClientChipFilter.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import Icon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import { formatTiyin } from '@/shared/formatters'
import { useClientCatalogStore } from '@/shared/stores/clientCatalog'
import { useClientEntryStore } from '@/shared/stores/clientEntry'
import type { DecorType } from '@/shared/stores/admin'
import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * One branch's price list, read-only — `/c/workshops/:workshopId/catalog`
 * (spec §6.2).
 *
 * Rows are **decor-first**, exactly as the editor's material picker is: one row
 * per decor, and the price is the *format's*, so it is shown wherever a
 * concrete format is and nowhere else. A decor the branch carries in several
 * formats lists them underneath, one price each.
 *
 * Nothing here is selectable: this is a price list, and the one «Yangi chizma»
 * lives on the workshop profile, one tap back.
 */
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const entry = useClientEntryStore()
const catalog = useClientCatalogStore()
const { t } = useI18n()

const workshopId = computed(() => String(route.params.workshopId ?? ''))
const workshop = computed(
  () => entry.workshops.find((item) => item.workshop_id === workshopId.value) ?? null,
)
const branches = computed(() => workshop.value?.branches ?? [])

const search = ref('')
const activeType = ref<string>('all')
/** The decor whose image is open full-size, and the thumbnail focus returns to. */
const lightbox = ref<{ title: string; fileId: string | null; swatch: string } | null>(null)
let lightboxTrigger: HTMLElement | null = null

/**
 * The branch is a query parameter so the choice survives a reload and a shared
 * link. An absent or foreign `?branch=` falls back to the workshop's pinned
 * branch, else its first — never to "no branch", which would render an empty
 * page that looks like an empty catalog.
 */
const branchId = computed(() => {
  const requested = String(route.query.branch ?? '')
  if (branches.value.some((branch) => branch.id === requested)) return requested
  const pinned = branches.value.find((branch) => branch.is_pinned)
  return pinned?.id ?? branches.value[0]?.id ?? ''
})
const branch = computed(() => branches.value.find((item) => item.id === branchId.value) ?? null)

const branchOptions = computed(() =>
  branches.value.map((item) => ({ value: item.id, label: item.name })),
)

function selectBranch(value: string | null) {
  if (!value || value === branchId.value) return
  void router.replace({ query: { ...route.query, branch: value } })
}

// ---------------------------------------------------------------- grouping

interface DecorGroup {
  key: string
  type: DecorType
  name: string
  hasGrain: boolean
  imageFileId: string | null
  swatch: string
  formats: ClientCatalogMaterialOption[]
}

/**
 * A decor is (substrate, manufacturer, code-or-name): the three fields that
 * make two formats the same colour of the same board. The formats under it are
 * ordered thickest-last so a thickness ladder reads in one direction.
 */
function decorKey(option: ClientCatalogMaterialOption): string {
  return [option.type, option.manufacturer_id, option.code ?? option.name].join('|')
}

const visible = computed(() =>
  // `discontinued` formats are never listed on a price list: the branch may
  // still hold stock, which is the editor's problem, not a quotable price.
  catalog.materials.filter((item) => !item.discontinued),
)

const groups = computed<DecorGroup[]>(() => {
  const byKey = new Map<string, DecorGroup>()
  for (const option of visible.value) {
    const key = decorKey(option)
    let group = byKey.get(key)
    if (!group) {
      group = {
        key,
        type: option.type,
        name: materialIdentityLabel(option),
        hasGrain: option.has_grain,
        imageFileId: option.image_file_id,
        swatch: materialSwatchClass({
          id: key,
          name: option.name,
          code: option.code,
        }),
        formats: [],
      }
      byKey.set(key, group)
    }
    group.formats.push(option)
  }
  for (const group of byKey.values()) {
    group.formats.sort((a, b) => Number(a.thickness_mm) - Number(b.thickness_mm))
  }
  return [...byKey.values()]
})

/** One chip per substrate actually on this branch's shelf — never a chip that
 *  filters to nothing. */
const presentTypes = computed(() => {
  const seen: DecorType[] = []
  for (const group of groups.value) if (!seen.includes(group.type)) seen.push(group.type)
  return seen
})

const typeChips = computed(() => [
  { value: 'all', label: t('client.orders.filter.all') },
  ...presentTypes.value.map((type) => ({ value: type as string, label: decorTypeLabel(type) })),
])

/** The substrate dot beside a section heading — the family colour, not one hue
 *  per enum member (the same grouping `decorTypePillClass` uses). */
function typeDotClass(type: DecorType): string {
  if (type === 'kromka') return 'bg-tur-tape'
  if (type === 'ldsp' || type === 'dsp') return 'bg-tur-board'
  if (type === 'mdf') return 'bg-tur-mdf'
  if (type === 'fanera' || type === 'yogoch') return 'bg-tur-wood'
  return 'bg-tur-other'
}

/** Groups under their substrate heading, in the chip row's order. */
const sections = computed(() =>
  presentTypes.value
    .filter((type) => activeType.value === 'all' || type === activeType.value)
    .map((type) => ({
      type,
      label: decorTypeLabel(type),
      groups: groups.value.filter((group) => group.type === type),
    }))
    .filter((section) => section.groups.length > 0),
)

const isEmpty = computed(() => !catalog.loading && !catalog.error && sections.value.length === 0)

// ------------------------------------------------------------------ format

/** `18 mm · 2800×2070 mm` for a panel, `0.8 mm · eni 22 mm` for a tape. */
function formatLine(option: ClientCatalogMaterialOption): string {
  const thickness = `${formatMm(option.thickness_mm)} mm`
  if (isTape(option.type)) {
    const width = option.tape_width_mm
    return width ? `${thickness} · eni ${formatMm(width)} mm` : thickness
  }
  if (!option.length_mm || !option.width_mm) return thickness
  return `${thickness} · ${option.length_mm}×${option.width_mm} mm`
}

function priceUnit(option: ClientCatalogMaterialOption): string {
  return isTape(option.type) ? 'client.catalog.perMetre' : 'client.catalog.perSheet'
}

/**
 * A format the branch has not priced yet reads «Narx kelishiladi», never
 * «0 so'm» — a zero on a price list is an offer, and this one would be a lie.
 * The row stays listed: the branch carries the decor, and hiding it would make
 * the catalog disagree with the shelf.
 */
function hasPrice(option: ClientCatalogMaterialOption): boolean {
  return !option.price_unset && option.price_tiyin > 0
}

// --------------------------------------------------------------- lightbox
//
// The one place in this view that fetches the full image, and it opens on the
// `sm` rendition the row already drew: that one is in the browser's cache, so
// the modal has a picture in it immediately and the original arrives behind it
// instead of leaving a hole on a phone connection.

function openLightbox(group: DecorGroup, event: MouseEvent | KeyboardEvent) {
  lightboxTrigger = event.currentTarget as HTMLElement
  lightbox.value = { title: group.name, fileId: group.imageFileId, swatch: group.swatch }
}

// AppModal's focus trap restores focus to whatever had it when the modal
// opened — which is the thumbnail only when the browser focused it on click
// (Safari does not). So the trigger is remembered and re-focused here, after
// the trap's own restore has run.
//
// A timeout rather than `requestAnimationFrame`: rAF is suspended while the tab
// is in the background, which would leave focus on `<body>` for a modal closed
// from a background tab — and a macrotask still lands after the post-flush
// watcher the trap restores from.
function closeLightbox() {
  lightbox.value = null
  const trigger = lightboxTrigger
  lightboxTrigger = null
  setTimeout(() => trigger?.focus(), 0)
}

// --------------------------------------------------------------- loading

let timer: number | undefined

function reload() {
  if (!branchId.value) return
  void catalog.loadMaterials(branchId.value, search.value.trim())
}

watch(search, () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(reload, SEARCH_DEBOUNCE_MS)
})
watch(branchId, () => {
  activeType.value = 'all'
  reload()
})

onMounted(async () => {
  await entry.ensureMyWorkshops()
  reload()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  catalog.reset()
})
</script>

<template>
  <section>
    <!-- Not one of the client's own workshops, or a branch it does not have. -->
    <div v-if="!entry.workshopsLoading && (!workshop || !branch)" class="client-empty">
      <div class="client-empty-icon"><Icon name="store" /></div>
      <h3>{{ $t('client.workshop.notFoundTitle') }}</h3>
      <p>{{ $t('client.workshop.notFoundBody') }}</p>
      <RouterLink :to="rolePath('/c/branches')" class="mp-button mp-button-primary mt-4">
        {{ $t('client.workshops.title') }}
      </RouterLink>
    </div>

    <template v-else>
      <!-- Head, search and chips have to leave the first material above the
           fold on a phone, so the branch switcher folds into the head line as a
           select; desktop has the room for a segmented control. -->
      <RouterLink
        :to="rolePath(`/c/workshops/${workshopId}`)"
        class="client-back hidden md:inline-flex"
      >
        ← {{ workshop?.name }}
      </RouterLink>

      <div class="mb-2.5 flex items-center gap-2 md:hidden">
        <RouterLink
          :to="rolePath(`/c/workshops/${workshopId}`)"
          class="min-w-0 flex-1 truncate text-sm font-bold text-ink no-underline"
        >
          {{ workshop?.name }}
        </RouterLink>
        <FormSelect
          v-if="branchOptions.length > 1"
          class="w-auto shrink-0"
          :model-value="branchId"
          :label="$t('client.workshop.branches')"
          hide-label
          :options="branchOptions"
          @update:model-value="selectBranch"
        />
        <span v-else class="shrink-0 text-[13.5px] font-bold text-ink">{{ branch?.name }}</span>
      </div>

      <div class="hidden md:block">
        <div class="client-page-head mb-3.5">
          <div>
            <h1>{{ $t('client.workshop.catalog') }}</h1>
            <p class="sub">
              {{
                $t('client.catalog.priceScope', {
                  workshop: workshop?.name ?? '',
                  branch: branch?.name ?? '',
                })
              }}
            </p>
          </div>
        </div>
      </div>

      <div class="mb-2.5 md:mb-3.5 md:flex md:items-center md:gap-3">
        <SegmentedControl
          v-if="branchOptions.length > 1"
          class="hidden md:block md:w-[420px]"
          :model-value="branchId"
          :label="$t('client.workshop.branches')"
          hide-label
          :options="branchOptions"
          @update:model-value="selectBranch"
        />
        <label class="block md:max-w-[320px] md:flex-1">
          <span class="sr-only">{{ $t('client.catalog.searchLabel') }}</span>
          <span class="mp-input flex items-center gap-2">
            <Icon name="search" class="size-[18px] shrink-0 text-ink-muted" />
            <input
              v-model="search"
              type="text"
              class="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none"
              :placeholder="$t('client.catalog.searchPlaceholder')"
            />
            <button
              v-if="search"
              type="button"
              class="grid size-6 shrink-0 place-items-center rounded-md text-ink-muted hover:text-ink"
              :aria-label="$t('client.catalog.clearSearch')"
              @click="search = ''"
            >
              <Icon name="x" class="size-4" />
            </button>
          </span>
        </label>
      </div>

      <ClientChipFilter
        v-if="typeChips.length > 2"
        v-model="activeType"
        class="mb-3 md:mb-5"
        :label="$t('client.catalog.typeFilter')"
        :options="typeChips"
      />

      <div v-if="catalog.loading && groups.length === 0" class="grid gap-3" aria-live="polite">
        <span class="sr-only">{{ $t('client.common.loading') }}</span>
        <div v-for="item in 4" :key="item" class="client-card flex items-center gap-3 p-3.5">
          <div class="client-skeleton size-12 rounded-[10px]"></div>
          <div class="min-w-0 flex-1">
            <div class="client-skeleton h-4 w-2/3"></div>
            <div class="client-skeleton mt-2 h-3 w-2/5"></div>
          </div>
        </div>
      </div>

      <ClientErrorState
        v-else-if="catalog.error"
        :title="$t('client.catalog.loadFailed')"
        :trace-id="catalog.traceId"
        @retry="reload"
      />

      <div v-else-if="isEmpty" class="client-empty">
        <div class="client-empty-icon">
          <Icon :name="search ? 'search' : 'layers'" />
        </div>
        <h3>
          {{ search ? $t('client.catalog.emptySearch') : $t('client.catalog.emptyBranch') }}
        </h3>
        <p>
          {{ search ? $t('client.catalog.emptySearchBody') : $t('client.catalog.emptyBranchBody') }}
        </p>
        <button
          v-if="search"
          type="button"
          class="mp-button mp-button-outline mt-4"
          @click="search = ''"
        >
          {{ $t('client.catalog.clearSearch') }}
        </button>
      </div>

      <div v-else class="grid gap-3" :class="catalog.loading ? 'opacity-60' : ''">
        <!-- `min-w-0`: a grid item's `min-width: auto` is its min-content size,
             and a decor row's min-content (thumbnail + longest word + the
             nowrap price) is wider than a 375px phone — so without this the
             column, and the page, scroll sideways. -->
        <div v-for="section in sections" :key="section.type" class="min-w-0">
          <div class="mb-[7px] flex items-center gap-2">
            <span
              class="size-[5px] shrink-0 rounded-full md:size-1.5"
              :class="typeDotClass(section.type)"
              aria-hidden="true"
            ></span>
            <span class="font-display text-sm font-bold tracking-[-0.01em] text-ink md:text-[15px]">
              {{ section.label }}
            </span>
            <span class="text-[12.5px] text-ink-muted">
              {{ $t('client.unit.count', section.groups.length) }}
            </span>
          </div>

          <div class="client-card">
            <template v-for="group in section.groups" :key="group.key">
              <div
                class="flex items-center gap-3 border-b border-divider px-3.5 py-2.5 last:border-b-0"
              >
                <!-- Tap the decor, see the decor: the picture is the point of a
                     colour catalog, and 48px is not enough of it. -->
                <button
                  type="button"
                  class="relative size-12 shrink-0 cursor-zoom-in overflow-visible rounded-[10px] border border-hairline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  :aria-label="$t('client.catalog.imageTitle', { material: group.name })"
                  @click="openLightbox(group, $event)"
                >
                  <AuthFileImage
                    v-if="group.imageFileId"
                    :file-id="group.imageFileId"
                    alt=""
                    size="sm"
                    class="size-full rounded-[9px] object-cover"
                  />
                  <span v-else class="block size-full rounded-[9px]" :class="group.swatch"></span>
                  <span
                    class="absolute -bottom-1.5 -right-1.5 grid size-4 place-items-center rounded-[5px] border border-hairline-strong bg-elevated text-ink-soft"
                    aria-hidden="true"
                  >
                    <Icon name="search" class="size-2.5" />
                  </span>
                </button>

                <span class="min-w-0 flex-1">
                  <span class="block truncate text-[13.5px] font-semibold leading-[1.35] text-ink">
                    {{ group.name }}
                  </span>
                  <span
                    class="mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] leading-[1.35] text-ink-muted"
                  >
                    <span>
                      {{
                        group.formats.length === 1
                          ? formatLine(group.formats[0])
                          : $t('client.catalog.formatCount', group.formats.length)
                      }}
                    </span>
                    <span
                      v-if="group.hasGrain"
                      class="inline-flex items-center gap-1 font-semibold text-ink-soft"
                    >
                      <Icon name="grain" class="size-3.5" />
                      {{ $t('client.catalog.grain') }}
                    </span>
                  </span>
                </span>

                <!-- The price belongs to a format, so it rides the row only when
                     the row *is* one format (§7.3). -->
                <span v-if="group.formats.length === 1" class="shrink-0 text-right">
                  <template v-if="hasPrice(group.formats[0])">
                    <span class="block text-[13.5px] font-bold leading-[1.3] text-ink">
                      {{ formatTiyin(group.formats[0].price_tiyin) }}
                    </span>
                    <span class="block text-[12.5px] leading-[1.3] text-ink-muted">
                      {{ $t(priceUnit(group.formats[0])) }}
                    </span>
                  </template>
                  <span v-else class="block text-[12.5px] leading-[1.3] text-ink-muted">
                    {{ $t('client.catalog.priceOnRequest') }}
                  </span>
                </span>
              </div>

              <div
                v-for="format in group.formats.length > 1 ? group.formats : []"
                :key="format.id"
                class="flex items-center gap-2.5 border-b border-divider bg-sunk py-[7px] pl-[73px] pr-3.5 last:border-b-0"
              >
                <span class="min-w-0 flex-1 text-[12.5px] font-semibold text-ink">
                  {{ formatLine(format) }}
                </span>
                <span
                  v-if="hasPrice(format)"
                  class="shrink-0 whitespace-nowrap text-[12.5px] font-bold text-ink"
                >
                  {{ formatTiyin(format.price_tiyin) }}
                  <span class="font-normal text-ink-muted">{{ $t(priceUnit(format)) }}</span>
                </span>
                <span v-else class="shrink-0 whitespace-nowrap text-[12.5px] text-ink-muted">
                  {{ $t('client.catalog.priceOnRequest') }}
                </span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </template>

    <AppModal
      :open="Boolean(lightbox)"
      :title="lightbox?.title ?? ''"
      max-width="max-w-2xl"
      @close="closeLightbox"
    >
      <AuthFileImage
        v-if="lightbox?.fileId"
        :file-id="lightbox.fileId"
        :alt="lightbox.title"
        size="sm"
        upgrade-to="original"
        class="mx-auto block max-h-[70dvh] w-auto rounded-lg object-contain"
      />
      <span
        v-else-if="lightbox"
        class="mx-auto block aspect-[4/3] w-full max-w-md rounded-lg"
        :class="lightbox.swatch"
      ></span>
    </AppModal>
  </section>
</template>
