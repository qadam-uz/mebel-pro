<script setup lang="ts">
// Platform material master — table (swatch, kind, type/thickness, colour/decor,
// sheet size, status), kind + status filters + search, + Material form with
// sheet/edge field switch and length≥width validation, Edit, Activate/Deactivate.
// No delete (architecture invariant). Mirrors prototype admin/materials.html.
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FilterBar, FilterChip, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useToast } from '@/shared/composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { materialCreatePayload, validateMaterialForm, type MaterialForm } from '../lib/admin'
import * as api from '../api'
import type { MaterialKind, MaterialOut, MaterialType } from '../api/types'

const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<MaterialOut[]>([])

const search = ref('')
const kindFilter = ref<'all' | MaterialKind>('all')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')

const SHEET_TYPES: { value: MaterialType; label: string }[] = [
  { value: 'dsp', label: 'LDSP' },
  { value: 'mdf', label: 'MDF' },
  { value: 'plywood', label: 'Fanera' },
  { value: 'natural_wood', label: "Tabiiy yog'och" },
  { value: 'other', label: 'Boshqa' },
]

const formOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref<MaterialForm>(emptyForm('sheet'))

const validation = computed(() => validateMaterialForm(form.value))

const confirmOpen = ref(false)
const pendingToggle = ref<MaterialOut | null>(null)

function emptyForm(kind: MaterialKind): MaterialForm {
  return {
    kind,
    type: 'dsp',
    name: '',
    thickness_mm: kind === 'edge' ? '0.4' : '18',
    color: '',
    decor_code: '',
    sheet_length_mm: '2750',
    sheet_width_mm: '1830',
    grain_direction: true,
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return rows.value.filter(
    (m) =>
      (kindFilter.value === 'all' || m.kind === kindFilter.value) &&
      (statusFilter.value === 'all' || m.status === statusFilter.value) &&
      (!q || m.name.toLowerCase().includes(q)),
  )
})

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listMaterials()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = emptyForm('sheet')
  formOpen.value = true
}

function openEdit(m: MaterialOut) {
  editingId.value = m.id
  form.value = {
    kind: m.kind,
    type: m.type ?? 'dsp',
    name: m.name,
    thickness_mm: String(m.thickness_mm),
    color: m.color,
    decor_code: m.decor_code ?? '',
    sheet_length_mm: m.sheet_length_mm != null ? String(m.sheet_length_mm) : '2750',
    sheet_width_mm: m.sheet_width_mm != null ? String(m.sheet_width_mm) : '1830',
    grain_direction: m.grain_direction ?? true,
  }
  formOpen.value = true
}

function onKindChange(kind: MaterialKind) {
  // Reset kind-dependent defaults (kind itself is locked on edit, see template).
  form.value.kind = kind
  if (kind === 'edge') form.value.thickness_mm = '0.4'
  else form.value.thickness_mm = '18'
}

async function save() {
  if (!validation.value.ok) {
    if (validation.value.dimsBad) toast.warn(t('admin.matDimsErr'))
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      const payload = materialCreatePayload(form.value)
      await api.editMaterial(editingId.value, {
        type: form.value.kind === 'sheet' ? payload.type : undefined,
        type_set: form.value.kind === 'sheet',
        name: payload.name,
        thickness_mm: payload.thickness_mm,
        color: payload.color,
        decor_code: payload.decor_code,
        decor_code_set: true,
        sheet_length_mm: payload.sheet_length_mm,
        sheet_width_mm: payload.sheet_width_mm,
        grain_direction: payload.grain_direction,
      })
      toast.ok(t('admin.matSaved', { name: payload.name }))
    } else {
      const created = await api.createMaterial(materialCreatePayload(form.value))
      toast.ok(t('admin.matCreated', { name: created.name }))
    }
    formOpen.value = false
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

function askToggle(m: MaterialOut) {
  pendingToggle.value = m
  confirmOpen.value = true
}

async function confirmToggle() {
  const m = pendingToggle.value
  if (!m) return
  const activate = m.status !== 'active'
  try {
    await api.setMaterialStatus(m.id, activate)
    toast.ok(activate ? t('admin.matActivated') : t('admin.matDeactivated'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    pendingToggle.value = null
  }
}

function typeLabel(m: MaterialOut): string {
  if (m.kind === 'edge') return t('admin.edgeMeterNote')
  return (SHEET_TYPES.find((s) => s.value === m.type)?.label ?? m.type ?? '—').toUpperCase()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.materialsTitle') }}</h1>
        <p class="sub">{{ t('admin.materialsSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-acc" type="button" @click="openCreate">
          {{ t('admin.newMaterial') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :title="t('admin.materialsLoadFailed')" :retry="load" />

    <template v-else>
      <FilterBar v-if="!loading">
        <div class="input">
          <input v-model="search" :placeholder="t('admin.materialSearchPlaceholder')" />
        </div>
        <div class="chips">
          <FilterChip :active="kindFilter === 'all'" @click="kindFilter = 'all'">{{
            t('admin.kindAll')
          }}</FilterChip>
          <FilterChip :active="kindFilter === 'sheet'" @click="kindFilter = 'sheet'">{{
            t('admin.kindSheet')
          }}</FilterChip>
          <FilterChip :active="kindFilter === 'edge'" @click="kindFilter = 'edge'">{{
            t('admin.kindEdge')
          }}</FilterChip>
        </div>
        <div class="chips">
          <FilterChip :active="statusFilter === 'all'" @click="statusFilter = 'all'">{{
            t('admin.statusAll')
          }}</FilterChip>
          <FilterChip :active="statusFilter === 'active'" @click="statusFilter = 'active'">{{
            t('admin.statusActive')
          }}</FilterChip>
          <FilterChip :active="statusFilter === 'inactive'" @click="statusFilter = 'inactive'">{{
            t('admin.statusInactive')
          }}</FilterChip>
        </div>
      </FilterBar>

      <div v-if="loading" class="card">
        <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
      </div>

      <div v-else-if="filtered.length === 0" class="st-empty">
        <div class="ic">⊞</div>
        <h3>{{ t('admin.materialsEmpty') }}</h3>
        <p>{{ t('admin.materialsEmptyBody') }}</p>
      </div>

      <div v-else class="card">
        <table class="tbl">
          <thead>
            <tr>
              <th>{{ t('admin.colMaterial') }}</th>
              <th>{{ t('admin.colKind') }}</th>
              <th>{{ t('admin.colTypeSize') }}</th>
              <th>{{ t('admin.colThickness') }}</th>
              <th>{{ t('admin.colSheetSize') }}</th>
              <th>{{ t('admin.colGrain') }}</th>
              <th>{{ t('admin.colStatus') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in filtered" :key="m.id">
              <td>
                <div style="display: flex; align-items: center; gap: 11px">
                  <div class="sw" :style="{ background: m.color }" />
                  <div>
                    <div class="nm">{{ m.name }}</div>
                    <small style="color: var(--ink-6); font: 400 11px var(--f-mono)">
                      {{ m.decor_code ? m.decor_code + ' · ' : '' }}{{ m.color }}
                    </small>
                  </div>
                </div>
              </td>
              <td>
                <StatusBadge
                  :tone="m.kind === 'edge' ? 'conf' : 'ok'"
                  :label="m.kind === 'edge' ? t('admin.pillEdge') : t('admin.pillSheet')"
                />
              </td>
              <td>{{ typeLabel(m) }}</td>
              <td class="num">{{ m.thickness_mm }} mm</td>
              <td class="num">
                {{ m.kind === 'edge' ? '—' : `${m.sheet_length_mm} × ${m.sheet_width_mm}` }}
              </td>
              <td>{{ m.kind === 'edge' ? '—' : m.grain_direction ? 'Ha' : '—' }}</td>
              <td>
                <StatusBadge
                  :tone="m.status === 'active' ? 'ok' : 'dn'"
                  :label="
                    m.status === 'active' ? t('admin.statusActive') : t('admin.statusInactive')
                  "
                />
              </td>
              <td>
                <div style="display: flex; gap: 6px; justify-content: flex-end">
                  <button class="btn btn-outline btn-sm" type="button" @click="openEdit(m)">
                    {{ t('common.edit') }}
                  </button>
                  <button
                    :class="m.status === 'active' ? 'btn btn-ghost btn-sm' : 'btn btn-acc btn-sm'"
                    type="button"
                    @click="askToggle(m)"
                  >
                    {{
                      m.status === 'active'
                        ? t('admin.matDeactivateBtn')
                        : t('admin.matActivateBtn')
                    }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- CREATE / EDIT -->
    <AppModal v-model:open="formOpen" :title="editingId ? t('admin.matEdit') : t('admin.matNew')">
      <div class="field">
        <label>{{ t('admin.matKind') }}</label>
        <select
          :value="form.kind"
          :disabled="editingId !== null"
          @change="onKindChange(($event.target as HTMLSelectElement).value as MaterialKind)"
        >
          <option value="sheet">{{ t('admin.matKindSheetOpt') }}</option>
          <option value="edge">{{ t('admin.matKindEdgeOpt') }}</option>
        </select>
        <div v-if="editingId" class="hint">{{ t('admin.matKindLocked') }}</div>
      </div>

      <div v-if="form.kind === 'sheet'" class="field">
        <label>{{ t('admin.matType') }}</label>
        <select v-model="form.type">
          <option v-for="opt in SHEET_TYPES" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div class="field">
        <label>{{ t('admin.matName') }}</label>
        <input
          v-model="form.name"
          :placeholder="
            form.kind === 'edge' ? 'Krom PVC 0.4 mm · Dub Sonoma' : 'LDSP H1334 ST9 · Dub Sonoma'
          "
        />
      </div>

      <div class="field-row">
        <div class="field">
          <label>{{ t('admin.matThickness') }}</label>
          <input v-model="form.thickness_mm" type="number" step="0.1" />
        </div>
        <div class="field">
          <label>{{ t('admin.matColor') }}</label>
          <input v-model="form.color" placeholder="Dub Sonoma" />
        </div>
      </div>
      <div class="field">
        <label>{{ t('admin.matDecor') }}</label>
        <input v-model="form.decor_code" placeholder="H1334" />
      </div>

      <template v-if="form.kind === 'sheet'">
        <div class="field-row">
          <div class="field">
            <label>{{ t('admin.matLength') }}</label>
            <input v-model="form.sheet_length_mm" type="number" />
          </div>
          <div class="field">
            <label>{{ t('admin.matWidth') }}</label>
            <input v-model="form.sheet_width_mm" type="number" />
          </div>
        </div>
        <div v-if="validation.dimsBad" class="field err" role="alert">
          {{ t('admin.matDimsErr') }}
        </div>
        <div class="field">
          <label>{{ t('admin.matGrain') }}</label>
          <select v-model="form.grain_direction">
            <option :value="true">{{ t('admin.matGrainYes') }}</option>
            <option :value="false">{{ t('admin.matGrainNo') }}</option>
          </select>
        </div>
      </template>

      <div v-else class="banner info">
        <div class="ic">i</div>
        <div class="grow">{{ t('admin.matEdgeNote') }}</div>
      </div>

      <template #footer>
        <button class="btn btn-outline" type="button" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || !validation.ok"
          @click="save"
        >
          {{ editingId ? t('common.save') : t('admin.create') }}
        </button>
      </template>
    </AppModal>

    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="
        pendingToggle?.status === 'active'
          ? t('admin.matDeactivateTitle')
          : t('admin.matActivateTitle')
      "
      :message="
        pendingToggle?.status === 'active'
          ? t('admin.matDeactivateBody')
          : t('admin.matActivateBody')
      "
      :ok-text="
        pendingToggle?.status === 'active' ? t('admin.matDeactivateBtn') : t('admin.matActivateBtn')
      "
      :danger="pendingToggle?.status === 'active'"
      @confirm="confirmToggle"
    />
  </div>
</template>
