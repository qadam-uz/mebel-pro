/**
 * Shared client-app constants (CB-102) — single source for values previously
 * hardcoded across views/stores, so a validator and the input it guards can never
 * drift apart. Backend mirrors (DRAFT_LIMIT, the 10mm minimum, the 100-part cap)
 * live in the backend; these are the frontend copies that must match it.
 */

/** Autosave debounce window for the cutting editor. */
export const AUTOSAVE_DEBOUNCE_MS = 700

/**
 * Debounce window for the editor's `localStorage` draft-recovery snapshot.
 *
 * The snapshot re-serialises every part in the drawing (~60 kB of JSON at 300
 * rows), so writing it per keystroke burns that on every character. Debouncing
 * trades it for a crash window: a tab killed within 300 ms of the last keystroke
 * recovers to the state before it. Kept well under `AUTOSAVE_DEBOUNCE_MS` so the
 * recovery layer still lands ahead of the server save it backs up, and paired
 * with synchronous flushes on every exit the editor can see (unload, pagehide,
 * tab hidden, route leave, unmount, and just before each save request), which
 * leaves only an unannounced process kill inside the window.
 */
export const DRAFT_RECOVERY_DEBOUNCE_MS = 300

/** Search-input debounce for list views (orders, branches). */
export const SEARCH_DEBOUNCE_MS = 250

/** Page size for the notifications list view. */
export const NOTIFICATIONS_PAGE_LIMIT = 50

/** How many rows the header bell's dropdown loads — its own slice, not the page's. */
export const NOTIFICATIONS_MENU_LIMIT = 10

/** Page size for the client orders list (load-more). */
export const ORDERS_PAGE_LIMIT = 30

/** Page size for stock transaction ledgers. */
export const INVENTORY_TX_PAGE_LIMIT = 50

/** Page size for the supplier-invoice list (load-more). */
export const INVENTORY_INVOICE_PAGE_LIMIT = 50

/** Page size for the admin + workshop material catalog tables (load-more). */
export const MATERIALS_PAGE_LIMIT = 50

/** Cap on catalog options returned to the "add material" picker (server-searched). */
export const CATALOG_PICKER_LIMIT = 50

/** Minimum part length/width in mm (matches the backend part-min). */
export const MIN_PART_MM = 10

/** Max parts (summed quantity) per optimisation (matches backend too_many_parts). */
export const MAX_PARTS = 300

/** Saved-drafts cap per client (matches backend DRAFT_LIMIT). */
export const DRAFT_LIMIT = 50
