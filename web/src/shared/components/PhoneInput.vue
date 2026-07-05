<script setup lang="ts">
import { computed, ref } from 'vue'

// A single Uzbek phone field shared across all three apps. The "+998" country
// code is a fixed adornment (never typed, never deletable); the user enters only
// the 9 national digits, hard-capped and shown grouped as "90 123 45 67". Pasting
// a full "+998 90 …", "998…", "0 90 …" or "8 998 …" string sanitizes to the same
// national digits. v-model always carries the normalized "+998XXXXXXXXX" (or ''
// when empty, for optional fields) so stores and the API see today's exact format.
//
// The wrapper owns the field look so every phone field is visually identical
// regardless of the surrounding form; the inner input is reset with a winning
// selector (see .mp-phone .mp-phone-native in main.css) so context rules like
// `.admin-field input` can't re-skin it.
defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue: string
    id?: string
    required?: boolean
    disabled?: boolean
    autocomplete?: string
  }>(),
  { required: false, disabled: false, autocomplete: 'tel' },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const inputRef = ref<HTMLInputElement | null>(null)

/** Extract the ≤9 national digits from any raw string, stripping the country
 *  code (+998 / 998), a trunk-8-before-998, and a leading national-trunk 0. */
function nationalDigits(raw: string): string {
  let digits = raw.replace(/\D/g, '')
  if (digits.startsWith('8998')) digits = digits.slice(1)
  if (digits.startsWith('998')) digits = digits.slice(3)
  else if (digits.startsWith('0')) digits = digits.replace(/^0+/, '')
  return digits.slice(0, 9)
}

/** "901234567" → "90 123 45 67" (trailing groups appear as they fill). */
function group(digits: string): string {
  return [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 7), digits.slice(7, 9)]
    .filter(Boolean)
    .join(' ')
}

const display = computed(() => group(nationalDigits(props.modelValue)))

function onInput() {
  const el = inputRef.value
  if (!el) return
  const national = nationalDigits(el.value)
  // Reflect the sanitized value immediately so invalid chars / overflow never
  // linger in the field, even when the emitted model value doesn't change.
  el.value = group(national)
  emit('update:modelValue', national ? `+998${national}` : '')
}
</script>

<template>
  <div class="mp-phone" :class="{ 'is-disabled': disabled }">
    <span class="mp-phone-prefix" aria-hidden="true">+998</span>
    <input
      :id="id"
      ref="inputRef"
      class="mp-phone-native"
      type="tel"
      inputmode="tel"
      :autocomplete="autocomplete"
      :required="required"
      :disabled="disabled"
      :value="display"
      v-bind="$attrs"
      @input="onInput"
    />
  </div>
</template>
