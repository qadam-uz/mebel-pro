// Shared, reference-counted body scroll lock for modals (CB-43/CB-63).
//
// `overflow: hidden` alone does not stop touch-scrolling the page behind a
// fixed modal on iOS Safari, so we also pin the body with `position: fixed` and
// restore the scroll position on release. Reference-counted so nested modals
// (e.g. a ConfirmDialog opened over the edge picker) don't release the lock
// early.

let lockCount = 0
let savedScrollY = 0

export function lockBodyScroll() {
  if (lockCount === 0) {
    savedScrollY = window.scrollY
    const { style } = document.body
    style.position = 'fixed'
    style.top = `-${savedScrollY}px`
    style.left = '0'
    style.right = '0'
    style.width = '100%'
    document.body.classList.add('modal-open')
  }
  lockCount += 1
}

export function unlockBodyScroll() {
  if (lockCount === 0) return
  lockCount -= 1
  if (lockCount === 0) {
    const { style } = document.body
    style.position = ''
    style.top = ''
    style.left = ''
    style.right = ''
    style.width = ''
    document.body.classList.remove('modal-open')
    window.scrollTo(0, savedScrollY)
  }
}
