<script setup lang="ts">
// Label + control + hint + error, using the design system's .field. Wraps a
// native input by default (v-model), or pass a control via the default slot
// (e.g. a select/textarea) and the field just provides label/hint/error.
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    label?: string
    modelValue?: string | number
    type?: string
    placeholder?: string
    hint?: string
    error?: string
    required?: boolean
    autocomplete?: string
    disabled?: boolean
  }>(),
  { type: 'text' },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const id = useId()
const hintId = computed(() => (props.hint ? `${id}-hint` : undefined))
const errorId = computed(() => (props.error ? `${id}-err` : undefined))
const describedBy = computed(
  () => [hintId.value, errorId.value].filter(Boolean).join(' ') || undefined,
)
</script>

<template>
  <div class="field">
    <label v-if="label" :for="id"
      >{{ label }}<span v-if="required" aria-hidden="true"> *</span></label
    >
    <slot :id="id" :described-by="describedBy">
      <input
        :id="id"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :required="required"
        :autocomplete="autocomplete"
        :disabled="disabled"
        :aria-describedby="describedBy"
        :aria-invalid="error ? 'true' : undefined"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      />
    </slot>
    <span v-if="hint && !error" :id="hintId" class="hint">{{ hint }}</span>
    <span v-if="error" :id="errorId" class="err" role="alert">{{ error }}</span>
  </div>
</template>
