/**
 * V2.M5 spike: what does `scip-go` actually give us? (ADR-037 evidence)
 *
 * Kept on the ADR-027 convention — the spike scripts stay in the tree as
 * the reproducible evidence behind an ADR's numbers, not as production
 * code. `analyze.mjs` did this for scip-python, `spike-ts.mjs` for the
 * TypeScript staging table.
 *
 * The one question that decides M5's shape: **does scip-go populate
 * `syntax_kind`?** scip-python populates it for 0 of 8,575 occurrences
 * (C-6), which is why lane A keeps call-site detection and why a language
 * with no lane A grammar cannot tell a call from a type annotation. If
 * scip-go populates it, Go can have a real call graph from lane B alone
 * and §3.7's "lane A is optional" holds literally. If it does not, the
 * checklist is wrong and M5 has to say so.
 *
 * Usage: node spike-go.mjs <index.scip>
 */

import { readFileSync } from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'
import { classify } from './index.mjs'

const { scip } = pkg

const path = process.argv[2]
if (!path) {
  process.stderr.write('usage: spike-go.mjs <index.scip>\n')
  process.exit(2)
}

const index = scip.Index.deserialize(readFileSync(path))

const syntaxKinds = new Map()
const roles = new Map()
const descriptorKinds = new Map()
const monikerSamples = { local: [], stdlib: [], thirdParty: [] }
let occurrences = 0
let definitions = 0
let documents = 0

for (const doc of index.documents) {
  documents += 1
  for (const occ of doc.occurrences) {
    occurrences += 1

    const kind = occ.syntax_kind ?? 0
    syntaxKinds.set(kind, (syntaxKinds.get(kind) ?? 0) + 1)

    const role = occ.symbol_roles ?? 0
    roles.set(role, (roles.get(role) ?? 0) + 1)
    // symbol_roles bit 0 = Definition
    if (role & 1) definitions += 1

    const symbol = occ.symbol ?? ''
    descriptorKinds.set(
      classify(symbol),
      (descriptorKinds.get(classify(symbol)) ?? 0) + 1,
    )

    if (symbol.includes('majax7714/Hobbes') && monikerSamples.local.length < 6) {
      monikerSamples.local.push(symbol)
    } else if (
      symbol.includes('github.com/golang/go/src') &&
      monikerSamples.stdlib.length < 4
    ) {
      monikerSamples.stdlib.push(symbol)
    } else if (
      symbol.startsWith('scip-go gomod ') &&
      !symbol.includes('majax7714') &&
      !symbol.includes('github.com/golang/go/src') &&
      monikerSamples.thirdParty.length < 4
    ) {
      monikerSamples.thirdParty.push(symbol)
    }
  }
}

// Definitions only, so the number is comparable with ADR-027's "~14% of
// SCIP definitions are graph-worthy" for scip-python.
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
console.log(`occurrences: ${occurrences}`)
console.log(`definitions: ${definitions} (${pct(definitions)})`)
console.log(`\nsyntax_kind histogram (0 = unset, the C-6 question):`)
for (const [kind, count] of [...syntaxKinds].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(kind).padStart(3)}: ${String(count).padStart(6)}  ${pct(count)}`)
}
console.log(`\nsymbol_roles histogram:`)
for (const [role, count] of [...roles].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(role).padStart(4)}: ${String(count).padStart(6)}  ${pct(count)}`)
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
