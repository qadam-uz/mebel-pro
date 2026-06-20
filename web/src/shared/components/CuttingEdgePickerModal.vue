<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { rankedEdges, recommendedEdge } from '@/shared/app/cuttingEdgeDisplay'
import {
  colorForMaterial,
  edgeFields,
  edgeSearchText,
  edgeShortLabel,
  edgeTinyLabel,
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

function pickerSideLabel(side: EdgeField) {
  return edgeTinyLabel(edgeById(edgePickerState.value[side]?.material_id))
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
        <p class="ep-help">
          {{
            edgePickerMaterials.some((item) => item.rank < 2)
              ? "Mos kromlar ro'yxatda yuqorida turadi; kerak bo'lsa rang yoki qalinlik bo'yicha tanlang."
              : "Bu panel uchun mos krom topilmadi; katalogdan rang yoki qalinlik bo'yicha tanlang."
          }}
        </p>

        <div class="ep-patterns" aria-label="Krom tomoni shablonlari">
          <button
            v-for="pattern in edgePatterns"
            :key="pattern.key"
            type="button"
            class="ep-pattern"
            :class="{ on: edgePickerPatternKey === pattern.key }"
            :disabled="pattern.sides.length > 0 && !recommendedEdgeForPart()"
            @click="applyEdgePattern(pattern.key)"
          >
            <span class="nm">{{ pattern.label }}</span>
            <span class="meta">{{ pattern.hint }}</span>
          </button>
        </div>

        <div class="edge-diagram" aria-label="Krom tomonlari">
          <span class="lbl">Yuqori</span>
          <button
            type="button"
            class="edge-btn h"
            :class="{
              set: Boolean(edgePickerState.edge_top),
              own: edgePickerState.edge_top?.source === 'own',
            }"
            :aria-pressed="Boolean(edgePickerState.edge_top)"
            @click="togglePickerSide('edge_top')"
          >
            {{ edgePickerState.edge_top ? pickerSideLabel('edge_top') : '-' }}
          </button>
          <div class="mid">
            <button
              type="button"
              class="edge-btn v"
              :class="{
                set: Boolean(edgePickerState.edge_left),
                own: edgePickerState.edge_left?.source === 'own',
              }"
              :aria-pressed="Boolean(edgePickerState.edge_left)"
              @click="togglePickerSide('edge_left')"
            >
              {{ edgePickerState.edge_left ? pickerSideLabel('edge_left') : '-' }}
            </button>
            <div class="panel">Qism</div>
            <button
              type="button"
              class="edge-btn v"
              :class="{
                set: Boolean(edgePickerState.edge_right),
                own: edgePickerState.edge_right?.source === 'own',
              }"
              :aria-pressed="Boolean(edgePickerState.edge_right)"
              @click="togglePickerSide('edge_right')"
            >
              {{ edgePickerState.edge_right ? pickerSideLabel('edge_right') : '-' }}
            </button>
          </div>
          <button
            type="button"
            class="edge-btn h"
            :class="{
              set: Boolean(edgePickerState.edge_bottom),
              own: edgePickerState.edge_bottom?.source === 'own',
            }"
            :aria-pressed="Boolean(edgePickerState.edge_bottom)"
            @click="togglePickerSide('edge_bottom')"
          >
            {{ edgePickerState.edge_bottom ? pickerSideLabel('edge_bottom') : '-' }}
          </button>
          <span class="lbl">Pastki</span>
        </div>

        <div class="ep-source">
          <button
            type="button"
            :class="{ on: edgePickerSource === 'shop' }"
            :aria-pressed="edgePickerSource === 'shop'"
            @click="setPickerSource('shop')"
          >
            <span class="nm">Ustaxonadan</span>
            <span class="meta">Krom narxga qo'shiladi</span>
          </button>
          <button
            type="button"
            :class="{ on: edgePickerSource === 'own' }"
            :aria-pressed="edgePickerSource === 'own'"
            @click="setPickerSource('own')"
          >
            <span class="nm">O'zim olib kelaman</span>
            <span class="meta">Faqat yopishtirish xizmati</span>
          </button>
        </div>

        <div class="ep-tools">
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
          <div v-if="edgePickerBranchNote" class="ep-branch-note">
            {{ edgePickerBranchNote }}
          </div>
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
