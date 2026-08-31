import { onBeforeUnmount, ref } from 'vue'

/**
 * A seconds countdown for "try again in N" copy — the client sign-in card's
 * `retry_after_seconds` throttles (token creation and code redeem) both use it.
 * `left` ticks down to 0 each second; `start(seconds)` (re)arms it, `stop()` clears.
 */
export function useCountdown() {
  const left = ref(0)
  let timer: number | undefined

  function start(seconds: number) {
    window.clearInterval(timer)
    left.value = Math.max(0, seconds)
    if (left.value === 0) return
    timer = window.setInterval(() => {
      left.value = Math.max(0, left.value - 1)
      if (left.value === 0) window.clearInterval(timer)
    }, 1000)
  }

  function stop() {
    window.clearInterval(timer)
    left.value = 0
  }

  onBeforeUnmount(() => window.clearInterval(timer))

  return { left, start, stop }
}
