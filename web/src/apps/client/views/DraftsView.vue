<script setup lang="ts">
// My drafts — unbound cutting drafts. Mirrors prototype client/cutting-drafts.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useToast } from '@/shared/composables/useToast'
import * as clientApi from '../api'
import type { Draft, Material } from '../api/types'
import { LIMITS, relativeTime, summariseDraft } from '../lib/cutting'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const drafts = ref<Draft[]>([])
const materials = ref<Material[]>([])
const creating = ref(false)

const confirmOpen = ref(false)
const pendingDelete = ref<string | null>(null)

const count = computed(() => drafts.value.length)

async function load() {
  loading.value = true
  error.value = null
  try {
    const [list, mats] = await Promise.all([clientApi.listDrafts(), clientApi.listMaterials()])
    drafts.value = list
    materials.value = mats
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function summary(d: Draft) {
  return summariseDraft(d, materials.value, null)
}

async function newCutting() {
  if (creating.value) return
  creating.value = true
  try {
    const draft = await clientApi.createDraft()
    router.push(`/c/cutting/${draft.id}`)
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    creating.value = false
  }
}

function askDelete(id: string) {
  pendingDelete.value = id
  confirmOpen.value = true
}

async function doDelete() {
  const id = pendingDelete.value
  if (!id) return
  try {
    await clientApi.deleteDraft(id)
    drafts.value = drafts.value.filter((d) => d.id !== id)
    toast.ok(t('client.draftDeleted'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
  pendingDelete.value = null
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('client.draftsTitle') }}</h1>
        <p class="sub">{{ t('client.draftsSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-acc" type="button" :disabled="creating" @click="newCutting">
          {{ t('client.newCutting') }}
        </button>
      </div>
    </div>

    <div class="drafts-hd">
      <h2>{{ t('client.draftsAll') }}</h2>
      <span v-if="!loading && !error" class="ct">{{
        t('client.draftsCount', { n: count, cap: LIMITS.MAX_DRAFTS })
      }}</span>
    </div>

    <div v-if="loading">
      <div v-for="n in 3" :key="n" class="sk-draft">
        <div>
          <div class="sk sk-line" style="width: 55%" />
          <div class="sk sk-line" style="width: 78%; margin-top: 10px" />
        </div>
        <div class="sk sk-line" style="width: 64px" />
      </div>
    </div>

    <ErrorState v-else-if="error" :error="error" :retry="load" />

    <div v-else-if="drafts.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('client.noDrafts') }}</h3>
      <p>{{ t('client.noDraftsBody') }}</p>
      <button class="btn btn-acc" type="button" :disabled="creating" @click="newCutting">
        {{ t('client.newCutting') }}
      </button>
    </div>

    <article v-for="d in drafts" v-else :key="d.id" class="draft-card">
      <div class="main" @click="router.push(`/c/cutting/${d.id}`)">
        <div class="nm">{{ summary(d).dominantLabel || t('client.noMaterial') }}</div>
        <div class="stats">
          <span
            ><b>{{ summary(d).totalParts }}</b> {{ t('client.partsUnit') }}</span
          >
          <span v-if="summary(d).sheets != null"
            ><b>{{ summary(d).sheets }}</b> {{ t('client.sheetsUnit') }}</span
          >
          <span v-if="summary(d).wastePct != null"
            ><b>{{ summary(d).wastePct }}%</b> {{ t('client.wasteUnit') }}</span
          >
          <span style="color: var(--ink-6)"
            >{{ relativeTime(d.updated_at) }} · {{ t('client.edited') }}</span
          >
        </div>
      </div>
      <div class="right">
        <button class="open-aff" type="button" @click="router.push(`/c/cutting/${d.id}`)">
          {{ t('client.open') }}
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>
        <button
          class="del-btn"
          type="button"
          :aria-label="t('client.deleteDraftTitle')"
          @click="askDelete(d.id)"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
          </svg>
        </button>
      </div>
    </article>

    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="t('client.deleteDraftTitle')"
      :message="t('client.deleteDraftMsg')"
      :ok-text="t('client.deleteDraftOk')"
      danger
      @confirm="doDelete"
    />
  </div>
</template>

<style scoped>
.drafts-hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 0 12px;
  border-bottom: 1px solid var(--line);
  margin: 12px 0 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.drafts-hd h2 {
  font: 600 18px var(--f-display);
  margin: 0;
  color: var(--ink-12);
}
.drafts-hd .ct {
  font: 500 13px var(--f-mono);
  color: var(--ink-6);
}
.draft-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 16px 18px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 10px;
  transition:
    border-color 0.12s,
    transform 0.12s;
}
.draft-card:hover {
  border-color: var(--ink-10);
  transform: translateY(-1px);
}
.draft-card .main {
  cursor: pointer;
  min-width: 0;
}
.draft-card .nm {
  font: 500 14.5px var(--f-ui);
  color: var(--ink-12);
  margin-bottom: 4px;
}
.draft-card .stats {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font: 500 12px var(--f-ui);
  color: var(--ink-10);
  margin-top: 6px;
}
.draft-card .stats b {
  font: 600 13px var(--f-mono);
  color: var(--ink-12);
}
.draft-card .right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.open-aff {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: 600 12.5px var(--f-ui);
  color: var(--accent);
  white-space: nowrap;
  cursor: pointer;
  background: none;
  border: 0;
  padding: 6px 8px;
  border-radius: 6px;
}
.open-aff svg {
  width: 14px;
  height: 14px;
}
.del-btn {
  background: none;
  border: 1px solid var(--line);
  color: var(--ink-7);
  cursor: pointer;
  border-radius: 6px;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
}
.del-btn:hover {
  border-color: var(--danger);
  color: var(--danger);
  background: var(--danger-tint);
}
.sk-draft {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 16px 18px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 10px;
}
</style>
