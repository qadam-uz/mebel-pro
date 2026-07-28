<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import Icon from '@/shared/components/AppIcon.vue'
import { useOnboardingStore, type OnboardingHintKey } from '@/shared/stores/onboarding'

// The first-run setup checklist (docs/ref/features/onboarding.md), shown on the
// workshop home while the owner's setup is incomplete. Step done-states are
// server-derived; the card's single CTA leads to the first pending step's screen
// and queues its spotlight hint. Not dismissible: while setup is incomplete the
// workshop cannot price an order, so the card is the tenant's truthful state.

interface ChecklistStep {
  key: string
  title: string
  description: string
  done: boolean
  cta: string | null
  hint: OnboardingHintKey | null
  targetPath: string | null
}

const router = useRouter()
const rolePath = useRolePath()
const onboarding = useOnboardingStore()

const steps = computed<ChecklistStep[]>(() => {
  const status = onboarding.status
  if (!status) return []
  const branchTarget = status.first_branch_id
    ? `/workshop/branches/${status.first_branch_id}`
    : '/workshop/branches'
  return [
    {
      key: 'password',
      title: "Parolni o'zgartirish",
      description: 'Vaqtinchalik parol yangi parolga almashtirildi.',
      done: true,
      cta: null,
      hint: null,
      targetPath: null,
    },
    {
      key: 'branch-pricing',
      title: 'Filial narxlarini kiritish',
      description:
        'Kesish va kromka yopishtirish narxlari buyurtma summasini hisoblashda ishlatiladi.',
      done: status.branch_configured,
      cta: 'Narxlarni kiritish',
      hint: 'branch-pricing',
      targetPath: branchTarget,
    },
    {
      key: 'materials',
      title: "Materiallar katalogini to'ldirish",
      description: "Mijozlar faqat filial katalogiga qo'shilgan materiallardan buyurtma beradi.",
      done: status.materials_added,
      cta: "Material qo'shish",
      hint: 'catalog-add',
      targetPath: '/workshop/catalog',
    },
  ]
})

const doneCount = computed(() => steps.value.filter((step) => step.done).length)
const firstPendingKey = computed(() => steps.value.find((step) => !step.done)?.key ?? null)
const remainingText = computed(() => {
  const remaining = steps.value.length - doneCount.value
  return `Buyurtma qabul qilishni boshlash uchun ${remaining} ta qadam qoldi.`
})

function openStep(step: ChecklistStep) {
  if (!step.targetPath) return
  if (step.hint) onboarding.queueHint(step.hint)
  void router.push(rolePath(step.targetPath))
}
</script>

<template>
  <section
    v-if="onboarding.showChecklist"
    class="card mb-5"
    aria-labelledby="onboarding-checklist-title"
    data-testid="onboarding-checklist"
  >
    <div class="card-h">
      <div>
        <h2 id="onboarding-checklist-title">Ishni boshlash</h2>
        <p class="sub">{{ remainingText }}</p>
      </div>
      <span class="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent-deep">
        {{ doneCount }}/{{ steps.length }} bajarildi
      </span>
    </div>
    <ol class="card-b grid gap-2">
      <li
        v-for="(step, index) in steps"
        :key="step.key"
        class="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2.5"
        :class="
          step.done
            ? 'border-hairline bg-sunk'
            : step.key === firstPendingKey
              ? 'border-accent-tint bg-accent-soft/40'
              : 'border-hairline'
        "
      >
        <span
          class="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-extrabold"
          :class="step.done ? 'bg-success text-white' : 'bg-accent-tint text-accent-deep'"
          aria-hidden="true"
        >
          <Icon v-if="step.done" name="check" class="!size-4" />
          <template v-else>{{ index + 1 }}</template>
        </span>
        <span class="min-w-0 grow basis-52">
          <span class="block text-sm font-bold" :class="step.done ? 'text-ink-muted' : 'text-ink'">
            {{ step.title }}
            <span v-if="step.done" class="sr-only">— bajarildi</span>
          </span>
          <span class="block text-xs text-ink-muted">{{ step.description }}</span>
        </span>
        <button
          v-if="!step.done && step.key === firstPendingKey && step.cta"
          type="button"
          class="mp-button mp-button-primary min-h-9 px-3 text-xs"
          @click="openStep(step)"
        >
          {{ step.cta }}
        </button>
      </li>
    </ol>
  </section>
  <section
    v-else-if="onboarding.isEligible && onboarding.loading && !onboarding.loaded"
    class="card mb-5 p-5"
    aria-hidden="true"
  >
    <div class="grid gap-3">
      <span class="sk-line"></span>
      <span class="sk-line"></span>
      <span class="sk-line"></span>
    </div>
  </section>
</template>
