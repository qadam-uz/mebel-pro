<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AuthFileImage from '@/shared/components/AuthFileImage.vue'

const props = withDefaults(
  defineProps<{
    fileId: string | null
    alt: string
    accept?: string
    disabled?: boolean
    error?: string | null
    helper?: string
    id?: string
    label?: string
    meta?: string
    resetKey?: number
    title?: string
    uploading?: boolean
  }>(),
  {
    accept: 'image/*',
    disabled: false,
    error: null,
    helper: '',
    id: undefined,
    // `label` and `title` default to '' rather than to their copy: a prop
    // default is evaluated once, when the component is defined, so a literal
    // here would freeze at whichever locale loaded the module. The fallback
    // lives in a computed below, where it re-reads on every language switch.
    label: '',
    meta: '',
    resetKey: 0,
    title: '',
    uploading: false,
  },
)

const emit = defineEmits<{
  remove: []
  select: [file: File]
}>()

const { t } = useI18n()
const inputRef = ref<HTMLInputElement | null>(null)
const localPreviewUrl = ref<string | null>(null)
const localFileName = ref('')

const fieldLabel = computed(() => props.label || t('catalog.image.label'))
const fieldTitle = computed(() => props.title || t('catalog.image.title'))
const hasImage = computed(() => Boolean(localPreviewUrl.value || props.fileId))
const chooseLabel = computed(() =>
  hasImage.value ? t('catalog.image.replace') : t('catalog.image.choose'),
)
const statusText = computed(() => {
  if (props.uploading) return t('catalog.image.uploading')
  if (localFileName.value) return localFileName.value
  if (props.fileId) return t('catalog.image.saved')
  return props.helper || t('catalog.image.hint')
})

function clearLocalPreview() {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  localPreviewUrl.value = null
  localFileName.value = ''
}

function resetInput() {
  if (inputRef.value) inputRef.value.value = ''
}

function onChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  clearLocalPreview()
  localPreviewUrl.value = URL.createObjectURL(file)
  localFileName.value = file.name
  emit('select', file)
}

function removeImage() {
  clearLocalPreview()
  resetInput()
  emit('remove')
}

watch(
  () => props.resetKey,
  () => {
    clearLocalPreview()
    resetInput()
  },
)

onBeforeUnmount(clearLocalPreview)
</script>

<template>
  <div class="admin-field admin-full">
    <span class="admin-field-label">{{ fieldLabel }}</span>
    <div class="admin-image-upload" :class="{ 'has-error': error }">
      <div class="admin-image-upload-preview">
        <img
          v-if="localPreviewUrl"
          :src="localPreviewUrl"
          :alt="alt"
          class="admin-image-upload-img"
        />
        <!-- The only place a stored image is shown large: the preview box is at
             least 132 px tall, where the 160 px rendition would visibly soften on
             a high-DPR screen. Every other use is a 34-58 px swatch and keeps the
             `sm` default. -->
        <AuthFileImage
          v-else-if="fileId"
          :file-id="fileId"
          :alt="alt"
          size="md"
          class="admin-image-upload-img"
        />
        <div v-else class="admin-image-upload-empty" aria-hidden="true">
          <span>{{ $t('catalog.image.none') }}</span>
        </div>
        <div v-if="uploading" class="admin-image-upload-busy" aria-live="polite">
          {{ $t('catalog.image.busy') }}
        </div>
      </div>

      <div class="admin-image-upload-copy">
        <strong>{{ fieldTitle }}</strong>
        <span>{{ meta || statusText }}</span>
        <small v-if="meta">{{ statusText }}</small>
        <input
          :id="id"
          ref="inputRef"
          class="sr-only"
          type="file"
          :accept="accept"
          :disabled="disabled || uploading"
          @change="onChange"
        />
        <div class="admin-image-upload-actions">
          <button
            type="button"
            class="mp-button mp-button-outline"
            :disabled="disabled || uploading"
            @click="inputRef?.click()"
          >
            {{ chooseLabel }}
          </button>
          <button
            v-if="hasImage"
            type="button"
            class="mp-button mp-button-outline"
            :disabled="disabled || uploading"
            @click="removeImage"
          >
            {{ $t('catalog.image.remove') }}
          </button>
        </div>
        <p v-if="error" class="admin-image-upload-error" role="alert">{{ error }}</p>
      </div>
    </div>
  </div>
</template>
