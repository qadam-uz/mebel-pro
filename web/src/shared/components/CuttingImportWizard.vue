<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiErrorCode } from '@/shared/api/client'
import { MAX_PARTS } from '@/shared/app/constants'
import Icon from '@/shared/components/AppIcon.vue'
import AppModal from '@/shared/components/AppModal.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useCuttingStore, type CuttingPart } from '@/shared/stores/cutting'
import {
  IMPORT_ROLES,
  MAX_IMPORT_FILE_BYTES,
  areImportMaterialPicksComplete,
  buildMapImportedParts,
  buildMapPanelPicks,
  buildImportedParts,
  cuttingImportErrorLabel,
  importRoleLabel,
  importSkipReasonLabel,
  importWarningLabel,
  isImportMappingComplete,
  parseCuttingImport,
  type ImportLoadMode,
  type ImportNeedsMappingResponse,
  type ImportParsedResponse,
  type ImportRole,
} from '@/shared/stores/cuttingImport'

// Two screens, not four steps. Parsing runs the moment a file is chosen, so
// everything after the drop is known at once — the old `mapping` / `materials` /
// `report` rail serialised decisions that were never sequential, and put the
// diagnostics (skipped rows, warnings) on a final screen where they could no
// longer change anyone's mind.
type ImportStep = 'file' | 'review'
type Diagnostic = 'skipped' | 'warnings' | 'ignored' | 'sheets'

const props = withDefaults(
  defineProps<{
    open: boolean
    panelChoices: ChoiceOption[]
    edgeChoices: ChoiceOption[]
    hasExistingParts: boolean
    currentPieces: number
    currentParts?: number
    preferredBranchName?: string | null
    preferredBranchId?: string | null
  }>(),
  { currentParts: 0, preferredBranchName: null, preferredBranchId: null },
)

const emit = defineEmits<{
  close: []
  load: [payload: { mode: ImportLoadMode; parts: CuttingPart[] }]
  committed: [draftId: string]
}>()

const cutting = useCuttingStore()
const { t } = useI18n()

const step = ref<ImportStep>('file')
const selectedFile = ref<File | null>(null)
const detection = ref<ImportNeedsMappingResponse | null>(null)
const parsed = ref<ImportParsedResponse | null>(null)
const skipRows = ref(0)
const columnRoles = ref<Record<number, ImportRole>>({})
const panelPicks = ref<Record<string, string | null>>({})
const edgePicks = ref<Record<string, string | null>>({})
const columnsOpen = ref(false)
const openDiagnostic = ref<Diagnostic | null>(null)
const mode = ref<ImportLoadMode>('append')
const loading = ref(false)
const error = ref<string | null>(null)
const fileInputKey = ref(0)
const mapPartsOnlyAllowed = ref(false)

const isXmlImport = computed(() => parsed.value?.source_format === 'bazis_xml')
const isMapImport = computed(() => parsed.value?.source_format === 'map_2dplace')
const canCommitMapLayout = computed(() => isMapImport.value && !!parsed.value?.map_layout)
const selectedFileName = computed(() => selectedFile.value?.name ?? '')
const formatBadge = computed(() => {
  if (isMapImport.value) return 'MAP'
  if (isXmlImport.value) return 'XML'
  return 'CSV'
})
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
// The columns block is a confirmation, not a task: the backend guesses the
// mapping and `seedMapping` applies it, so it stays collapsed to a one-line
// summary. It opens on its own when the guess is short of what parsing needs —
// the operator should never have to hunt for why the import is blocked.
const needsMapping = computed(() => !!detection.value)
const columnsExpanded = computed(() => columnsOpen.value || !mappingComplete.value)
const mappingSummary = computed(() =>
  IMPORT_ROLES.flatMap((role) => {
    const column = mappingPayload.value[role]
    return column === undefined ? [] : [`${columnLetter(column)}→${importRoleLabel(role)}`]
  }),
)

// The branch is chosen before the flow ever reaches materials, so the list is
// always that branch's own catalog — the "browse everything" toggle it used to
// carry has no state left to switch between.
const catalogHint = computed(() => {
  if (!props.preferredBranchName) return ''
  const count = props.panelChoices.length
  return t('cutting.import.branchCatalog', { branch: props.preferredBranchName, n: count }, count)
})
const materialPicksComplete = computed(() =>
  parsed.value
    ? areImportMaterialPicksComplete(parsed.value, panelPicks.value, edgePicks.value)
    : false,
)
const mapMaterialSizesMatch = computed(() => {
  if (!isMapImport.value || !parsed.value) return true
  return parsed.value.panel_materials.every((group) => selectedPanelMatchesMap(group.key) !== false)
})

const skippedCount = computed(() => parsed.value?.skipped_rows.length ?? 0)
const warningCount = computed(() => parsed.value?.warnings.length ?? 0)
const ignoredCount = computed(() => parsed.value?.ignored_object_count ?? 0)
const sheetCount = computed(() => parsed.value?.map_layout?.sheets.length ?? 0)

// A committed MAP layout starts its own draft, so nothing is carried over; every
// other import lands in the open draft and the mode decides what happens to what
// is already there.
const replacesDraft = computed(() => canCommitMapLayout.value || mode.value === 'replace')
const totalAfterImport = computed(() =>
  replacesDraft.value
    ? (parsed.value?.total_pieces ?? 0)
    : props.currentPieces + (parsed.value?.total_pieces ?? 0),
)
const overCap = computed(() => totalAfterImport.value > MAX_PARTS)
// Each accepted extension named with the program it comes out of and the exact
// menu path that produces it. Ordered by how much of the operator's own work
// survives the import: `.map` keeps the finished layout, `.xml` keeps materials
// and banding, `.csv` keeps only the dimensions. Russian menu labels stay in
// Russian — that is what the operator sees on their own screen, and translating
// them would send them hunting for a string their copy of Bazis does not have.
const fileSources = computed(() =>
  (['map', 'xml', 'csv'] as const).map((format) => ({
    extension: `.${format}`,
    program: t(`cutting.import.source.${format}.program`),
    how: t(`cutting.import.source.${format}.how`),
  })),
)
const modeOptions = computed<ChoiceOption[]>(() => [
  { value: 'append', label: t('cutting.import.modeAppend') },
  { value: 'replace', label: t('cutting.import.modeReplace') },
])
// Names the consequence rather than leaving it to a red button: the old dialog
// offered `Qo'shish` and a `bg-danger` `Almashtirish` side by side, which read as
// two competing actions instead of one action with a mode.
const modeConsequence = computed(() => {
  if (!parsed.value) return ''
  const incoming = parsed.value.total_parts
  if (mode.value === 'replace') {
    return t('cutting.import.replaceConsequence', { n: props.currentParts }, props.currentParts)
  }
  return t(
    'cutting.import.appendConsequence',
    { n: incoming, total: props.currentParts + incoming },
    incoming,
  )
})
const commitDisabled = computed(
  () => loading.value || !parsed.value || !materialPicksComplete.value || overCap.value,
)

watch(
  () => props.open,
  (open) => {
    if (!open) resetWizard()
  },
)

function columnLetter(index: number) {
  let value = index
  let letters = ''
  do {
    letters = String.fromCharCode(65 + (value % 26)) + letters
    value = Math.floor(value / 26) - 1
  } while (value >= 0)
  return letters
}

function resetWizard() {
  step.value = 'file'
  selectedFile.value = null
  detection.value = null
  parsed.value = null
  skipRows.value = 0
  columnRoles.value = {}
  panelPicks.value = {}
  edgePicks.value = {}
  columnsOpen.value = false
  openDiagnostic.value = null
  mode.value = 'append'
  loading.value = false
  error.value = null
  mapPartsOnlyAllowed.value = false
  fileInputKey.value += 1
}

function closeWizard() {
  if (!loading.value) emit('close')
}

function chooseAnotherFile() {
  resetWizard()
}

function setMode(value: string) {
  if (value === 'append' || value === 'replace') mode.value = value
}

function toggleDiagnostic(name: Diagnostic) {
  openDiagnostic.value = openDiagnostic.value === name ? null : name
}

function validateFile(file: File): string | null {
  if (file.size > MAX_IMPORT_FILE_BYTES) return t('cutting.error.fileTooLargeShort')
  const name = file.name.toLowerCase()
  if (!name.endsWith('.csv') && !name.endsWith('.xml') && !name.endsWith('.map')) {
    return t('cutting.error.unsupportedFormatShort')
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
      enterReview(response)
      return
    }
    detection.value = response
    parsed.value = null
    skipRows.value = response.guessed_skip_rows
    seedMapping(response)
    step.value = 'review'
  } catch (errorValue) {
    error.value = cuttingImportErrorLabel(errorValue)
  } finally {
    loading.value = false
  }
  // The guess is usually right, so parse straight through it: the review screen
  // then opens with real materials instead of an empty shell behind a button
  // nobody needed to press.
  if (detection.value && mappingComplete.value) await applyMapping()
}

function enterReview(response: ImportParsedResponse) {
  parsed.value = response
  mapPartsOnlyAllowed.value = false
  panelPicks.value = Object.fromEntries(
    response.panel_materials.map((group) => [group.key, panelPicks.value[group.key] ?? null]),
  )
  edgePicks.value = Object.fromEntries(
    response.edge_materials.map((group) => [group.key, edgePicks.value[group.key] ?? null]),
  )
  step.value = 'review'
}

function invalidateParse() {
  parsed.value = null
  error.value = null
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
  invalidateParse()
}

function adjustSkipRows(delta: number) {
  skipRows.value = Math.max(0, skipRows.value + delta)
  invalidateParse()
}

function setSkipRows(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  const value = Number(target.value)
  skipRows.value = Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0
  invalidateParse()
}

async function applyMapping() {
  if (!selectedFile.value || !mappingComplete.value) return
  loading.value = true
  error.value = null
  try {
    const response = await parseCuttingImport(
      selectedFile.value,
      { skip_rows: skipRows.value, mapping: mappingPayload.value },
      cutting.scope,
    )
    if (response.status !== 'parsed') {
      error.value = t('cutting.error.parseFailed')
      return
    }
    enterReview(response)
    columnsOpen.value = false
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
  return panel.length_mm === group.width_mm && panel.width_mm === group.height_mm
}

function buildPartsFromParsed() {
  if (!parsed.value || !materialPicksComplete.value) return
  return isMapImport.value
    ? buildMapImportedParts(parsed.value, panelPicks.value, edgePicks.value)
    : buildImportedParts(parsed.value, panelPicks.value, edgePicks.value)
}

async function commitImport() {
  if (commitDisabled.value || !parsed.value) return
  if (canCommitMapLayout.value && mapMaterialSizesMatch.value && !mapPartsOnlyAllowed.value) {
    await commitMapLayout()
    return
  }
  try {
    const parts = buildPartsFromParsed()
    if (!parts) return
    emit('load', { mode: props.hasExistingParts ? mode.value : 'replace', parts })
  } catch {
    error.value = t('cutting.error.materialPicksIncomplete')
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
      source_filename: selectedFile.value?.name ?? null,
    })
    emit('committed', draft.id)
  } catch (errorValue) {
    if (apiErrorCode(errorValue) === 'map_layout_material_mismatch') {
      // The server refused the layout; the next press imports the parts alone
      // rather than retrying a commit that cannot succeed.
      mapPartsOnlyAllowed.value = true
      error.value = t('cutting.error.map_layout_material_mismatch')
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
  <AppModal
    :open="open"
    :title="$t('cutting.import.title')"
    max-width="max-w-3xl"
    @close="closeWizard"
  >
    <div class="grid gap-4">
      <div v-if="error" class="client-banner danger" role="alert">
        <span class="font-black">!</span>
        <span>{{ error }}</span>
      </div>

      <section v-if="step === 'file'" class="grid gap-4">
        <label
          class="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-hairline-strong bg-sunk px-5 py-6 text-center transition hover:border-accent hover:bg-neutral-soft"
        >
          <Icon name="upload" class="size-9 text-accent" />
          <span class="text-sm font-extrabold text-ink">{{ $t('cutting.import.dropzone') }}</span>
          <span class="text-xs font-semibold text-ink-muted">{{
            $t('cutting.import.maxSize')
          }}</span>
          <input
            :key="fileInputKey"
            type="file"
            accept=".csv,.xml,.map"
            class="sr-only"
            :disabled="loading"
            @change="onFileChange"
          />
        </label>

        <p v-if="loading" class="text-sm font-semibold text-ink-soft" aria-live="polite">
          {{ $t('cutting.import.reading') }}
        </p>

        <!-- Which file comes from which program, and how to get it out of that
             program. Open by default and one row per extension: a first-time
             importer does not yet know that `.map` is 2D-Place's word, so a
             collapsed panel hides the answer behind a question they can't ask
             and a single paragraph makes them read all three to find theirs. -->
        <section class="grid gap-2 rounded-lg border border-hairline bg-elevated p-3">
          <h3 class="text-sm font-extrabold text-ink">{{ $t('cutting.import.sourcesTitle') }}</h3>
          <div
            v-for="source in fileSources"
            :key="source.extension"
            class="grid gap-x-3 gap-y-1 border-t border-hairline pt-2 sm:grid-cols-[68px_minmax(0,1fr)]"
          >
            <span class="text-xs font-extrabold text-accent-deep">{{ source.extension }}</span>
            <div class="min-w-0">
              <p class="text-sm font-extrabold text-ink">{{ source.program }}</p>
              <p class="mt-0.5 text-sm text-ink-soft">{{ source.how }}</p>
            </div>
          </div>
        </section>
      </section>

      <!-- Review. Ordered by how likely each block is to need attention: what was
           loaded (never wrong), what the parser dropped (sometimes), which column
           is what (rarely), which catalog material (always). -->
      <section v-else class="grid gap-4">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg bg-sunk px-3 py-2.5">
          <span class="text-sm font-extrabold text-ink">{{ selectedFileName }}</span>
          <span
            class="rounded-full border border-hairline-strong bg-elevated px-2 py-0.5 text-[11px] font-extrabold text-ink-soft"
            >{{ formatBadge }}</span
          >
          <span v-if="parsed" class="text-sm font-semibold text-ink-soft">
            {{ parsed.total_parts }} {{ $t('cutting.unit.kind', parsed.total_parts) }} ·
            {{ parsed.total_pieces }} {{ $t('cutting.unit.piece', parsed.total_pieces) }}
          </span>
          <button
            type="button"
            class="ml-auto text-sm font-extrabold text-accent-deep hover:text-accent-strong"
            @click="chooseAnotherFile"
          >
            {{ $t('cutting.import.anotherFile') }}
          </button>
        </div>

        <div v-if="canCommitMapLayout" class="client-banner info">
          <span class="font-black">i</span>
          <span>{{ $t('cutting.import.mapLayoutKept') }}</span>
        </div>

        <!-- Diagnostics sit ahead of the commit, not on a report screen after it:
             "12 qator o'tkazib yuborildi" is the one fact that can still change
             the operator's mind, and it used to arrive too late to. -->
        <div v-if="parsed" class="grid gap-2">
          <div
            v-if="skippedCount || warningCount || ignoredCount || sheetCount"
            class="flex flex-wrap gap-2"
          >
            <button
              v-if="sheetCount"
              type="button"
              class="import-chip import-chip-ok"
              :aria-expanded="openDiagnostic === 'sheets'"
              @click="toggleDiagnostic('sheets')"
            >
              {{ $t('cutting.import.sheetLayouts', { n: sheetCount }, sheetCount) }}
              <span aria-hidden="true">⌄</span>
            </button>
            <button
              v-if="skippedCount"
              type="button"
              class="import-chip import-chip-warn"
              :aria-expanded="openDiagnostic === 'skipped'"
              @click="toggleDiagnostic('skipped')"
            >
              {{ $t('cutting.import.skippedRows', { n: skippedCount }, skippedCount) }}
              <span aria-hidden="true">⌄</span>
            </button>
            <button
              v-if="warningCount"
              type="button"
              class="import-chip import-chip-warn"
              :aria-expanded="openDiagnostic === 'warnings'"
              @click="toggleDiagnostic('warnings')"
            >
              {{ $t('cutting.import.warnings', { n: warningCount }, warningCount) }}
              <span aria-hidden="true">⌄</span>
            </button>
            <button
              v-if="ignoredCount"
              type="button"
              class="import-chip import-chip-warn"
              :aria-expanded="openDiagnostic === 'ignored'"
              @click="toggleDiagnostic('ignored')"
            >
              {{ $t('cutting.import.ignoredObjects', { n: ignoredCount }, ignoredCount) }}
              <span aria-hidden="true">⌄</span>
            </button>
          </div>

          <div
            v-if="openDiagnostic === 'sheets' && parsed.map_layout"
            class="grid gap-2 sm:grid-cols-2"
          >
            <div
              v-for="sheet in parsed.map_layout.sheets"
              :key="`${sheet.sheet_index}-${sheet.name}`"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm"
            >
              <div class="flex items-center justify-between gap-3">
                <b class="min-w-0 truncate text-ink">{{ sheet.name }}</b>
                <span class="shrink-0 text-ink-muted">
                  {{ sheet.width_mm }}×{{ sheet.height_mm }}
                </span>
              </div>
              <p class="mt-1 text-xs font-semibold text-ink-muted">
                {{ sheet.parts_count }} {{ $t('cutting.unit.part', sheet.parts_count) }} ·
                {{ sheet.waste_count }} {{ $t('cutting.unit.waste', sheet.waste_count) }} ·
                {{ sheet.remainder_count }}
                {{ $t('cutting.unit.remainder', sheet.remainder_count) }} ·
                {{ sheet.fill_percentage }}%
              </p>
            </div>
          </div>

          <ul v-else-if="openDiagnostic === 'skipped'" class="grid gap-2">
            <li
              v-for="row in parsed.skipped_rows"
              :key="`${row.row}-${row.reason}`"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft"
            >
              <b class="text-ink">{{ $t('cutting.import.rowLabel', { n: row.row }) }}</b>
              {{ importSkipReasonLabel(row.reason) }} · {{ row.preview }}
            </li>
          </ul>

          <ul v-else-if="openDiagnostic === 'warnings'" class="grid gap-2">
            <li
              v-for="warning in parsed.warnings"
              :key="warning.code"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft"
            >
              <b class="text-ink">{{ importWarningLabel(warning.code) }}</b>
              · {{ $t('cutting.import.warningRows', { rows: warning.rows.join(', ') }) }}
            </li>
          </ul>

          <p
            v-else-if="openDiagnostic === 'ignored'"
            class="rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-ink-soft"
          >
            {{ $t('cutting.import.ignoredBody', { n: ignoredCount }, ignoredCount) }}
          </p>
        </div>

        <!-- Columns: a confirmation row, not a step. It only exists for CSV, and
             only opens itself when the backend's guess is short. -->
        <section v-if="needsMapping" class="rounded-lg border border-hairline">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
            <span
              class="font-black"
              :class="mappingComplete ? 'text-success' : 'text-warning'"
              aria-hidden="true"
              >{{ mappingComplete ? '✓' : '!' }}</span
            >
            <span class="text-sm font-extrabold text-ink">
              {{
                mappingComplete
                  ? $t('cutting.import.columnsDetected')
                  : $t('cutting.import.columnsNeeded')
              }}
            </span>
            <span
              v-if="mappingComplete && !columnsExpanded"
              class="min-w-0 truncate text-xs text-ink-soft"
            >
              {{ mappingSummary.join(' · ') }}
            </span>
            <button
              v-if="mappingComplete"
              type="button"
              class="ml-auto text-sm font-extrabold text-accent-deep hover:text-accent-strong"
              :aria-expanded="columnsExpanded"
              @click="columnsOpen = !columnsOpen"
            >
              {{ columnsExpanded ? $t('cutting.action.close') : $t('cutting.import.adjust') }}
            </button>
          </div>

          <div v-if="columnsExpanded && detection" class="grid gap-3 border-t border-hairline p-3">
            <div class="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
              <span>{{ $t('cutting.import.skipRowsLabel', { n: skipRows }, skipRows) }}</span>
              <button
                type="button"
                class="mp-button mp-button-outline px-3"
                :aria-label="$t('cutting.import.skipRowsLess')"
                @click="adjustSkipRows(-1)"
              >
                −
              </button>
              <input
                class="h-10 w-20 rounded-md border border-hairline-strong bg-elevated px-3"
                type="number"
                min="0"
                :aria-label="$t('cutting.import.skipRowsInput')"
                :value="skipRows"
                @input="setSkipRows"
              />
              <button
                type="button"
                class="mp-button mp-button-outline px-3"
                :aria-label="$t('cutting.import.skipRowsMore')"
                @click="adjustSkipRows(1)"
              >
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
                            {{ columnRoles[column] ? importRoleLabel(columnRoles[column]) : '—' }}
                          </span>
                          <span class="text-ink-muted" aria-hidden="true">⌄</span>
                        </summary>
                        <div
                          class="absolute left-0 z-30 mt-1 grid w-52 gap-1 rounded-md border border-hairline-strong bg-elevated p-1 shadow-[0_18px_40px_-24px_color-mix(in_srgb,var(--color-ink)_55%,transparent)]"
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
                            {{ importRoleLabel(role) }}
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

            <div v-if="!parsed" class="flex justify-end">
              <button
                type="button"
                class="mp-button mp-button-primary"
                :disabled="loading || !mappingComplete"
                @click="applyMapping"
              >
                {{ loading ? $t('cutting.import.checking') : $t('cutting.import.applyColumns') }}
              </button>
            </div>
          </div>
        </section>

        <!-- The only decision that always needs a person. -->
        <section v-if="parsed" class="grid gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-ink-muted">
              {{ $t('cutting.import.materialsTitle') }}
            </h3>
          </div>

          <div
            v-for="group in parsed.panel_materials"
            :key="group.key"
            class="grid gap-3 rounded-lg border bg-elevated p-3 md:grid-cols-[minmax(0,1fr)_minmax(260px,1.05fr)]"
            :class="panelPicks[group.key] ? 'border-hairline' : 'border-accent-tint'"
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
                <template v-if="mapGroupForKey(group.key)">
                  {{
                    $t(
                      'cutting.import.mapGroupMeta',
                      {
                        width: mapGroupForKey(group.key)?.width_mm,
                        height: mapGroupForKey(group.key)?.height_mm,
                        n: group.part_count,
                      },
                      group.part_count,
                    )
                  }}
                </template>
                <template v-else
                  >{{ group.part_count }} {{ $t('cutting.unit.kind', group.part_count) }}</template
                >
              </p>
            </div>
            <div class="grid gap-2">
              <SearchCombobox
                :model-value="panelPicks[group.key] ?? null"
                :label="$t('cutting.import.panelLabel')"
                :options="panelChoices"
                :placeholder="$t('cutting.import.panelPlaceholder')"
                :hint="catalogHint"
                @update:model-value="setPanelPick(group.key, $event)"
              />
              <span
                v-if="selectedPanelMatchesMap(group.key) !== null"
                class="import-chip"
                :class="selectedPanelMatchesMap(group.key) ? 'import-chip-ok' : 'import-chip-warn'"
              >
                {{
                  selectedPanelMatchesMap(group.key)
                    ? $t('cutting.import.sizeMatch')
                    : $t('cutting.import.sizeMismatch')
                }}
              </span>
            </div>
          </div>

          <div
            v-for="group in parsed.edge_materials"
            :key="group.key"
            class="grid gap-3 rounded-lg border bg-elevated p-3 md:grid-cols-[minmax(0,1fr)_minmax(260px,1.05fr)]"
            :class="edgePicks[group.key] ? 'border-hairline' : 'border-accent-tint'"
          >
            <div class="min-w-0">
              <p class="break-words text-sm font-extrabold text-ink">
                <template v-if="isMapImport">
                  {{ $t('cutting.import.edgeSides', { n: group.side_count }, group.side_count) }}
                </template>
                <template v-else>{{ group.label }}</template>
              </p>
              <p class="mt-1 text-xs font-semibold text-ink-muted">
                {{
                  isMapImport
                    ? $t('cutting.import.edgeNotInFile')
                    : $t('cutting.import.sideCount', { n: group.side_count }, group.side_count)
                }}
              </p>
            </div>
            <SearchCombobox
              :model-value="edgePicks[group.key] ?? null"
              :label="$t('cutting.import.edgeLabel')"
              :options="edgeChoices"
              :placeholder="$t('cutting.edge.placeholder')"
              :hint="catalogHint"
              @update:model-value="setEdgePick(group.key, $event)"
            />
          </div>

          <div v-if="canCommitMapLayout && !mapMaterialSizesMatch" class="client-banner danger">
            <span class="font-black">!</span>
            <span>{{ $t('cutting.import.layoutDropped') }}</span>
          </div>
        </section>

        <div
          v-if="parsed"
          class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-hairline pt-3"
        >
          <SegmentedControl
            v-if="hasExistingParts && !canCommitMapLayout"
            :model-value="mode"
            :label="$t('cutting.import.modeLabel')"
            :options="modeOptions"
            @update:model-value="setMode"
          />
          <span
            v-if="overCap"
            class="min-w-0 text-sm font-semibold text-danger"
            data-testid="import-cap-warning"
          >
            {{
              $t(
                'cutting.import.capWarning',
                { n: totalAfterImport, max: MAX_PARTS },
                totalAfterImport,
              )
            }}
          </span>
          <span
            v-else-if="modeConsequence && hasExistingParts && !canCommitMapLayout"
            class="min-w-0 text-sm font-semibold"
            :class="mode === 'replace' ? 'text-warning' : 'text-ink-soft'"
          >
            {{ modeConsequence }}
          </span>
          <button
            type="button"
            class="mp-button mp-button-primary ml-auto"
            :disabled="commitDisabled"
            @click="commitImport"
          >
            {{ loading ? $t('cutting.import.loading') : $t('cutting.import.commit') }}
          </button>
        </div>
      </section>
    </div>
  </AppModal>
</template>
