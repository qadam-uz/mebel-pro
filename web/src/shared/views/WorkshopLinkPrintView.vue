<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { workshopLinkUrl } from '@/shared/app/workshopLink'
import AuthFileImage from '@/shared/components/AuthFileImage.vue'
import QrCode from '@/shared/components/QrCode.vue'
import { useWorkshopStore } from '@/shared/stores/workshop'

/**
 * The counter sheet (spec §1.4): workshop name + logo, the branch name, the QR,
 * and the tagline — nothing else. Laid out on screen the way it prints, so
 * printing is a restyle of this DOM rather than a second implementation
 * (DESIGN.md, "Documents that leave the building").
 *
 * A chromeless route (`meta.layout: 'print'`): the workshop shell's fixed frame
 * and sidebar have no business on a sheet of paper, and the reader gets here
 * from the "Chop etish" action, not from the nav.
 */
const route = useRoute()
const workshop = useWorkshopStore()

/** Branch sheet when the route carries a branch; workshop sheet otherwise. */
const branchId = computed(() => {
  const raw = route.params.branch_id
  return typeof raw === 'string' && raw ? raw : null
})
const branch = computed(() =>
  branchId.value && workshop.selectedBranch?.id === branchId.value ? workshop.selectedBranch : null,
)
const workshopName = computed(() => workshop.settings?.name ?? '')
const logoFileId = computed(() => workshop.settings?.logo_file_id ?? null)
const code = computed(
  () => branch.value?.workshop_public_code ?? workshop.settings?.public_code ?? '',
)
const url = computed(() =>
  code.value ? workshopLinkUrl(code.value, branch.value?.branch_no ?? null) : '',
)

function printSheet() {
  window.print()
}

async function load() {
  // Settings carries the workshop's own name, logo and code; both sheets need
  // it, and the branch sheet needs its branch on top.
  await Promise.all([
    workshop.loadSettings(),
    branchId.value ? workshop.loadBranch(branchId.value) : Promise.resolve(),
  ])
}

onMounted(load)
</script>

<template>
  <main class="mx-auto max-w-[520px] px-6 py-10">
    <div v-if="!code" class="text-center text-sm text-ink-muted" aria-live="polite">
      {{ $t('common.state.loading') }}
    </div>

    <template v-else>
      <!-- Screen-only: paper cannot be clicked, and the browser's own print
           dialog is the action. -->
      <div class="mb-8 flex justify-end print:hidden">
        <button type="button" class="mp-button mp-button-primary" @click="printSheet">
          {{ $t('workshopAdmin.clientLink.print') }}
        </button>
      </div>

      <article class="rounded-[18px] border border-hairline bg-elevated px-8 py-10 text-center">
        <AuthFileImage
          v-if="logoFileId"
          :file-id="logoFileId"
          :alt="workshopName"
          size="md"
          class="mx-auto mb-5 h-20 w-auto max-w-[220px] object-contain"
        />
        <h1 class="font-display text-2xl font-bold leading-tight text-ink">{{ workshopName }}</h1>
        <p v-if="branch" class="mt-1 text-base font-semibold text-ink-soft">{{ branch.name }}</p>

        <div class="mx-auto mt-8 w-[240px] max-w-full">
          <QrCode :value="url" :label="$t('workshopAdmin.clientLink.qrLabel')" />
        </div>

        <p class="mt-8 font-display text-lg font-semibold leading-snug text-ink">
          {{ $t('workshopAdmin.clientLink.tagline') }}
        </p>
        <p class="mt-3 break-all text-sm text-ink-muted">{{ url }}</p>
      </article>
    </template>
  </main>
</template>
