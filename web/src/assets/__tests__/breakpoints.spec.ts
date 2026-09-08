import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { compile } from 'tailwindcss'

/**
 * Tailwind orders the responsive variants in the emitted cascade by comparing the
 * `--breakpoint-*` values — and it can only compare them when they share a unit. A mixed
 * set (px overrides layered on Tailwind's rem defaults) makes the comparison fail and the
 * variants fall back to declaration order, which silently puts `lg` before `sm` in the
 * stylesheet: on `sm:grid-cols-2 lg:grid-cols-3` the `sm` rule then wins at ≥ lg and the
 * grid never reaches three columns. Nothing else in the gate can see that.
 *
 * These tests compile the real `main.css` and assert the emitted order, so the invariant
 * survives a future tier being added in the wrong unit.
 */

// Vitest's `root` is `web/`, and `import.meta.url` is not a file: URL under jsdom.
const webRoot = process.cwd()
const assetsDir = path.join(webRoot, 'src/assets')
const TIERS = ['sm', 'md', 'lg', 'xl', '2xl'] as const

async function compileMainCss(candidates: string[]): Promise<string> {
  const input = await readFile(path.join(assetsDir, 'main.css'), 'utf8')
  const compiler = await compile(input, {
    base: assetsDir,
    async loadStylesheet(id, base) {
      const resolved =
        id === 'tailwindcss'
          ? path.join(webRoot, 'node_modules/tailwindcss/index.css')
          : path.resolve(base, id)
      return {
        path: resolved,
        base: path.dirname(resolved),
        content: await readFile(resolved, 'utf8'),
      }
    },
  })
  return compiler.build(candidates)
}

describe('breakpoint tokens', () => {
  it('emits the responsive variants in ascending min-width order', async () => {
    // One property, one value per tier: whichever rule the browser sees last wins, so the
    // emitted order IS the resolution order.
    const css = await compileMainCss(TIERS.map((tier) => `${tier}:grid-cols-3`))

    const emitted = TIERS.map((tier) => {
      // Tailwind escapes a class that starts with a digit as `.\32 xl\:…`.
      const selector = tier === '2xl' ? String.raw`.\32 xl\:grid-cols-3` : `.${tier}\\:grid-cols-3`
      const at = css.indexOf(selector)
      expect(at, `${tier}:grid-cols-3 was not emitted`).toBeGreaterThan(-1)
      return { tier, at }
    })

    expect(emitted.map((e) => e.tier)).toEqual(
      [...emitted].sort((a, b) => a.at - b.at).map((e) => e.tier),
    )
  })

  it('declares the whole breakpoint scale in one unit, ascending', async () => {
    const css = await compileMainCss(TIERS.map((tier) => `${tier}:grid-cols-3`))
    const widths = [...css.matchAll(/@media \(width >= ([\d.]+)(px|rem)\)/g)]

    expect(widths).toHaveLength(TIERS.length)
    expect(new Set(widths.map((m) => m[2])).size, 'breakpoints must share one unit').toBe(1)

    const values = widths.map((m) => Number(m[1]))
    expect(values).toEqual([...values].sort((a, b) => a - b))
    expect(values).toEqual([640, 768, 922, 1152, 1382])
  })
})
