/**
 * Java spike (J.M0, ADR-096 evidence): what does `scip-java index` give us?
 *
 * On the ADR-027 convention — the spike scripts stay in the tree as the
 * reproducible evidence behind an ADR's numbers (`analyze.mjs`,
 * `spike-ts.mjs`, `spike-go.mjs`, `spike-rust.mjs`).
 *
 * Five questions, in the order they decide the Java milestones:
 *
 * 1. **`syntax_kind`** — populated? Four indexers so far: 0 for 0 of every
 *    occurrence (C-6). If scip-java also leaves it unset, lane A
 *    (`javasource.py`) is mandatory a fourth time.
 * 2. **The moniker version field** — scip-java's Maven-coordinate scheme
 *    puts the artifact version there; is it commit-varying or the
 *    build's own? (Decision 1, ADR-027.)
 * 3. **Overloads** — one terminal name, several declarations: what does
 *    the descriptor look like (`foo().` vs `foo(+1).`)? Lane agreement
 *    must compare on the resolved definition, not on the name.
 * 4. **Nested and anonymous classes** — `Outer#Inner#` shapes, and what an
 *    anonymous class's members are scoped under.
 * 5. **Document paths** — inside the repo only? Generated sources
 *    (annotation processors) show up where?
 *
 * Usage: node spike-java.mjs <index.scip>
 */

import { readFileSync } from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'
import { classify, insideRepo, terminalName } from './index.mjs'

const { scip } = pkg

const path = process.argv[2]
if (!path) {
  process.stderr.write('usage: spike-java.mjs <index.scip>\n')
  process.exit(2)
}

const index = scip.Index.deserialize(readFileSync(path))

const syntaxKinds = new Map()
const descriptorKinds = new Map()
const versions = new Map()
const packages = new Map()
const schemes = new Map()
const outsideDocs = []
const generatedDocs = []
const overloadSamples = []
const nestedSamples = []
const anonSamples = []
const localSamples = []
const stdlibSamples = []
let occurrences = 0
let definitions = 0
let documents = 0

// terminal name -> set of distinct method monikers, to see overload shape
const byName = new Map()

for (const doc of index.documents) {
  documents += 1
  const rel = doc.relative_path ?? ''
  if (!insideRepo(rel)) outsideDocs.push(rel)
  if (/\/(target|build)\/generated/.test(rel) || /generated/.test(rel)) generatedDocs.push(rel)
  for (const occ of doc.occurrences) {
    occurrences += 1
    const kind = occ.syntax_kind ?? 0
    syntaxKinds.set(kind, (syntaxKinds.get(kind) ?? 0) + 1)
    if ((occ.symbol_roles ?? 0) & 1) definitions += 1

    const symbol = occ.symbol ?? ''
    const cls = classify(symbol)
    descriptorKinds.set(cls, (descriptorKinds.get(cls) ?? 0) + 1)
    const parts = symbol.split(' ')
    if (parts.length >= 5) {
      schemes.set(parts[0], (schemes.get(parts[0]) ?? 0) + 1)
      versions.set(parts[3], (versions.get(parts[3]) ?? 0) + 1)
      packages.set(parts[2], (packages.get(parts[2]) ?? 0) + 1)
      const desc = parts.slice(4).join(' ')
      if (cls === 'method' && ((occ.symbol_roles ?? 0) & 1)) {
        const name = terminalName(symbol)
        if (!byName.has(name)) byName.set(name, new Set())
        byName.get(name).add(symbol)
      }
      if (/#[^#/]+#[^#/]+#/.test(desc) && nestedSamples.length < 6 && ((occ.symbol_roles ?? 0) & 1)) nestedSamples.push(symbol)
      if (/#\d+#|\$\d+|anon/.test(desc) && anonSamples.length < 6) anonSamples.push(symbol)
      if (parts[2] === 'jdk' || /^java\./.test(desc)) { if (stdlibSamples.length < 4) stdlibSamples.push(symbol) }
      else if (localSamples.length < 8 && ((occ.symbol_roles ?? 0) & 1) && cls !== 'local') localSamples.push(symbol)
    }
  }
}

for (const [name, set] of byName) {
  if (set.size > 1 && overloadSamples.length < 5) overloadSamples.push([name, [...set]])
}

const pct = (n) => `${((n / occurrences) * 100).toFixed(1)}%`
console.log(`documents:   ${documents}`)
console.log(`  outside repo: ${outsideDocs.length}`)
for (const p of outsideDocs.slice(0, 5)) console.log(`    ${p}`)
console.log(`  generated-looking paths: ${generatedDocs.length}`)
for (const p of generatedDocs.slice(0, 5)) console.log(`    ${p}`)
console.log(`occurrences: ${occurrences}`)
console.log(`definitions: ${definitions} (${pct(definitions)})`)
console.log(`\nsyntax_kind histogram (0 = unset, the C-6 question):`)
for (const [kind, count] of [...syntaxKinds].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(kind).padStart(3)}: ${String(count).padStart(7)}  ${pct(count)}`)
}
console.log(`\nscheme field:`)
for (const [s, count] of schemes) console.log(`  ${s.padEnd(16)}: ${count}`)
console.log(`\nmoniker version field histogram (Decision 1):`)
for (const [v, count] of [...versions].sort((a, b) => b[1] - a[1]).slice(0, 10)) {
  console.log(`  ${String(v).padEnd(24)}: ${String(count).padStart(7)}`)
}
console.log(`\npackage field histogram (feeds SELF_PACKAGES):`)
for (const [p, count] of [...packages].sort((a, b) => b[1] - a[1]).slice(0, 12)) {
  console.log(`  ${String(p).padEnd(40)}: ${String(count).padStart(7)}`)
}
console.log(`\ndescriptor classification, all occurrences:`)
for (const [kind, count] of [...descriptorKinds].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${kind.padEnd(12)}: ${String(count).padStart(7)}  ${pct(count)}`)
}
console.log(`\noverload shapes (name → distinct method definition monikers):`)
for (const [name, syms] of overloadSamples) {
  console.log(`  ${name}: ${syms.length}`)
  for (const s of syms.slice(0, 4)) console.log(`    ${s}`)
}
console.log(`\nnested-class definition samples:`)
for (const s of nestedSamples) console.log(`  ${s}`)
console.log(`\nanonymous-class-looking samples:`)
for (const s of anonSamples) console.log(`  ${s}`)
console.log(`\nlocal definition samples:`)
for (const s of localSamples) console.log(`  ${s}`)
console.log(`\nstdlib samples:`)
for (const s of stdlibSamples) console.log(`  ${s}`)
