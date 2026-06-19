/**
 * Shared client-app constants (CB-102) — single source for values previously
 * hardcoded across views/stores, so a validator and the input it guards can never
 * drift apart. Backend mirrors (DRAFT_LIMIT, the 50mm minimum, the 100-part cap)
 * live in the backend; these are the frontend copies that must match it.
 */

/** Autosave debounce window for the cutting editor. */
export const AUTOSAVE_DEBOUNCE_MS = 700

/** Search-input debounce for list views (orders, branches). */
export const SEARCH_DEBOUNCE_MS = 250

/** Page size for the notifications list view. */
export const NOTIFICATIONS_PAGE_LIMIT = 50

/** Page size for the client orders list (load-more). */
export const ORDERS_PAGE_LIMIT = 30

/** Page size for stock transaction ledgers. */
export const INVENTORY_TX_PAGE_LIMIT = 50

/** Minimum part length/width in mm (matches the backend part-min). */
export const MIN_PART_MM = 50

/** Max parts (summed quantity) per optimisation (matches backend too_many_parts). */
export const MAX_PARTS = 100

/** Saved-drafts cap per client (matches backend DRAFT_LIMIT). */
export const DRAFT_LIMIT = 50

/**
 * Cap for the editor's catalog load when NO preferred branch is set (CB-40). A
 * branch-scoped load stays unlimited (CB-84 filters + CB-19/86 recovery need the
 * full per-branch list); only the otherwise-unbounded whole-catalog load on a
 * no-branch draft is capped, so a fresh draft doesn't pull every material. The
 * editor nudges the user to pick a branch for the full catalog. The backend
 * bounds the `limit` query at le=200.
 */
export const NO_BRANCH_CATALOG_LIMIT = 60
