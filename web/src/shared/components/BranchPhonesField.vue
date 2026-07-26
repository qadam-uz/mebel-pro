<script setup lang="ts">
import { computed, nextTick } from 'vue'

import { MAX_ADDITIONAL_BRANCH_PHONES } from '@/shared/app/branchPhones'
import Icon from '@/shared/components/AppIcon.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'

// The repeatable list of a branch's extra published numbers, sitting under the
// primary phone field in both branch forms. The primary is never in this list —
// it stays its own field because it is the one number orders carry (QAD-158).
const props = defineProps<{
  modelValue: string[]
  /** Prefix for the row input ids, so two forms on one page never collide. */
  idPrefix: string
  /** Per-row messages, index-aligned with `modelValue`; `undefined` = row is fine. */
  errors?: Array<string | undefined>
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const atCap = computed(() => props.modelValue.length >= MAX_ADDITIONAL_BRANCH_PHONES)

function rowId(index: number) {
  return `${props.idPrefix}-${index}`
}

// The primary is the branch's first number, so the extras read as 2nd, 3rd, 4th.
function rowLabel(index: number) {
  return `${index + 2}-telefon`
}

function setPhone(index: number, value: string) {
  const next = [...props.modelValue]
  next[index] = value
  emit('update:modelValue', next)
}

async function addPhone() {
  if (atCap.value || props.disabled) return
  const index = props.modelValue.length
  emit('update:modelValue', [...props.modelValue, ''])
  await nextTick()
  document.getElementById(rowId(index))?.focus()
}

function removePhone(index: number) {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, position) => position !== index),
  )
}
</script>

<template>
  <fieldset>
    <legend class="text-sm font-extrabold text-ink">Qo'shimcha telefonlar</legend>
    <p class="mb-2 mt-1 text-xs text-ink-muted">
      Filial sahifasida mijozlarga ko'rinadi. Buyurtmalarda faqat asosiy raqam ishlatiladi.
    </p>

    <p v-if="modelValue.length === 0" class="mb-2 text-xs text-ink-muted">
      Hozircha qo'shimcha raqam yo'q.
    </p>

    <div v-for="(phone, index) in modelValue" :key="index" class="mb-2 last:mb-0">
      <div class="flex items-end gap-2">
        <label class="field !mb-0 grow" :for="rowId(index)">
          <span>{{ rowLabel(index) }}</span>
          <PhoneInput
            :id="rowId(index)"
            :model-value="phone"
            :disabled="disabled"
            :aria-invalid="!!errors?.[index]"
            :aria-describedby="errors?.[index] ? `${rowId(index)}-error` : undefined"
            @update:model-value="setPhone(index, $event)"
          />
        </label>
        <button
          type="button"
          class="mp-button mp-button-outline size-10 shrink-0 px-0"
          :disabled="disabled"
          :aria-label="`${rowLabel(index)}ni o'chirish`"
          @click="removePhone(index)"
        >
          <Icon name="trash" />
        </button>
      </div>
      <span v-if="errors?.[index]" :id="`${rowId(index)}-error`" class="mp-field-error mt-1 block">
        {{ errors[index] }}
      </span>
    </div>

    <button
      type="button"
      class="mp-button mp-button-outline mt-1"
      :disabled="atCap || disabled"
      @click="addPhone"
    >
      + Telefon qo'shish
    </button>
    <p v-if="atCap" class="mt-2 text-xs text-ink-muted">
      Eng ko'pi {{ MAX_ADDITIONAL_BRANCH_PHONES }} ta qo'shimcha raqam qo'shiladi.
    </p>
  </fieldset>
</template>
