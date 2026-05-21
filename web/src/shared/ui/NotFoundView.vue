<script setup lang="ts">
import { t } from '@/shared/i18n'
</script>

<template>
  <div class="auth-wrap">
    <div class="st-empty" style="max-width: 460px">
      <div class="ic" aria-hidden="true">404</div>
      <h3>Sahifa topilmadi</h3>
      <p>{{ t('common.noData') }}</p>
    </div>
  </div>
</template>
