<script setup lang="ts">
// Passive branches info page. There is no client-facing branches directory
// endpoint (branch data is workshop-scoped), so this page explains that the
// branch is chosen at order time and points back to the cutting flow.
import { t } from '@/shared/i18n'
</script>

<template>
  <div>
    <div class="page-head" style="margin-bottom: 6px">
      <div>
        <h1>{{ t('client.branchesTitle') }}</h1>
        <p class="sub">{{ t('client.branchesSub') }}</p>
      </div>
      <div class="tools">
        <RouterLink class="btn btn-acc" to="/c/cutting/drafts">{{
          t('client.newCutting')
        }}</RouterLink>
      </div>
    </div>

    <div class="info-banner">{{ t('client.branchesInfo') }}</div>

    <div class="st-empty">
      <div class="ic">⌂</div>
      <h3>{{ t('client.branchesUnavailable') }}</h3>
      <p>{{ t('client.branchesUnavailableBody') }}</p>
      <RouterLink class="btn btn-acc" to="/c/cutting/drafts">{{
        t('client.newCutting')
      }}</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.info-banner {
  padding: 14px 18px;
  background: var(--sunk);
  border: 1px solid var(--line);
  border-radius: 8px;
  font: 500 13.5px/1.45 var(--f-ui);
  color: var(--ink-10);
  margin: 8px 0 20px;
}
</style>
