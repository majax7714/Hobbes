// pinned.py's harness for merman's flowchart layout and routing: random flowcharts, each summarized by the tests'
// own `layout-summary.ts` (each node's box, each frame's, each route's points, the canvas), one key per item, or as
// an error where the layout shows a known wrong kind: nodes overlapping, a node outside its own frame, or one inside
// a frame it is not in. An input's `%%opts` line (a comment to the parser) carries the layout options. It loads the
// package from `cli.ts`'s root (the planted copy).
import { type Box, inside, overlap } from "./boxes"
import { packageRoot, runHarness } from "./cli"

const { layoutFlowchartDiagram } = await import(`${packageRoot}/src/flowchart/layout.ts`)
const { parseMermaidFlowchartDiagram } = await import(`${packageRoot}/src/flowchart/parser.ts`)
const { summary } = await import(`${packageRoot}/test/flowchart/layout-summary.ts`)

const IDS = ["A", "B", "C", "D", "E", "F"]
const SHAPES = ["", "", "", "[x]", "[wwwwwwwwww]", "{d}", "[(db)]", "[[s]]", "[a<br>b]"]
const ARROWS = ["-->", "---", "-.->", "==>", "~~~"]
const LABELS = ["l", "lllllll", "ll<br>l", "a long label here"]

export function generate(rand: () => number): string {
  const pick = <T>(items: readonly T[]) => items[Math.floor(rand() * items.length)]!
  const chance = (p: number) => rand() < p
  const options: Record<string, unknown> = {}
  if (chance(0.25)) options.compact = true
  if (chance(0.2)) options.layoutMaxWidth = 15 + Math.floor(rand() * 50)
  if (chance(0.15)) options.minNodeGap = 1 + Math.floor(rand() * 8)
  const lines = [`%%opts ${JSON.stringify(options)}`, `flowchart ${pick(["TD", "LR", "BT", "RL", "TD", "LR"])}`]
  const declared = new Set<string>()
  const node = () => {
    const id = pick(IDS)
    if (declared.has(id)) return id
    declared.add(id)
    return `${id}${pick(SHAPES)}`
  }
  for (let g = Math.floor(rand() * 3); g > 0; g--) {
    lines.push(`subgraph G${g}${chance(0.3) ? ` [${pick(["t", "tttttttttttt", "tt<br>t"])}]` : ""}`)
    if (chance(0.3)) lines.push(`direction ${pick(["TB", "LR", "RL", "BT"])}`)
    // A node is listed in one frame at most, as a member, so where it belongs is never in doubt.
    const member = () => {
      const free = IDS.filter((id) => !declared.has(id))
      if (free.length === 0) return []
      const id = pick(free)
      declared.add(id)
      return [`${id}${pick(SHAPES)}`]
    }
    for (let n = 1 + Math.floor(rand() * 2); n > 0; n--) lines.push(...member())
    if (chance(0.25)) lines.push(`subgraph H${g}`, ...(chance(0.7) ? member() : []), "end")
    lines.push("end")
  }
  for (let e = 1 + Math.floor(rand() * 6); e > 0; e--) {
    const label = chance(0.3) ? `|${pick(LABELS)}|` : ""
    const from = node()
    lines.push(`${from} ${pick(ARROWS)}${label} ${chance(0.15) ? from.replace(/[[{(].*$/, "") : node()}`)
  }
  return lines.join("\n")
}


/** The known wrong kinds a flowchart layout shows, sorted. */
export function flowchartDefects(layout: {
  diagram: { subgraphs?: { id: string; parentId?: string; nodeIds: string[] }[] }
  bounds: Map<string, Box>
  subgraphBounds: Map<string, Box>
}): string[] {
  const found = new Set<string>()
  const subgraphs = new Map((layout.diagram.subgraphs ?? []).map((subgraph) => [subgraph.id, subgraph]))
  const owner = new Map<string, string>()
  for (const subgraph of subgraphs.values()) for (const id of subgraph.nodeIds) owner.set(id, subgraph.id)
  const within = (id: string, frame: string) => {
    for (let parent = owner.get(id); parent; parent = subgraphs.get(parent)?.parentId) if (parent === frame) return true
    return false
  }
  const nodes = [...layout.bounds.values()]
  nodes.forEach((a, index) => {
    for (const b of nodes.slice(index + 1)) if (overlap(a, b)) found.add("nodes overlap")
  })
  for (const box of nodes) {
    const own = owner.get(box.id)
    const frame = own ? layout.subgraphBounds.get(own) : undefined
    if (frame && !inside(box, frame)) found.add("outside its frame")
    for (const [id, other] of layout.subgraphBounds) if (!within(box.id, id) && overlap(box, other)) found.add("in another frame")
  }
  return [...found].sort()
}

export function summarize(input: string): Record<string, unknown> {
  try {
    const options = JSON.parse(input.match(/^%%opts (.*)$/m)?.[1] ?? "{}")
    const layout = layoutFlowchartDiagram(parseMermaidFlowchartDiagram(input), options)
    const defects = flowchartDefects(layout)
    if (defects.length > 0) return { error: `defect: ${defects.join(", ")}` }
    const out: Record<string, unknown> = {}
    for (const part of (summary(layout) as string).split("; ")) {
      const key = /^\d+x\d+ /.test(part) ? "size" : part.split(" ")[0]!
      let unique = key
      for (let n = 1; unique in out; n++) unique = `${key}#${n}`
      out[unique] = part
    }
    return out
  } catch (error) {
    return { error: String(error) }
  }
}

if (import.meta.main) await runHarness(generate, summarize)
