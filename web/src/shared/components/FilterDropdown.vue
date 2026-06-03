<script setup lang="ts">
import { computed } from 'vue'

import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'

const props = defineProps<{
  label: string
  modelValue: string | null
  options: ChoiceOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const value = computed({
  get: () => props.modelValue,
  set: (next) => emit('update:modelValue', next),
})
</script>

<template>
  <FormSelect v-model="value" :label="label" :options="options" />
</template>
