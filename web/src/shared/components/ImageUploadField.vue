<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

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
    label: 'Rasm',
    meta: '',
    resetKey: 0,
    title: 'Material rasmi',
    uploading: false,
  },
)

const emit = defineEmits<{
  remove: []
  select: [file: File]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const localPreviewUrl = ref<string | null>(null)
const localFileName = ref('')

const hasImage = computed(() => Boolean(localPreviewUrl.value || props.fileId))
const chooseLabel = computed(() => (hasImage.value ? 'Rasmni almashtirish' : 'Rasm tanlash'))
const statusText = computed(() => {
  if (props.uploading) return 'Rasm yuklanmoqda…'
  if (localFileName.value) return localFileName.value
  if (props.fileId) return 'Saqlangan rasm'
  return props.helper || 'PNG, JPG yoki WEBP rasm tanlang.'
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
    <span class="admin-field-label">{{ label }}</span>
    <div class="admin-image-upload" :class="{ 'has-error': error }">
      <div class="admin-image-upload-preview">
        <img
          v-if="localPreviewUrl"
          :src="localPreviewUrl"
          :alt="alt"
          class="admin-image-upload-img"
        />
        <AuthFileImage
          v-else-if="fileId"
          :file-id="fileId"
          :alt="alt"
          class="admin-image-upload-img"
        />
        <div v-else class="admin-image-upload-empty" aria-hidden="true">
          <span>Rasm yo'q</span>
        </div>
        <div v-if="uploading" class="admin-image-upload-busy" aria-live="polite">Yuklanmoqda</div>
      </div>

      <div class="admin-image-upload-copy">
        <strong>{{ title }}</strong>
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
            Olib tashlash
          </button>
        </div>
        <p v-if="error" class="admin-image-upload-error" role="alert">{{ error }}</p>
      </div>
    </div>
  </div>
</template>
