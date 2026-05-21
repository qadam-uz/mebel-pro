<script setup lang="ts">
// THE cutting wizard at /c/cutting/:id. One editing surface (parts editor +
// branches indicator) above, one result panel below. Auto-saves the draft
// (debounced PUT), runs the optimiser, renders the SVG layout, and routes into
// the order wizard. Read-only when the bound result is confirmed/invalidated.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useToast } from '@/shared/composables/useToast'
import * as clientApi from '../api'
import type { BranchesIndicator, CuttingResult, Material, PartIn } from '../api/types'
import {
  type Edges,
  type EditablePart,
  LIMITS,
  blankPart,
  materialById,
  materialShortLabel,
  snapshotToEditable,
  totalSheets,
} from '../lib/cutting'
import { RUN_ERROR_KEYS, partMaxFor, validateDraft, validatePart } from '../lib/validate'
import MaterialPicker from '../components/MaterialPicker.vue'
import EdgesPopover from '../components/EdgesPopover.vue'
import SheetVisualiser from '../components/SheetVisualiser.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const draftId = computed(() => String(route.params.id))

const loading = ref(true)
const loadError = ref<ApiError | null>(null)
const notFound = ref(false)
const materials = ref<Material[]>([])
const parts = ref<EditablePart[]>([])
const results = ref<CuttingResult[]>([])
const chosenResultId = ref<string | null>(null)
const boundOrderId = ref<string | null>(null)
const readOnly = ref(false)
const invalidated = ref(false)

const branches = ref<BranchesIndicator | null>(null)
const optimising = ref(false)
const ranOnce = ref(false)
const resultStale = ref(false)
const runFailure = ref<{ code: string; detail: string } | null>(null)
const algosOpen = ref(false)

// modals
const matPickerOpen = ref(false)
const edgesOpen = ref(false)
const pickingRef = ref<string | null>(null)
const editingEdgesRef = ref<string | null>(null)
const editingEdges = ref<Edges>({ t: null, b: null, l: null, r: null })

const chosen = computed(
  () => results.value.find((r) => r.id === chosenResultId.value) ?? results.value[0] ?? null,
)

// ---- load ----------------------------------------------------------------
async function load() {
  loading.value = true
  loadError.value = null
  notFound.value = false
  try {
    const [mats, draft] = await Promise.all([
      clientApi.listMaterials(),
      clientApi.getDraft(draftId.value),
    ])
    materials.value = mats
    parts.value = (draft.parts_snapshot ?? []).map(snapshotToEditable)
    if (parts.value.length === 0) parts.value = [blankPart()]
    chosenResultId.value = draft.chosen_result_id
    // Re-run optimise to load any existing candidate results for display.
    // (the draft endpoint doesn't return results; optimise returns the run.)
    await loadBranches()
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 404) notFound.value = true
      else if (e.status === 403) notFound.value = true
      else loadError.value = e
    } else throw e
  } finally {
    loading.value = false
  }
}

async function loadBranches() {
  try {
    branches.value = await clientApi.draftBranches(draftId.value)
  } catch {
    branches.value = null
  }
}

// ---- editing -------------------------------------------------------------
function markStale() {
  if (results.value.length) {
    resultStale.value = true
  }
  ranOnce.value = false
  runFailure.value = null
  scheduleSave()
}

function addPart() {
  parts.value.push(blankPart())
  markStale()
}

function deletePart(ref: string) {
  if (parts.value.length <= 1) {
    toast.warn(t('client.minOnePart'))
    return
  }
  parts.value = parts.value.filter((p) => p.ref !== ref)
  markStale()
}

function duplicatePart(ref: string) {
  const idx = parts.value.findIndex((p) => p.ref === ref)
  if (idx < 0) return
  const copy: EditablePart = JSON.parse(JSON.stringify(parts.value[idx]))
  copy.ref = blankPart().ref
  parts.value.splice(idx + 1, 0, copy)
  markStale()
}

function toggleSource(ref: string) {
  const p = parts.value.find((x) => x.ref === ref)
  if (!p) return
  p.source = p.source === 'shop' ? 'own' : 'shop'
  markStale()
  loadBranches()
}

function onNumInput(p: EditablePart, field: 'l' | 'w' | 'qty', value: string) {
  const n = value === '' ? null : Math.max(0, parseInt(value, 10) || 0)
  if (field === 'qty') p.qty = n ?? 1
  else p[field] = n
  markStale()
}

// ---- material picker -----------------------------------------------------
function openMatPicker(ref: string) {
  pickingRef.value = ref
  matPickerOpen.value = true
}
function onPickMaterial(m: Material) {
  const p = parts.value.find((x) => x.ref === pickingRef.value)
  if (p) {
    p.materialId = m.id
    markStale()
    loadBranches()
  }
}

// ---- edges ---------------------------------------------------------------
function openEdges(ref: string) {
  const p = parts.value.find((x) => x.ref === ref)
  if (!p) return
  editingEdgesRef.value = ref
  editingEdges.value = { ...p.edges }
  edgesOpen.value = true
}
function onApplyEdges(payload: { edges: Edges; applyAll: boolean }) {
  if (payload.applyAll) {
    parts.value.forEach((p) => (p.edges = { ...payload.edges }))
  } else {
    const p = parts.value.find((x) => x.ref === editingEdgesRef.value)
    if (p) p.edges = { ...payload.edges }
  }
  markStale()
}

// ---- validation ----------------------------------------------------------
function rowValidation(p: EditablePart) {
  return validatePart(p, materials.value)
}

const draftValidation = computed(() => validateDraft(parts.value, materials.value))

function resolveValidation(v: ReturnType<typeof validateDraft>): string {
  if (!v.key) return ''
  const inner = v.inner ? t(v.inner.key ?? '', v.inner.params) : ''
  const params = { ...v.params, ...(v.inner ? { msg: inner } : {}) }
  return t(v.key, params)
}

const optimiseDisabled = computed(() => {
  if (readOnly.value || optimising.value) return true
  if (!draftValidation.value.ok) return true
  if (ranOnce.value && !resultStale.value) return true
  return false
})

const optimiseHint = computed(() => {
  if (!draftValidation.value.ok) return resolveValidation(draftValidation.value)
  if (ranOnce.value && !resultStale.value) return t('client.optHintReady')
  if (resultStale.value) return t('client.optHintStale')
  return t('client.optHintDefault')
})

// ---- save (debounced PUT) ------------------------------------------------
let saveTimer: ReturnType<typeof setTimeout> | null = null
function scheduleSave() {
  if (readOnly.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 800)
}

function toPartIn(p: EditablePart): PartIn {
  return {
    part_ref: p.ref,
    material_id: p.materialId!,
    material_source: p.source,
    length_mm: p.l ?? 0,
    width_mm: p.w ?? 0,
    quantity: p.qty,
    edge_top_mm: p.edges.t,
    edge_bottom_mm: p.edges.b,
    edge_left_mm: p.edges.l,
    edge_right_mm: p.edges.r,
  }
}

async function save() {
  if (readOnly.value) return
  // Only persist parts that are complete enough for the backend (material +
  // positive dims). The backend rejects partial rows.
  const usable = parts.value.filter(
    (p) => p.materialId && (p.l ?? 0) > 0 && (p.w ?? 0) > 0 && p.qty >= 1,
  )
  if (usable.length === 0) return
  try {
    await clientApi.replaceParts(draftId.value, usable.map(toPartIn))
    chosenResultId.value = null
  } catch {
    // a transient save failure is non-fatal; the next edit retries.
  }
}

// ---- optimise ------------------------------------------------------------
async function runOptimise() {
  runFailure.value = null
  const v = draftValidation.value
  if (!v.ok) {
    toast.warn(resolveValidation(v))
    return
  }
  // ensure the latest parts are saved before optimising
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  optimising.value = true
  try {
    await save()
    const run = await clientApi.optimise(draftId.value)
    results.value = run.results
    chosenResultId.value = run.chosen_result_id ?? run.results[0]?.id ?? null
    resultStale.value = false
    ranOnce.value = true
    await loadBranches()
  } catch (e) {
    if (e instanceof ApiError) {
      const key = RUN_ERROR_KEYS[e.code]
      runFailure.value = { code: e.code, detail: key ? `${e.detail}` : e.detail }
    } else throw e
  } finally {
    optimising.value = false
  }
}

async function useAlgorithm(resultId: string) {
  try {
    await clientApi.chooseResult(draftId.value, resultId)
    chosenResultId.value = resultId
    const r = results.value.find((x) => x.id === resultId)
    toast.ok(t('client.algoPicked', { name: r?.algorithm_name ?? '' }))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

// ---- PDF -----------------------------------------------------------------
async function downloadPdf() {
  toast.ok(t('client.pdfPreparing'))
  try {
    const url = await clientApi.openDraftPdf(draftId.value)
    window.open(url, '_blank')
  } catch {
    toast.warn(t('common.loadFailedBody'))
  }
}

// ---- place order ---------------------------------------------------------
async function placeOrder() {
  const v = draftValidation.value
  if (!v.ok) {
    toast.warn(resolveValidation(v))
    return
  }
  if (resultStale.value || !chosenResultId.value) {
    toast.warn(t('client.draftNotUsable'))
    return
  }
  // make sure the chosen result is bound on the server before the wizard reads it
  try {
    await clientApi.chooseResult(draftId.value, chosenResultId.value)
  } catch {
    /* the optimise call already chose one; ignore */
  }
  router.push(`/c/orders/new/${draftId.value}`)
}

// ---- result metrics ------------------------------------------------------
const metrics = computed(() => {
  const r = chosen.value
  if (!r) return null
  const sheets = totalSheets(r)
  const sheetsPerMat = Object.entries(r.sheets_used_by_material)
    .map(
      ([mid, n]) =>
        `${materialShortLabel(materialById(materials.value, mid)) || mid.slice(0, 6)}: ${n}`,
    )
    .join(' · ')
  const edgeBits = Object.entries(r.edge_length_by_thickness)
    .filter(([, v]) => Number(v) > 0)
    .map(([k, v]) => `${k}: ${(Number(v) / 1000).toFixed(1)} m`)
    .join(' · ')
  const placedUnits = r.sheets.reduce((a, s) => a + s.placements.length, 0)
  const totalUnits = parts.value.reduce((a, p) => a + (p.qty || 0), 0)
  return {
    waste: Math.round(r.waste_percentage * 1000) / 10,
    sheets,
    sheetsPerMat,
    edgeTotalM: (r.total_edge_length_mm / 1000).toFixed(1),
    edgeBits: edgeBits || '—',
    cutLenM: (r.total_cut_length_mm / 1000).toFixed(1),
    placed: placedUnits,
    totalUnits,
    allFit: placedUnits >= totalUnits,
  }
})

const showResult = computed(() => results.value.length > 0 && chosen.value !== null)

watch(draftId, () => {
  results.value = []
  ranOnce.value = false
  resultStale.value = false
  load()
})

onMounted(load)
onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

function maxLabel(p: EditablePart) {
  return partMaxFor(materials.value, p.materialId)
}
</script>

<template>
  <div>
    <div v-if="loading" class="card" style="padding: 24px">
      <div class="sk sk-line" style="width: 40%" />
      <div class="sk sk-line" style="width: 100%; margin-top: 16px; height: 60px" />
      <div class="sk sk-line" style="width: 100%; margin-top: 12px; height: 60px" />
    </div>

    <ErrorState v-else-if="loadError" :error="loadError" :retry="load" />

    <div v-else-if="notFound" class="st-empty" style="margin-top: 40px">
      <div class="ic">∅</div>
      <h3>{{ t('client.cuttingNotFound') }}</h3>
      <p>{{ t('client.cuttingNotFoundBody') }}</p>
      <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap">
        <RouterLink class="btn btn-outline" to="/c/cutting/drafts">{{
          t('client.draftsTitle')
        }}</RouterLink>
      </div>
    </div>

    <template v-else>
      <div class="page-head" style="margin-bottom: 12px">
        <div>
          <h1>{{ t('client.cuttingTitle') }}</h1>
          <p class="sub">{{ t('client.cuttingSub') }}</p>
        </div>
      </div>

      <div v-if="readOnly" class="banner" :class="invalidated ? 'warn' : 'success'">
        <div class="ic">{{ invalidated ? '!' : '✓' }}</div>
        <div class="grow">
          <template v-if="invalidated">
            {{ t('client.boundInvalidated') }}
            <RouterLink
              v-if="boundOrderId"
              :to="`/c/orders/${boundOrderId}`"
              style="text-decoration: underline; font-weight: 600"
            >
              {{ t('client.viewCurrentResult') }}
            </RouterLink>
          </template>
          <template v-else>
            {{ t('client.boundSuccess', { order: boundOrderId ? ` (${boundOrderId})` : '' }) }}
          </template>
        </div>
      </div>

      <!-- mode switch -->
      <div class="seg" role="tablist" :aria-label="t('client.inputMethod')">
        <button class="seg-btn on" type="button">{{ t('client.inputManual') }}</button>
        <button
          class="seg-btn"
          type="button"
          disabled
          @click="toast.warn(t('client.inputFileToast'))"
        >
          {{ t('client.inputFile') }} <span class="soon">{{ t('client.inputFileSoon') }}</span>
        </button>
      </div>

      <!-- parts editor -->
      <section class="card editor" :class="{ locked: readOnly }">
        <div class="editor-hd">
          <h2>
            {{ t('client.parts') }}
            <span class="meta">{{ parts.length }} {{ t('client.countUnit') }}</span>
          </h2>
        </div>
        <div class="parts-grid">
          <div v-for="(p, idx) in parts" :key="p.ref" class="part-row">
            <div class="rownum">#{{ idx + 1 }}</div>
            <div class="matwrap">
              <button
                class="mat-btn"
                type="button"
                :disabled="readOnly"
                @click="openMatPicker(p.ref)"
              >
                <span
                  class="sw"
                  :style="
                    p.materialId
                      ? { background: 'var(--accent)' }
                      : { background: 'var(--sunk)', border: '1px dashed var(--line)' }
                  "
                />
                <span class="lab">
                  <template v-if="materialById(materials, p.materialId)">
                    {{ materialShortLabel(materialById(materials, p.materialId)) }}
                    <small style="color: var(--ink-6); font: 400 10.5px var(--f-mono)"
                      >{{ materialById(materials, p.materialId)?.thickness_mm }}mm</small
                    >
                    <span
                      v-if="materialById(materials, p.materialId)?.grain_direction"
                      class="grain-ic"
                      :title="t('client.grainTitle')"
                    >
                      <span class="arr">↑</span>{{ t('client.grain') }}
                    </span>
                  </template>
                  <span v-else class="placeholder">{{ t('client.materialPick') }}</span>
                </span>
              </button>
              <button
                class="src-chip"
                :class="{ own: p.source === 'own' }"
                type="button"
                :disabled="readOnly"
                :title="t('client.srcTitle')"
                @click="toggleSource(p.ref)"
              >
                {{ p.source === 'own' ? t('client.srcOwn') : t('client.srcShop') }}
              </button>
            </div>
            <input
              class="num"
              :class="{
                bad: maxLabel(p) && p.l != null && (p.l < LIMITS.PART_MIN || p.l > maxLabel(p)!.l),
              }"
              type="number"
              :placeholder="t('client.colLength')"
              min="50"
              :disabled="readOnly"
              :value="p.l ?? ''"
              :aria-label="t('client.ariaLength')"
              @input="onNumInput(p, 'l', ($event.target as HTMLInputElement).value)"
            />
            <input
              class="num"
              :class="{
                bad: maxLabel(p) && p.w != null && (p.w < LIMITS.PART_MIN || p.w > maxLabel(p)!.w),
              }"
              type="number"
              :placeholder="t('client.colWidth')"
              min="50"
              :disabled="readOnly"
              :value="p.w ?? ''"
              :aria-label="t('client.ariaWidth')"
              @input="onNumInput(p, 'w', ($event.target as HTMLInputElement).value)"
            />
            <input
              class="num"
              type="number"
              :placeholder="t('client.colQty')"
              min="1"
              :disabled="readOnly"
              :value="p.qty"
              :aria-label="t('client.ariaQty')"
              @input="onNumInput(p, 'qty', ($event.target as HTMLInputElement).value)"
            />
            <button
              class="edges-btn"
              type="button"
              :disabled="readOnly"
              :title="t('client.edgesBtnTitle')"
              @click="openEdges(p.ref)"
            >
              <span class="e" :class="{ has: !!p.edges.t }">{{ p.edges.t ?? '–' }}</span>
              <span class="e" :class="{ has: !!p.edges.b }">{{ p.edges.b ?? '–' }}</span>
              <span class="e" :class="{ has: !!p.edges.l }">{{ p.edges.l ?? '–' }}</span>
              <span class="e" :class="{ has: !!p.edges.r }">{{ p.edges.r ?? '–' }}</span>
            </button>
            <div class="row-menu">
              <button
                class="rm-btn"
                type="button"
                :disabled="readOnly"
                :title="t('client.duplicate')"
                @click="duplicatePart(p.ref)"
              >
                ⧉
              </button>
              <button
                class="rm-btn danger"
                type="button"
                :disabled="readOnly"
                :title="t('common.delete')"
                @click="deletePart(p.ref)"
              >
                ✕
              </button>
            </div>
            <div
              v-if="
                !rowValidation(p).ok &&
                rowValidation(p).code !== 'incomplete' &&
                rowValidation(p).code !== 'no_material'
              "
              class="row-err"
            >
              {{ t(rowValidation(p).key ?? '', rowValidation(p).params) }}
            </div>
          </div>
        </div>
        <div v-if="!readOnly" style="padding: 10px 16px 16px">
          <button class="btn btn-outline" type="button" @click="addPart">
            {{ t('client.addPart') }}
          </button>
        </div>
      </section>

      <!-- branches indicator -->
      <div
        v-if="!readOnly && branches"
        class="br-strip"
        :class="{ warn: branches.mode === 'none' }"
      >
        <span class="ic">{{
          branches.mode === 'none' ? '!' : branches.mode === 'any' ? '✓' : branches.branches.length
        }}</span>
        <span v-if="branches.mode === 'any'">{{ t('client.brAnyShop') }}</span>
        <span
          v-else-if="branches.mode === 'none'"
          v-html="
            t('client.brNoneWarn', {
              names: branches.uncovered_material_ids
                .map((id) => materialShortLabel(materialById(materials, id)) || id.slice(0, 6))
                .join(' · '),
            })
          "
        />
        <template v-else>
          <span>
            <b>{{ t('client.brAvailable', { n: branches.branches.length }) }}</b> ·
            <span class="br-names">{{
              branches.branches
                .slice(0, 3)
                .map((b) => b.name)
                .join(' · ')
            }}</span>
            <template v-if="branches.branches.length > 3">
              {{ t('client.brMore', { n: branches.branches.length - 3 }) }}</template
            >
          </span>
          <span style="margin-left: auto; font: 500 12px var(--f-ui); color: var(--ink-6)">{{
            t('client.brPickedLater')
          }}</span>
        </template>
      </div>

      <!-- optimise -->
      <div v-if="!readOnly" class="run">
        <button class="btn btn-acc" type="button" :disabled="optimiseDisabled" @click="runOptimise">
          {{
            optimising
              ? t('client.optimising')
              : ranOnce
                ? t('client.optimiseRerun')
                : t('client.optimise')
          }}
        </button>
        <span class="sub">{{ optimiseHint }}</span>
      </div>

      <div
        v-if="runFailure"
        class="br-strip warn"
        style="margin-top: 14px; align-items: flex-start"
      >
        <span class="ic">!</span>
        <span>
          <b>{{ t('client.optFailed') }}</b> ·
          <code style="font: 600 11.5px var(--f-mono)">{{ runFailure.code }}</code
          ><br />
          {{ runFailure.detail }}
        </span>
      </div>

      <!-- result panel -->
      <section v-if="showResult && chosen && metrics" class="result">
        <div class="result-hd">
          <h2>{{ t('client.resultTitle') }}</h2>
          <span v-if="resultStale" class="stale">{{ t('client.staleBadge') }}</span>
        </div>

        <div class="metrics-strip">
          <div
            class="metric"
            :class="metrics.waste <= 10 ? 'ok' : metrics.waste >= 18 ? 'warn' : ''"
          >
            <div class="lab">{{ t('client.metricWaste') }}</div>
            <div class="v">{{ metrics.waste }}%</div>
            <div class="sub">{{ t('client.metricWasteSub') }}</div>
          </div>
          <div class="metric">
            <div class="lab">{{ t('client.metricSheets') }}</div>
            <div class="v">{{ metrics.sheets }}</div>
            <div class="sub">{{ metrics.sheetsPerMat }}</div>
          </div>
          <div class="metric">
            <div class="lab">{{ t('client.metricEdge') }}</div>
            <div class="v">{{ metrics.edgeTotalM }} m</div>
            <div class="sub">{{ metrics.edgeBits }}</div>
          </div>
          <div class="metric" :class="metrics.allFit ? 'ok' : 'warn'">
            <div class="lab">{{ t('client.metricParts') }}</div>
            <div class="v">
              {{ metrics.placed }} / {{ metrics.totalUnits }} {{ metrics.allFit ? '✓' : '✕' }}
            </div>
            <div class="sub">{{ t('client.metricCutLen', { m: metrics.cutLenM }) }}</div>
          </div>
        </div>

        <!-- algorithm comparison -->
        <div class="algos" :class="{ open: algosOpen }">
          <div class="algos-hd">
            <span
              >{{ t('client.curAlgo') }}: <b>{{ chosen.algorithm_name }}</b> ·
              {{
                t('client.algoSummary', {
                  waste: metrics.waste,
                  sheets: metrics.sheets,
                  cut: metrics.cutLenM,
                })
              }}</span
            >
            <button class="expand" type="button" @click="algosOpen = !algosOpen">
              {{ t('client.otherAlgos') }}
            </button>
          </div>
          <div class="algos-list">
            <table>
              <thead>
                <tr>
                  <th>{{ t('client.algoCol') }}</th>
                  <th>{{ t('client.wasteCol') }}</th>
                  <th>{{ t('client.sheetsCol') }}</th>
                  <th>{{ t('client.cutLenCol') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in results" :key="a.id" :class="{ chosen: a.id === chosenResultId }">
                  <td>
                    {{ a.algorithm_name }}
                    <span v-if="a.id === chosenResultId" class="badge">{{
                      t('client.chosen')
                    }}</span>
                  </td>
                  <td>{{ Math.round(a.waste_percentage * 1000) / 10 }}%</td>
                  <td>{{ totalSheets(a) }}</td>
                  <td>{{ (a.total_cut_length_mm / 1000).toFixed(1) }} m</td>
                  <td>
                    <button
                      v-if="a.id !== chosenResultId && !readOnly"
                      class="use"
                      type="button"
                      @click="useAlgorithm(a.id)"
                    >
                      {{ t('client.useThis') }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <SheetVisualiser :result="chosen" :materials="materials" />

        <div class="result-actions">
          <button v-if="!readOnly" class="btn btn-acc" type="button" @click="placeOrder">
            {{ t('client.placeOrder') }}
          </button>
          <button class="btn btn-outline" type="button" @click="downloadPdf">
            {{ t('client.downloadPdf') }}
          </button>
        </div>
      </section>
    </template>

    <MaterialPicker v-model:open="matPickerOpen" :materials="materials" @pick="onPickMaterial" />
    <EdgesPopover v-model:open="edgesOpen" :edges="editingEdges" @apply="onApplyEdges" />
  </div>
</template>

<style scoped>
.seg {
  display: inline-flex;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.seg-btn {
  padding: 7px 14px;
  background: transparent;
  border: 0;
  border-radius: 6px;
  color: var(--ink-8);
  font: 500 13px var(--f-ui);
  cursor: pointer;
}
.seg-btn.on {
  background: var(--elev);
  color: var(--ink-12);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.seg-btn[disabled] {
  opacity: 0.55;
  cursor: not-allowed;
}
.seg-btn .soon {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 6px;
  font: 600 9.5px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-6);
  background: var(--line);
  border-radius: 999px;
}

.editor {
  margin-top: 18px;
}
.editor.locked {
  opacity: 0.78;
}
.editor-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  gap: 14px;
  flex-wrap: wrap;
}
.editor-hd h2 {
  font: 600 16px var(--f-display);
  color: var(--ink-12);
  margin: 0;
}
.editor-hd .meta {
  font: 500 12px var(--f-ui);
  color: var(--ink-6);
}
.parts-grid {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
}
.part-row {
  display: grid;
  grid-template-columns: 28px minmax(160px, 1.7fr) 70px 70px 60px 110px 56px;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.part-row .rownum {
  font: 600 12px var(--f-mono);
  color: var(--ink-6);
  text-align: center;
}
.matwrap {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.mat-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  background: var(--sunk);
  border-radius: 6px;
  cursor: pointer;
  font: 500 12.5px var(--f-ui);
  color: var(--ink-12);
  text-align: left;
}
.mat-btn .sw {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  flex-shrink: 0;
}
.mat-btn .lab {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mat-btn .placeholder {
  color: var(--ink-6);
}
.src-chip {
  padding: 3px 8px;
  font: 600 10.5px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink-8);
  cursor: pointer;
  white-space: nowrap;
}
.src-chip.own {
  background: rgba(166, 71, 31, 0.08);
  border-color: rgba(166, 71, 31, 0.3);
  color: var(--accent);
}
.grain-ic {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  font: 600 10px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-8);
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 4px;
}
.grain-ic .arr {
  font: 700 11px var(--f-mono);
  color: var(--ink-12);
}
input.num {
  padding: 7px 8px;
  border: 1px solid var(--line);
  border-radius: 5px;
  font: 500 13px var(--f-mono);
  background: var(--elev);
  color: var(--ink-12);
  width: 100%;
  box-sizing: border-box;
}
input.num:focus {
  outline: 0;
  border-color: var(--ink-12);
}
input.num.bad {
  border-color: var(--danger);
  background: rgba(180, 38, 38, 0.05);
}
.edges-btn {
  padding: 6px 8px;
  border: 1px solid var(--line);
  background: var(--sunk);
  border-radius: 5px;
  font: 600 11px var(--f-mono);
  cursor: pointer;
  color: var(--ink-12);
  display: flex;
  gap: 4px;
  justify-content: center;
}
.edges-btn .e {
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--elev);
  border: 1px solid var(--line);
  min-width: 22px;
  text-align: center;
}
.edges-btn .e.has {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.row-menu {
  display: flex;
  gap: 4px;
}
.rm-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--line);
  background: var(--sunk);
  border-radius: 5px;
  cursor: pointer;
  color: var(--ink-8);
}
.rm-btn.danger:hover {
  border-color: var(--danger);
  color: var(--danger);
}
.row-err {
  grid-column: 1 / -1;
  font: 500 11.5px var(--f-ui);
  color: var(--danger);
  padding: 2px 4px 0;
}
@media (max-width: 760px) {
  .part-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 10px;
    padding: 12px;
  }
  .matwrap {
    flex: 1 1 55%;
  }
  input.num {
    flex: 1 1 72px;
    min-width: 64px;
  }
  .edges-btn {
    flex: 1 1 100%;
    justify-content: flex-start;
  }
}

.br-strip {
  margin-top: 14px;
  padding: 12px 16px;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  font: 500 13px var(--f-ui);
  color: var(--ink-10);
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}
.br-strip.warn {
  border-left-color: #b87024;
  background: rgba(184, 112, 36, 0.06);
  color: var(--ink-12);
}
.br-strip .ic {
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: var(--elev);
  color: var(--accent);
  font: 700 13px var(--f-mono);
}
.br-strip b {
  color: var(--ink-12);
  font-weight: 600;
}
.br-names {
  color: var(--ink-12);
  font-weight: 600;
}

.run {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.run .sub {
  font: 500 12.5px var(--f-ui);
  color: var(--ink-6);
}

.result {
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px dashed var(--line);
}
.result-hd {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.result-hd h2 {
  font: 600 22px var(--f-display);
  color: var(--ink-12);
  margin: 0;
}
.result-hd .stale {
  padding: 4px 10px;
  font: 600 11px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #b87024;
  background: rgba(184, 112, 36, 0.1);
  border-radius: 999px;
}
.metrics-strip {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
@media (min-width: 700px) {
  .metrics-strip {
    grid-template-columns: repeat(4, 1fr);
  }
}
.metric {
  padding: 14px 16px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.metric .lab {
  font: 600 10.5px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-6);
  margin-bottom: 4px;
}
.metric .v {
  font: 600 22px var(--f-display);
  color: var(--ink-12);
}
.metric .sub {
  font: 400 11.5px var(--f-mono);
  color: var(--ink-6);
  margin-top: 2px;
}
.metric.ok .v {
  color: #2d6045;
}
.metric.warn .v {
  color: #b87024;
}

.algos {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 18px;
}
.algos-hd {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font: 500 13px var(--f-ui);
  color: var(--ink-10);
}
.algos-hd .expand {
  background: transparent;
  border: 0;
  cursor: pointer;
  padding: 4px 8px;
  color: var(--ink-8);
  font: 500 12px var(--f-ui);
}
.algos-list {
  display: none;
}
.algos.open .algos-list {
  display: block;
}
.algos-list table {
  width: 100%;
  border-collapse: collapse;
}
.algos-list th,
.algos-list td {
  text-align: left;
  padding: 10px 16px;
  font: 500 12.5px var(--f-mono);
  border-top: 1px solid var(--line);
  color: var(--ink-10);
}
.algos-list th {
  font: 600 10.5px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-6);
  background: var(--sunk);
}
.algos-list tr.chosen td {
  background: rgba(166, 71, 31, 0.05);
  color: var(--ink-12);
}
.algos-list .use {
  padding: 4px 10px;
  border: 1px solid var(--line);
  background: var(--sunk);
  border-radius: 5px;
  font: 500 11px var(--f-ui);
  cursor: pointer;
  color: var(--ink-12);
}
.algos-list .badge {
  padding: 2px 8px;
  font: 600 10px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--accent);
  color: #fff;
  border-radius: 999px;
}
.result-actions {
  display: flex;
  gap: 10px;
  margin-top: 22px;
  flex-wrap: wrap;
}
</style>
