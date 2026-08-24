/**
 * V2.M7 spike: what does `rust-analyzer scip` actually give us? (ADR-040
 * evidence)
 *
 * Kept on the ADR-027 convention — the spike scripts stay in the tree as
 * the reproducible evidence behind an ADR's numbers. `analyze.mjs` did
 * this for scip-python, `spike-ts.mjs` for the TypeScript staging table,
 * `spike-go.mjs` for ADR-037's syntax_kind finding.
 *
 * Three questions, in the order they decide M7's shape:
 *
 * 1. **Does rust-analyzer populate `syntax_kind`?** scip-python: 0 of
 *    8,575. scip-go: 0 of 18,682. ADR-037 predicted the third indexer
 *    would match; this is the measurement. If it does not populate it,
 *    the mandatory syntax provider (§3.7 step 2) is confirmed a third
 *    time. If it *does*, that is worth knowing loudly — it would be the
 *    first indexer that can tell a call from a mention.
 * 2. **What is the moniker version field?** scip-python and scip-go both
 *    default it to something commit-varying, which is why
 *    `--project-version` / `--module-version` are always pinned
 *    (Decision 1). rust-analyzer has no such flag, so whatever it emits
 *    is what we live with — measured here rather than assumed.
 * 3. **Do document paths stay inside the repo?** scip-go emits documents
 *    for the Go build cache (`../../.cache/go-build/…`), which is why
 *    `insideRepo` exists. Does rust-analyzer do the same for
 *    `~/.cargo/registry` or the sysroot?
 *
 * Usage: node spike-rust.mjs <index.scip>
 */

import { readFileSync } from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'
import { classify, insideRepo } from './index.mjs'

const { scip } = pkg

const path = process.argv[2]
if (!path) {
  process.stderr.write('usage: spike-rust.mjs <index.scip>\n')
  process.exit(2)
}

const index = scip.Index.deserialize(readFileSync(path))

const syntaxKinds = new Map()
const roles = new Map()
const descriptorKinds = new Map()
const versions = new Map()
const packages = new Map()
const monikerSamples = { local: [], stdlib: [], thirdParty: [] }
const outsideDocs = []
let occurrences = 0
let definitions = 0
let documents = 0

for (const doc of index.documents) {
  documents += 1
  if (!insideRepo(doc.relative_path)) outsideDocs.push(doc.relative_path)
  for (const occ of doc.occurrences) {
    occurrences += 1

    const kind = occ.syntax_kind ?? 0
    syntaxKinds.set(kind, (syntaxKinds.get(kind) ?? 0) + 1)

    const role = occ.symbol_roles ?? 0
    roles.set(role, (roles.get(role) ?? 0) + 1)
    if (role & 1) definitions += 1

    const symbol = occ.symbol ?? ''
    descriptorKinds.set(
      classify(symbol),
      (descriptorKinds.get(classify(symbol)) ?? 0) + 1,
    )

    // `<scheme> <manager> <package> <version> <descriptors>` — the version
    // field is question 2, the package field feeds SELF_PACKAGES.
    const parts = symbol.split(' ')
    if (parts.length >= 5) {
      versions.set(parts[3], (versions.get(parts[3]) ?? 0) + 1)
      packages.set(parts[2], (packages.get(parts[2]) ?? 0) + 1)
    }

    const isStd = / (std|core|alloc|proc_macro) /.test(symbol)
    if (symbol.includes('example_project_structure') || symbol.includes('mylib')) {
      if (monikerSamples.local.length < 6) monikerSamples.local.push(symbol)
    } else if (isStd) {
      if (monikerSamples.stdlib.length < 4) monikerSamples.stdlib.push(symbol)
    } else if (symbol && !symbol.startsWith('local ')) {
      if (monikerSamples.thirdParty.length < 4) monikerSamples.thirdParty.push(symbol)
    }
  }
}

const defKinds = new Map()
let defTotal = 0
for (const doc of index.documents) {
  for (const occ of doc.occurrences) {
    if (!((occ.symbol_roles ?? 0) & 1)) continue
    defTotal += 1
    const kind = classify(occ.symbol ?? '')
    defKinds.set(kind, (defKinds.get(kind) ?? 0) + 1)
  }
}

const pct = (n) => `${((n / occurrences) * 100).toFixed(1)}%`

console.log(`documents:   ${documents}`)
console.log(`  outside repo (the scip-go build-cache question): ${outsideDocs.length}`)
for (const p of outsideDocs.slice(0, 5)) console.log(`    ${p}`)
console.log(`occurrences: ${occurrences}`)
console.log(`definitions: ${definitions} (${pct(definitions)})`)
console.log(`\nsyntax_kind histogram (0 = unset, the C-6 question):`)
for (const [kind, count] of [...syntaxKinds].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(kind).padStart(3)}: ${String(count).padStart(6)}  ${pct(count)}`)
}
console.log(`\nmoniker version field histogram (Decision 1 — is it commit-varying?):`)
for (const [v, count] of [...versions].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(v).padEnd(20)}: ${String(count).padStart(6)}`)
}
console.log(`\npackage field histogram (feeds SELF_PACKAGES):`)
for (const [p, count] of [...packages].sort((a, b) => b[1] - a[1]).slice(0, 12)) {
  console.log(`  ${String(p).padEnd(28)}: ${String(count).padStart(6)}`)
}
console.log(`\ndescriptor classification, all occurrences:`)
for (const [kind, count] of [...descriptorKinds].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${kind.padEnd(12)}: ${String(count).padStart(6)}  ${pct(count)}`)
}
console.log(
  `\ndescriptor classification, DEFINITIONS only ` +
    `(comparable to ADR-027's ~14% for scip-python):`,
)
for (const [kind, count] of [...defKinds].sort((a, b) => b[1] - a[1])) {
  const share = `${((count / defTotal) * 100).toFixed(1)}%`
  console.log(`  ${kind.padEnd(12)}: ${String(count).padStart(6)}  ${share}`)
}
const graphWorthy = [...defKinds]
  .filter(([kind]) => kind !== 'local')
  .reduce((sum, [, count]) => sum + count, 0)
console.log(
  `  → graph-worthy: ${graphWorthy}/${defTotal} ` +
    `(${((graphWorthy / defTotal) * 100).toFixed(1)}%)`,
)
console.log(`\nmoniker samples:`)
for (const [group, samples] of Object.entries(monikerSamples)) {
  console.log(`  ${group}:`)
  for (const sample of samples) console.log(`    ${sample}`)
}
