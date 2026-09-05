import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'

import { describe, expect, it } from 'vitest'

/**
 * Decision 21, enforced across all three apps: **every image in a list is a
 * thumbnail**.
 *
 * `AuthFileImage` defaults to `sm`, so the rule only breaks where someone types
 * a `size` — and it breaks silently, because a 1.5 MB original and a 5 KB
 * rendition look identical on a development machine. The regression that
 * prompted this went unnoticed for exactly that reason.
 *
 * So the inventory of every image that asks for anything other than `sm` is
 * written out here. Adding one is fine; adding one without saying why, in a
 * screen that draws it 40 px wide, is not.
 */

const SRC = join(process.cwd(), 'src')

type Usage = { file: string; size: string; upgradeTo: string | null }

function vueFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return entry === '__tests__' ? [] : vueFiles(full)
    return full.endsWith('.vue') ? [full] : []
  })
}

function usages(): Usage[] {
  return vueFiles(SRC).flatMap((file) => {
    const source = readFileSync(file, 'utf8')
    return [...source.matchAll(/<AuthFileImage\b[\s\S]*?\/>/g)].map((match) => ({
      file: file.slice(SRC.length + 1),
      // No `size` at all is the component's default, which is `sm`.
      size: /\bsize="([^"]+)"/.exec(match[0])?.[1] ?? 'sm',
      upgradeTo: /\bupgrade-to="([^"]+)"/.exec(match[0])?.[1] ?? null,
    }))
  })
}

describe('image renditions', () => {
  it('finds the image component in every app, so this check is not vacuous', () => {
    const files = new Set(usages().map((usage) => usage.file))

    expect(usages().length).toBeGreaterThan(10)
    expect([...files].some((file) => file.startsWith('apps/client/'))).toBe(true)
    expect([...files].some((file) => file.includes('Workshop'))).toBe(true)
    expect([...files].some((file) => file.includes('Admin'))).toBe(true)
  })

  it('draws every list, grid, row and swatch from the small rendition', () => {
    const notSmall = usages()
      .filter((usage) => usage.size !== 'sm')
      .map((usage) => `${usage.file} → ${usage.size}`)
      .sort()

    expect(notSmall).toEqual([
      // The upload preview: shown at form width, and the only image on screen.
      'shared/components/ImageUploadField.vue → md',
      // The counter sheet, which is printed — `sm` would be visible on paper.
      'shared/views/WorkshopLinkPrintView.vue → md',
    ])
  })

  it('fetches the original only where the whole picture is the point', () => {
    const fullSize = usages()
      .filter((usage) => usage.size === 'original' || usage.upgradeTo === 'original')
      .map((usage) => `${usage.file} → ${usage.size} then ${usage.upgradeTo ?? 'nothing'}`)
      .sort()

    // Both are lightboxes, and both open on the rendition the row behind them
    // already drew: it is in the browser cache, so the picture is there in the
    // frame the modal opens in, and the original arrives behind it.
    expect(fullSize).toEqual([
      'apps/client/views/ClientWorkshopCatalogView.vue → sm then original',
      'shared/components/CuttingDecorThumb.vue → sm then original',
    ])
  })
})
