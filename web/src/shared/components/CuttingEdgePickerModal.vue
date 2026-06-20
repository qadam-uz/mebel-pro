<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  type EdgeField,
} from '@/shared/app/cuttingDisplay'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import {
  useCuttingStore,
  type CuttingEdgeBand,
  type CuttingPart,
  type MaterialSource,
} from '@/shared/stores/cutting'

// CB-93 seam: the edge-banding modal. The editor owns which part is open
// (`part` prop = the part being edited, null = closed) and the preferred-edge memory;
// this dialog owns its own working selection (sides / source / search / thickness),
// the recommended-edge ranking, the Tab focus-trap, the Escape handler, and the body
// scroll-lock. It EMITS the chosen edges on apply (the editor writes them onto the
// part + remembers the material) and `close` on cancel — it never mutates the part.
// Focus RETURN stays in the editor (it captured the trigger element), so this only
// focuses the dialog on open.
const props = defineProps<{
  part: CuttingPart | null
  partNumber: number
  preferredEdgeId: string | null
  preferredBranchId: string | null
  preferredBranchName: string
  // Overrides the "qism #N" part of the title — used for bulk apply ("N qismga").
  titleSuffix?: string
}>()
const emit = defineEmits<{
  apply: [{ edges: Record<EdgeField, CuttingEdgeBand | null>; rememberedMaterialId: string | null }]
  close: []
}>()

const cutting = useCuttingStore()

const edgePickerState = ref<Record<EdgeField, CuttingEdgeBand | null>>(blankEdgeState())
const edgePickerSource = ref<MaterialSource>('shop')
const edgePickerSearch = ref('')
const edgePickerThickness = ref<string | null>('all')
const edgeDialogRef = ref<HTMLElement | null>(null)
// The searchable tape list is revealed on demand. Open it by default only when the
// part has no banding yet (the first-time pick); when editing a part that already
// has a tape, collapse to the compact summary + an "O'zgartirish" toggle.
const showTapeList = ref(false)

const sideNames: Record<EdgeField, string> = {
  edge_top: 'Yuqori',
  edge_bottom: 'Pastki',
  edge_left: 'Chap',
  edge_right: "O'ng",
}

const edgePatterns: Array<{ key: string; label: string; hint: string; sides: EdgeField[] }> = [
  { key: 'none', label: 'Hech qaysi', hint: 'Krom olib tashlanadi', sides: [] },
  { key: 'all', label: 'Hamma tomon', hint: "Ko'p ishlatiladi", sides: [...edgeFields] },
  {
    key: 'tb',
    label: 'Yuqori + pastki',
    hint: 'Uzun tomonlar',
    sides: ['edge_top', 'edge_bottom'],
  },
  { key: 'lr', label: "Chap + o'ng", hint: 'Yon tomonlar', sides: ['edge_left', 'edge_right'] },
]

function blankEdgeState(): Record<EdgeField, CuttingEdgeBand | null> {
  return { edge_top: null, edge_bottom: null, edge_left: null, edge_right: null }
}

function materialById(id: string | null | undefined) {
  return cutting.panelOptions.find((material) => material.id === id) ?? null
}

function edgeById(id: string | null | undefined) {
  return cutting.edgeOptions.find((material) => material.id === id) ?? null
}

function bandedEdgeFields(state: Record<EdgeField, CuttingEdgeBand | null>) {
  return edgeFields.filter((side) => state[side])
}

function commonEdgeSource(part: CuttingPart): MaterialSource {
  return (
    part.edge_top?.source ??
    part.edge_bottom?.source ??
    part.edge_left?.source ??
    part.edge_right?.source ??
    'shop'
  )
}

function cloneEdgeStateFromPart(part: CuttingPart): Record<EdgeField, CuttingEdgeBand | null> {
  return {
    edge_top: part.edge_top ? { ...part.edge_top } : null,
    edge_bottom: part.edge_bottom ? { ...part.edge_bottom } : null,
    edge_left: part.edge_left ? { ...part.edge_left } : null,
    edge_right: part.edge_right ? { ...part.edge_right } : null,
  }
}

function firstEdgeId(edges: Record<EdgeField, CuttingEdgeBand | null>) {
  return (
    edges.edge_top?.material_id ??
    edges.edge_bottom?.material_id ??
    edges.edge_left?.material_id ??
    edges.edge_right?.material_id ??
    null
  )
}

function recommendedEdgeForPart() {
  const part = props.part
  if (!part) return null
  return recommendedEdge(
    materialById(part.material_id),
    cutting.edgeOptions,
    edgePickerSelectedMaterialId.value,
    props.preferredEdgeId,
  )
}

function pickerSideThickness(side: EdgeField) {
  const material = edgeById(edgePickerState.value[side]?.material_id)
  return material?.thickness_mm ? `${material.thickness_mm}mm` : ''
}

// Tailwind classes for a side strip in the diagram: filled (shop = accent, own =
// dark teal) when banded, dashed/muted when empty.
function sideClass(side: EdgeField) {
  const edge = edgePickerState.value[side]
  if (!edge) {
    return 'border border-dashed border-hairline-strong bg-sunk text-ink-muted hover:border-ink-soft'
  }
  return edge.source === 'own' ? 'bg-[#0b5a54] text-white' : 'bg-accent text-white'
}

function sideAria(side: EdgeField) {
  return `${sideNames[side]} tomon — ${edgePickerState.value[side] ? 'krom bor, bosib olib tashlang' : "krom qo'shing"}`
}

const edgeThicknessOptions = computed<ChoiceOption[]>(() => {
  const values = [...new Set(cutting.edgeOptions.map((material) => material.thickness_mm))]
    .filter(Boolean)
    .sort((left, right) => Number(left) - Number(right))
  return [
    { value: 'all', label: 'Hamma qalinlik', meta: 'Barcha kromlar' },
    ...values.map((value) => ({ value, label: `${value} mm`, meta: 'Qalinlik' })),
  ]
})
const edgePickerMaterials = computed(() => {
  const part = props.part
  if (!part) return []
  const query = edgePickerSearch.value.trim().toLowerCase()
  return rankedEdges(materialById(part.material_id), cutting.edgeOptions)
    .filter(({ material }) =>
      edgePickerThickness.value && edgePickerThickness.value !== 'all'
        ? material.thickness_mm === edgePickerThickness.value
        : true,
    )
    .filter(({ material }) => {
      if (!query) return true
      return edgeSearchText(material).includes(query)
    })
})
const edgePickerActiveSides = computed(() => bandedEdgeFields(edgePickerState.value))
const edgePickerPatternKey = computed(() => {
  const active = edgePickerActiveSides.value
  return (
    edgePatterns.find(
      (pattern) =>
        pattern.sides.length === active.length &&
        pattern.sides.every((side) => active.includes(side)),
    )?.key ?? null
  )
})
const edgePickerSelectedMaterialId = computed(() => {
  const first = edgePickerActiveSides.value
    .map((side) => edgePickerState.value[side]?.material_id)
    .find(Boolean)
  return first ?? null
})
const selectedEdgeMaterial = computed(() => edgeById(edgePickerSelectedMaterialId.value))
const edgePickerBranchNote = computed(() => {
  if (!props.preferredBranchId) return null
  const missing = new Map<string, string>()
  for (const side of edgeFields) {
    const edge = edgePickerState.value[side]
    if (!edge || edge.source === 'own') continue
    const material = edgeById(edge.material_id)
    if (material && !material.branch_carried) {
      missing.set(material.id, edgeShortLabel(material, true))
    }
  }
  if (!missing.size) return null
  return `${props.preferredBranchName} filialida ${[...missing.values()].join(' · ')} hozir mavjud emas. Manbani "O'zim olib kelaman" qiling yoki boshqa krom tanlang.`
})

function applyEdgePattern(key: string) {
  if (!props.part) return
  const pattern = edgePatterns.find((item) => item.key === key)
  if (!pattern) return
  if (pattern.sides.length === 0) {
    edgePickerState.value = blankEdgeState()
    return
  }
  const fallback = recommendedEdgeForPart()
  if (!fallback) return
  const next = blankEdgeState()
  for (const side of pattern.sides) {
    next[side] = { material_id: fallback.id, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

function togglePickerSide(side: EdgeField) {
  if (!props.part) return
  const next = { ...edgePickerState.value }
  if (next[side]) {
    next[side] = null
  } else {
    const fallback = recommendedEdgeForPart()
    if (!fallback) return
    next[side] = { material_id: fallback.id, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

function setPickerSource(source: MaterialSource) {
  edgePickerSource.value = source
  const next = { ...edgePickerState.value }
  for (const side of edgeFields) {
    if (next[side]) next[side] = { ...next[side], source }
  }
  edgePickerState.value = next
}

function selectPickerMaterial(materialId: string) {
  const active = edgePickerActiveSides.value
  const targetSides = active.length ? active : edgeFields
  const next = { ...edgePickerState.value }
  for (const side of targetSides) {
    next[side] = { material_id: materialId, source: edgePickerSource.value }
  }
  edgePickerState.value = next
}

function applyEdgePicker() {
  const edges: Record<EdgeField, CuttingEdgeBand | null> = {
    edge_top: edgePickerState.value.edge_top ? { ...edgePickerState.value.edge_top } : null,
    edge_bottom: edgePickerState.value.edge_bottom
      ? { ...edgePickerState.value.edge_bottom }
      : null,
    edge_left: edgePickerState.value.edge_left ? { ...edgePickerState.value.edge_left } : null,
    edge_right: edgePickerState.value.edge_right ? { ...edgePickerState.value.edge_right } : null,
  }
  emit('apply', { edges, rememberedMaterialId: firstEdgeId(edges) })
}

const EDGE_FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Trap Tab/Shift-Tab inside the modal so keyboard/SR users can't reach the obscured
// part rows behind the scrim (CB-06; mirrors ConfirmDialog).
function trapEdgeFocus(event: KeyboardEvent) {
  const root = edgeDialogRef.value
  if (!root) return
  const focusable = Array.from(root.querySelectorAll<HTMLElement>(EDGE_FOCUSABLE)).filter(
    (element) => element.getClientRects().length > 0,
  )
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) {
    event.preventDefault()
    root.focus()
    return
  }
  const active = document.activeElement
  if (event.shiftKey) {
    if (active === first || active === root) {
      event.preventDefault()
      last.focus()
    }
  } else if (active === last) {
    event.preventDefault()
    first.focus()
  }
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (!props.part) return
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (event.key === 'Tab') trapEdgeFocus(event)
}

// Open/close are driven by the `part` prop. On open: seed the working selection
// from the part, lock the body, listen for Escape/Tab, and focus the dialog. On
// close: undo those. Focus RETURN to the trigger is the editor's job.
watch(
  () => props.part,
  (part, previous) => {
    if (part && !previous) {
      edgePickerState.value = cloneEdgeStateFromPart(part)
      const active = bandedEdgeFields(edgePickerState.value)
      edgePickerSource.value =
        active.length > 0 && active.every((side) => edgePickerState.value[side]?.source === 'own')
          ? 'own'
          : commonEdgeSource(part)
      // First-time pick (no banding yet) opens the tape list; editing an existing
      // banded part starts collapsed to the compact summary.
      showTapeList.value = active.length === 0
      edgePickerSearch.value = ''
      edgePickerThickness.value = 'all'
      lockBodyScroll()
      document.addEventListener('keydown', onDocumentKeydown)
      void nextTick(() => edgeDialogRef.value?.focus())
    } else if (!part && previous) {
      unlockBodyScroll()
      document.removeEventListener('keydown', onDocumentKeydown)
      edgePickerState.value = blankEdgeState()
      edgePickerSearch.value = ''
      edgePickerThickness.value = 'all'
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKeydown)
  if (props.part) unlockBodyScroll()
})
</script>

<template>
  <template v-if="part">
    <div class="client-modal-scrim" @click="emit('close')"></div>
    <section
      ref="edgeDialogRef"
      class="client-edge-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edge-picker-title"
      tabindex="-1"
    >
      <div class="client-edge-modal-h">
        <h3 id="edge-picker-title">
          Krom yopishtirish — {{ titleSuffix ?? `qism #${partNumber}` }}
        </h3>
        <button
          type="button"
          class="client-edge-close"
          aria-label="Krom oynasini yopish"
          @click="emit('close')"
        >
          ×
        </button>
      </div>

      <div class="client-edge-modal-b">
        <div class="flex flex-wrap gap-2" aria-label="Krom tomoni shablonlari">
          <button
            v-for="pattern in edgePatterns"
            :key="pattern.key"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
            :class="
              edgePickerPatternKey === pattern.key
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-hairline-strong bg-elevated text-ink hover:border-ink-soft'
            "
            :disabled="pattern.sides.length > 0 && !recommendedEdgeForPart()"
            @click="applyEdgePattern(pattern.key)"
          >
            {{ pattern.label }}
            <span
              v-if="pattern.key === 'all'"
              class="rounded bg-accent px-1.5 py-0.5 text-[9px] font-extrabold text-white"
              >tez</span
            >
          </button>
        </div>

        <div
          class="mx-auto grid w-full max-w-[340px] grid-cols-[62px_minmax(0,1fr)_62px] grid-rows-[34px_92px_34px] items-stretch gap-1.5"
          aria-label="Krom tomonlari"
        >
          <span></span>
          <button
            type="button"
            class="flex items-center justify-center gap-1.5 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_top')"
            :aria-pressed="Boolean(edgePickerState.edge_top)"
            :aria-label="sideAria('edge_top')"
            @click="togglePickerSide('edge_top')"
          >
            <span>{{ sideNames.edge_top }}</span>
            <span v-if="edgePickerState.edge_top" class="font-mono text-[10px] opacity-90">{{
              pickerSideThickness('edge_top')
            }}</span>
            <span v-else class="text-sm leading-none opacity-70">+</span>
          </button>
          <span></span>

          <button
            type="button"
            class="flex items-center justify-center rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_left')"
            :aria-pressed="Boolean(edgePickerState.edge_left)"
            :aria-label="sideAria('edge_left')"
            @click="togglePickerSide('edge_left')"
          >
            {{ sideNames.edge_left }}
          </button>
          <div
            class="flex flex-col items-center justify-center gap-1 rounded-md border border-hairline text-ink-muted"
            style="
              background: repeating-linear-gradient(
                45deg,
                var(--color-sunk),
                var(--color-sunk) 7px,
                var(--color-elevated) 7px,
                var(--color-elevated) 14px
              );
            "
          >
            <span class="text-xs font-bold">Qism</span>
            <span v-if="part" class="font-mono text-[11px] font-bold text-ink-soft"
              >{{ part.length_mm }} × {{ part.width_mm }}</span
            >
          </div>
          <button
            type="button"
            class="flex items-center justify-center rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_right')"
            :aria-pressed="Boolean(edgePickerState.edge_right)"
            :aria-label="sideAria('edge_right')"
            @click="togglePickerSide('edge_right')"
          >
            {{ sideNames.edge_right }}
          </button>

          <span></span>
          <button
            type="button"
            class="flex items-center justify-center gap-1.5 rounded-md px-1 text-center text-[11px] font-bold leading-tight transition"
            :class="sideClass('edge_bottom')"
            :aria-pressed="Boolean(edgePickerState.edge_bottom)"
            :aria-label="sideAria('edge_bottom')"
            @click="togglePickerSide('edge_bottom')"
          >
            <span>{{ sideNames.edge_bottom }}</span>
            <span v-if="edgePickerState.edge_bottom" class="font-mono text-[10px] opacity-90">{{
              pickerSideThickness('edge_bottom')
            }}</span>
            <span v-else class="text-sm leading-none opacity-70">+</span>
          </button>
          <span></span>
        </div>

        <div
          v-if="selectedEdgeMaterial && !showTapeList"
          class="flex items-center gap-3 rounded-xl border border-hairline bg-elevated p-3"
        >
          <span
            class="size-9 shrink-0 rounded-lg border border-hairline"
            :style="{ background: colorForMaterial(selectedEdgeMaterial.color) }"
          ></span>
          <div class="min-w-0">
            <div class="truncate text-sm font-bold text-ink">
              {{ edgeShortLabel(selectedEdgeMaterial) }}
            </div>
            <div class="font-mono text-[11.5px] text-ink-muted">
              {{ selectedEdgeMaterial.name }} · {{ edgePickerActiveSides.length }} tomonga
            </div>
          </div>
          <button
            type="button"
            class="ml-auto shrink-0 text-sm font-bold text-accent"
            @click="showTapeList = true"
          >
            O'zgartirish →
          </button>
        </div>

        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-xs font-bold text-ink-muted">Manba:</span>
          <div class="inline-flex overflow-hidden rounded-lg border border-hairline-strong">
            <button
              type="button"
              class="px-3.5 py-2 text-xs font-bold transition"
              :class="
                edgePickerSource === 'shop' ? 'bg-accent text-white' : 'bg-elevated text-ink-muted'
              "
              :aria-pressed="edgePickerSource === 'shop'"
              @click="setPickerSource('shop')"
            >
              Ustaxonadan
            </button>
            <button
              type="button"
              class="border-l border-hairline-strong px-3.5 py-2 text-xs font-bold transition"
              :class="
                edgePickerSource === 'own' ? 'bg-accent text-white' : 'bg-elevated text-ink-muted'
              "
              :aria-pressed="edgePickerSource === 'own'"
              @click="setPickerSource('own')"
            >
              O'zim olib kelaman
            </button>
          </div>
          <span class="text-[11.5px] text-ink-muted">{{
            edgePickerSource === 'shop' ? "narxga qo'shiladi" : 'faqat yopishtirish'
          }}</span>
        </div>

        <div v-if="showTapeList" class="ep-tools">
          <input
            v-model="edgePickerSearch"
            class="ep-search"
            type="search"
            placeholder="Krom nomi, decor yoki rang..."
            aria-label="Krom qidirish"
          />
          <FormSelect
            v-model="edgePickerThickness"
            class="picker-select"
            label="Qalinlik"
            :options="edgeThicknessOptions"
          />
          <div class="ep-edge-list">
            <button
              v-for="{ material, rank } in edgePickerMaterials"
              :key="material.id"
              type="button"
              class="ep-edge-opt"
              :class="{ on: edgePickerSelectedMaterialId === material.id }"
              @click="selectPickerMaterial(material.id)"
            >
              <span class="rad" aria-hidden="true"></span>
              <span class="sw" :style="{ background: colorForMaterial(material.color) }"></span>
              <span class="lab">
                <span class="nm">
                  {{ edgeShortLabel(material) }}
                  <span v-if="rank < 2" class="fav">Mos</span>
                </span>
                <span class="meta">{{ material.name }}</span>
              </span>
              <span class="thk">{{ material.thickness_mm }} mm</span>
            </button>
            <div v-if="edgePickerMaterials.length === 0" class="ep-empty">
              Mos krom topilmadi. Qidiruv yoki qalinlikni o'zgartiring.
            </div>
          </div>
        </div>

        <div v-if="edgePickerBranchNote" class="ep-branch-note">
          {{ edgePickerBranchNote }}
        </div>
      </div>

      <div class="client-edge-modal-f">
        <button type="button" class="mp-button mp-button-outline" @click="emit('close')">
          Bekor qilish
        </button>
        <button type="button" class="mp-button mp-button-primary" @click="applyEdgePicker">
          Qo'llash
        </button>
      </div>
    </section>
  </template>
</template>
