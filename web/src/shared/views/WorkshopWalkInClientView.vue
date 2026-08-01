<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useWorkshopStore } from '@/shared/stores/workshop'

// First step of the staff order flow: identify the walk-in client by phone
// (find-or-create). If the phone already belongs to a client, the registered
// name is shown for the staffer to confirm before entering the editor — a phone
// typo must not silently attach the order to a stranger.
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const workshop = useWorkshopStore()
const { t } = useI18n()

const phone = ref('')
const name = ref('')
const resolving = ref(false)
const error = ref<string | null>(null)
// After a phone match: the disclosed existing name awaiting staff confirmation.
const matched = ref<{ id: string; name: string; phone: string } | null>(null)

const branch = computed(() =>
  workshop.branches.find((item) => item.id === workshop.selectedBranchContext),
)
const canResolve = computed(() => isUzPhone(phone.value) && !resolving.value)

async function resolve() {
  error.value = null
  if (!isUzPhone(phone.value)) {
    error.value = t('orders.error.phoneInvalid')
    return
  }
  resolving.value = true
  try {
    const resolved = await cutting.resolveWalkInClient({
      phone: normalizeUzPhone(phone.value),
      name: name.value.trim() || undefined,
    })
    if (resolved.created) {
      enterEditor(resolved.id)
    } else {
      // Existing client — confirm the disclosed name before proceeding.
      matched.value = { id: resolved.id, name: resolved.name, phone: resolved.phone }
    }
  } catch (caught) {
    const code = apiErrorCode(caught)
    error.value =
      code === 'client_name_required'
        ? t('orders.error.clientNameRequired')
        : workshopErrorMessage(code)
  } finally {
    resolving.value = false
  }
}

function enterEditor(clientId: string) {
  void router.push({
    path: rolePath('/workshop/orders/new/cutting'),
    query: { client: clientId },
  })
}
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('orders.walkIn.title') }}</h1>
        <div class="sub">
          {{
            branch
              ? $t('orders.walkIn.branch', { branch: branch.name })
              : $t('orders.walkIn.branchMissing')
          }}
        </div>
      </div>
    </div>

    <div class="card max-w-[560px]">
      <div class="card-b grid gap-4">
        <p class="text-sm text-ink-soft">{{ $t('orders.walkIn.intro') }}</p>

        <template v-if="!matched">
          <label class="field">
            <span>{{ $t('orders.walkIn.phone') }}</span>
            <PhoneInput v-model="phone" />
          </label>
          <label class="field">
            <span
              >{{ $t('orders.walkIn.name') }}
              <small class="text-ink-muted">{{ $t('orders.walkIn.nameHint') }}</small></span
            >
            <input
              v-model="name"
              class="mp-input"
              :placeholder="$t('orders.walkIn.namePlaceholder')"
            />
          </label>

          <p v-if="error" class="mp-field-error">{{ error }}</p>

          <div class="flex justify-end">
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="!canResolve"
              @click="resolve"
            >
              {{ resolving ? $t('orders.walkIn.checking') : $t('orders.walkIn.continue') }}
            </button>
          </div>
        </template>

        <template v-else>
          <div class="rounded-lg border border-hairline bg-sunk p-4">
            <div class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted">
              {{ $t('orders.walkIn.found') }}
            </div>
            <div class="mt-1 text-lg font-bold text-ink">{{ matched.name }}</div>
            <div class="font-mono text-sm text-ink-muted">{{ matched.phone }}</div>
          </div>
          <p class="text-sm text-ink-soft">{{ $t('orders.walkIn.confirm') }}</p>
          <div class="flex justify-between gap-2">
            <button type="button" class="mp-button mp-button-outline" @click="matched = null">
              {{ $t('orders.walkIn.back') }}
            </button>
            <button
              type="button"
              class="mp-button mp-button-primary"
              @click="enterEditor(matched.id)"
            >
              {{ $t('orders.walkIn.confirmContinue') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>
