<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { formatPhone } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import Icon from '@/shared/components/AppIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useToast } from '@/shared/composables/useToast'
import { useClientEntryStore, type ClientWorkshop } from '@/shared/stores/clientEntry'

/**
 * **Ustaxonalarim** — the client's own workshops (spec §5).
 *
 * The pinned workshop plus every workshop the client has an order or a drawing
 * with, pinned first. Pickup and contact information only: no prices, no
 * catalogs, no CTAs into the editor — and no path from here to a list of every
 * workshop on the platform, which this page replaced.
 */
const entry = useClientEntryStore()
const toast = useToast()
const router = useRouter()
const rolePath = useRolePath()
const { t } = useI18n()

/** The workshop whose branch choice (§3.2) is open, if any. */
const choosingFor = ref<ClientWorkshop | null>(null)
const pinningWorkshopId = ref<string | null>(null)
const pinError = ref<string | null>(null)

const workshops = computed(() => entry.workshops)

async function refresh() {
  await entry.loadMyWorkshops()
}

/**
 * "Asosiy qilish" — one visible branch pins straight through; several ask which,
 * the same question the workshop-level link asks. Either way the write goes
 * through `POST /client/entry`, the one audited path that can move the pin.
 */
function makePrimary(workshop: ClientWorkshop) {
  pinError.value = null
  if (workshop.branches.length === 1) {
    void pinBranch(workshop, workshop.branches[0].id)
    return
  }
  choosingFor.value = workshop
}

async function pinBranch(workshop: ClientWorkshop, branchId: string) {
  pinningWorkshopId.value = workshop.workshop_id
  pinError.value = null
  try {
    const applied = await entry.applyEntry(workshop.public_code, branchId)
    choosingFor.value = null
    toast.success(t('client.entry.connected', { workshop: applied.workshop_name }))
    await refresh()
  } catch {
    pinError.value = workshop.workshop_id
  } finally {
    pinningWorkshopId.value = null
  }
}

function startCutting() {
  void router.push(rolePath('/c/cutting/new'))
}

onMounted(refresh)
</script>

<template>
  <section>
    <div class="client-page-head mb-5">
      <div>
        <h1>{{ $t('client.workshops.title') }}</h1>
        <p class="sub">{{ $t('client.workshops.subtitle') }}</p>
      </div>
    </div>

    <div v-if="entry.workshopsLoading" class="grid gap-3" aria-live="polite">
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div v-for="item in 2" :key="item" class="client-card p-5">
        <div class="flex items-center gap-3">
          <div class="client-skeleton size-12 rounded-[14px]"></div>
          <div class="client-skeleton h-5 w-1/3"></div>
        </div>
        <div class="client-skeleton mt-4 h-4 w-2/3"></div>
        <div class="client-skeleton mt-3 h-4 w-1/2"></div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="entry.workshopsError"
      :title="$t('client.workshops.loadFailed')"
      :trace-id="entry.workshopsTraceId"
      @retry="refresh"
    />

    <!-- First run: nothing pinned and no history. The app is joined through a
         workshop's link, so say that — and keep the organic path open. -->
    <div v-else-if="workshops.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="store" /></div>
      <h3>{{ $t('client.workshops.emptyTitle') }}</h3>
      <p>{{ $t('client.workshops.emptyBody') }}</p>
      <button type="button" class="mp-button mp-button-primary mt-4" @click="startCutting">
        {{ $t('client.common.newDraft') }}
      </button>
    </div>

    <div v-else class="grid gap-4">
      <article
        v-for="workshop in workshops"
        :key="workshop.workshop_id"
        class="client-card overflow-hidden"
      >
        <div class="flex flex-wrap items-center gap-3 p-5">
          <AuthFileImage
            v-if="workshop.logo_file_id"
            :file-id="workshop.logo_file_id"
            :alt="workshop.name"
            size="sm"
            class="size-12 rounded-[14px] border border-hairline object-contain"
          />
          <span
            v-else
            class="grid size-12 place-items-center rounded-[14px] bg-accent-soft font-display text-lg font-bold text-accent-strong"
            aria-hidden="true"
          >
            {{ workshop.name.slice(0, 1).toUpperCase() }}
          </span>

          <div class="min-w-0 flex-1">
            <h2 class="m-0 flex flex-wrap items-center gap-2">
              <span class="truncate font-display text-lg font-semibold text-ink">
                {{ workshop.name }}
              </span>
              <span v-if="workshop.is_pinned" class="client-pill client-pill-ready">
                {{ $t('client.workshops.pinned') }}
              </span>
            </h2>
          </div>

          <button
            v-if="!workshop.is_pinned"
            type="button"
            class="mp-button mp-button-outline"
            :disabled="pinningWorkshopId === workshop.workshop_id"
            @click="makePrimary(workshop)"
          >
            {{
              pinningWorkshopId === workshop.workshop_id
                ? $t('client.common.busy')
                : $t('client.workshops.makePrimary')
            }}
          </button>
        </div>

        <p
          v-if="pinError === workshop.workshop_id"
          class="px-5 pb-3 text-sm font-bold text-danger"
          role="alert"
        >
          {{ $t('client.workshops.pinFailed') }}
        </p>

        <!-- §3.2-style choice, inline: which counter of this workshop. -->
        <div
          v-if="choosingFor?.workshop_id === workshop.workshop_id"
          class="border-t border-divider bg-sunk px-5 py-4"
        >
          <h3 class="text-sm font-bold text-ink">{{ $t('client.entry.chooseTitle') }}</h3>
          <div class="mt-3 grid gap-2">
            <button
              v-for="branch in workshop.branches"
              :key="branch.id"
              type="button"
              class="rounded-lg border border-hairline bg-elevated px-3 py-2 text-left hover:bg-sunk"
              :disabled="pinningWorkshopId === workshop.workshop_id"
              @click="pinBranch(workshop, branch.id)"
            >
              <b class="text-sm text-ink">{{ branch.name }}</b>
              <span class="mt-0.5 block text-xs text-ink-muted">{{ branch.address }}</span>
            </button>
          </div>
        </div>

        <ul class="border-t border-divider">
          <li
            v-for="branch in workshop.branches"
            :key="branch.id"
            class="border-b border-divider px-5 py-4 last:border-b-0"
          >
            <div class="flex flex-wrap items-center gap-2">
              <b class="text-sm text-ink">{{ branch.name }}</b>
              <span
                class="client-pill"
                :class="branch.status === 'active' ? 'client-pill-ready' : 'client-pill-info'"
              >
                {{
                  branch.status === 'active'
                    ? $t('client.workshops.active')
                    : $t('client.workshops.closed')
                }}
              </span>
            </div>
            <p class="mt-1 text-xs text-ink-muted">{{ branch.address }}</p>
            <a
              class="mt-1 inline-flex min-h-11 items-center text-xs font-bold text-accent-deep underline underline-offset-2"
              :href="`tel:${branch.phone}`"
            >
              {{ formatPhone(branch.phone) }}
            </a>
            <p v-if="branch.closed_reason" class="mt-1 text-sm font-bold text-warning">
              {{ branch.closed_reason }}
            </p>
          </li>
          <li v-if="workshop.branches.length === 0" class="px-5 py-4 text-sm text-ink-muted">
            {{ $t('client.workshops.noBranches') }}
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>
