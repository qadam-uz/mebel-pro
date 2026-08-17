<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import Icon from '@/shared/components/AppIcon.vue'

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

// A numbered rail: circle → label → connector. Four filled pills read as four
// tags; a rail reads as one journey with a position on it, which is what a head
// for a four-route flow is for. The number moved into the circle, so the label
// is the bare word.
const steps = computed(() =>
  STEP_LABELS.map((key, index) => {
    const number = index + 1
    const state = number === props.step ? 'current' : number < props.step ? 'done' : 'ahead'
    return {
      key,
      number,
      label: t(key),
      state,
      done: state === 'done',
      circle:
        state === 'current'
          ? 'bg-accent text-on-accent [box-shadow:0_0_0_3px_var(--color-track)]'
          : state === 'done'
            ? 'bg-ink-nav text-on-accent'
            : 'bg-elevated text-ink-muted [box-shadow:inset_0_0_0_1.5px_var(--color-hairline)]',
      label_klass:
        state === 'current'
          ? 'font-bold text-ink'
          : state === 'done'
            ? 'font-medium text-ink-nav'
            : 'font-medium text-ink-muted',
      // The connector belongs to the step behind it: it is dark once that step
      // is finished, which is what makes the rail read as progress.
      connector: state === 'done' ? 'bg-ink-nav' : 'bg-hairline',
      last: number === STEP_LABELS.length,
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
    <ol class="mr-auto flex flex-none list-none items-center p-0">
      <li
        v-for="item in steps"
        :key="item.key"
        class="flex items-center gap-[9px]"
        :aria-current="item.state === 'current' ? 'step' : undefined"
      >
        <span
          class="num grid size-[26px] flex-none place-items-center rounded-full text-[12.5px] font-bold"
          :class="item.circle"
        >
          <Icon v-if="item.done" name="check" class="size-3.5 [stroke-width:2.6]" />
          <template v-else>{{ item.number }}</template>
        </span>
        <span class="whitespace-nowrap text-[13.5px]" :class="item.label_klass">
          {{ item.label }}
        </span>
        <span
          v-if="!item.last"
          aria-hidden="true"
          class="mx-3 h-0.5 w-[34px] flex-none rounded-[2px]"
          :class="item.connector"
        ></span>
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
