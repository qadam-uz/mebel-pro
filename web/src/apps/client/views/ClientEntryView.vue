<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { formatPhone } from '@/shared/app/clientUi'
import { publicWorkshopLogoUrl, storeClientEntry } from '@/shared/app/clientEntry'
import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig } from '@/shared/app/roleConfig'
import Icon from '@/shared/components/AppIcon.vue'
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
const { t } = useI18n()

const code = computed(() => String(route.params.code ?? ''))
const branchNo = computed(() => {
  const raw = route.params.branchNo
  if (raw === undefined || raw === null || raw === '') return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) ? parsed : null
})

const applying = ref(false)
const applyFailed = ref(false)

const link = computed(() => entry.link)
const branches = computed(() => link.value?.branches ?? [])

/**
 * The branch this entry pins — or `null`, which is a real outcome (§2.2, and
 * decision 15).
 *
 * A branch QR names one. A workshop link to a one-branch workshop means that
 * counter. A workshop link to a **multi-branch** workshop pins nothing: entry
 * never asks which counter, so it must not name one either. The workshop is
 * still recorded, so it lands on Ustaxonalarim, and home then shows «Ustaxona
 * tanlang». A printed branch QR whose `branch_no` no longer resolves falls back
 * to the same workshop-level behaviour rather than dying (§8).
 */
const settledBranchId = computed<string | null>(() => {
  const resolved = link.value
  if (!resolved) return null
  if (resolved.requested_branch_id) return resolved.requested_branch_id
  return branches.value.length === 1 ? (branches.value[0]?.id ?? null) : null
})
const settledBranch = computed<WorkshopLinkBranch | null>(
  () => branches.value.find((branch) => branch.id === settledBranchId.value) ?? null,
)
/**
 * A multi-branch link says how many counters there are and names them — enough
 * for the client to recognise the workshop — without turning it into a choice.
 */
const branchSummary = computed(() => {
  if (settledBranchId.value || branches.value.length < 2) return null
  return t('client.entry.branchCount', {
    n: branches.value.length,
    names: branches.value.map((branch) => branch.name).join(', '),
  })
})
/** 429 gets the dead-link screen's transient variant — a retry, not a dead end. */
const isTransient = computed(() => entry.linkError === 'workshop_link_rate_limited')

/**
 * The real logo, over the code-scoped public route — this screen renders before
 * there is a session, so the authenticated file route is out of reach here.
 *
 * Only requested when the resolve says the workshop has a logo, and any failure
 * (a file that went away, a throttled lookup, an offline hop) falls back to the
 * name monogram this screen drew before the route existed.
 */
const logoFailed = ref(false)
const logoUrl = computed(() =>
  link.value?.workshop_logo_file_id ? publicWorkshopLogoUrl(link.value.code) : null,
)

/**
 * Resolve, then apply straight away — there is no question to ask.
 *
 * Signed in, the entry is recorded (and the branch pinned when the link named
 * one) and the client lands on home; signed out, the entry is parked so the
 * Telegram login round-trip can apply it on the other side.
 */
async function resolve() {
  applyFailed.value = false
  logoFailed.value = false
  const resolved = await entry.resolveLink(code.value, branchNo.value)
  if (!resolved) return
  storeClientEntry({ code: resolved.code, branch_id: settledBranchId.value })
  if (!auth.isAllowedFor('client')) return
  await applyNow(settledBranchId.value)
}

async function applyNow(branchId: string | null) {
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
          <!-- The workshop's own logo, fetched by code over the public route so
               a signed-out scan sees the real thing; the monogram stays as the
               fallback for a workshop that has none or a load that fails. -->
          <img
            v-if="logoUrl && !logoFailed"
            :src="logoUrl"
            :alt="link.workshop_name"
            class="size-14 rounded-[14px] border border-hairline object-contain"
            @error="logoFailed = true"
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

        <!-- One branch, named: the counter this link is for. -->
        <div v-if="settledBranch" class="mt-4 rounded-[14px] bg-sunk p-4">
          <b class="text-sm text-ink">{{ settledBranch.name }}</b>
          <p class="mt-1 text-xs text-ink-muted">{{ settledBranch.address }}</p>
          <a
            class="mt-1 inline-flex min-h-11 items-center text-xs font-bold text-accent-deep underline underline-offset-2"
            :href="`tel:${settledBranch.phone}`"
          >
            {{ formatPhone(settledBranch.phone) }}
          </a>
          <p v-if="settledBranch.closed_reason" class="mt-1 text-xs text-warning">
            {{ settledBranch.closed_reason }}
          </p>
        </div>

        <!-- Several counters: entry never asks which, so it names none. The
             count and the names are recognition, not a choice (§2.2). -->
        <p v-else-if="branchSummary" class="mt-2.5 text-[12.5px] leading-[1.45] text-ink-muted">
          {{ branchSummary }}
        </p>

        <button
          v-if="!auth.isAllowedFor('client')"
          type="button"
          class="mp-button mp-button-primary mt-6 min-h-[46px] w-full"
          @click="goToLogin"
        >
          {{ $t('client.entry.enter') }}
        </button>
        <button
          v-else
          type="button"
          class="mp-button mp-button-primary mt-6 min-h-[46px] w-full"
          @click="openApp"
        >
          {{ $t('client.entry.openApp') }}
        </button>

        <div class="mt-6 border-t border-hairline pt-5">
          <LocaleSwitcher variant="segmented" />
        </div>
      </template>
    </section>
  </main>
</template>
