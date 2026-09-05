<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { formatPhone } from '@/shared/app/clientUi'
import { storeClientEntry } from '@/shared/app/clientEntry'
import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig } from '@/shared/app/roleConfig'
import Icon from '@/shared/components/AppIcon.vue'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import BrandMark from '@/shared/components/BrandMark.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientEntryStore, type WorkshopLinkBranch } from '@/shared/stores/clientEntry'

/**
 * `/w/{code}` and `/w/{code}/{branch_no}` — the door a workshop's QR opens.
 *
 * Public route: it renders before there is a session, and the resolved entry is
 * parked in `localStorage` so it survives the Telegram login round-trip. A
 * client who is already signed in never sees this screen unless the link needs a
 * branch chosen — the pin is applied and home is the landing (spec §3).
 */
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const config = useRoleConfig()
const auth = useAuthStore()
const entry = useClientEntryStore()

const code = computed(() => String(route.params.code ?? ''))
const branchNo = computed(() => {
  const raw = route.params.branchNo
  if (raw === undefined || raw === null || raw === '') return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) ? parsed : null
})

/** The branch this entry will pin, once one is settled on. */
const selectedBranchId = ref<string | null>(null)
const applying = ref(false)
const applyFailed = ref(false)

const link = computed(() => entry.link)
const branches = computed(() => link.value?.branches ?? [])
/**
 * The choice step (§3.2) is for a workshop-level link with several branches —
 * and for a branch link whose `branch_no` no longer resolves, which falls back
 * to exactly that behaviour rather than dying on a printed QR (§8).
 */
const needsChoice = computed(() => {
  if (!link.value) return false
  if (link.value.requested_branch_id) return false
  return branches.value.length > 1
})
const resolvedBranch = computed<WorkshopLinkBranch | null>(() => {
  const id = selectedBranchId.value
  return id ? (branches.value.find((branch) => branch.id === id) ?? null) : null
})
/** 429 gets the dead-link screen's transient variant — a retry, not a dead end. */
const isTransient = computed(() => entry.linkError === 'workshop_link_rate_limited')

async function resolve() {
  applyFailed.value = false
  selectedBranchId.value = null
  const resolved = await entry.resolveLink(code.value, branchNo.value)
  if (!resolved) return
  // A single visible branch is not a choice — the link means that counter.
  const only = resolved.branches.length === 1 ? resolved.branches[0].id : null
  const settled = resolved.requested_branch_id ?? only
  if (!settled) return
  await choose(settled)
}

/**
 * One tap chooses and continues: signed in, the pin is applied and the client
 * lands on home; signed out, the entry is parked for the login round-trip.
 */
async function choose(branchId: string) {
  selectedBranchId.value = branchId
  storeClientEntry({ code: link.value?.code ?? code.value, branch_id: branchId })
  if (!auth.isAllowedFor('client')) return
  await applyNow(branchId)
}

async function applyNow(branchId: string) {
  applying.value = true
  applyFailed.value = false
  try {
    const applied = await entry.applyPendingEntry({
      code: link.value?.code ?? code.value,
      branch_id: branchId,
    })
    // The workshop was blocked, or the branch retired, between the resolve and
    // the apply. The session is untouched — say so and offer the plain way in.
    if (!applied) {
      applyFailed.value = true
      return
    }
    await router.replace(config.homePath)
  } finally {
    applying.value = false
  }
}

function goToLogin() {
  void router.push(config.loginPath)
}

function openApp() {
  void router.push(config.homePath)
}

onMounted(resolve)
</script>

<template>
  <main class="grid min-h-[var(--app-vh)] place-items-center bg-bg px-4 py-8">
    <section class="client-card w-[min(100%,420px)] p-8">
      <RouterLink :to="rolePath('/c')" class="client-brand mb-7 inline-flex">
        <BrandMark :size="32" />
        <span class="client-brand-name">Mebel Pro</span>
      </RouterLink>

      <!-- Loading: the card keeps its shape so nothing jumps when the workshop
           name and its branches land. -->
      <div v-if="entry.linkLoading || applying" aria-live="polite">
        <span class="sr-only">{{ $t('client.common.loading') }}</span>
        <div class="client-skeleton size-14 rounded-[14px]"></div>
        <div class="client-skeleton mt-4 h-6 w-3/4"></div>
        <div class="client-skeleton mt-3 h-4 w-full"></div>
        <div class="client-skeleton mt-6 h-11 w-full"></div>
      </div>

      <!-- One dead-link screen for every cause; the throttle variant retries. -->
      <div v-else-if="entry.linkError || !link">
        <div class="client-empty-icon"><Icon name="store" /></div>
        <h1 class="mt-4 font-display text-2xl font-semibold leading-tight text-ink">
          {{ isTransient ? $t('client.entry.busyTitle') : $t('client.entry.deadTitle') }}
        </h1>
        <p class="mt-2 text-sm text-ink-soft">
          {{ isTransient ? $t('client.entry.busyBody') : $t('client.entry.deadBody') }}
        </p>
        <button
          v-if="isTransient"
          type="button"
          class="mp-button mp-button-primary mt-6 min-h-[46px] w-full"
          @click="resolve"
        >
          {{ $t('client.common.retry') }}
        </button>
        <button
          type="button"
          class="mp-button mt-3 min-h-[46px] w-full"
          :class="isTransient ? 'mp-button-outline' : 'mp-button-primary'"
          @click="openApp"
        >
          {{ $t('client.entry.openApp') }}
        </button>
      </div>

      <template v-else>
        <div class="flex items-center gap-3">
          <!-- The stored logo is served over an authenticated route, so a
               signed-out scan gets the workshop's monogram instead of a broken
               frame; the name beside it is the trust cue either way. -->
          <AuthFileImage
            v-if="link.workshop_logo_file_id && auth.isAllowedFor('client')"
            :file-id="link.workshop_logo_file_id"
            :alt="link.workshop_name"
            size="sm"
            class="size-14 rounded-[14px] border border-hairline object-contain"
          />
          <span
            v-else
            class="grid size-14 place-items-center rounded-[14px] bg-accent-soft font-display text-xl font-bold text-accent-strong"
            aria-hidden="true"
          >
            {{ link.workshop_name.slice(0, 1).toUpperCase() }}
          </span>
        </div>

        <h1 class="mt-4 font-display text-2xl font-semibold leading-tight text-ink">
          {{ $t('client.entry.greeting', { workshop: link.workshop_name }) }}
        </h1>
        <p class="mt-2 text-sm text-ink-soft">{{ $t('client.entry.sub') }}</p>

        <p v-if="applyFailed" class="mt-4 text-sm font-bold text-danger" role="alert">
          {{ $t('client.entry.applyFailed') }}
        </p>

        <!-- §3.2 — that workshop's branches only, one tap. A temporarily closed
             branch shows its reason and stays choosable. -->
        <div v-if="needsChoice && !resolvedBranch" class="mt-6">
          <h2 class="text-sm font-bold text-ink">{{ $t('client.entry.chooseTitle') }}</h2>
          <div class="mt-3 overflow-hidden rounded-[14px] border border-hairline">
            <button
              v-for="branch in branches"
              :key="branch.id"
              type="button"
              class="flex w-full flex-col items-start gap-1 border-b border-hairline px-4 py-3 text-left last:border-b-0 hover:bg-sunk"
              @click="choose(branch.id)"
            >
              <span class="flex flex-wrap items-center gap-2">
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
              </span>
              <span class="text-xs text-ink-muted">{{ branch.address }}</span>
              <span v-if="branch.closed_reason" class="text-xs text-warning">
                {{ branch.closed_reason }}
              </span>
            </button>
          </div>
        </div>

        <!-- Settled on a branch and signed out: the standard Kirish action into
             the existing Telegram sign-in. The entry is already parked. -->
        <div v-else-if="resolvedBranch" class="mt-6">
          <div class="rounded-[14px] bg-sunk p-4">
            <b class="text-sm text-ink">{{ resolvedBranch.name }}</b>
            <p class="mt-1 text-xs text-ink-muted">{{ resolvedBranch.address }}</p>
            <a
              class="mt-1 inline-flex min-h-11 items-center text-xs font-bold text-accent-deep underline underline-offset-2"
              :href="`tel:${resolvedBranch.phone}`"
            >
              {{ formatPhone(resolvedBranch.phone) }}
            </a>
            <p v-if="resolvedBranch.closed_reason" class="mt-1 text-xs text-warning">
              {{ resolvedBranch.closed_reason }}
            </p>
          </div>
          <button
            v-if="!auth.isAllowedFor('client')"
            type="button"
            class="mp-button mp-button-primary mt-4 min-h-[46px] w-full"
            @click="goToLogin"
          >
            {{ $t('client.entry.enter') }}
          </button>
          <button
            v-else
            type="button"
            class="mp-button mp-button-primary mt-4 min-h-[46px] w-full"
            @click="openApp"
          >
            {{ $t('client.entry.openApp') }}
          </button>
        </div>

        <div class="mt-6 border-t border-hairline pt-5">
          <LocaleSwitcher variant="segmented" />
        </div>
      </template>
    </section>
  </main>
</template>
