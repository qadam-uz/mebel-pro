<script setup lang="ts">
// Change-password card shared by workshop and admin (and reachable from the
// force-password-change guard). Strength meter + requirement checklist mirror
// the prototype. On success the parent decides where to go.
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import { pwStrength } from '@/shared/password'
import { t } from '@/shared/i18n'
import FormField from '../FormField.vue'
import AppButton from '../AppButton.vue'

const props = withDefaults(
  defineProps<{
    brandLabel: string
    // When true the principal was forced here (first login / after reset);
    // the current-password field is still required by the API.
    forced?: boolean
    submit: (currentPassword: string, newPassword: string) => Promise<void>
  }>(),
  { forced: false },
)

const emit = defineEmits<{ done: [] }>()

const current = ref('')
const next = ref('')
const confirm = ref('')
const error = ref('')
const busy = ref(false)

const strength = computed(() => pwStrength(next.value))
const mismatch = computed(() => confirm.value.length > 0 && next.value !== confirm.value)
const canSubmit = computed(() => strength.value.ok && next.value === confirm.value && !busy.value)

const reqs = computed(() => [
  { key: 'len', ok: strength.value.len, label: t('auth.pwReqLen') },
  { key: 'hasU', ok: strength.value.hasU, label: t('auth.pwReqUpper') },
  { key: 'hasL', ok: strength.value.hasL, label: t('auth.pwReqLower') },
  { key: 'hasD', ok: strength.value.hasD, label: t('auth.pwReqDigit') },
])

async function onSubmit() {
  if (!canSubmit.value) return
  error.value = ''
  busy.value = true
  try {
    await props.submit(current.value, next.value)
    emit('done')
  } catch (e) {
    error.value = e instanceof ApiError ? e.detail : t('auth.wrongCredentials')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <span class="brand">
        <span class="mk">M</span>
        <span style="font-family: var(--f-display); font-size: 19px; font-weight: 600">
          {{ t('common.appName')
          }}<small
            style="
              display: block;
              font-family: var(--f-ui);
              font-size: 11px;
              color: var(--ink-6);
              font-weight: 500;
              letter-spacing: 0.04em;
              text-transform: uppercase;
            "
            >{{ brandLabel }}</small
          >
        </span>
      </span>
      <h1>{{ t('auth.setNewPassword') }}</h1>
      <p class="sub">{{ forced ? t('auth.setNewPasswordSub') : '' }}</p>

      <div v-if="error" class="err-msg">{{ error }}</div>

      <form novalidate @submit.prevent="onSubmit">
        <FormField
          v-model="current"
          type="password"
          :label="t('auth.currentPassword')"
          autocomplete="current-password"
          required
        />
        <div class="field">
          <label>{{ t('auth.newPassword') }}</label>
          <input v-model="next" type="password" autocomplete="new-password" required />
          <div class="pw-meter" :class="`s${strength.score}`"><i /><i /><i /><i /></div>
          <div class="pw-reqs">
            <span v-for="r in reqs" :key="r.key" :class="{ ok: r.ok }">{{ r.label }}</span>
          </div>
        </div>
        <FormField
          v-model="confirm"
          type="password"
          :label="t('auth.confirmPassword')"
          autocomplete="new-password"
          :error="mismatch ? t('auth.passwordsDontMatch') : ''"
          required
        />
        <AppButton
          variant="primary"
          size="lg"
          block
          type="submit"
          :disabled="!canSubmit"
          :loading="busy"
        >
          {{ t('auth.saveAndContinue') }}
        </AppButton>
      </form>
    </div>
  </div>
</template>
