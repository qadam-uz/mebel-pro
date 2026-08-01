<script setup lang="ts">
import { computed } from 'vue'

import { LOCALES, LOCALE_NAMES, LOCALE_SHORT_NAMES, setLocale, type Locale } from '@/shared/i18n'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/shared/components/ActionMenu.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'

// Two shapes for one control, because the two places it appears ask different
// things of it.
//
// `segmented` on the login screens: every language is visible without opening
// anything. Someone who cannot read the screen cannot be expected to find a
// menu whose trigger is written in the language they don't read — the whole
// point is to be legible before the app is.
//
// `menu` in the topbars, where a branch switcher, a search field, notifications
// and the account menu are already competing for the row. The trigger carries
// the globe plus the current language's own two letters, so it still says what
// it does without three segments of width.
withDefaults(defineProps<{ variant?: 'menu' | 'segmented' }>(), { variant: 'menu' })

const { t, locale } = useI18n()

const options = computed(() => LOCALES.map((value) => ({ value, label: LOCALE_NAMES[value] })))

const current = computed(() => locale.value as Locale)
const currentShort = computed(() => LOCALE_SHORT_NAMES[current.value])

const menuItems = computed(() =>
  LOCALES.map((value) => ({
    label: LOCALE_NAMES[value],
    // The active language is marked, not hidden: a menu that drops the current
    // choice makes the user guess which one they are on.
    icon: value === current.value ? 'check' : undefined,
  })),
)

function onSelect(index: number) {
  void setLocale(LOCALES[index])
}

function onSegmentedSelect(value: string) {
  void setLocale(value as Locale)
}
</script>

<template>
  <SegmentedControl
    v-if="variant === 'segmented'"
    :label="t('locale.label')"
    :model-value="current"
    :options="options"
    @update:model-value="onSegmentedSelect"
  />

  <ActionMenu
    v-else
    :items="menuItems"
    :label="`${t('locale.change')} — ${LOCALE_NAMES[current]}`"
    trigger-class="mp-locale-trigger"
    @select="onSelect"
  >
    <template #trigger>
      <svg viewBox="0 0 24 24" aria-hidden="true" class="mp-locale-glyph">
        <circle cx="12" cy="12" r="8.5" />
        <path d="M3.5 12h17" />
        <path
          d="M12 3.5c2.2 2.3 3.4 5.3 3.4 8.5s-1.2 6.2-3.4 8.5c-2.2-2.3-3.4-5.3-3.4-8.5S9.8 5.8 12 3.5Z"
        />
      </svg>
      <span class="mp-locale-code">{{ currentShort }}</span>
    </template>
  </ActionMenu>
</template>
