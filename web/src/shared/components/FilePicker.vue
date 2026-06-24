<script setup lang="ts">
import { ref } from 'vue'

// A styled, Uzbek file picker that replaces the browser-native file input (whose
// "Choose File / No file chosen" text is unstyled and English). It wraps a hidden
// native input and re-emits its `change` event unchanged, so existing handlers
// that read `event.target.files[0]` keep working as-is.
withDefaults(
  defineProps<{
    accept?: string
    disabled?: boolean
    id?: string
    buttonLabel?: string
    placeholder?: string
  }>(),
  { buttonLabel: 'Fayl tanlang', placeholder: 'Fayl tanlanmagan', disabled: false },
)
const emit = defineEmits<{ change: [event: Event] }>()

const inputRef = ref<HTMLInputElement | null>(null)
const fileName = ref('')

function onChange(event: Event) {
  fileName.value = (event.target as HTMLInputElement).files?.[0]?.name ?? ''
  emit('change', event)
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
      :disabled="disabled"
      @change="onChange"
    />
    <span class="min-w-0 flex-1 truncate text-sm" :class="fileName ? 'text-ink' : 'text-ink-muted'">
      {{ fileName || placeholder }}
    </span>
    <button
      type="button"
      class="mp-button mp-button-outline shrink-0"
      :disabled="disabled"
      @click="inputRef?.click()"
    >
      {{ buttonLabel }}
    </button>
  </div>
</template>
