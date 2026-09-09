<script setup lang="ts">
/**
 * «Yangi dekor» — the workshop enters what the platform library lacks.
 *
 * The catalog stopped being an authority in 2026-09-07 and became a library: a
 * pre-filled list so nobody types Egger's 300 decors by hand. What it does not
 * hold, the workshop adds here — a manufacturer, a decor, and at least one
 * o'lcham — and what it adds is visible to that workshop alone. Nothing is
 * moderated, nothing waits.
 *
 * Its own component rather than a fourth branch of `BranchMaterialAttachSheet`:
 * the sheet is already the longest file in `shared/components`, and this form
 * has a lifecycle of its own (an upload, a create, a 409 that sends the
 * operator back to the picker).
 *
 * **The formats block is create-only.** A `decor_format` is immutable — branch
 * rows, stock, cutting panels and order history all resolve through its id —
 * so the edit mode is identity only.
 *
 * **The decor has no `type`.** The substrate is a property of each o'lcham, so
 * the chip row lives inside the composer and one decor may carry an LDSP board
 * and a kromka at once (Egger H1145). The form only collects the drafts and
 * sends each one's own type.
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { apiErrorCode, apiTraceId, ApiError } from '@/shared/api/client'
import {
  clearFieldErrors,
  focusFirstFieldError,
  type FieldErrors,
} from '@/shared/app/adminValidation'
import { traceSuffix } from '@/shared/app/errorTrace'
import { decorTypeLabel } from '@/shared/app/materialLabel'
import { foldIncludes } from '@/shared/app/searchFold'
import { formatDraftKey, formatDraftLabel, type FormatDraft } from '@/shared/app/standardFormats'
import AppIcon from '@/shared/components/AppIcon.vue'
import BranchDecorFormatPicker from '@/shared/components/BranchDecorFormatPicker.vue'
import ImageUploadField from '@/shared/components/ImageUploadField.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import type { Decor, DecorFormat } from '@/shared/stores/admin'
import { useFilesStore } from '@/shared/stores/files'
import { useWorkshopStore } from '@/shared/stores/workshop'

const props = withDefaults(
  defineProps<{
    branchId: string
    /** Step 1's typed query, carried in so the search is not typed twice. */
    initialName?: string
    /** An own decor being corrected — identity only, no formats block. */
    decor?: Decor | null
    /**
     * Render the form's own action row.
     *
     * The attach sheet turns it off and drives `submit()` from the modal's
     * fixed footer instead (§3.1): a footer that scrolls away with the form is
     * the defect the fixed frame exists to fix, and the buttons belong to the
     * modal frame rather than to this form when it is a step inside one.
     */
    actions?: boolean
  }>(),
  { initialName: '', decor: null, actions: true },
)

const emit = defineEmits<{
  created: [result: { decor: Decor; formats: DecorFormat[] }]
  updated: [decor: Decor]
  back: []
}>()

/** The sentinel a picked "+ „X“ ni qo'shish" row carries until the decor saves. */
const NEW_MANUFACTURER = '__new__'

type Field = 'manufacturer' | 'name' | 'formats'

const { t } = useI18n()
const workshop = useWorkshopStore()
const files = useFilesStore()

const editing = computed(() => props.decor !== null)

const form = reactive({
  manufacturerId: null as string | null,
  newManufacturerName: '',
  name: '',
  code: '',
  hasGrain: false,
  imageFileId: '' as string,
})
const drafts = ref<FormatDraft[]>([])
const manufacturerQuery = ref('')
const fieldErrors = reactive<FieldErrors<Field>>({})
const fieldOrder: Field[] = ['manufacturer', 'name', 'formats']
const fieldIds: Record<Field, string> = {
  manufacturer: 'branch-decor-manufacturer',
  name: 'branch-decor-name',
  formats: 'branch-decor-formats',
}
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const imageError = ref<string | null>(null)
const pickerError = ref<string | null>(null)
// `SearchCombobox` mints its own input id, so the shared focus helper cannot
// reach it — it exposes `focus()` instead, and the caret lands through that.
const manufacturerRef = ref<{ focus: () => void } | null>(null)

/** The rejected field takes the caret, whichever kind of control it is. */
function focusFirstError() {
  const first = fieldOrder.find((field) => fieldErrors[field])
  if (!first) return
  if (first === 'manufacturer') {
    requestAnimationFrame(() => manufacturerRef.value?.focus())
    return
  }
  focusFirstFieldError(fieldErrors, fieldOrder, fieldIds)
}

/**
 * Seed the form whenever the host opens it — a fresh create carries step 1's
 * query into Nomi, an edit carries the decor it is correcting.
 */
watch(
  () => [props.decor, props.initialName] as const,
  () => {
    const decor = props.decor
    clearFieldErrors(fieldErrors)
    saveError.value = null
    saveTraceId.value = null
    imageError.value = null
    pickerError.value = null
    drafts.value = []
    manufacturerQuery.value = ''
    form.manufacturerId = decor?.manufacturer_id ?? null
    form.newManufacturerName = ''
    form.name = decor?.name ?? props.initialName
    form.code = decor?.code ?? ''
    form.hasGrain = decor?.has_grain ?? false
    form.imageFileId = decor?.image_file_id ?? ''
  },
  { immediate: true },
)

// ---- Ishlab chiqaruvchi ---------------------------------------------------

/**
 * The visible manufacturers, plus an inline create row when the typed name
 * matches none of them.
 *
 * `serverFiltered` on the combobox and the filtering done here, so the create
 * row is never filtered out by the picker's own text match — it is the one
 * option whose label is not the thing being searched for.
 */
const manufacturerOptions = computed<ChoiceOption[]>(() => {
  const query = manufacturerQuery.value.trim()
  const rows = workshop.branchManufacturers.filter((row) => !query || foldIncludes(row.name, query))
  const options: ChoiceOption[] = rows.map((row) => ({
    value: row.id,
    label: row.name,
    // Library rows say nothing — they are the norm; the workshop's own are the
    // exception a reader has to be able to see.
    meta: row.own ? t('inventory.attach.ownBadge') : undefined,
  }))
  if (form.newManufacturerName) {
    options.push({ value: NEW_MANUFACTURER, label: form.newManufacturerName })
  } else if (query && !rows.some((row) => row.name.trim().toLowerCase() === query.toLowerCase())) {
    options.push({
      value: NEW_MANUFACTURER,
      label: t('inventory.attach.manufacturerCreate', { name: query }),
    })
  }
  return options
})

function pickManufacturer(value: string | null) {
  if (value === NEW_MANUFACTURER) {
    const typed = manufacturerQuery.value.trim()
    form.newManufacturerName = typed
    form.manufacturerId = typed ? NEW_MANUFACTURER : null
  } else {
    form.newManufacturerName = ''
    form.manufacturerId = value
  }
  fieldErrors.manufacturer = undefined
}

// ---- Rasm -----------------------------------------------------------------

async function onImageSelect(file: File) {
  imageError.value = null
  try {
    const uploaded = await files.upload(file)
    form.imageFileId = uploaded.id
  } catch {
    imageError.value = t('inventory.attach.imageFailed') + traceSuffix(files.traceId)
  }
}

function removeImage() {
  form.imageFileId = ''
  imageError.value = null
}

// ---- O'lchamlar -----------------------------------------------------------

/**
 * The composed list, each row named by the substrate it is: a decor may hold
 * an LDSP board and a kromka, and «18 mm · 2800×2070» beside «0.8 mm · 22 mm»
 * would leave the reader to infer which is which from the shape of the number.
 */
const draftRows = computed(() =>
  drafts.value.map((draft) => ({
    key: formatDraftKey(draft),
    label: [decorTypeLabel(draft.type), formatDraftLabel(draft, t('catalog.finishedSides.1'))].join(
      ' · ',
    ),
  })),
)

function addDraft(draft: FormatDraft) {
  const key = formatDraftKey(draft)
  if (drafts.value.some((row) => formatDraftKey(row) === key)) {
    pickerError.value = t('inventory.attach.formatDuplicate')
    return
  }
  pickerError.value = null
  fieldErrors.formats = undefined
  drafts.value = [...drafts.value, draft]
}

function removeDraft(key: string) {
  drafts.value = drafts.value.filter((row) => formatDraftKey(row) !== key)
  // The duplicate that raised it is gone, so the message is about a list that
  // no longer exists — two rejections stacked in one block read as two faults.
  pickerError.value = null
}

// ---- Submit ---------------------------------------------------------------

function validate() {
  clearFieldErrors(fieldErrors)
  pickerError.value = null
  if (!form.manufacturerId) fieldErrors.manufacturer = t('inventory.attach.manufacturerRequired')
  if (!form.name.trim()) fieldErrors.name = t('inventory.attach.nameRequired')
  if (!editing.value && drafts.value.length === 0) {
    fieldErrors.formats = t('inventory.attach.formatsRequired')
  }
  const hasErrors = fieldOrder.some((field) => Boolean(fieldErrors[field]))
  if (hasErrors) focusFirstError()
  return !hasErrors
}

/** `manufacturer_id` XOR `manufacturer_name` — the server refuses both or neither. */
function manufacturerPayload() {
  return form.manufacturerId === NEW_MANUFACTURER
    ? { manufacturer_name: form.newManufacturerName.trim() }
    : { manufacturer_id: form.manufacturerId }
}

/**
 * The existing decor a 409 names, for the message that sends the operator back
 * to the picker. The label is the server's; the typed name is the fallback so
 * the sentence is never «Bunday dekor bor: ».
 */
function existingDecorLabel(error: unknown): string {
  if (error instanceof ApiError && typeof error.body === 'object' && error.body !== null) {
    const details = (error.body as { details?: unknown }).details
    if (typeof details === 'object' && details !== null) {
      const label = (details as { decor_label?: unknown }).decor_label
      if (typeof label === 'string' && label.trim()) return label
    }
  }
  return [form.code.trim(), form.name.trim()].filter(Boolean).join(' ')
}

async function submit() {
  if (!validate()) return
  saving.value = true
  saveError.value = null
  saveTraceId.value = null
  try {
    if (editing.value && props.decor) {
      const updated = await workshop.updateBranchDecor(props.branchId, props.decor.id, {
        ...manufacturerPayload(),
        name: form.name.trim(),
        code: form.code.trim() || null,
        has_grain: form.hasGrain,
        image_file_id: form.imageFileId || null,
      })
      emit('updated', updated)
      return
    }
    const created = await workshop.createBranchDecor(props.branchId, {
      ...manufacturerPayload(),
      name: form.name.trim(),
      code: form.code.trim() || null,
      has_grain: form.hasGrain,
      image_file_id: form.imageFileId || null,
      formats: drafts.value.map((draft) => ({ ...draft })),
    })
    emit('created', created)
  } catch (caught) {
    const code = apiErrorCode(caught)
    if (code === 'decor_exists') {
      // The name and the code together are the identity that clashed, so the
      // message anchors on both fields rather than on the form's foot.
      const message = t('inventory.attach.decorExists', { label: existingDecorLabel(caught) })
      fieldErrors.name = message
      focusFirstError()
    } else if (code === 'decor_formats_required') {
      fieldErrors.formats = t('inventory.attach.formatsRequired')
      focusFirstError()
    } else if (code === 'manufacturer_required' || code === 'manufacturer_not_found') {
      fieldErrors.manufacturer = t('inventory.attach.manufacturerRequired')
      focusFirstError()
    } else {
      saveError.value = t('inventory.attach.createFailed')
    }
    saveTraceId.value = apiTraceId(caught)
  } finally {
    saving.value = false
  }
}

// The host's footer needs both halves: the action to fire and the progress to
// show while it runs (see the `actions` prop).
defineExpose({ submit, saving })
</script>

<template>
  <form class="grid gap-3" novalidate @submit.prevent="submit">
    <SearchCombobox
      ref="manufacturerRef"
      :label="$t('inventory.attach.manufacturerField')"
      :model-value="form.manufacturerId"
      :options="manufacturerOptions"
      :error="fieldErrors.manufacturer ?? null"
      server-filtered
      clearable
      @update:model-value="pickManufacturer"
      @search="manufacturerQuery = $event"
    />

    <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_200px]">
      <label class="field !mb-0" :for="fieldIds.name">
        <span>{{ $t('inventory.attach.nameLabel') }}</span>
        <input
          :id="fieldIds.name"
          v-model="form.name"
          class="mp-input"
          :placeholder="$t('inventory.attach.namePlaceholder')"
          required
          :aria-invalid="fieldErrors.name ? 'true' : undefined"
          :aria-describedby="fieldErrors.name ? `${fieldIds.name}-error` : undefined"
        />
        <span v-if="fieldErrors.name" :id="`${fieldIds.name}-error`" class="mp-field-error">
          {{ fieldErrors.name }}
        </span>
      </label>
      <label class="field !mb-0">
        <span>{{ $t('inventory.attach.codeLabel') }}</span>
        <input v-model="form.code" class="mp-input" placeholder="H1145" />
      </label>
    </div>

    <label class="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-ink">
      <input v-model="form.hasGrain" type="checkbox" class="size-4 shrink-0 accent-accent" />
      {{ $t('inventory.attach.grainLabel') }}
    </label>
    <p class="-mt-2 text-xs text-ink-muted">{{ $t('inventory.attach.grainHint') }}</p>

    <ImageUploadField
      :file-id="form.imageFileId || null"
      :alt="form.name || $t('inventory.attach.createTitle')"
      :label="$t('inventory.attach.imageLabel')"
      accept="image/png,image/jpeg,image/webp"
      :uploading="files.uploading"
      :error="imageError"
      @select="onImageSelect"
      @remove="removeImage"
    />

    <!-- Formats are immutable, so an edit has no block here at all: a wrong
         o'lcham is left alone and the right one attached instead. -->
    <div v-if="!editing" class="field !mb-0">
      <span :id="fieldIds.formats">{{ $t('inventory.attach.formatsLabel') }}</span>
      <BranchDecorFormatPicker
        :error="pickerError"
        :invalid="Boolean(fieldErrors.formats)"
        :described-by="fieldErrors.formats ? 'branch-decor-formats-error' : undefined"
        @add="addDraft"
      />
      <ul v-if="draftRows.length > 0" class="grid gap-1.5">
        <li
          v-for="row in draftRows"
          :key="row.key"
          class="flex min-w-0 items-center justify-between gap-2 rounded-md border border-hairline bg-elevated px-3 py-2"
        >
          <span class="min-w-0 break-words text-sm font-semibold text-ink">{{ row.label }}</span>
          <button
            type="button"
            class="mp-row-icon"
            :aria-label="$t('inventory.attach.removeFormat', { label: row.label })"
            @click="removeDraft(row.key)"
          >
            <AppIcon name="x" />
          </button>
        </li>
      </ul>
      <span v-if="fieldErrors.formats" id="branch-decor-formats-error" class="mp-field-error">
        {{ fieldErrors.formats }}
      </span>
    </div>

    <p v-if="saveError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      {{ saveError }}{{ traceSuffix(saveTraceId) }}
    </p>

    <div v-if="actions" class="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
      <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
        {{
          saving
            ? $t('inventory.attach.saving')
            : editing
              ? $t('inventory.action.save')
              : $t('inventory.attach.createSubmit')
        }}
      </button>
      <button type="button" class="mp-button mp-button-outline" @click="emit('back')">
        {{ $t('inventory.attach.back') }}
      </button>
    </div>
  </form>
</template>
