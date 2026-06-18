import { ref } from 'vue'

// Shared, app-wide toast queue (CB-14). The state is module-level so any
// component can raise a toast and the single <ToastHost> in AppShell renders it
// — toasts survive route navigation (e.g. a "placed" toast shown as the order
// wizard redirects to the order page).

export type ToastTone = 'success' | 'warn' | 'danger'

export interface Toast {
  id: number
  message: string
  tone: ToastTone
}

const DEFAULT_DURATION_MS = 4000

const toasts = ref<Toast[]>([])
const timers = new Map<number, ReturnType<typeof setTimeout>>()
let seq = 0

function dismiss(id: number) {
  toasts.value = toasts.value.filter((toast) => toast.id !== id)
  const timer = timers.get(id)
  if (timer !== undefined) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

function show(message: string, tone: ToastTone = 'success', durationMs = DEFAULT_DURATION_MS) {
  const id = ++seq
  toasts.value = [...toasts.value, { id, message, tone }]
  if (durationMs > 0) {
    timers.set(
      id,
      setTimeout(() => dismiss(id), durationMs),
    )
  }
  return id
}

export function useToast() {
  return {
    toasts,
    show,
    success: (message: string, durationMs?: number) => show(message, 'success', durationMs),
    warn: (message: string, durationMs?: number) => show(message, 'warn', durationMs),
    danger: (message: string, durationMs?: number) => show(message, 'danger', durationMs),
    dismiss,
  }
}
