/**
 * Where the suite runs — the one place the stack's coordinates are declared.
 *
 * The two variables travel together. `E2E_BASE_URL` points the browser at an
 * already-running stack (Playwright then skips its `webServer` block), and
 * `E2E_DATABASE_URL` points the seeding CLI at *that stack's* database. Setting
 * only the first seeds a platform user into a database the API under test never
 * reads, and every seeded fixture is invisible — so they are documented, and
 * meant to be used, as a pair (`e2e/AGENTS.md`).
 */

/** DSN of the database the stack under test reads. */
export const databaseUrl =
  process.env.E2E_DATABASE_URL ?? 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'

/** Origin of the app under test. */
export const baseUrl = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

/** No external stack named — Playwright boots (and owns) the local one. */
export const usesLocalServers = !process.env.E2E_BASE_URL

// `postgresql+asyncpg` is a well-formed non-special scheme, so the WHATWG
// parser still yields the user and path we need.
const dsn = new URL(databaseUrl)

/** Database inside `databaseUrl`; the local stack drops and recreates it per run. */
export const databaseName = decodeURIComponent(dsn.pathname.replace(/^\//, ''))

/** Role inside `databaseUrl`, used to reach the local stack's `psql`. */
export const databaseUser = decodeURIComponent(dsn.username)
