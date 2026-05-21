<script setup lang="ts">
// Edge-banding popover: presets (None / All 0.4 / All 2.0), a tap-to-cycle
// panel diagram, and an "apply to all parts" checkbox. Mirrors the prototype.
import { ref, watch } from 'vue'
import { AppButton, AppModal } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { type Edges, cycleEdge, presetEdges } from '../lib/cutting'
import type { EdgeThickness } from '../api/types'

const props = defineProps<{ open: boolean; edges: Edges }>()
const emit = defineEmits<{
  'update:open': [v: boolean]
  apply: [payload: { edges: Edges; applyAll: boolean }]
}>()

const state = ref<Edges>({ t: null, b: null, l: null, r: null })
const applyAll = ref(false)

watch(
  () => props.open,
  (open) => {
    if (open) {
      state.value = { ...props.edges }
      applyAll.value = false
    }
  },
)

function cycle(side: keyof Edges) {
  state.value[side] = cycleEdge(state.value[side])
}

function preset(value: EdgeThickness) {
  state.value = presetEdges(value)
}

function label(v: EdgeThickness): string {
  return v ? v.toFixed(1) : t('client.edgesNo')
}

function apply() {
  emit('apply', { edges: { ...state.value }, applyAll: applyAll.value })
  emit('update:open', false)
}
</script>

<template>
  <AppModal :open="open" :title="t('client.edgesTitle')" @update:open="emit('update:open', $event)">
    <div class="edges-pop">
      <div class="presets">
        <button type="button" @click="preset(null)">{{ t('client.edgesNone') }}</button>
        <button type="button" @click="preset(0.4)">{{ t('client.edgesAll04') }}</button>
        <button type="button" @click="preset(2.0)">{{ t('client.edgesAll20') }}</button>
      </div>
      <div class="edge-diagram">
        <span class="lbl">{{ t('client.edgesTop') }}</span>
        <button class="edge-btn h" type="button" :class="{ set: !!state.t }" @click="cycle('t')">
          {{ label(state.t) }}
        </button>
        <div class="mid">
          <button class="edge-btn v" type="button" :class="{ set: !!state.l }" @click="cycle('l')">
            {{ label(state.l) }}
          </button>
          <div class="panel">{{ t('client.parts') }}</div>
          <button class="edge-btn v" type="button" :class="{ set: !!state.r }" @click="cycle('r')">
            {{ label(state.r) }}
          </button>
        </div>
        <button class="edge-btn h" type="button" :class="{ set: !!state.b }" @click="cycle('b')">
          {{ label(state.b) }}
        </button>
        <span class="lbl">{{ t('client.edgesBottom') }}</span>
      </div>
      <div class="edge-hint">{{ t('client.edgesHint') }}</div>
      <label class="ck"
        ><input v-model="applyAll" type="checkbox" /> {{ t('client.edgesApplyAll') }}</label
      >
    </div>
    <template #footer>
      <AppButton variant="outline" @click="emit('update:open', false)">{{
        t('common.cancel')
      }}</AppButton>
      <AppButton variant="acc" @click="apply">{{ t('client.apply') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.presets {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.presets button {
  padding: 7px 12px;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 6px;
  cursor: pointer;
  font: 500 12px var(--f-ui);
  color: var(--ink-12);
}
.edge-diagram {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 0 4px;
}
.edge-diagram .mid {
  display: flex;
  align-items: stretch;
  gap: 6px;
}
.edge-diagram .panel {
  width: 168px;
  height: 104px;
  border-radius: 4px;
  background: repeating-linear-gradient(
    45deg,
    var(--sunk),
    var(--sunk) 7px,
    var(--elev) 7px,
    var(--elev) 14px
  );
  border: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  font: 600 12px var(--f-ui);
  color: var(--ink-7);
}
.edge-btn {
  background: var(--sunk);
  border: 1px dashed var(--line-strong);
  color: var(--ink-7);
  cursor: pointer;
  border-radius: 5px;
  font: 600 12px var(--f-mono);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.edge-btn.set {
  background: var(--accent);
  border-style: solid;
  border-color: var(--accent);
  color: #fff;
}
.edge-btn.h {
  width: 168px;
  height: 30px;
}
.edge-btn.v {
  width: 56px;
}
.edge-diagram .lbl {
  font: 500 10px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-6);
}
.edge-hint {
  text-align: center;
  font: 500 12px var(--f-ui);
  color: var(--ink-6);
  margin: 12px 0 2px;
}
.ck {
  display: flex;
  align-items: center;
  gap: 8px;
  font: 500 12.5px var(--f-ui);
  color: var(--ink-8);
  margin-top: 14px;
  justify-content: center;
}
</style>
