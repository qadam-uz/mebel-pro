// Toast state — a single shared queue rendered by <ToastHost> (mounted once
// per app in its layout). Mirrors the prototype's window.toast(msg, kind).

import { ref } from 'vue'

export type ToastKind = 'ok' | 'warn' | 'danger'

export interface ToastItem {
  id: number
  message: string
  kind: ToastKind
}

const toasts = ref<ToastItem[]>([])
let seq = 0
const timers = new Map<number, ReturnType<typeof setTimeout>>()

function dismiss(id: number): void {
  toasts.value = toasts.value.filter((t) => t.id !== id)
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

function show(message: string, kind: ToastKind = 'ok', duration = 2600): number {
  const id = ++seq
  toasts.value = [...toasts.value, { id, message, kind }]
  timers.set(
    id,
    setTimeout(() => dismiss(id), duration),
  )
  return id
}

export function useToast() {
  return {
    toasts,
    show,
    dismiss,
    ok: (message: string) => show(message, 'ok'),
    warn: (message: string) => show(message, 'warn'),
    danger: (message: string) => show(message, 'danger'),
  }
}
