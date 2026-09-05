// Two checks over the message catalog, both invisible to `vue-tsc`:
//
// 1. Every literal key passed to `t()` / `$t()` exists. `vue-tsc` already
//    checks keys it can see as literals in `.ts`, but a key spelled inside a
//    template expression is a plain string to it, and a key built from a
//    variable (`t(item.labelKey)`) is invisible to both. This walks the source
//    instead, so a typo surfaces here rather than as the key path rendering
//    itself into the UI.
//
// 2. Every namespace a role can reach is a namespace that role ships. Each SPA
//    installs its own slice of the catalog (`src/shared/i18n/catalogs/`), so a
//    key that resolves in the catalog can still render as its own path in one
//    app and not another. The role's module graph — its entry, its routes, the
//    shared views/components/stores they pull in — is walked from
//    `src/apps/<role>/main.ts`, and the namespaces it *ships* are read off the
//    same graph: the `locales/uz/*.json` files it statically imports. So the
//    catalog module and the screens can never drift apart quietly.
//
// Run: node scripts/check-i18n-keys.mjs

import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dirname, '..')
const SRC = path.join(ROOT, 'src')
const CATALOG = path.join(SRC, 'shared/i18n/locales/uz')
const FULL_CATALOG_MODULES = [
  path.join(CATALOG, 'index.ts'),
  path.join(SRC, 'shared/i18n/locales/ru/index.ts'),
]
const ROLES = ['client', 'workshop', 'admin']

// ---- catalog ---------------------------------------------------------------

function namespaces() {
  return fs
    .readdirSync(CATALOG)
    .filter((file) => file.endsWith('.json'))
    .map((file) => path.basename(file, '.json'))
    .sort()
}

/** Both leaves (`a.b.c`, a message) and branches (`a.b`, a section): a
 *  computed key like `` t(`cutting.panelType.${type}`) `` names a branch, and
 *  its namespace has to ship even though no leaf is spelled out. */
function flatten(node, prefix, keys, sections) {
  for (const [key, value] of Object.entries(node)) {
    const keyPath = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'string') keys.add(keyPath)
    else if (value && typeof value === 'object') {
      sections.add(keyPath)
      flatten(value, keyPath, keys, sections)
    }
  }
}

const NAMESPACES = namespaces()
const keys = new Set()
const sections = new Set(NAMESPACES)
for (const namespace of NAMESPACES) {
  const file = path.join(CATALOG, `${namespace}.json`)
  flatten(JSON.parse(fs.readFileSync(file, 'utf8')), namespace, keys, sections)
}

// ---- source ----------------------------------------------------------------

/** Blanks whole-line comments so a `t('a.b.c')` written in prose to explain the
 *  helper is not read as a call. Line numbers survive because only the content
 *  is dropped, never the line. */
function withoutCommentLines(source) {
  return source
    .split('\n')
    .map((line) => (/^\s*(\/\/|\/\*|\*)/.test(line) ? '' : line))
    .join('\n')
}

function sourceFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) sourceFiles(full, out)
    else if (/\.(vue|ts)$/.test(entry.name)) out.push(full)
  }
  return out
}

const read = (file) => withoutCommentLines(fs.readFileSync(file, 'utf8'))

// ---- 1: every literal key resolves ----------------------------------------

// `t('a.b.c')`, `$t("a.b.c")` and the `roleMessageKey`-style prefixes are all
// plain literals at the call site; anything computed is skipped by design.
const CALL = /\$?\bt\(\s*(['"])([A-Za-z][A-Za-z0-9_.]*)\1/g

const problems = []
for (const file of sourceFiles(SRC)) {
  const source = read(file)
  for (const match of source.matchAll(CALL)) {
    const key = match[2]
    // A namespace-less token is something else called `t` (a local helper, a
    // test double); catalog keys always carry a dot.
    if (!key.includes('.')) continue
    if (keys.has(key)) continue
    const line = source.slice(0, match.index).split('\n').length
    problems.push(`${path.relative(ROOT, file)}:${line}  ${key}`)
  }
}

if (problems.length) {
  console.error(`${problems.length} message key(s) are used but not defined in the uz catalog:\n`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(1)
}

// ---- 2: every namespace a role reaches is one it ships ---------------------

const RESOLVE_EXTENSIONS = ['', '.ts', '.vue', '.json', '/index.ts']

function resolveImport(specifier, importer) {
  let base
  if (specifier.startsWith('@/')) base = path.join(SRC, specifier.slice(2))
  else if (specifier.startsWith('.')) base = path.resolve(path.dirname(importer), specifier)
  else return null // a package, not our source
  for (const extension of RESOLVE_EXTENSIONS) {
    const candidate = base + extension
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate
  }
  return null
}

// Static imports, re-exports and dynamic `import()`. `import type` / `export
// type` are deliberately not matched: the compiler erases them, so the schema
// (which type-imports all fourteen namespaces) must not make every role look
// like it ships all fourteen.
const IMPORTS = new RegExp(
  [
    String.raw`(?:^|[\s;}])import\s+(?!type\s)(?:[^'"()]*?\sfrom\s*)?['"]([^'"]+)['"]`,
    String.raw`(?:^|[\s;}])export\s+(?!type\s)[^'"()]*?\sfrom\s*['"]([^'"]+)['"]`,
    String.raw`\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)`,
  ].join('|'),
  'g',
)

/** Every module a role's entry can reach, lazy routes included. */
function moduleGraph(entry) {
  const seen = new Set()
  const queue = [entry]
  while (queue.length) {
    const file = queue.pop()
    if (seen.has(file)) continue
    seen.add(file)
    if (!/\.(ts|vue)$/.test(file)) continue
    for (const match of read(file).matchAll(IMPORTS)) {
      const target = resolveImport(match[1] ?? match[2] ?? match[3], file)
      if (target && !seen.has(target)) queue.push(target)
    }
  }
  return seen
}

const NS_ALTERNATION = NAMESPACES.join('|')
// Any string literal that names a catalog key. Not just `t(…)` calls: a route's
// `meta.titleKey`, a nav item's `labelKey` and the status→key maps are all bare
// literals handed to `t` somewhere else, and they bind their namespace to the
// role just the same.
const KEY_LITERAL = new RegExp(`['"\`]((?:${NS_ALTERNATION})\\.[A-Za-z0-9_.]*)`, 'g')
// `` `cutting.panelType.${type}` `` — the interpolation hides the leaf, so the
// section in front of it is what has to resolve.
const KEY_TEMPLATE = new RegExp('`((?:' + NS_ALTERNATION + ')\\.[A-Za-z0-9_.]*)\\$\\{', 'g')

const gaps = []
const shipped = {}
for (const role of ROLES) {
  const graph = moduleGraph(path.join(SRC, `apps/${role}/main.ts`))

  const full = FULL_CATALOG_MODULES.filter((file) => graph.has(file))
  for (const file of full) {
    gaps.push(
      `${role}: reaches ${path.relative(ROOT, file)} — the all-namespaces catalog. ` +
        `Import the namespaces the role needs from shared/i18n/catalogs/${role}.ts instead.`,
    )
  }

  shipped[role] = new Set(
    [...graph]
      .filter((file) => file.startsWith(CATALOG + path.sep) && file.endsWith('.json'))
      .map((file) => path.basename(file, '.json')),
  )

  for (const file of graph) {
    if (!/\.(ts|vue)$/.test(file)) continue
    if (file.includes(`${path.sep}__tests__${path.sep}`)) continue
    const source = read(file)
    const referenced = new Map()
    for (const match of source.matchAll(KEY_LITERAL)) {
      if (keys.has(match[1])) referenced.set(match[1], match.index)
    }
    for (const match of source.matchAll(KEY_TEMPLATE)) {
      const section = match[1].replace(/\.$/, '')
      if (sections.has(section)) referenced.set(`${match[1]}\${…}`, match.index)
    }
    for (const [key, index] of referenced) {
      const namespace = key.split('.')[0]
      if (shipped[role].has(namespace)) continue
      const line = source.slice(0, index).split('\n').length
      gaps.push(
        `${role}: ${path.relative(ROOT, file)}:${line}  ${key} — ` +
          `'${namespace}' is not in shared/i18n/catalogs/${role}.ts`,
      )
    }
  }
}

if (gaps.length) {
  console.error(
    `${gaps.length} namespace gap(s): a role renders copy its catalog does not ship,\n` +
      `so the key would print its own path in that app.\n`,
  )
  for (const gap of gaps) console.error(`  ${gap}`)
  process.exit(1)
}

const perRole = ROLES.map((role) => `${role} ${shipped[role].size}`).join(' · ')
console.log(
  `i18n keys OK — ${keys.size} messages in ${NAMESPACES.length} namespaces, ` +
    `every literal t() call resolves.\n` +
    `Namespaces shipped per role: ${perRole}.`,
)
