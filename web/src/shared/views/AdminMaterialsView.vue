<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  dropdownOption,
  materialKindLabel,
  materialStatusLabel,
  materialStatusTone,
} from '@/shared/app/adminUi'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useFocusTrap } from '@/shared/composables/useFocusTrap'
import { useToast } from '@/shared/composables/useToast'
import {
  useAdminStore,
  type Material,
  type MaterialKind,
  type MaterialStatus,
  type PanelMaterialType,
} from '@/shared/stores/admin'
import { useFilesStore } from '@/shared/stores/files'

const admin = useAdminStore()
const files = useFilesStore()
const toast = useToast()
const modalOpen = ref(false)
const manufacturerModalOpen = ref(false)
const uploadError = ref<string | null>(null)
const statusTarget = ref<{ row: Material; status: MaterialStatus } | null>(null)
const formPanel = ref<HTMLElement | null>(null)
const inlineMfrPanel = ref<HTMLElement | null>(null)
const formTrap = useFocusTrap(formPanel, modalOpen, () => (modalOpen.value = false))
const inlineMfrTrap = useFocusTrap(
  inlineMfrPanel,
  manufacturerModalOpen,
  () => (manufacturerModalOpen.value = false),
)
const saving = ref(false)
const manufacturerSaving = ref(false)
const actionId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const saveError = ref<string | null>(null)
const manufacturerError = ref<string | null>(null)
const search = ref('')
const statusFilter = ref('all')
const kindFilter = ref('all')
const manufacturerFilter = ref('all')

const form = reactive({
  kind: 'panel' as MaterialKind,
  manufacturerId: '',
  type: 'dsp' as PanelMaterialType,
  name: '',
  thicknessMm: '18',
  color: '',
  decorCode: '',
  panelLengthMm: '2800',
  panelWidthMm: '2070',
  grainDirection: true,
  imageFileId: null as string | null,
})
const manufacturerForm = reactive({
  name: '',
  country: '',
  note: '',
})

const kindOptions = [
  dropdownOption('all', 'Hammasi', 'panel va krom'),
  dropdownOption('panel', 'Panel', 'DSP/MDF/Plywood'),
  dropdownOption('edge', 'Krom', 'edge banding'),
]
const statusOptions = [
  dropdownOption('all', 'Hammasi', 'barcha holatlar'),
  dropdownOption('active', 'Faol', "branch tanlovida ko'rinadi"),
  dropdownOption('inactive', 'Faol emas', 'yangi tanlovdan yashirilgan'),
]
const manufacturerFilterOptions = computed(() => [
  dropdownOption('all', 'Hammasi', 'barcha manufacturerlar'),
  ...admin.manufacturers.map((manufacturer) =>
    dropdownOption(manufacturer.id, manufacturer.name, manufacturer.country ?? ''),
  ),
])
const manufacturerChoiceOptions = computed<ChoiceOption[]>(() =>
  admin.manufacturers
    .filter((manufacturer) => manufacturer.status === 'active')
    .map((manufacturer) => ({
      value: manufacturer.id,
      label: manufacturer.name,
      meta: manufacturer.country ?? '',
    })),
)
const materialTypeOptions: ChoiceOption[] = [
  { value: 'dsp', label: 'DSP' },
  { value: 'mdf', label: 'MDF' },
  { value: 'plywood', label: 'Plywood' },
  { value: 'natural_wood', label: 'Natural wood' },
  { value: 'other', label: 'Other' },
]
const materialKindOptions: ChoiceOption[] = [
  { value: 'panel', label: 'Panel', meta: 'list material' },
  { value: 'edge', label: 'Krom', meta: 'edge banding' },
]

const filtered = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return admin.materials.filter((material) => {
    if (statusFilter.value !== 'all' && material.status !== statusFilter.value) return false
    if (kindFilter.value !== 'all' && material.kind !== kindFilter.value) return false
    if (manufacturerFilter.value !== 'all' && material.manufacturer_id !== manufacturerFilter.value)
      return false
    if (!needle) return true
    return [
      material.name,
      material.manufacturer_name,
      material.type ?? '',
      material.color,
      material.decor_code ?? '',
      material.thickness_mm,
    ]
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })
})

function openCreate() {
  editingId.value = null
  form.kind = 'panel'
  form.manufacturerId = admin.manufacturers.find((row) => row.status === 'active')?.id ?? ''
  form.type = 'dsp'
  form.name = ''
  form.thicknessMm = '18'
  form.color = ''
  form.decorCode = ''
  form.panelLengthMm = '2800'
  form.panelWidthMm = '2070'
  form.grainDirection = true
  form.imageFileId = null
  saveError.value = null
  modalOpen.value = true
}

function openEdit(material: Material) {
  editingId.value = material.id
  form.kind = material.kind
  form.manufacturerId = material.manufacturer_id
  form.type = material.type ?? 'dsp'
  form.name = material.name
  form.thicknessMm = material.thickness_mm
  form.color = material.color
  form.decorCode = material.decor_code ?? ''
  form.panelLengthMm = String(material.panel_length_mm ?? 2800)
  form.panelWidthMm = String(material.panel_width_mm ?? 2070)
  form.grainDirection = material.grain_direction ?? false
  form.imageFileId = material.image_file_id
  saveError.value = null
  modalOpen.value = true
}

function materialSpec(material: Material) {
  if (material.kind === 'panel') {
    return `${material.type ?? 'panel'} . ${material.panel_length_mm} x ${material.panel_width_mm} mm`
  }
  return 'krom · metr'
}

async function onMaterialFile(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !target.files?.[0]) return
  uploadError.value = null
  try {
    const uploaded = await files.upload(target.files[0])
    form.imageFileId = uploaded.id
    toast.success('Rasm yuklandi')
  } catch {
    uploadError.value = 'image_upload_failed'
    toast.danger("Rasmni yuklab bo'lmadi")
    target.value = ''
  }
}

function removeImage() {
  form.imageFileId = null
  uploadError.value = null
}

async function save() {
  saving.value = true
  saveError.value = null
  try {
    const isPanel = form.kind === 'panel'
    const payload = {
      kind: form.kind,
      manufacturer_id: form.manufacturerId,
      type: isPanel ? form.type : null,
      name: form.name,
      thickness_mm: form.thicknessMm,
      color: form.color,
      decor_code: form.decorCode || null,
      panel_length_mm: isPanel ? Number(form.panelLengthMm) : null,
      panel_width_mm: isPanel ? Number(form.panelWidthMm) : null,
      grain_direction: isPanel ? form.grainDirection : null,
      image_file_id: form.imageFileId,
    }
    if (editingId.value) await admin.updateMaterial(editingId.value, payload)
    else await admin.createMaterial(payload)
    modalOpen.value = false
    toast.success(editingId.value ? 'Material yangilandi' : "Material qo'shildi")
  } catch {
    saveError.value = 'material_save_failed'
    toast.danger('Material saqlanmadi')
  } finally {
    saving.value = false
  }
}

async function saveInlineManufacturer() {
  manufacturerSaving.value = true
  manufacturerError.value = null
  try {
    const created = await admin.createManufacturer({
      name: manufacturerForm.name,
      country: manufacturerForm.country || null,
      note: manufacturerForm.note || null,
    })
    form.manufacturerId = created.id
    manufacturerForm.name = ''
    manufacturerForm.country = ''
    manufacturerForm.note = ''
    manufacturerModalOpen.value = false
  } catch {
    manufacturerError.value = 'manufacturer_save_failed'
  } finally {
    manufacturerSaving.value = false
  }
}

function askStatus(row: Material, status: MaterialStatus) {
  statusTarget.value = { row, status }
}

async function confirmStatus() {
  const target = statusTarget.value
  if (!target) return
  statusTarget.value = null
  actionId.value = target.row.id
  try {
    await admin.setMaterialStatus(target.row.id, target.status)
    toast.success(target.status === 'active' ? 'Faollashtirildi' : 'Faol emas qilindi')
  } catch {
    toast.danger('Amal bajarilmadi')
  } finally {
    actionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([admin.loadManufacturers(), admin.loadMaterials()])
})
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Platforma material katalogi</h1>
        <p class="sub">Platforma master materiallari: panel va krom records.</p>
      </div>
      <button type="button" class="admin-primary-action" @click="openCreate">Yangi material</button>
    </div>

    <div class="admin-filters">
      <label class="admin-filter-input">
        <span class="sr-only">Material nomi</span>
        <input v-model="search" placeholder="Material nomi" />
      </label>
      <ProjectDropdown v-model="kindFilter" label="Tur" :options="kindOptions" />
      <ProjectDropdown
        v-model="manufacturerFilter"
        label="Manufacturer"
        :options="manufacturerFilterOptions"
      />
      <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
    </div>

    <section v-if="admin.catalogLoading" class="admin-card p-5" aria-live="polite">
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="admin.catalogError"
      :code="admin.catalogError"
      :trace-id="admin.catalogTraceId"
      title="Materiallar yuklanmadi"
      @retry="admin.loadMaterials()"
    />

    <section v-else-if="filtered.length === 0" class="admin-empty">
      <h3>Material yo'q</h3>
      <p>Manufacturer qo'shing, keyin panel yoki krom material yarating.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Material</th>
              <th>Manufacturer</th>
              <th>Tur</th>
              <th>Turi / o'lcham</th>
              <th>Qalinligi</th>
              <th>Panel o'lchami</th>
              <th>Tola</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="material in filtered" :key="material.id">
              <td class="nm">
                {{ material.name }}
                <small>{{ material.color }} . {{ material.decor_code ?? 'decor yoq' }}</small>
              </td>
              <td>{{ material.manufacturer_name }}</td>
              <td>{{ materialKindLabel(material.kind) }}</td>
              <td>{{ materialSpec(material) }}</td>
              <td class="admin-mono">{{ material.thickness_mm }} mm</td>
              <td class="admin-mono">
                <template v-if="material.kind === 'panel'">
                  {{ material.panel_length_mm }} x {{ material.panel_width_mm }}
                </template>
                <template v-else>-</template>
              </td>
              <td>{{ material.grain_direction ? 'bor' : '-' }}</td>
              <td>
                <span class="admin-pill" :class="materialStatusTone(material.status)">
                  {{ materialStatusLabel(material.status) }}
                </span>
              </td>
              <td class="admin-right">
                <div class="flex justify-end gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    @click="openEdit(material)"
                  >
                    Tahrirlash
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === material.id"
                    @click="
                      askStatus(material, material.status === 'active' ? 'inactive' : 'active')
                    "
                  >
                    {{ material.status === 'active' ? 'Faol emas qilish' : 'Faollashtirish' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <template v-if="modalOpen">
      <div class="admin-modal-scrim" aria-hidden="true" @click="modalOpen = false"></div>
      <section
        ref="formPanel"
        class="admin-modal wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="material-title"
        tabindex="-1"
        @keydown="formTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="material-title">{{ editingId ? 'Material tahrirlash' : 'Yangi material' }}</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="modalOpen = false"
          >
            x
          </button>
        </div>
        <form @submit.prevent="save">
          <div class="admin-modal-b">
            <div class="admin-form-grid three">
              <FormSelect
                v-model="form.kind"
                label="Kind"
                :options="materialKindOptions"
                class="admin-full"
              />
              <div class="admin-full grid gap-2 md:grid-cols-[1fr_auto]">
                <FormSelect
                  v-model="form.manufacturerId"
                  label="Manufacturer"
                  :options="manufacturerChoiceOptions"
                  placeholder="Manufacturer tanlang"
                />
                <button
                  type="button"
                  class="mp-button mp-button-outline self-end"
                  @click="manufacturerModalOpen = true"
                >
                  Inline manufacturer
                </button>
              </div>
              <label class="admin-field admin-full" for="mat-name">
                <span>Material nomi</span>
                <input
                  id="mat-name"
                  v-model="form.name"
                  placeholder="LDSP H1334 ST9 . Dub Sonoma"
                  required
                />
              </label>
              <FormSelect
                v-if="form.kind === 'panel'"
                v-model="form.type"
                label="Panel turi"
                :options="materialTypeOptions"
              />
              <label class="admin-field" for="mat-thick">
                <span>Qalinligi, mm</span>
                <input id="mat-thick" v-model="form.thicknessMm" inputmode="decimal" required />
              </label>
              <label class="admin-field" for="mat-color">
                <span>Rang / decor</span>
                <input id="mat-color" v-model="form.color" required />
              </label>
              <label class="admin-field" for="mat-decor">
                <span>Decor code</span>
                <input id="mat-decor" v-model="form.decorCode" />
              </label>
              <template v-if="form.kind === 'panel'">
                <label class="admin-field" for="mat-len">
                  <span>Uzunlik, mm</span>
                  <input id="mat-len" v-model="form.panelLengthMm" inputmode="numeric" required />
                </label>
                <label class="admin-field" for="mat-wid">
                  <span>Eni, mm</span>
                  <input id="mat-wid" v-model="form.panelWidthMm" inputmode="numeric" required />
                </label>
                <label
                  class="flex min-h-11 items-center gap-3 self-end rounded-md border border-hairline-strong px-3 text-sm font-bold"
                >
                  <input
                    v-model="form.grainDirection"
                    type="checkbox"
                    class="size-4 accent-accent"
                  />
                  Tola yo'nalishi bor
                </label>
              </template>
              <label class="admin-field admin-full" for="mat-image">
                <span>Rasm</span>
                <input id="mat-image" type="file" accept="image/*" @change="onMaterialFile" />
                <span v-if="form.imageFileId" class="flex items-center gap-2 text-ink-muted">
                  <span class="admin-mono">file {{ form.imageFileId.slice(0, 8) }}</span>
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                    @click="removeImage"
                  >
                    Olib tashlash
                  </button>
                </span>
              </label>
            </div>
            <p v-if="files.uploading" class="mt-3 text-sm font-bold text-info" aria-live="polite">
              Rasm yuklanmoqda...
            </p>
            <p
              v-if="uploadError"
              class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              role="alert"
            >
              Rasmni yuklab bo'lmadi. Boshqa fayl bilan qayta urinib ko'ring.
            </p>
            <p
              v-if="saveError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Material saqlanmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button type="button" class="mp-button mp-button-outline" @click="modalOpen = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <template v-if="manufacturerModalOpen">
      <div
        class="admin-modal-scrim"
        aria-hidden="true"
        @click="manufacturerModalOpen = false"
      ></div>
      <section
        ref="inlineMfrPanel"
        class="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="inline-mfr-title"
        tabindex="-1"
        @keydown="inlineMfrTrap.onKeydown"
      >
        <div class="admin-modal-h">
          <h3 id="inline-mfr-title">Yangi manufacturer</h3>
          <button
            type="button"
            class="admin-icon-button"
            aria-label="Yopish"
            @click="manufacturerModalOpen = false"
          >
            x
          </button>
        </div>
        <form @submit.prevent="saveInlineManufacturer">
          <div class="admin-modal-b">
            <div class="admin-form-grid">
              <label class="admin-field admin-full" for="inline-mfr-name">
                <span>Nomi</span>
                <input id="inline-mfr-name" v-model="manufacturerForm.name" required />
              </label>
              <label class="admin-field" for="inline-mfr-country">
                <span>Country</span>
                <input id="inline-mfr-country" v-model="manufacturerForm.country" />
              </label>
              <label class="admin-field admin-full" for="inline-mfr-note">
                <span>Izoh</span>
                <textarea id="inline-mfr-note" v-model="manufacturerForm.note"></textarea>
              </label>
            </div>
            <p
              v-if="manufacturerError"
              class="mt-4 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            >
              Manufacturer yaratilmadi.
            </p>
          </div>
          <div class="admin-modal-f">
            <button
              type="button"
              class="mp-button mp-button-outline"
              @click="manufacturerModalOpen = false"
            >
              Bekor
            </button>
            <button
              type="submit"
              class="mp-button mp-button-primary"
              :disabled="manufacturerSaving"
            >
              {{ manufacturerSaving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <ConfirmDialog
      :open="statusTarget !== null"
      :title="statusTarget?.status === 'inactive' ? 'Faol emas qilish' : 'Faollashtirish'"
      :message="
        statusTarget?.status === 'inactive'
          ? `${statusTarget?.row.name} faol emas qilinadi — uni filiallarning yangi tanlovlaridan yashiriladi; mavjud buyurtmalarga ta'sir qilmaydi.`
          : `${statusTarget?.row.name} faollashtiriladi va filial tanlovida ko'rinadi.`
      "
      confirm-label="Tasdiqlash"
      cancel-label="Bekor qilish"
      :danger="statusTarget?.status === 'inactive'"
      :busy="actionId === statusTarget?.row.id"
      @confirm="confirmStatus"
      @cancel="statusTarget = null"
    />
  </section>
</template>
