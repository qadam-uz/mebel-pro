<script setup lang="ts">
import { computed, ref } from 'vue'
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
    error.value = "Telefon raqamini to'g'ri kiriting."
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
        ? 'Yangi mijoz uchun ism kiriting.'
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
        <h1>Yangi buyurtma</h1>
        <div class="sub">
          {{ branch ? `${branch.name} · mijoz uchun` : 'Filial tanlang' }}
        </div>
      </div>
    </div>

    <div class="card max-w-[560px]">
      <div class="card-b grid gap-4">
        <p class="text-sm text-ink-soft">
          Mijozning telefon raqamini kiriting. Agar mijoz avval ro'yxatdan o'tgan bo'lsa, uni
          topamiz; bo'lmasa, yangi mijoz sifatida qo'shamiz.
        </p>

        <template v-if="!matched">
          <label class="field">
            <span>Telefon raqami</span>
            <PhoneInput v-model="phone" />
          </label>
          <label class="field">
            <span>Ism <small class="text-ink-muted">(yangi mijoz uchun)</small></span>
            <input v-model="name" class="mp-input" placeholder="Masalan: Dilshod" />
          </label>

          <p v-if="error" class="mp-field-error">{{ error }}</p>

          <div class="flex justify-end">
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="!canResolve"
              @click="resolve"
            >
              {{ resolving ? 'Tekshirilmoqda…' : 'Davom etish' }}
            </button>
          </div>
        </template>

        <template v-else>
          <div class="rounded-lg border border-hairline bg-sunk p-4">
            <div class="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-muted">
              Topilgan mijoz
            </div>
            <div class="mt-1 text-lg font-bold text-ink">{{ matched.name }}</div>
            <div class="font-mono text-sm text-ink-muted">{{ matched.phone }}</div>
          </div>
          <p class="text-sm text-ink-soft">
            Bu mijoz uchun buyurtma yaratilsinmi? Agar bu boshqa odam bo'lsa, orqaga qaytib raqamni
            tekshiring.
          </p>
          <div class="flex justify-between gap-2">
            <button type="button" class="mp-button mp-button-outline" @click="matched = null">
              Orqaga
            </button>
            <button
              type="button"
              class="mp-button mp-button-primary"
              @click="enterEditor(matched.id)"
            >
              Ha, davom etish
            </button>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>
