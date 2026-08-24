// M0 spike scratch: derive module-level edges from a SCIP index the way the
// v2 graph builder would, and diff them against lane A's module_edges from
// the current graph.json. This is the feasibility check — if the join can't
// reproduce lane A, the architecture's premise needs revisiting before M1.
import { readFileSync } from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'

const { scip } = pkg
const [, , scipPath, graphPath, prefix = '', extFilter = ''] = process.argv

const index = scip.Index.deserialize(readFileSync(scipPath))
const graph = JSON.parse(readFileSync(graphPath, 'utf8'))

// Where each symbol is defined: symbol -> document path.
const definedIn = new Map()
for (const doc of index.documents) {
  for (const o of doc.occurrences) {
    if (!o.symbol || o.symbol.startsWith('local ')) continue
    if ((o.symbol_roles & scip.SymbolRole.Definition) !== 0)
      if (!definedIn.has(o.symbol)) definedIn.set(o.symbol, doc.relative_path)
  }
}

// Reference in file A to a symbol defined in file B => A depends on B.
const scipEdges = new Set()
for (const doc of index.documents) {
  for (const o of doc.occurrences) {
    if (!o.symbol || o.symbol.startsWith('local ')) continue
    if ((o.symbol_roles & scip.SymbolRole.Definition) !== 0) continue
    const target = definedIn.get(o.symbol)
    if (!target || target === doc.relative_path) continue
    if (extFilter && !(doc.relative_path.endsWith(extFilter) && target.endsWith(extFilter))) continue
    scipEdges.add(`${prefix}${doc.relative_path} -> ${prefix}${target}`)
  }
}

// Lane A's edges, expressed as file pairs so the two are comparable at all:
// lane A keys nodes by dotted module id, SCIP by document path.
const pathOf = new Map()
for (const n of graph.nodes) if (n.path) pathOf.set(n.id, n.path)
const laneA = new Set()
for (const e of graph.module_edges) {
  if (e.type !== 'imports') continue
  const from = pathOf.get(e.from)
  const to = pathOf.get(e.to)
  if (!from || !to) continue // ext:/env: nodes have no path
  if (!from.startsWith(prefix) || !to.startsWith(prefix)) continue
  // An indexer only owns its own language, so comparing across the whole
  // repo scores scip-python on files it correctly never looked at.
  if (extFilter && !(from.endsWith(extFilter) && to.endsWith(extFilter))) continue
  laneA.add(`${from} -> ${to}`)
}

const inBoth = [...laneA].filter((e) => scipEdges.has(e))
const onlyLaneA = [...laneA].filter((e) => !scipEdges.has(e))
const onlyScip = [...scipEdges].filter((e) => !laneA.has(e))

console.log(
  JSON.stringify(
    {
      scip_file_edges: scipEdges.size,
      lane_a_file_edges: laneA.size,
      agree: inBoth.length,
      lane_a_only: onlyLaneA.length,
      scip_only: onlyScip.length,
      lane_a_recall:
        laneA.size ? +(inBoth.length / laneA.size).toFixed(3) : null,
      sample_lane_a_only: onlyLaneA.slice(0, 10),
      sample_scip_only: onlyScip.slice(0, 10),
    },
    null,
    2
  )
)
