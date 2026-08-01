<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// A styled, localised file picker that replaces the browser-native file input
// (whose "Choose File / No file chosen" text is unstyled and English). It wraps a hidden
// native input and re-emits its `change` event unchanged, so existing handlers
// that read `event.target.files[0]` keep working as-is.
//
// Controlled vs. uncontrolled name: pass `selectedName` (even '') to control the
// shown name from the parent (e.g. an uploaded receipt's name); omit it and the
// picker shows the last locally chosen file name. `uploading` shows a busy state
// and disables the control; `removable` adds a clear (×) that emits `remove`.
const props = withDefaults(
  defineProps<{
    accept?: string
    disabled?: boolean
    id?: string
    buttonLabel?: string
    placeholder?: string
    uploading?: boolean
    selectedName?: string
    removable?: boolean
  }>(),
  {
    // Empty rather than the copy itself: a prop default is evaluated once, when
    // the component is defined, so a literal would freeze at whichever locale
    // loaded the module. The fallback lives in the computeds below.
    buttonLabel: '',
    placeholder: '',
    disabled: false,
    uploading: false,
    removable: false,
  },
)
const emit = defineEmits<{ change: [event: Event]; remove: [] }>()

const { t } = useI18n()
const inputRef = ref<HTMLInputElement | null>(null)
const localName = ref('')

const buttonText = computed(() => props.buttonLabel || t('catalog.file.choose'))
const placeholderText = computed(() => props.placeholder || t('catalog.file.empty'))

// `selectedName === undefined` ⇒ uncontrolled: fall back to the last picked name.
const displayName = computed(() =>
  props.selectedName !== undefined ? props.selectedName : localName.value,
)

function onChange(event: Event) {
  localName.value = (event.target as HTMLInputElement).files?.[0]?.name ?? ''
  emit('change', event)
}

function onRemove() {
  localName.value = ''
  if (inputRef.value) inputRef.value.value = ''
  emit('remove')
}
</script>

<template>
  <div
    class="flex items-center gap-2 rounded-md border border-hairline-strong bg-elevated p-1.5 pl-3"
  >
    <!-- Hidden input first so a wrapping <label> associates with it (its first
         labelable descendant), not the button. sr-only keeps it out of layout. -->
    <input
      :id="id"
      ref="inputRef"
      class="sr-only"
      type="file"
      :accept="accept"
      :disabled="disabled || uploading"
      @change="onChange"
    />
    <span
      class="min-w-0 flex-1 truncate text-sm"
      :class="uploading || displayName ? 'text-ink' : 'text-ink-muted'"
    >
      {{ uploading ? $t('catalog.file.uploading') : displayName || placeholderText }}
    </span>
    <button
      v-if="removable && displayName && !uploading"
      type="button"
      class="shrink-0 rounded-md px-2 text-lg font-bold leading-none text-ink-muted transition hover:text-danger"
      :aria-label="$t('catalog.file.remove')"
      @click="onRemove"
    >
      ×
    </button>
    <button
      type="button"
      class="mp-button mp-button-outline shrink-0"
      :disabled="disabled || uploading"
      @click="inputRef?.click()"
    >
      {{ uploading ? $t('catalog.file.busy') : buttonText }}
    </button>
  </div>
</template>
