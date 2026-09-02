<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { copyText } from '@/shared/app/clipboard'
import { workshopLinkUrl } from '@/shared/app/workshopLink'
import QrCode from '@/shared/components/QrCode.vue'
import { useToast } from '@/shared/composables/useToast'

/**
 * **Mijoz havolasi** — the artifact a counter needs (spec §1.4).
 *
 * The absolute `/w/{code}` link a client scans, its QR, a copy button and the
 * print action. Two hosts: the branch screen passes `branchNo` for the counter
 * QR, workshop settings omits it for the workshop-level link that goes on
 * business cards and in a Telegram bio.
 *
 * The QR is generated in the browser and drawn as inline SVG (`QrCode`) — no
 * external QR service is ever contacted with a workshop's link.
 */
const props = defineProps<{
  code: string
  /** Omit for the workshop-level link. */
  branchNo?: number | null
  /** Where the print sheet lives, already role-normalised by the caller. */
  printTo: string
}>()

const { t } = useI18n()
const toast = useToast()
const copyFailed = ref(false)

const url = computed(() => workshopLinkUrl(props.code, props.branchNo ?? null))

async function copy() {
  copyFailed.value = false
  if (await copyText(url.value)) {
    toast.success(t('workshopAdmin.clientLink.copied'))
    return
  }
  // An insecure context or a denied permission: the field is selectable, so say
  // what to do instead of reporting a failure with no way out.
  copyFailed.value = true
}
</script>

<template>
  <section class="card max-w-[760px]">
    <div class="card-h">
      <h2>{{ $t('workshopAdmin.clientLink.title') }}</h2>
    </div>
    <div class="card-b grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
      <div class="min-w-0">
        <p class="text-sm text-ink-soft">
          {{
            branchNo == null
              ? $t('workshopAdmin.clientLink.workshopHint')
              : $t('workshopAdmin.clientLink.branchHint')
          }}
        </p>

        <label class="field mt-3" for="client-link-url">
          <span>{{ $t('workshopAdmin.clientLink.urlLabel') }}</span>
          <input id="client-link-url" class="mp-input" :value="url" readonly />
        </label>

        <p v-if="copyFailed" class="mt-2 text-sm font-bold text-warning" role="status">
          {{ $t('workshopAdmin.clientLink.copyFailed') }}
        </p>

        <div class="mt-4 flex flex-wrap gap-3">
          <button type="button" class="mp-button mp-button-outline" @click="copy">
            {{ $t('workshopAdmin.clientLink.copy') }}
          </button>
          <RouterLink :to="printTo" class="mp-button mp-button-outline" target="_blank">
            {{ $t('workshopAdmin.clientLink.print') }}
          </RouterLink>
        </div>
      </div>

      <div class="w-[180px] max-w-full justify-self-start rounded-xl border border-hairline p-3">
        <QrCode :value="url" :label="$t('workshopAdmin.clientLink.qrLabel')" />
      </div>
    </div>
  </section>
</template>
