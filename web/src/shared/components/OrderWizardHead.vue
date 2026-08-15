<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// The one head every screen of the staff order-creation flow wears: the title,
// the four numbered steps, and the way out. The flow is four routes
// (walk-in → editor → result → checkout), so before this the operator had no
// standing answer to "where am I and how many steps are left" — each screen
// named itself and nothing named the journey.
//
// Deliberately a head, not a layout: it renders the strip and emits `cancel`.
// Each step decides what leaving costs there, because that differs — nothing
// exists yet on step 1, a saved draft does from step 2 on.
const props = defineProps<{
  /** 1 Mijoz · 2 Detallar · 3 Natija · 4 Rasmiylashtirish */
  step: 1 | 2 | 3 | 4
  /** Under the title — the branch this order is being written against. */
  subtitle?: string | null
  /** Hidden where there is nothing to abandon, or where the screen is read-only. */
  cancellable?: boolean
}>()

const emit = defineEmits<{ cancel: [] }>()

const { t } = useI18n()

// Literal keys, never an interpolated one — `pnpm i18n:check` only resolves
// what it can read as a literal.
const STEP_LABELS = [
  'orders.wizard.stepClient',
  'orders.wizard.stepParts',
  'orders.wizard.stepResult',
  'orders.wizard.stepCheckout',
] as const

const steps = computed(() =>
  STEP_LABELS.map((key, index) => {
    const number = index + 1
    const state = number === props.step ? 'current' : number < props.step ? 'done' : 'ahead'
    return {
      key,
      number,
      label: `${number}. ${t(key)}`,
      state,
      // `accent-deep` is the handoff's colour for a done chip, but on
      // `accent-soft` it measures 4.44:1 — under the 4.5 floor DESIGN.md sets.
      // `accent-strong` is the same orange one step down and clears it.
      klass:
        state === 'current'
          ? 'bg-accent font-semibold text-on-accent'
          : state === 'done'
            ? 'bg-accent-soft font-medium text-accent-strong'
            : 'bg-track font-medium text-ink-nav',
    }
  }),
)
</script>

<template>
  <div class="page-head wizard-head">
    <div class="min-w-0">
      <h1>{{ $t('orders.wizard.title') }}</h1>
      <div v-if="subtitle" class="sub">{{ subtitle }}</div>
    </div>
    <!-- A status readout, not a control: a step is reached by finishing the one
         before it, so a chip is never clickable and never focusable.
         `aria-current` is what tells a screen reader which one is live. -->
    <ol class="mr-auto flex list-none flex-wrap gap-1.5 p-0">
      <li
        v-for="item in steps"
        :key="item.key"
        class="inline-flex items-center rounded-full px-[13px] py-[5px] text-[13px]"
        :class="item.klass"
        :aria-current="item.state === 'current' ? 'step' : undefined"
      >
        {{ item.label }}
      </li>
    </ol>
    <div class="tools">
      <!-- Per-step chrome that has nowhere else to go — the editor's autosave
           chip, a delete action. It sits before Bekor qilish so the way out
           stays the last thing on the row on every step. -->
      <slot name="tools" />
      <!-- Quieter than a page action: leaving is always available and never the
           thing to do, so it reads at the nav weight rather than the ink one. -->
      <button
        v-if="cancellable"
        type="button"
        class="mp-button mp-button-outline text-[13.5px] text-ink-nav"
        @click="emit('cancel')"
      >
        {{ $t('orders.wizard.cancel') }}
      </button>
    </div>
  </div>
</template>
