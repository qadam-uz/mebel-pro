<script setup lang="ts">
// Confirm dialog with an optional reason field — mirrors the prototype's
// confirmAction(). Built on the shared AppModal. v-model:open controls it.
import { ref, watch } from 'vue'
import { AppButton, AppModal } from '@/shared/ui'
import { t } from '@/shared/i18n'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    okText?: string
    danger?: boolean
    reason?: boolean
    reasonLabel?: string
  }>(),
  { okText: '', danger: false, reason: false, reasonLabel: '' },
)

const emit = defineEmits<{
  'update:open': [v: boolean]
  confirm: [reason: string]
}>()

const reasonText = ref('')
const reasonErr = ref(false)

watch(
  () => props.open,
  (open) => {
    if (open) {
      reasonText.value = ''
      reasonErr.value = false
    }
  },
)

function close() {
  emit('update:open', false)
}

function confirm() {
  if (props.reason && !reasonText.value.trim()) {
    reasonErr.value = true
    return
  }
  emit('confirm', reasonText.value.trim())
  close()
}
</script>

<template>
  <AppModal :open="open" :title="title" @update:open="emit('update:open', $event)">
    <p style="margin: 0; color: var(--ink-10); font-size: 14px">{{ message }}</p>
    <div v-if="reason" class="field" style="margin-top: 14px">
      <label>{{ reasonLabel }}</label>
      <textarea
        v-model="reasonText"
        rows="3"
        :aria-invalid="reasonErr ? 'true' : undefined"
        :style="reasonErr ? 'border-color: var(--danger)' : ''"
      />
      <span v-if="reasonErr" class="err" role="alert">{{ reasonLabel }}</span>
    </div>
    <template #footer>
      <AppButton variant="outline" @click="close">{{ t('common.cancel') }}</AppButton>
      <AppButton :variant="danger ? 'danger' : 'acc'" @click="confirm">
        {{ okText || t('common.confirm') }}
      </AppButton>
    </template>
  </AppModal>
</template>
