<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { formatPhone } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import { yandexMapUrl } from '@/shared/app/yandexMapLink'
import Icon from '@/shared/components/AppIcon.vue'
import { useToast } from '@/shared/composables/useToast'
import { useClientEntryStore, type ClientWorkshopBranch } from '@/shared/stores/clientEntry'

/**
 * One branch of a related workshop — the row Ustaxonalarim and the workshop
 * profile both render, identically (spec §6.1).
 *
 * It carries the pin and both actions, because the pin *is* a branch: a filled
 * star marks the pinned row and an outline star button pins any other in place.
 * «Yangi chizma» only opens the editor at that branch — it writes nothing
 * (decision 25: "shunchaki bosib ko'rishi ham mumkin"); the pin moves when an
 * order is actually placed. The head above it carries no drawing action.
 */
const props = defineProps<{
  branch: ClientWorkshopBranch
  workshopId: string
  /** For the re-pin write, which goes through the audited entry endpoint. */
  publicCode: string
  /**
   * The row's title line. `null` renders no title at all — a one-branch
   * workshop on Ustaxonalarim is already named by its card head (decision 16),
   * and the star then sits at the end of the address line instead.
   */
  title: string | null
}>()

const entry = useClientEntryStore()
const rolePath = useRolePath()
const toast = useToast()
const { t } = useI18n()

/** The star is the row's only write, so it owns the in-flight flag. */
const pinning = ref(false)

const isClosed = computed(() => props.branch.status !== 'active')
const mapUrl = computed(() => yandexMapUrl(props.branch.latitude, props.branch.longitude))
const catalogTo = computed(() =>
  rolePath(`/c/workshops/${props.workshopId}/catalog?branch=${props.branch.id}`),
)
/**
 * The branch travels to the editor in the URL, not through the pin (decision
 * 25). The editor validates it against the client's own branch options, so a
 * hand-typed id can't point a drawing at a counter the client can't reach.
 */
const drawingTo = computed(() => rolePath(`/c/cutting/new?branch=${props.branch.id}`))

async function makePrimary() {
  if (props.branch.is_pinned || pinning.value) return
  pinning.value = true
  try {
    await entry.pinBranch(props.publicCode, props.branch.id)
    toast.success(t('client.workshop.madePrimaryToast', { name: props.branch.name }))
  } catch {
    toast.danger(t('client.workshops.pinFailed'))
  } finally {
    pinning.value = false
  }
}
</script>

<template>
  <li class="border-b border-divider px-3.5 py-3 last:border-b-0 sm:px-5 sm:py-4">
    <div class="flex items-center gap-1.5">
      <!-- Title-less rows still carry the status: the address takes the line,
           and the pill rides it, or a closed one-branch workshop would announce
           itself only in the reason sentence underneath. -->
      <span class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
        <b v-if="title" class="text-[14.5px] text-ink">{{ title }}</b>
        <span v-else class="min-w-0 text-[12.5px] leading-[1.4] text-ink-muted">
          {{ branch.address }}
        </span>
        <!-- Only `temporarily_closed` earns a pill: an «Faol» pill beside a
             workshop name reads as an order status (§3 item 5). -->
        <span v-if="isClosed" class="client-pill client-pill-info">
          {{ $t('client.workshops.closed') }}
        </span>
      </span>

      <span
        v-if="branch.is_pinned"
        class="grid size-6 shrink-0 place-items-center text-accent"
        role="img"
        :aria-label="$t('client.workshop.primary')"
      >
        <Icon name="star-filled" class="size-6" />
      </span>
      <button
        v-else
        type="button"
        class="-my-2.5 -mr-2.5 grid size-11 shrink-0 place-items-center rounded-[11px] text-ink-muted transition hover:bg-sunk hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60"
        :aria-label="$t('client.workshop.makePrimary')"
        :title="$t('client.workshop.makePrimary')"
        :disabled="pinning"
        @click="makePrimary"
      >
        <Icon name="star" class="size-6" />
      </button>
    </div>

    <p v-if="title" class="mt-[3px] text-[12.5px] leading-[1.4] text-ink-muted">
      {{ branch.address }}
    </p>
    <p
      v-if="branch.closed_reason"
      class="mt-[3px] text-[13px] font-bold leading-[1.4] text-warning"
    >
      {{ branch.closed_reason }}
    </p>

    <div class="flex flex-wrap items-center gap-x-3.5">
      <a
        class="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-deep underline underline-offset-2"
        :href="`tel:${branch.phone}`"
      >
        {{ formatPhone(branch.phone) }}
      </a>
      <!-- Rendered only when the branch actually has a pin — decision 8: the
           map is Yandex's, opened in a new tab, never an in-app frame. -->
      <a
        v-if="mapUrl"
        class="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-deep underline underline-offset-2"
        :href="mapUrl"
        target="_blank"
        rel="noopener noreferrer"
      >
        {{ $t('client.workshop.viewOnMap') }}
      </a>
    </div>

    <div class="mt-0.5 flex flex-wrap gap-2">
      <!-- A plain link: opening the editor at this branch is a look, not a
           choice, so it writes nothing (decision 25). -->
      <RouterLink
        :to="drawingTo"
        class="mp-button mp-button-primary min-h-10 px-3.5 py-2.5 text-[13.5px]"
      >
        <Icon name="plus" class="size-[17px]" />
        {{ $t('client.workshop.newDrawing') }}
      </RouterLink>
      <RouterLink
        :to="catalogTo"
        class="mp-button mp-button-outline min-h-10 px-3.5 py-2.5 text-[13.5px]"
      >
        {{ $t('client.workshop.catalog') }}
      </RouterLink>
    </div>
  </li>
</template>
