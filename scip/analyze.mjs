// M0 spike scratch: classify SCIP symbols by descriptor kind and measure
// how much of an index is actually graph-worthy. Answers "can monikers be
// node ids directly" with counts instead of opinion.
import { readFileSync } from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'

const { scip } = pkg

// A SCIP symbol is "<scheme> <manager> <package> <version> <descriptors>".
// The descriptor suffix encodes what the thing is; see the SCIP spec.
function classify(symbol) {
  if (symbol.startsWith('local ')) return 'local'
  const parts = symbol.split(' ')
  if (parts.length < 5) return 'malformed'
  const desc = parts.slice(4).join(' ')
  if (desc.endsWith('(') || /\(\w[^)]*\)$/.test(desc)) return 'parameter'
  if (desc.endsWith('().')) return 'method'
  if (desc.endsWith('#')) return 'type'
  if (desc.endsWith('.')) return 'term'
  if (desc.endsWith('/')) return 'namespace'
  if (desc.endsWith(':')) return 'meta'
  return 'other'
}

function packageOf(symbol) {
  const p = symbol.split(' ')
  return p.length >= 4 ? `${p[1]}:${p[2]}@${p[3]}` : '?'
}

const index = scip.Index.deserialize(readFileSync(process.argv[2]))
const localPkgs = new Set()
const defs = new Map()
const refKinds = {}
const refPkgs = {}
let occ = 0

for (const doc of index.documents) {
  for (const o of doc.occurrences) {
    if (!o.symbol) continue
    occ++
    const isDef = (o.symbol_roles & scip.SymbolRole.Definition) !== 0
    if (isDef) {
      localPkgs.add(packageOf(o.symbol))
      if (!defs.has(o.symbol)) defs.set(o.symbol, classify(o.symbol))
    }
  }
}
for (const doc of index.documents) {
  for (const o of doc.occurrences) {
    if (!o.symbol) continue
    const isDef = (o.symbol_roles & scip.SymbolRole.Definition) !== 0
    if (isDef || defs.has(o.symbol)) continue
    const k = classify(o.symbol)
    refKinds[k] = (refKinds[k] || 0) + 1
    const p = packageOf(o.symbol)
    if (k !== 'local') refPkgs[p] = (refPkgs[p] || 0) + 1
  }
}

const byKind = {}
for (const k of defs.values()) byKind[k] = (byKind[k] || 0) + 1

// What a module-level graph would actually take: namespaces, types, methods
// and top-level terms — never parameters, locals or meta.
const graphWorthy = ['namespace', 'type', 'method', 'term']
const keep = Object.entries(byKind)
  .filter(([k]) => graphWorthy.includes(k))
  .reduce((a, [, n]) => a + n, 0)

console.log(
  JSON.stringify(
    {
      file: process.argv[2].split('/').pop(),
      documents: index.documents.length,
      occurrences: occ,
      definitions_total: defs.size,
      definitions_by_kind: byKind,
      graph_worthy_definitions: keep,
      dropped_as_noise: defs.size - keep,
      local_packages: [...localPkgs],
      external_symbols_declared: index.external_symbols?.length ?? 0,
      unresolved_reference_kinds: refKinds,
      top_referenced_packages: Object.entries(refPkgs)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8),
    },
    null,
    2
  )
)
