<script setup lang="ts">
import { computed, ref } from 'vue'

// A styled, Uzbek file picker that replaces the browser-native file input (whose
// "Choose File / No file chosen" text is unstyled and English). It wraps a hidden
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
    buttonLabel: 'Fayl tanlang',
    placeholder: 'Fayl tanlanmagan',
    disabled: false,
    uploading: false,
    removable: false,
  },
)
const emit = defineEmits<{ change: [event: Event]; remove: [] }>()

const inputRef = ref<HTMLInputElement | null>(null)
const localName = ref('')

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
      {{ uploading ? 'Yuklanmoqda…' : displayName || placeholder }}
    </span>
    <button
      v-if="removable && displayName && !uploading"
      type="button"
      class="shrink-0 rounded-md px-2 text-lg font-bold leading-none text-ink-muted transition hover:text-danger"
      aria-label="Faylni olib tashlash"
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
      {{ uploading ? 'Yuklanmoqda' : buttonLabel }}
    </button>
  </div>
</template>
