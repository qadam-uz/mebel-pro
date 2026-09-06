<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'

import { branchStatusLabel } from '@/shared/app/adminUi'
import { copyText } from '@/shared/app/clipboard'
import { workshopLinkUrl } from '@/shared/app/workshopLink'
import { useToast } from '@/shared/composables/useToast'

/**
 * **Mijoz havolalari** — the operator's read of the same artifact the owner
 * copies in the workshop app (`WorkshopLinkCard`, client-entry.md): the
 * workshop's `/w/{code}` link and one `/w/{code}/{branch_no}` link per branch.
 *
 * Support cannot ask an owner to read a QR down the phone, so the platform
 * screen shows what the owner sees. It is deliberately **not** `WorkshopLinkCard`
 * reused: that card speaks the `workshopAdmin` i18n namespace, which the
 * platform SPA does not ship (~62 kB of copy no operator screen renders), and
 * its **Chop etish** action opens a workshop route no operator can reach.
 * Copy here is literal Uzbek like every other platform screen.
 */
const props = defineProps<{
  /** The workshop's `/w/{code}` public code. */
  code: string
  branches: ReadonlyArray<{
    id: string
    branch_no: number
    name: string
    status: string
  }>
}>()

// `qrcode` is a library one card on one platform screen draws with — pulled on
// demand so it never lands in the workshop-detail route chunk (web/AGENTS.md).
const QrCode = defineAsyncComponent(() => import('@/shared/components/QrCode.vue'))

const toast = useToast()
// Keyed by row, so a denied clipboard on one link does not annotate the others.
// The URL is in a selectable readonly field either way — the message says so
// rather than reporting a dead end.
const copyFailedFor = ref<string | null>(null)

const workshopUrl = computed(() => workshopLinkUrl(props.code, null))
const branchLinks = computed(() =>
  props.branches.map((branch) => ({
    ...branch,
    url: workshopLinkUrl(props.code, branch.branch_no),
  })),
)

async function copy(key: string, url: string) {
  copyFailedFor.value = null
  if (await copyText(url)) {
    toast.success('Havola nusxalandi')
    return
  }
  copyFailedFor.value = key
}
</script>

<template>
  <section class="admin-card max-w-[720px]">
    <div class="admin-card-h">
      <h2>Mijoz havolalari</h2>
      <span class="sub">Ustaxona rahbari ko'radigan havolalar</span>
    </div>
    <div class="admin-card-b">
      <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
        <div class="min-w-0">
          <p class="text-sm text-ink-soft">
            Mijoz bu havolani ochsa, ilova ustaxonaga ulanadi va filialni o'zi tanlaydi. Filial
            havolasi mijozni to'g'ridan-to'g'ri o'sha filialga bog'laydi.
          </p>

          <label class="admin-field mt-3" for="admin-client-link-workshop">
            <span>Ustaxona havolasi</span>
            <input id="admin-client-link-workshop" class="mp-input" :value="workshopUrl" readonly />
          </label>

          <p
            v-if="copyFailedFor === 'workshop'"
            class="mt-2 text-sm font-bold text-warning"
            role="status"
          >
            Nusxalab bo'lmadi — havolani belgilab qo'lda nusxalang.
          </p>

          <div class="mt-3">
            <button
              type="button"
              class="mp-button mp-button-outline"
              aria-label="Ustaxona havolasini nusxalash"
              @click="copy('workshop', workshopUrl)"
            >
              Nusxalash
            </button>
          </div>
        </div>

        <div class="w-[160px] max-w-full justify-self-start rounded-xl border border-hairline p-3">
          <QrCode :value="workshopUrl" label="Ustaxona mijoz havolasining QR kodi" />
        </div>
      </div>

      <template v-if="branchLinks.length">
        <h3 class="mt-6 text-[12.5px] font-semibold text-ink-muted">Filial havolalari</h3>
        <ul class="admin-row-list mt-1">
          <li v-for="branch in branchLinks" :key="branch.id" class="admin-row-item">
            <span class="admin-mono text-ink-muted">{{ branch.branch_no }}</span>
            <span class="min-w-0">
              <span class="flex flex-wrap items-center gap-2">
                <b class="text-ink">{{ branch.name }}</b>
                <!-- A closed or inactive branch keeps its link: the QR on its
                     counter is still printed, and support still has to read it
                     back. The pill says what state that branch is in. -->
                <span v-if="branch.status !== 'active'" class="admin-pill admin-pill-warning">{{
                  branchStatusLabel(branch.status)
                }}</span>
              </span>
              <span class="admin-mono mt-0.5 block truncate text-[12.5px] text-ink-muted">
                {{ branch.url }}
              </span>
              <span
                v-if="copyFailedFor === branch.id"
                class="mt-1 block text-[12.5px] font-bold text-warning"
                role="status"
              >
                Nusxalab bo'lmadi — havolani belgilab qo'lda nusxalang.
              </span>
            </span>
            <button
              type="button"
              class="mp-button mp-button-outline min-h-8 px-2.5 text-xs"
              :aria-label="`${branch.name} havolasini nusxalash`"
              @click="copy(branch.id, branch.url)"
            >
              Nusxalash
            </button>
          </li>
        </ul>
      </template>
    </div>
  </section>
</template>
