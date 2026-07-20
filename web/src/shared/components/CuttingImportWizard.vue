<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { apiErrorCode } from '@/shared/api/client'
import { MAX_PARTS } from '@/shared/app/constants'
import Icon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useCuttingStore, type CuttingPart } from '@/shared/stores/cutting'
import {
  IMPORT_ROLE_LABELS,
  IMPORT_ROLES,
  IMPORT_SKIP_REASON_LABELS,
  IMPORT_WARNING_LABELS,
  MAX_IMPORT_FILE_BYTES,
  areImportMaterialPicksComplete,
  buildMapImportedParts,
  buildMapPanelPicks,
  buildImportedParts,
  cuttingImportErrorLabel,
  isImportMappingComplete,
  parseCuttingImport,
  type ImportLoadMode,
  type ImportNeedsMappingResponse,
  type ImportParsedResponse,
  type ImportRole,
} from '@/shared/stores/cuttingImport'

type ImportStep = 'file' | 'mapping' | 'materials' | 'report'

const props = withDefaults(
  defineProps<{
    open: boolean
    panelChoices: ChoiceOption[]
    allPanelChoices: ChoiceOption[]
    edgeChoices: ChoiceOption[]
    allEdgeChoices: ChoiceOption[]
    hasExistingParts: boolean
    currentPieces: number
    preferredBranchName?: string | null
    preferredBranchId?: string | null
  }>(),
  { preferredBranchName: null, preferredBranchId: null },
)

const emit = defineEmits<{
  close: []
  load: [payload: { mode: ImportLoadMode; parts: CuttingPart[] }]
  committed: [draftId: string]
}>()

const cutting = useCuttingStore()

const steps: { key: ImportStep; label: string }[] = [
  { key: 'file', label: 'Fayl' },
  { key: 'mapping', label: 'Ustunlar' },
  { key: 'materials', label: 'Materiallar' },
  { key: 'report', label: 'Xulosa' },
]

const step = ref<ImportStep>('file')
const selectedFile = ref<File | null>(null)
const detection = ref<ImportNeedsMappingResponse | null>(null)
const parsed = ref<ImportParsedResponse | null>(null)
const skipRows = ref(0)
const columnRoles = ref<Record<number, ImportRole>>({})
const panelPicks = ref<Record<string, string | null>>({})
const edgePicks = ref<Record<string, string | null>>({})
const showAllCatalog = ref(false)
const helpOpen = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const fileInputKey = ref(0)
const mapPartsOnlyAllowed = ref(false)

const isXmlImport = computed(() => parsed.value?.source_format === 'bazis_xml')
const isMapImport = computed(() => parsed.value?.source_format === 'map_2dplace')
const isDirectParsedImport = computed(() => isXmlImport.value || isMapImport.value)
const canCommitMapLayout = computed(
  () => isMapImport.value && !!parsed.value?.map_layout,
)
const visibleSteps = computed(() => {
  if (isMapImport.value) {
    return [
      { key: 'file' as const, label: 'Fayl' },
      { key: 'materials' as const, label: 'Materiallar' },
      { key: 'report' as const, label: 'Tekshirish' },
    ]
  }
  return isDirectParsedImport.value ? steps.filter((item) => item.key !== 'mapping') : steps
})
const stepGridClass = computed(() =>
  visibleSteps.value.length === 3 ? 'grid-cols-3' : 'grid-cols-4',
)
const currentStepIndex = computed(() =>
  visibleSteps.value.findIndex((item) => item.key === step.value),
)
const selectedFileName = computed(() => selectedFile.value?.name ?? '')
const previewColumns = computed(() => {
  const width = Math.max(0, ...(detection.value?.grid.map((row) => row.length) ?? []))
  return Array.from({ length: width }, (_, index) => index)
})
const mappingPayload = computed(() => {
  const mapping: Partial<Record<ImportRole, number>> = {}
  for (const [column, role] of Object.entries(columnRoles.value)) {
    mapping[role] = Number(column)
  }
  return mapping
})
const mappingComplete = computed(() => isImportMappingComplete(mappingPayload.value))
const effectivePanelChoices = computed(() =>
  props.preferredBranchName && !showAllCatalog.value ? props.panelChoices : props.allPanelChoices,
)
const effectiveEdgeChoices = computed(() =>
  props.preferredBranchName && !showAllCatalog.value ? props.edgeChoices : props.allEdgeChoices,
)
const materialPicksComplete = computed(() =>
  parsed.value
    ? areImportMaterialPicksComplete(parsed.value, panelPicks.value, edgePicks.value)
    : false,
)
const mapMaterialSizesMatch = computed(() => {
  if (!isMapImport.value || !parsed.value) return true
  return parsed.value.panel_materials.every((group) => selectedPanelMatchesMap(group.key) !== false)
})
const totalAfterImport = computed(() =>
  canCommitMapLayout.value
    ? (parsed.value?.total_pieces ?? 0)
    : props.currentPieces + (parsed.value?.total_pieces ?? 0),
)
const overCap = computed(() => totalAfterImport.value > MAX_PARTS)

watch(
  () => props.open,
  (open) => {
    if (!open) resetWizard()
  },
)

function resetWizard() {
  step.value = 'file'
  selectedFile.value = null
  detection.value = null
  parsed.value = null
  skipRows.value = 0
  columnRoles.value = {}
  panelPicks.value = {}
  edgePicks.value = {}
  showAllCatalog.value = false
  helpOpen.value = false
  loading.value = false
  error.value = null
  mapPartsOnlyAllowed.value = false
  fileInputKey.value += 1
}

function closeWizard() {
  if (!loading.value) emit('close')
}

function validateFile(file: File): string | null {
  if (file.size > MAX_IMPORT_FILE_BYTES) return 'Fayl 1 MB dan katta'
  const name = file.name.toLowerCase()
  if (!name.endsWith('.csv') && !name.endsWith('.xml') && !name.endsWith('.map')) {
    return "Bu fayl turi qo'llab-quvvatlanmaydi - faqat CSV, XML yoki MAP."
  }
  return null
}

async function onFileChange(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  const file = target.files?.[0]
  if (!file) return
  error.value = validateFile(file)
  if (error.value) {
    selectedFile.value = null
    fileInputKey.value += 1
    return
  }
  selectedFile.value = file
  detection.value = null
  parsed.value = null
  skipRows.value = 0
  columnRoles.value = {}
  panelPicks.value = {}
  edgePicks.value = {}
  mapPartsOnlyAllowed.value = false
  await detectFile()
}

function seedMapping(response: ImportNeedsMappingResponse) {
  const next: Record<number, ImportRole> = {}
  for (const [role, column] of Object.entries(response.guessed_mapping)) {
    if (typeof column === 'number' && IMPORT_ROLES.includes(role as ImportRole)) {
      next[column] = role as ImportRole
    }
  }
  columnRoles.value = next
}

async function detectFile() {
  if (!selectedFile.value) return
  loading.value = true
  error.value = null
  try {
    const response = await parseCuttingImport(selectedFile.value, undefined, cutting.scope)
    if (response.status === 'parsed') {
      detection.value = null
      enterMaterials(response)
      return
    }
    detection.value = response
    parsed.value = null
    skipRows.value = response.guessed_skip_rows
    seedMapping(response)
    step.value = 'mapping'
  } catch (errorValue) {
    error.value = cuttingImportErrorLabel(errorValue)
  } finally {
    loading.value = false
  }
}

function enterMaterials(response: ImportParsedResponse) {
  parsed.value = response
  mapPartsOnlyAllowed.value = false
  panelPicks.value = Object.fromEntries(
    response.panel_materials.map((group) => [group.key, panelPicks.value[group.key] ?? null]),
  )
  edgePicks.value = Object.fromEntries(
    response.edge_materials.map((group) => [group.key, edgePicks.value[group.key] ?? null]),
  )
  step.value = 'materials'
}

function setColumnRole(column: number, rawRole: string) {
  const next = { ...columnRoles.value }
  delete next[column]
  if (IMPORT_ROLES.includes(rawRole as ImportRole)) {
    const role = rawRole as ImportRole
    for (const [usedColumn, usedRole] of Object.entries(next)) {
      if (usedRole === role) delete next[Number(usedColumn)]
    }
    next[column] = role
  }
  columnRoles.value = next
  parsed.value = null
  error.value = null
}

function adjustSkipRows(delta: number) {
  skipRows.value = Math.max(0, skipRows.value + delta)
}

function setSkipRows(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  const value = Number(target.value)
  skipRows.value = Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0
}

async function confirmMapping() {
  if (!selectedFile.value || !mappingComplete.value) return
  loading.value = true
  error.value = null
  try {
    const response = await parseCuttingImport(selectedFile.value, {
      skip_rows: skipRows.value,
      mapping: mappingPayload.value,
    }, cutting.scope)
    if (response.status !== 'parsed') {
      error.value = "Faylni o'qib bo'lmadi."
      return
    }
    enterMaterials(response)
  } catch (errorValue) {
    error.value = cuttingImportErrorLabel(errorValue)
  } finally {
    loading.value = false
  }
}

function setPanelPick(key: string, value: string | null) {
  panelPicks.value = { ...panelPicks.value, [key]: value }
}

function setEdgePick(key: string, value: string | null) {
  edgePicks.value = { ...edgePicks.value, [key]: value }
}

function pickedPanelMaterial(key: string) {
  const id = panelPicks.value[key]
  return id ? (cutting.panelOptions.find((material) => material.id === id) ?? null) : null
}

function mapGroupForKey(key: string) {
  return parsed.value?.material_groups?.find((group) => group.key === key) ?? null
}

function selectedPanelMatchesMap(key: string): boolean | null {
  if (!isMapImport.value) return null
  const group = mapGroupForKey(key)
  const panel = pickedPanelMaterial(key)
  if (!group || !panel) return null
  return panel.panel_length_mm === group.width_mm && panel.panel_width_mm === group.height_mm
}

function goBack() {
  error.value = null
  if (step.value === 'report') step.value = 'materials'
  else if (step.value === 'materials') step.value = isDirectParsedImport.value ? 'file' : 'mapping'
  else if (step.value === 'mapping') step.value = 'file'
}

function openReport() {
  if (materialPicksComplete.value) step.value = 'report'
}

function buildPartsFromParsed() {
  if (!parsed.value || !materialPicksComplete.value) return
  return isMapImport.value
    ? buildMapImportedParts(parsed.value, panelPicks.value, edgePicks.value)
    : buildImportedParts(parsed.value, panelPicks.value, edgePicks.value)
}

async function loadParts(mode: ImportLoadMode) {
  if (!parsed.value || !materialPicksComplete.value) return
  if (canCommitMapLayout.value && mapMaterialSizesMatch.value && !mapPartsOnlyAllowed.value) {
    await commitMapLayout()
    return
  }
  try {
    const parts = buildPartsFromParsed()
    if (!parts) return
    emit('load', { mode, parts })
  } catch {
    error.value = "Material tanlovlari to'liq emas."
  }
}

async function commitMapLayout() {
  if (!parsed.value?.map_layout || !materialPicksComplete.value) return
  loading.value = true
  error.value = null
  try {
    const draft = await cutting.commitMapImport({
      preferred_branch_id: props.preferredBranchId,
      parts: buildMapImportedParts(parsed.value, panelPicks.value, edgePicks.value),
      map_layout: parsed.value.map_layout,
      panel_picks: buildMapPanelPicks(parsed.value, panelPicks.value),
    })
    emit('committed', draft.id)
  } catch (errorValue) {
    if (apiErrorCode(errorValue) === 'map_layout_material_mismatch') {
      mapPartsOnlyAllowed.value = true
      error.value =
        "Tanlangan panel o'lchami MAP list o'lchamiga mos emas. Boshqa panel tanlang yoki faqat detallarni yuklang."
    } else {
      error.value = cuttingImportErrorLabel(errorValue)
    }
  } finally {
    loading.value = false
  }
}

function previewCell(row: (string | null)[], column: number) {
  return row[column] ?? ''
}
</script>

<template>
  <AppModal :open="open" title="Fayldan import" max-width="max-w-5xl" @close="closeWizard">
    <div class="grid gap-4">
      <ol class="grid gap-2 text-xs font-extrabold" :class="stepGridClass">
        <li
          v-for="(item, index) in visibleSteps"
          :key="item.key"
          class="rounded-md border px-3 py-2 text-center"
          :class="
            index <= currentStepIndex
              ? 'border-accent bg-accent-soft text-accent'
              : 'border-hairline bg-sunk text-ink-muted'
          "
        >
          {{ item.label }}
        </li>
      </ol>

      <div v-if="error" class="client-banner danger" role="alert">
        <span class="font-mono font-black">!</span>
        <span>{{ error }}</span>
      </div>

      <section v-if="step === 'file'" class="grid gap-4">
        <label
          class="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-hairline-strong bg-sunk px-5 py-6 text-center transition hover:border-accent hover:bg-accent-soft/40"
        >
          <Icon name="upload" class="size-9 text-accent" />
          <span class="text-sm font-extrabold text-ink"
            >CSV, XML yoki MAP (*.csv, *.xml, *.map)</span
          >
          <span class="text-xs font-semibold text-ink-muted">1 MB gacha</span>
          <input
            :key="fileInputKey"
            type="file"
            accept=".csv,.xml,.map"
            class="sr-only"
            :disabled="loading"
            @change="onFileChange"
          />
        </label>

        <p v-if="selectedFileName" class="text-sm font-semibold text-ink-soft">
          {{ selectedFileName }}
        </p>

        <section class="rounded-lg border border-hairline bg-elevated">
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-extrabold text-ink"
            @click="helpOpen = !helpOpen"
          >
            <span>Bazis'dan qanday eksport qilinadi?</span>
            <span aria-hidden="true">{{ helpOpen ? '−' : '+' }}</span>
          </button>
          <p v-if="helpOpen" class="border-t border-hairline px-4 py-3 text-sm text-ink-soft">
            БАЗИС-Мебельщик'da: Мебель panelidagi «Спецификация в CSV» yoki «Спецификация в XML»
            tugmasini bosing (butun loyiha uchun — «Формирование проекта» oynasidagi shu tugma).
            2D-Place'da tayyor joylashuvni saqlagan bo'lsangiz, `.map` faylni yuklang. Excel'da
            tayyorlangan ro'yxat bo'lsa: Файл -> Сохранить как -> CSV. Hosil bo'lgan faylni shu
            yerga yuklang.
          </p>
        </section>
      </section>

      <section v-else-if="step === 'mapping' && detection" class="grid gap-4">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 class="font-serif text-lg font-semibold text-ink">Qaysi ustun nimani bildiradi?</h3>
            <p class="mt-1 text-sm text-ink-muted">CSV · {{ selectedFileName }}</p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
          <span>Yuqoridan o'tkazib yuborish: {{ skipRows }} qator</span>
          <button
            type="button"
            class="mp-button mp-button-outline px-3"
            @click="adjustSkipRows(-1)"
          >
            −
          </button>
          <input
            class="h-10 w-20 rounded-md border border-hairline-strong bg-elevated px-3"
            type="number"
            min="0"
            :value="skipRows"
            @input="setSkipRows"
          />
          <button type="button" class="mp-button mp-button-outline px-3" @click="adjustSkipRows(1)">
            +
          </button>
        </div>

        <div class="overflow-x-auto rounded-lg border border-hairline">
          <table class="min-w-full border-collapse text-left text-xs">
            <thead class="bg-sunk text-ink-muted">
              <tr>
                <th
                  v-for="column in previewColumns"
                  :key="column"
                  class="min-w-36 border-b border-r border-hairline p-2"
                >
                  <details class="group relative">
                    <summary
                      class="flex min-h-9 cursor-pointer list-none items-center justify-between gap-2 rounded-md border border-hairline-strong bg-elevated px-2 text-xs font-bold text-ink"
                    >
                      <span class="min-w-0 truncate">
                        {{ columnRoles[column] ? IMPORT_ROLE_LABELS[columnRoles[column]] : '—' }}
                      </span>
                      <span class="text-ink-muted" aria-hidden="true">⌄</span>
                    </summary>
                    <div
                      class="absolute left-0 z-30 mt-1 grid w-52 gap-1 rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_40px_-24px_rgb(15_27_45_/_55%)]"
                    >
                      <button
                        type="button"
                        class="rounded px-2 py-1.5 text-left text-xs font-bold text-ink-muted hover:bg-sunk hover:text-ink"
                        @click="setColumnRole(column, '')"
                      >
                        —
                      </button>
                      <button
                        v-for="role in IMPORT_ROLES"
                        :key="role"
                        type="button"
                        class="rounded px-2 py-1.5 text-left text-xs font-bold hover:bg-sunk"
                        :class="columnRoles[column] === role ? 'text-accent' : 'text-ink-soft'"
                        @click="setColumnRole(column, role)"
                      >
                        {{ IMPORT_ROLE_LABELS[role] }}
                      </button>
                    </div>
                  </details>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, rowIndex) in detection.grid"
                :key="rowIndex"
                :class="rowIndex + 1 <= skipRows ? 'bg-sunk text-ink-muted opacity-60' : ''"
              >
                <td
                  v-for="column in previewColumns"
                  :key="`${rowIndex}-${column}`"
                  class="max-w-60 border-r border-t border-hairline p-2 align-top"
                >
                  <span class="break-words">{{ previewCell(row, column) || '—' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="!mappingComplete" class="text-sm font-semibold text-warning">
          Uzunlik va kenglik ustunlarini tanlang.
        </p>

        <div class="flex flex-wrap justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline" @click="goBack">Orqaga</button>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="loading || !mappingComplete"
            @click="confirmMapping"
          >
            {{ loading ? 'Tekshirilmoqda' : 'Davom etish' }}
          </button>
        </div>
      </section>

      <section v-else-if="step === 'materials' && parsed" class="grid gap-4">
        <div v-if="isMapImport" class="client-banner info">
          <span class="font-mono font-black">i</span>
          <span>
            Fayldagi joylashuv saqlanadi va birinchi variant sifatida ko'rsatiladi. Narx va
            statistika qayta hisoblanadi.
          </span>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="font-serif text-lg font-semibold text-ink">
              Katalogdan mos materialni tanlang
            </h3>
            <p class="mt-1 text-sm text-ink-muted">
              {{ parsed.total_parts }} ta detal · {{ parsed.total_pieces }} dona
            </p>
            <p class="mt-1 text-sm font-semibold text-ink-soft">Fayl: {{ selectedFileName }}</p>
          </div>
          <label
            v-if="preferredBranchName"
            class="inline-flex min-h-9 items-center gap-2 text-sm font-semibold text-ink-soft"
          >
            <input v-model="showAllCatalog" type="checkbox" class="size-4" />
            Barcha katalogni ko'rsatish
          </label>
        </div>

        <section class="grid gap-3">
          <h4 class="text-sm font-extrabold uppercase text-ink-muted">Panel materiallari</h4>
          <div
            v-for="group in parsed.panel_materials"
            :key="group.key"
            class="grid gap-3 rounded-lg border border-hairline bg-elevated p-3 md:grid-cols-[minmax(0,1fr)_minmax(260px,0.9fr)]"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <p class="break-words text-sm font-extrabold text-ink">
                  {{ mapGroupForKey(group.key)?.hint || group.label }}
                </p>
                <span
                  v-if="group.thickness_hint"
                  class="rounded-md bg-info-soft px-2 py-1 text-xs font-extrabold text-info"
                >
                  {{ group.thickness_hint }} mm
                </span>
              </div>
              <p class="mt-1 text-xs font-semibold text-ink-muted">
                <template v-if="isMapImport && mapGroupForKey(group.key)">
                  fayl nomidan · list {{ mapGroupForKey(group.key)?.width_mm }}×{{
                    mapGroupForKey(group.key)?.height_mm
                  }}
                  · {{ group.part_count }} detal
                </template>
                <template v-else>{{ group.part_count }} ta detal</template>
              </p>
            </div>
            <div class="grid gap-2">
              <SearchCombobox
                :model-value="panelPicks[group.key] ?? null"
                label="Panel materiali"
                :options="effectivePanelChoices"
                placeholder="Panel tanlang"
                @update:model-value="setPanelPick(group.key, $event)"
              />
              <p
                v-if="isMapImport && selectedPanelMatchesMap(group.key) !== null"
                class="text-xs font-bold"
                :class="selectedPanelMatchesMap(group.key) ? 'text-success' : 'text-warning'"
              >
                {{
                  selectedPanelMatchesMap(group.key)
                    ? "List o'lchami mos — joylashuv saqlanadi"
                    : "List o'lchami mos emas — faqat detallar import qilinadi"
                }}
              </p>
            </div>
          </div>
        </section>

        <section v-if="parsed.edge_materials.length > 0" class="grid gap-3">
          <h4 class="text-sm font-extrabold uppercase text-ink-muted">Kromka materiallari</h4>
          <div
            v-for="group in parsed.edge_materials"
            :key="group.key"
            class="grid gap-3 rounded-lg border border-hairline bg-elevated p-3 md:grid-cols-[minmax(0,1fr)_minmax(260px,0.9fr)]"
          >
            <div class="min-w-0">
              <p class="break-words text-sm font-extrabold text-ink">
                <template v-if="isMapImport">
                  {{ group.side_count }} tomonda kromka bor · kromka faylda ko'rsatilmagan
                </template>
                <template v-else>{{ group.label }}</template>
              </p>
              <p class="mt-1 text-xs font-semibold text-ink-muted">
                {{ group.side_count }} ta tomon
              </p>
            </div>
            <SearchCombobox
              :model-value="edgePicks[group.key] ?? null"
              label="Kromka materiali"
              :options="effectiveEdgeChoices"
              placeholder="Kromka tanlang"
              @update:model-value="setEdgePick(group.key, $event)"
            />
          </div>
        </section>

        <p v-if="!materialPicksComplete" class="text-sm font-semibold text-warning">
          Har bir material guruhi uchun katalogdan mos variant tanlang.
        </p>

        <div class="flex flex-wrap justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline" @click="goBack">Orqaga</button>
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="!materialPicksComplete"
            @click="openReport"
          >
            Davom etish
          </button>
        </div>
      </section>

      <section v-else-if="step === 'report' && parsed" class="grid gap-4">
        <div class="rounded-lg border border-hairline bg-sunk p-4">
          <h3 class="font-serif text-lg font-semibold text-ink">
            <template v-if="canCommitMapLayout">MAP joylashuvi tayyor</template>
            <template v-else
              >{{ parsed.total_parts }} ta detal ({{ parsed.total_pieces }} dona) tayyor</template
            >
          </h3>
          <p v-if="canCommitMapLayout" class="mt-2 text-sm font-semibold text-ink-soft">
            {{ parsed.total_parts }} ta detal · {{ parsed.total_pieces }} dona ·
            {{ parsed.map_layout?.sheets.length ?? 0 }} list
          </p>
          <p v-if="overCap" class="mt-2 text-sm font-semibold text-warning">
            Jami {{ totalAfterImport }} dona - 100 dan oshadi, optimallashtirish uchun qatorlarni
            kamaytiring.
          </p>
        </div>

        <section v-if="isMapImport && parsed.map_layout" class="grid gap-2">
          <h4 class="text-sm font-extrabold text-ink">MAP listlari</h4>
          <div class="grid gap-2 sm:grid-cols-2">
            <div
              v-for="sheet in parsed.map_layout.sheets"
              :key="`${sheet.sheet_index}-${sheet.name}`"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm"
            >
              <div class="flex items-center justify-between gap-3">
                <b class="min-w-0 truncate text-ink">{{ sheet.name }}</b>
                <span class="shrink-0 font-mono text-ink-muted">
                  {{ sheet.width_mm }}×{{ sheet.height_mm }}
                </span>
              </div>
              <p class="mt-1 text-xs font-semibold text-ink-muted">
                {{ sheet.parts_count }} detal · {{ sheet.waste_count }} chiqindi ·
                {{ sheet.remainder_count }} qoldiq · {{ sheet.fill_percentage }}%
              </p>
            </div>
          </div>
        </section>

        <section v-if="parsed.skipped_rows.length > 0" class="grid gap-2">
          <h4 class="text-sm font-extrabold text-ink">O'tkazib yuborilgan qatorlar</h4>
          <ul class="grid gap-2">
            <li
              v-for="row in parsed.skipped_rows"
              :key="`${row.row}-${row.reason}`"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft"
            >
              <b class="text-ink">{{ row.row }}-qator:</b>
              {{ IMPORT_SKIP_REASON_LABELS[row.reason] }} · {{ row.preview }}
            </li>
          </ul>
        </section>

        <section v-if="parsed.ignored_object_count > 0" class="grid gap-2">
          <h4 class="text-sm font-extrabold text-ink">Import qilinmagan obyektlar</h4>
          <p class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft">
            XML ichidagi {{ parsed.ignored_object_count }} ta panel bo'lmagan obyekt o'tkazib
            yuborildi.
          </p>
        </section>

        <section v-if="parsed.warnings.length > 0" class="grid gap-2">
          <h4 class="text-sm font-extrabold text-ink">Ogohlantirishlar</h4>
          <ul class="grid gap-2">
            <li
              v-for="warning in parsed.warnings"
              :key="warning.code"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft"
            >
              <b class="text-ink">{{ IMPORT_WARNING_LABELS[warning.code] }}</b>
              · qatorlar: {{ warning.rows.join(', ') }}
            </li>
          </ul>
        </section>

        <p v-if="mapPartsOnlyAllowed" class="text-sm font-semibold text-warning">
          MAP joylashuvi saqlanmadi. Faqat detallarni oddiy chizma sifatida yuklash mumkin.
        </p>

        <div class="flex flex-wrap justify-end gap-2">
          <button type="button" class="mp-button mp-button-outline" @click="goBack">Orqaga</button>
          <button
            v-if="canCommitMapLayout && mapMaterialSizesMatch && !mapPartsOnlyAllowed"
            type="button"
            class="mp-button mp-button-primary"
            :disabled="loading"
            @click="loadParts('replace')"
          >
            {{ loading ? 'Yaratilmoqda' : 'Import qilish' }}
          </button>
          <button
            v-else-if="!hasExistingParts"
            type="button"
            class="mp-button mp-button-primary"
            @click="loadParts('replace')"
          >
            Import qilish
          </button>
          <template v-else>
            <button type="button" class="mp-button mp-button-primary" @click="loadParts('append')">
              Qo'shish
            </button>
            <button
              type="button"
              class="mp-button bg-danger text-white"
              @click="loadParts('replace')"
            >
              Almashtirish
            </button>
          </template>
        </div>
      </section>
    </div>
  </AppModal>
</template>
