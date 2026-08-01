// Every literal key passed to `t()` / `$t()` must exist in the uz catalog.
//
// `vue-tsc` already checks keys it can see as literals in `.ts`, but a key
// spelled inside a template expression is a plain string to it, and a key built
// from a variable (`t(item.labelKey)`) is invisible to both. This walks the
// source instead, so a typo surfaces here rather than as the key path rendering
// itself into the UI.
//
// Run: node scripts/check-i18n-keys.mjs

import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dirname, '..')
const CATALOG = path.join(ROOT, 'src/shared/i18n/locales/uz')

function loadCatalog() {
  const messages = {}
  for (const file of fs.readdirSync(CATALOG)) {
    if (!file.endsWith('.json')) continue
    messages[path.basename(file, '.json')] = JSON.parse(
      fs.readFileSync(path.join(CATALOG, file), 'utf8'),
    )
  }
  return messages
}

function flatten(node, prefix = '', out = new Set()) {
  for (const [key, value] of Object.entries(node)) {
    const keyPath = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'string') out.add(keyPath)
    else if (value && typeof value === 'object') flatten(value, keyPath, out)
  }
  return out
}

function sourceFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) sourceFiles(full, out)
    else if (/\.(vue|ts)$/.test(entry.name)) out.push(full)
  }
  return out
}

const known = flatten(loadCatalog())
// `t('a.b.c')`, `$t("a.b.c")` and the `roleMessageKey`-style prefixes are all
// plain literals at the call site; anything computed is skipped by design.
const CALL = /\$?\bt\(\s*(['"])([A-Za-z][A-Za-z0-9_.]*)\1/g

/** Blanks whole-line comments so a `t('a.b.c')` written in prose to explain the
 *  helper is not read as a call. Line numbers survive because only the content
 *  is dropped, never the line. */
function withoutCommentLines(source) {
  return source
    .split('\n')
    .map((line) => (/^\s*(\/\/|\/\*|\*)/.test(line) ? '' : line))
    .join('\n')
}

const problems = []
for (const file of sourceFiles(path.join(ROOT, 'src'))) {
  const source = withoutCommentLines(fs.readFileSync(file, 'utf8'))
  for (const match of source.matchAll(CALL)) {
    const key = match[2]
    // A namespace-less token is something else called `t` (a local helper, a
    // test double); catalog keys always carry a dot.
    if (!key.includes('.')) continue
    if (known.has(key)) continue
    const line = source.slice(0, match.index).split('\n').length
    problems.push(`${path.relative(ROOT, file)}:${line}  ${key}`)
  }
}

if (problems.length) {
  console.error(`${problems.length} message key(s) are used but not defined in the uz catalog:\n`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(1)
}

console.log(`i18n keys OK — ${known.size} messages defined, every literal t() call resolves.`)
