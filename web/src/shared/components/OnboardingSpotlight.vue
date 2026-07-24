<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ONBOARDING_HINTS, useOnboardingStore } from '@/shared/stores/onboarding'

// Spotlight coach-mark host (docs/ref/features/onboarding.md). Dims and blocks
// the screen except the hint's target control, which stays live — the user
// advances by clicking the real control, and the first interaction dismisses
// the hint. Trigger policy lives here: a hint auto-shows once per principal on
// arriving at its screen while the step is pending; a hint queued by the
// checklist CTA re-shows regardless of the seen-marker.

const HOLE_PADDING = 8
const CALLOUT_GAP = 12
const VIEWPORT_MARGIN = 12
// Generous: the target screen may still be loading its data (branch detail,
// catalog) — polling is idle-cheap, and a route change cancels it anyway.
const RESOLVE_DEADLINE_MS = 8000

const route = useRoute()
const onboarding = useOnboardingStore()

const targetEl = ref<HTMLElement | null>(null)
const hole = ref<{ top: number; left: number; width: number; height: number } | null>(null)
const calloutRef = ref<HTMLElement | null>(null)
const skipButtonRef = ref<HTMLButtonElement | null>(null)
const calloutStyle = ref<Record<string, string>>({ visibility: 'hidden' })

let resolveFrame = 0
let resolveDeadline = 0
let resizeObserver: ResizeObserver | null = null
// One-shot per attach: when the callout fits neither below nor above the hole,
// nudge the scroll so the target sits at the viewport bottom and retry once.
let scrollNudged = false

const active = computed(() => onboarding.activeHint !== null && hole.value !== null)

const blockerRects = computed(() => {
  const area = hole.value
  if (!area) return []
  const right = area.left + area.width
  const bottom = area.top + area.height
  return [
    { top: '0px', left: '0px', right: '0px', height: `${Math.max(0, area.top)}px` },
    { top: `${bottom}px`, left: '0px', right: '0px', bottom: '0px' },
    {
      top: `${area.top}px`,
      left: '0px',
      width: `${Math.max(0, area.left)}px`,
      height: `${area.height}px`,
    },
    { top: `${area.top}px`, left: `${right}px`, right: '0px', height: `${area.height}px` },
  ]
})

const ringStyle = computed(() => {
  const area = hole.value
  if (!area) return {}
  return {
    top: `${area.top}px`,
    left: `${area.left}px`,
    width: `${area.width}px`,
    height: `${area.height}px`,
  }
})

function currentRouteName(): string | null {
  return typeof route.name === 'string' ? route.name : null
}

// Trigger policy: on every route/status/queue change, decide whether the
// current screen owes the owner a hint.
async function evaluateTriggers() {
  if (!onboarding.isEligible) return
  await onboarding.ensureLoaded()
  if (!onboarding.status) return
  const routeName = currentRouteName()
  if (!routeName) return
  const hint = Object.values(ONBOARDING_HINTS).find((entry) => entry.routeName === routeName)
  if (!hint) return
  if (onboarding.queuedHintKey === hint.key) {
    onboarding.consumeQueuedHint()
    onboarding.requestHint(hint.key, { force: true })
    return
  }
  if (onboarding.activeHintKey === null) onboarding.requestHint(hint.key)
}

function stopResolving() {
  if (resolveFrame) cancelAnimationFrame(resolveFrame)
  resolveFrame = 0
}

function detachTarget() {
  stopResolving()
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('scroll', reposition, true)
  window.removeEventListener('resize', reposition)
  window.removeEventListener('pointerdown', onGlobalPointerDown, true)
  window.removeEventListener('keydown', onGlobalKeydown, true)
  targetEl.value = null
  hole.value = null
  calloutStyle.value = { visibility: 'hidden' }
}

// The target screen renders async (skeletons, lazy data) — poll per frame until
// the marked element exists; give up quietly when it never appears.
function resolveTarget(key: string) {
  stopResolving()
  resolveDeadline = performance.now() + RESOLVE_DEADLINE_MS
  const attempt = () => {
    const found = document.querySelector<HTMLElement>(`[data-onboard="${key}"]`)
    if (found) {
      attachTarget(found)
      return
    }
    if (performance.now() > resolveDeadline) {
      onboarding.dismissHint({ markSeen: false })
      return
    }
    resolveFrame = requestAnimationFrame(attempt)
  }
  attempt()
}

function attachTarget(element: HTMLElement) {
  targetEl.value = element
  scrollNudged = false
  reposition()
  element.scrollIntoView({ block: 'center', behavior: 'auto' })
  window.addEventListener('scroll', reposition, true)
  window.addEventListener('resize', reposition)
  window.addEventListener('pointerdown', onGlobalPointerDown, true)
  window.addEventListener('keydown', onGlobalKeydown, true)
  resizeObserver = new ResizeObserver(reposition)
  resizeObserver.observe(element)
  void nextTick(() => {
    reposition()
    focusIntoSpotlight(element)
  })
}

function focusIntoSpotlight(element: HTMLElement) {
  const focusable = element.matches('button, a[href], input, select, textarea, [tabindex]')
    ? element
    : element.querySelector<HTMLElement>(
        'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      )
  ;(focusable ?? skipButtonRef.value)?.focus()
}

function reposition() {
  const element = targetEl.value
  if (!element) return
  if (!element.isConnected) {
    onboarding.dismissHint({ markSeen: false })
    return
  }
  const rect = element.getBoundingClientRect()
  hole.value = {
    top: rect.top - HOLE_PADDING,
    left: rect.left - HOLE_PADDING,
    width: rect.width + HOLE_PADDING * 2,
    height: rect.height + HOLE_PADDING * 2,
  }
  void nextTick(positionCallout)
}

function positionCallout() {
  const area = hole.value
  const callout = calloutRef.value
  if (!area || !callout) return
  const width = Math.min(340, window.innerWidth - VIEWPORT_MARGIN * 2)
  const height = callout.offsetHeight
  const below = area.top + area.height + CALLOUT_GAP
  const fitsBelow = below + height + VIEWPORT_MARGIN <= window.innerHeight
  const fitsAbove = area.top - height - CALLOUT_GAP >= VIEWPORT_MARGIN
  if (!fitsBelow && !fitsAbove && !scrollNudged && targetEl.value) {
    // Short viewport: park the target at the bottom edge so the space above can
    // host the callout without covering the hole, then re-measure.
    scrollNudged = true
    targetEl.value.scrollIntoView({ block: 'end', behavior: 'auto' })
    requestAnimationFrame(reposition)
    return
  }
  const top = fitsBelow ? below : Math.max(VIEWPORT_MARGIN, area.top - height - CALLOUT_GAP)
  const left = Math.min(
    Math.max(VIEWPORT_MARGIN, area.left),
    Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN),
  )
  calloutStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    width: `${width}px`,
    visibility: 'visible',
  }
}

// The forced click: any pointer interaction inside the target counts as taking
// the step — dismiss and let the real control receive the event untouched.
function onGlobalPointerDown(event: PointerEvent) {
  const element = targetEl.value
  if (!element) return
  if (event.target instanceof Node && element.contains(event.target)) {
    onboarding.dismissHint({ markSeen: true })
  }
}

function onGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    onboarding.dismissHint({ markSeen: true })
  }
}

function skip() {
  onboarding.dismissHint({ markSeen: true })
}

watch(
  () => onboarding.activeHintKey,
  (key) => {
    detachTarget()
    if (key) resolveTarget(key)
  },
)

watch(
  [() => route.fullPath, () => onboarding.status, () => onboarding.queuedHintKey],
  () => {
    const hint = onboarding.activeHint
    if (hint && hint.routeName !== currentRouteName()) {
      onboarding.dismissHint({ markSeen: false })
    }
    void evaluateTriggers()
  },
  { immediate: true },
)

onBeforeUnmount(detachTarget)
</script>

<template>
  <Teleport to="body">
    <!-- The root must NOT catch pointer events — the hole between the blockers is
         what keeps the target live; a plain inset-0 div would swallow it. -->
    <div
      v-if="active && onboarding.activeHint"
      class="pointer-events-none fixed inset-0 z-[60]"
      data-testid="onboarding-spotlight"
    >
      <!-- Invisible click-blockers around the hole: the target stays live, the rest of the screen doesn't. -->
      <div
        v-for="(blocker, index) in blockerRects"
        :key="index"
        class="pointer-events-auto absolute"
        :style="blocker"
        aria-hidden="true"
      ></div>
      <!-- Visual layer: rounded scrim-with-hole + accent ring, never intercepting clicks. -->
      <div
        class="pointer-events-none absolute rounded-[10px] border-2 border-accent shadow-[0_0_0_9999px_color-mix(in_srgb,var(--color-ink)_45%,transparent)]"
        :style="ringStyle"
        aria-hidden="true"
      ></div>
      <div
        ref="calloutRef"
        class="pointer-events-auto absolute rounded-lg border border-hairline bg-elevated p-4 shadow-xl"
        :style="calloutStyle"
        role="dialog"
        aria-labelledby="onboarding-hint-title"
        aria-describedby="onboarding-hint-body"
      >
        <p id="onboarding-hint-title" class="text-sm font-extrabold text-ink">
          {{ onboarding.activeHint.title }}
        </p>
        <p id="onboarding-hint-body" class="mt-1.5 text-sm leading-relaxed text-ink-soft">
          {{ onboarding.activeHint.body }}
        </p>
        <div class="mt-3 flex items-center justify-between gap-3">
          <span class="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent-deep">
            {{ onboarding.activeHint.step }}-qadam
          </span>
          <button
            ref="skipButtonRef"
            type="button"
            class="mp-button mp-button-outline min-h-8 px-3 text-xs"
            @click="skip"
          >
            Keyinroq
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
