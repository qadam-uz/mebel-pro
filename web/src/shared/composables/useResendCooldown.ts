import { onBeforeUnmount, ref } from 'vue'

/**
 * OTP resend cooldown countdown (CB-94) — shared by the client login flow.
 * `left` ticks down to 0 each second; `start(seconds)` (re)arms it, `stop()` clears.
 */
export function useResendCooldown() {
  const left = ref(0)
  let timer: number | undefined

  function start(seconds: number) {
    window.clearInterval(timer)
    left.value = Math.max(0, seconds)
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
