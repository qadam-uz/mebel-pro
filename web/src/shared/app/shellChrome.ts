import type { NavGroupId, NavItem } from '@/shared/app/roleConfig'

/**
 * Chrome helpers shared by the three role shells (`src/apps/<role>/*Shell.vue`).
 * Only what more than one shell genuinely needs lands here — everything else
 * stays in the shell that owns it, so a role's bundle carries a role's code.
 */

/**
 * Two layouts render without the shell, for different reasons: `auth` is the
 * signed-out card (and the public workshop-link landing), `print` is a document
 * that leaves the building — a sidebar and a topbar have no place on paper.
 * Everything that asks "is there chrome around me?" asks this.
 */
export function isChromelessLayout(layout: unknown): boolean {
  return layout === 'auth' || layout === 'print'
}

/**
 * Sidebar sections for the workshop and platform shells. One grouping for both —
 * they only ever differed in the fallback for an item with no group, and no item
 * ships without one.
 *
 * Groups by the stable `NavGroupId`, not by the rendered label — grouping on
 * display text would split or merge sections the moment a locale changed. The
 * caller resolves `nav.group.<id>` for the heading.
 */
export function groupedNav(items: NavItem[]) {
  const groups: Array<{ id: NavGroupId; items: NavItem[] }> = []
  for (const item of items) {
    const id = item.group ?? 'platform'
    let group = groups.find((current) => current.id === id)
    if (!group) {
      group = { id, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
}

/** Icon set for the client header and the workshop sidebar. The platform shell
 *  has its own, larger set (`iconPath` in `adminUi.ts`) — the two sidebars name
 *  different things and share almost no glyphs. */
export function iconPath(name: string | undefined) {
  const paths: Record<string, string> = {
    dashboard: '<path d="M4 13h6V4H4v9Zm10 7h6V4h-6v16ZM4 20h6v-5H4v5Z"/>',
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
    orders: '<path d="M6 3h9l3 3v15H6V3Z"/><path d="M14 3v4h4"/><path d="M9 11h6M9 15h6"/>',
    scissors:
      '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8 8l10 10M8 16 18 6"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
    box: '<path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
    grid: '<path d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z"/>',
    chart: '<path d="M4 19V5"/><path d="M4 19h17"/><path d="M8 16v-5M13 16V8M18 16v-9"/>',
    wallet:
      '<path d="M4 7h15a2 2 0 0 1 2 2v9H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h13"/><path d="M17 12h4v4h-4a2 2 0 0 1 0-4Z"/>',
    scale:
      '<path d="M12 3v18"/><path d="M8 21h8"/><path d="M5 7h14"/><path d="m5 7-2.5 5a2.9 2.9 0 0 0 5 0L5 7Z"/><path d="m19 7-2.5 5a2.9 2.9 0 0 0 5 0L19 7Z"/>',
    store: '<path d="M4 10h16l-1-5H5l-1 5Z"/><path d="M6 10v10h12V10"/><path d="M9 20v-6h6v6"/>',
    users:
      '<path d="M16 20v-2a4 4 0 0 0-8 0v2"/><circle cx="12" cy="8" r="4"/><path d="M20 20v-2a3 3 0 0 0-3-3"/><path d="M4 20v-2a3 3 0 0 1 3-3"/>',
    settings:
      '<path d="M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2m-5.7-3.7 1.4-1.4m8.6-8.6 1.4-1.4m0 11.4-1.4-1.4M7.7 7.7 6.3 6.3"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  }
  return paths[name ?? 'dashboard'] ?? paths.dashboard
}
