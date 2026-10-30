import { expect, test } from "bun:test"
import type { FlowchartDiagramRenderOptions } from "../../src/flowchart/options"
import { parseMermaidFlowchartDiagram } from "../../src/flowchart/parser"
import { layoutFlowchartDiagram, normalizePositiveInt, visualLength } from "../../src/flowchart/layout"
import { summary } from "./layout-summary"

const parts = (source: string, options: FlowchartDiagramRenderOptions) => summary(layout(source, options)).split("; ")

function layout(source: string, options: FlowchartDiagramRenderOptions = {}) {
  return layoutFlowchartDiagram(parseMermaidFlowchartDiagram(source), options)
}

/** Each node's [left, top, width, height]. */
function boxes(source: string, options: FlowchartDiagramRenderOptions = {}) {
  const result = layout(source, options)
  return Object.fromEntries([...result.bounds].map(([id, b]) => [id, [b.left, b.top, b.width, b.height]]))
}

function frames(source: string, options: FlowchartDiagramRenderOptions = {}) {
  const result = layout(source, options)
  return Object.fromEntries(
    [...result.subgraphBounds].map(([id, b]) => [id, [b.left, b.top, b.width, b.height, b.labelSide]]),
  )
}

test("text is measured in cells, and an option is a positive whole number or its fallback", () => {
  expect([visualLength("abc"), visualLength("日本"), visualLength("")]).toEqual([3, 4, 0])
  expect([undefined, Number.NaN, Number.POSITIVE_INFINITY].map((value) => normalizePositiveInt(value, 7))).toEqual([7, 7, 7])
  expect([2.9, 0, -3, 1].map((value) => normalizePositiveInt(value, 7))).toEqual([2, 1, 1, 1])
})

test("each shape is sized around its label: a decision is odd-wide and at least five tall", () => {
  const result = layout("flowchart\nA[abc]\nB(abc)\nC[[abc]]\nD[(abc)]\nE{abc}\nF{ab}\nG[a<br>bcd]\nH{a<br>bcd}")
  const sizes = Object.fromEntries([...result.bounds].map(([id, b]) => [id, [b.width, b.height, b.lines]]))
  expect(sizes).toEqual({
    A: [7, 3, ["abc"]],
    B: [7, 3, ["abc"]],
    C: [9, 3, ["abc"]],
    D: [7, 5, ["abc"]],
    E: [9, 5, ["abc"]],
    F: [9, 5, ["ab"]],
    G: [7, 4, ["a", "bcd"]],
    H: [9, 6, ["a", "bcd"]],
  })
  // One rank 148 wide at the roomy gap, so the nodes close to five apart, each centred in the band's height.
  expect([...result.bounds.values()].map((b) => [b.left, b.top])).toEqual([
    [0, 1], [12, 1], [24, 1], [38, 0], [50, 0], [64, 0], [78, 1], [90, 0],
  ])
  expect([result.width, result.height]).toEqual([103, 10])
})

test("top-down, ranks sit four rows apart and a rank is centred over the widest; the canvas has four cells spare", () => {
  const result = layout("flowchart\nA --> B")
  expect(Object.fromEntries([...result.bounds].map(([id, b]) => [id, [b.left, b.top, b.centerX, b.centerY]]))).toEqual({
    A: [0, 0, 2, 1],
    B: [0, 7, 2, 8],
  })
  expect([result.width, result.height]).toEqual([9, 14])
  expect(boxes("flowchart\nA --> B & C")).toEqual({ A: [8, 0, 5, 3], B: [0, 7, 5, 3], C: [17, 7, 5, 3] })
})

test("siblings sit twelve apart while the widest rank is at most 120 cells that way, else the minimum gap", () => {
  const row = (left: number, right: number) => boxes(`flowchart\nR --> X[${"a".repeat(left)}] & Y[${"a".repeat(right)}]`)
  expect([row(50, 50).X, row(50, 50).Y]).toEqual([[0, 7, 54, 3], [66, 7, 54, 3]])
  expect([row(51, 50).X, row(51, 50).Y]).toEqual([[0, 7, 55, 3], [60, 7, 54, 3]])
  expect(boxes("flowchart\nA --> B & C", { minNodeGap: 20 }).C).toEqual([25, 7, 5, 3])
  expect(boxes("flowchart\nA --> B & C", { minNodeGap: 3 }).C).toEqual([17, 7, 5, 3])
})

test("a labelled edge widens the gap between its rank's siblings and between its ranks", () => {
  expect(boxes("flowchart\nA -->|long label| B\nA --> C")).toEqual({ A: [12, 0, 5, 3], B: [0, 7, 5, 3], C: [25, 7, 5, 3] })
  expect(boxes("flowchart\nA -->|a<br>b<br>c| B").B).toEqual([0, 8, 5, 3])
  expect(boxes("flowchart\nA -->|a| B").B).toEqual([0, 7, 5, 3])
  expect(boxes("flowchart LR\nA -->|go| B").B).toEqual([16, 0, 5, 3])
})

test("the rank gap is seven across or four down, two and four when compact, or as given", () => {
  expect(boxes("flowchart LR\nA --> B").B).toEqual([12, 0, 5, 3])
  expect(boxes("flowchart LR\nA --> B", { compact: true }).B).toEqual([9, 0, 5, 3])
  expect(boxes("flowchart\nA --> B", { compact: true }).B).toEqual([0, 5, 5, 3])
  expect(boxes("flowchart\nA --> B", { minRankGap: 9 }).B).toEqual([0, 12, 5, 3])
  expect(boxes("flowchart LR\nA --> B", { minRankGap: 1, compact: true }).B).toEqual([6, 0, 5, 3])
})

test("left to right, a rank is a column, centred on the tallest and stacked five apart, each node centred in its width", () => {
  expect(boxes("flowchart LR\nA --> B[abc] & C")).toEqual({ A: [0, 4, 5, 3], B: [12, 0, 7, 3], C: [13, 8, 5, 3] })
})

test("RL and BT lay the ranks out reversed, and a direction option replaces the diagram's", () => {
  expect(boxes("flowchart RL\nA --> B")).toEqual({ A: [12, 0, 5, 3], B: [0, 0, 5, 3] })
  expect(boxes("flowchart BT\nA --> B")).toEqual({ A: [0, 7, 5, 3], B: [0, 0, 5, 3] })
  const turned = layout("flowchart\nA --> B", { direction: "LR" })
  expect([turned.diagram.direction, turned.bounds.get("B")!.left]).toEqual(["LR", 12])
})

test("a node no start reaches takes the next rank in order; a cycle ranks from its first node, its return edge routed around", () => {
  expect(boxes("flowchart\nA\nB <--> C\nC --> B")).toEqual({ A: [4, 0, 5, 3], B: [4, 7, 5, 3], C: [4, 14, 5, 3] })
  expect(boxes("flowchart\nA --> B --> A")).toEqual({ A: [4, 0, 5, 3], B: [4, 7, 5, 3] })
})

test("a rank is reordered only when that removes a crossing, and never inside a subgraph diagram", () => {
  expect(boxes("flowchart\nA & B\nC & D\nA --> D\nB --> C")).toMatchObject({ D: [0, 7, 5, 3], C: [17, 7, 5, 3] })
  expect(boxes("flowchart\nA & B\nC & D\nA --> C\nB --> D")).toMatchObject({ C: [0, 7, 5, 3], D: [17, 7, 5, 3] })
  const grouped = boxes("flowchart\nsubgraph S\nA & B\nC & D\nend\nA --> D\nB --> C")
  expect(grouped.C![0]).toBeLessThan(grouped.D![0]!)
})

test("top-down, a rank wider than the target width wraps into bands five rows apart, at the minimum gap", () => {
  const result = layout("flowchart\nA --> B & C & D", { layoutMaxWidth: 20 })
  expect(Object.fromEntries([...result.bounds].map(([id, b]) => [id, [b.left, b.top]]))).toEqual({
    A: [5, 0],
    B: [0, 7],
    C: [10, 7],
    D: [5, 15],
  })
  expect(result.width).toBe(19)
  expect(boxes("flowchart\nA --> B & C & D", { layoutMaxWidth: Number.NaN }).D).toEqual([34, 7, 5, 3])
})

test("left to right, a layout wider than the target turns top-down, and right to left turns bottom-up", () => {
  expect(layout("flowchart LR\nA --> B", { layoutMaxWidth: 21 }).diagram.direction).toBe("LR")
  const turned = layout("flowchart LR\nA --> B", { layoutMaxWidth: 20 })
  expect([turned.diagram.direction, turned.width, turned.bounds.get("B")!.top]).toEqual(["TD", 9, 7])
  expect(layout("flowchart RL\nA --> B", { layoutMaxWidth: 20.9 }).diagram.direction).toBe("BT")
  expect(layout("flowchart LR\nA --> B", { layoutMaxWidth: Number.POSITIVE_INFINITY }).diagram.direction).toBe("LR")
})

test("a subgraph frame pads its nodes two across and one down, widens to its title, and shifts all onto the canvas", () => {
  const result = layout("flowchart\nsubgraph S [Group]\nA\nend")
  const frame = result.subgraphBounds.get("S")!
  expect([frame.left, frame.top, frame.width, frame.height, frame.centerX, frame.centerY]).toEqual([0, 0, 10, 5, 5, 2])
  expect([frame.id, frame.label, frame.labelSide]).toEqual(["S", "Group", "top"])
  expect(boxes("flowchart\nsubgraph S [Group]\nA\nend").A).toEqual([2, 1, 5, 3])
  expect([result.width, result.height]).toEqual([14, 9])
  expect(frames("flowchart\nsubgraph S [Two<br>lines]\nA\nend").S).toEqual([0, 0, 10, 7, "top"])
})

test("a frame's title moves to the bottom when an edge crosses the top, and a parent frame holds its child's", () => {
  expect(frames("flowchart\nX --> A\nsubgraph S [Group]\nA\nend").S).toEqual([0, 6, 10, 5, "bottom"])
  expect(frames("flowchart\nsubgraph P\nsubgraph C\nA\nend\nB\nend")).toEqual({
    C: [2, 1, 9, 5, "top"],
    P: [0, 0, 28, 7, "top"],
  })
})

test("a subgraph's own direction lays its members out that way, centred where they were", () => {
  expect(boxes("flowchart\nsubgraph S\ndirection LR\nA --> B\nend")).toEqual({ A: [2, 3, 5, 3], B: [11, 3, 5, 3] })
  expect(frames("flowchart\nsubgraph S\ndirection LR\nA --> B\nend").S).toEqual([0, 2, 18, 5, "top"])
})

test("top-level frames already apart stay put, and a linked frame sits a rank on", () => {
  expect(frames("flowchart\nsubgraph S1\nA\nend\nsubgraph S2\nB\nend")).toEqual({
    S1: [0, 0, 9, 5, "top"],
    S2: [17, 0, 9, 5, "top"],
  })
  expect(frames("flowchart\nsubgraph S1\nA\nend\nsubgraph S2\nB\nend\nA --> B")).toEqual({
    S1: [0, 0, 9, 5, "top"],
    S2: [0, 7, 9, 5, "bottom"],
  })
})

test("a labelled edge widens every rank gap it spans, either way, and only those", () => {
  expect(boxes("flowchart LR\nA --> B --> C\nA -->|label| C")).toMatchObject({ B: [19, 3, 5, 3], C: [38, 3, 5, 3] })
  expect(boxes("flowchart LR\nA -->|label| B --> C").C).toEqual([31, 0, 5, 3])
  expect(boxes("flowchart LR\nA --> B\nB -->|label| A").B).toEqual([19, 4, 5, 3])
  expect(boxes("flowchart\nA --> B --> C\nA -->|x<br>y<br>z| C")).toMatchObject({ B: [0, 8, 5, 3], C: [0, 16, 5, 3] })
  expect(boxes("flowchart\nA -->|x<br>y<br>z| B --> C").C).toEqual([0, 15, 5, 3])
  expect(boxes("flowchart\nA --> B\nB -->|x<br>y<br>z| A").B).toEqual([4, 8, 5, 3])
})

test("a labelled edge sets its source rank's sibling gap too, never below the roomy twelve", () => {
  expect(boxes("flowchart\nA & B -->|long label| C")).toEqual({ A: [0, 0, 5, 3], B: [25, 0, 5, 3], C: [12, 7, 5, 3] })
  expect(boxes("flowchart\nA -->|a| B\nA --> C").C).toEqual([17, 7, 5, 3])
})

test("a node's rank is its longest path from a start; an order-only link to or from a subgraph ranks its members", () => {
  expect(boxes("flowchart\nA --> B --> C\nA --> C").C).toEqual([0, 14, 5, 3])
  expect(boxes("flowchart\nsubgraph S\nB\nend\nA ~~~ S")).toEqual({ A: [2, 0, 5, 3], B: [2, 7, 5, 3] })
  expect(boxes("flowchart\nsubgraph S\nB\nend\nS ~~~ A")).toEqual({ B: [2, 1, 5, 3], A: [2, 8, 5, 3] })
  expect(boxes("flowchart\nA & B & C\nA --> C\nC --> B\nB --> A")).toEqual({ A: [4, 0, 5, 3], C: [4, 7, 5, 3], B: [4, 14, 5, 3] })
})

test("a frame too narrow for its title grows by the shortfall, the odd cell on the right, centred on its floor", () => {
  const wide = layout("flowchart\nsubgraph S [abcdefgh]\nA\nend")
  const frame = wide.subgraphBounds.get("S")!
  expect([frame.left, frame.width, frame.centerX, wide.bounds.get("A")!.left]).toEqual([0, 13, 6, 4])
  const odd = layout("flowchart\nsubgraph S [abcdefg]\nA\nend")
  expect([odd.subgraphBounds.get("S")!.width, odd.subgraphBounds.get("S")!.centerX, odd.bounds.get("A")!.left]).toEqual([12, 6, 3])
})

test("a labelled route keeps the label point it was laid out with; an unlabelled one has none", () => {
  const routes = layout("flowchart\nA -->|go| B\nA --> C").routes
  expect(routes.map((route) => [route.edge.to, route.labelPoint])).toEqual([
    ["B", expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) })],
    ["C", undefined],
  ])
})

test("each node's centre is its floor-half along each axis, in a column of mixed sizes as in a row", () => {
  const result = layout("flowchart LR\nA --> B[(db)] & C{d}")
  expect(Object.fromEntries([...result.bounds].map(([id, b]) => [id, [b.left, b.top, b.centerX, b.centerY]]))).toEqual({
    A: [0, 6, 2, 7],
    B: [12, 0, 15, 2],
    C: [12, 10, 15, 12],
  })
  const row = layout("flowchart\nA[(db)] & C{d}")
  expect([...row.bounds.values()].map((b) => [b.centerX, b.centerY])).toEqual([[3, 2], [21, 2]])
})

test("only a rank of several nodes can count as wide: one 114-wide node keeps its neighbours twelve apart", () => {
  const wide = boxes(`flowchart\nX[${"a".repeat(110)}] --> B & C`)
  expect([wide.B, wide.C]).toEqual([[46, 7, 5, 3], [63, 7, 5, 3]])
})

test("a crossing is removed between any adjacent ranks, either way up; order-only and rank-skipping links never reorder", () => {
  expect(boxes("flowchart\nR --> A & B\nC & D\nA --> D\nB --> C")).toMatchObject({ D: [0, 14, 5, 3], C: [17, 14, 5, 3] })
  expect(boxes("flowchart BT\nR --> A & B\nC & D\nA --> D\nB --> C")).toMatchObject({
    C: [0, 0, 5, 3],
    D: [17, 0, 5, 3],
    B: [0, 7, 5, 3],
    A: [17, 7, 5, 3],
  })
  expect(boxes("flowchart\nA & B\nC & D\nA ~~~ D\nB ~~~ C")).toMatchObject({ C: [0, 7, 5, 3], D: [17, 7, 5, 3] })
  const skipping = boxes("flowchart\nA & B\nM & N\nC & D\nA --> M\nB --> N\nM --> C\nN --> D\nA --> D\nB --> C")
  expect([skipping.C![0], skipping.D![0]]).toEqual([2, 19])
})

test("a wrapped rank fills each band up to exactly the target width, and a band is as tall as its tallest node", () => {
  expect(boxes("flowchart\nA --> B & C & D & E", { layoutMaxWidth: 15 })).toMatchObject({
    B: [3, 7, 5, 3],
    C: [13, 7, 5, 3],
    D: [3, 15, 5, 3],
    E: [13, 15, 5, 3],
  })
  expect(boxes("flowchart\nA --> B[(db)] & C & D", { layoutMaxWidth: 15 })).toEqual({
    A: [5, 0, 5, 3],
    B: [4, 7, 6, 5],
    C: [0, 17, 5, 3],
    D: [10, 17, 5, 3],
  })
})

test("a squeezed rank keeps the roomy gap for a labelled fan inside one subgraph, wrapping instead", () => {
  expect(boxes("flowchart\nsubgraph S\nA -->|x| B\nA -->|y| C\nend", { layoutMaxWidth: 21 })).toEqual({
    A: [2, 1, 5, 3],
    B: [2, 8, 5, 3],
    C: [2, 16, 5, 3],
  })
  expect(boxes("flowchart\nsubgraph S\nB -->|x| A\nC -->|y| A\nend", { layoutMaxWidth: 21 })).toEqual({
    B: [2, 1, 5, 3],
    C: [2, 9, 5, 3],
    A: [2, 16, 5, 3],
  })
  expect(boxes("flowchart\nA -->|x| B\nA -->|y| C", { layoutMaxWidth: 21 })).toMatchObject({ B: [0, 7, 5, 3], C: [10, 7, 5, 3] })
})

test("a local direction is laid out only when it differs, its edges routed that way; child frames are its items", () => {
  expect(boxes("flowchart LR\nsubgraph S\ndirection TB\nA --> B\nend")).toEqual({ A: [6, 1, 5, 3], B: [6, 11, 5, 3] })
  expect(boxes("flowchart\nsubgraph S\ndirection TD\nA --> B\nend")).toEqual({ A: [2, 1, 5, 3], B: [2, 8, 5, 3] })
  const local = layout("flowchart\nsubgraph S\ndirection LR\nA --> B\nend")
  expect(local.routes.map((route) => route.points)).toEqual([[{ x: 7, y: 4 }, { x: 10, y: 4 }]])
  expect(frames("flowchart\nsubgraph P\ndirection LR\nsubgraph C1\nA\nend\nsubgraph C2\nB\nend\nend")).toEqual({
    C2: [6, 11, 9, 5, "top"],
    C1: [6, 1, 9, 5, "top"],
    P: [4, 0, 13, 17, "top"],
  })
})

test("top-level frames that overlap are moved apart by half the rank gap, along the ranks or across them", () => {
  const titled = (direction: string, link: string) =>
    frames(`flowchart ${direction}\nsubgraph S1 [a long title here]\nA\nend\nsubgraph S2 [another long title]\nB\nend${link}`)
  expect(titled("TD", "")).toEqual({ S2: [24, 0, 23, 5, "top"], S1: [0, 0, 22, 5, "top"] })
  expect(titled("LR", "\nA --> B")).toEqual({ S2: [25, 0, 23, 5, "top"], S1: [0, 0, 22, 5, "top"] })
  expect(frames("flowchart LR\nsubgraph S1 [x<br>y<br>z]\nA\nend\nsubgraph S2 [p<br>q<br>r]\nB\nend")).toEqual({
    S2: [0, 12, 9, 9, "top"],
    S1: [0, 0, 9, 9, "top"],
  })
  const tall = "subgraph S1 [a<br>b<br>c]\nA\nend\nsubgraph S2\nB\nend\nA --> B"
  expect(boxes(`flowchart\n${tall}`)).toEqual({ A: [2, 3, 5, 3], B: [2, 12, 5, 3] })
  expect(frames(`flowchart BT\n${tall}`)).toEqual({ S2: [0, 0, 9, 5, "top"], S1: [0, 7, 9, 9, "bottom"] })
})

test("beside a subgraph with its own direction, top-level items are laid out one after another by rank", () => {
  expect(boxes("flowchart\nsubgraph S\ndirection LR\nA --> B\nend\nC\nA --> C")).toEqual({
    A: [2, 4, 5, 3],
    B: [11, 4, 5, 3],
    C: [20, 10, 5, 3],
  })
})

test("with a target width, a node still landing on another item's node is moved past that item, down or up", () => {
  const source = "subgraph G0\nB[Bx]\nD[Dx]\nend\nsubgraph G1\nA[Ax]\nC{C}\nend\nE{E}\nF"
  const options = { layoutMaxWidth: 30, compact: true }
  expect(boxes(`flowchart TD\n${source}`, options)).toMatchObject({ C: [24, 9, 7, 5], F: [26, 15, 5, 3] })
  expect(boxes(`flowchart BT\n${source}`, options)).toMatchObject({ A: [46, 4, 6, 3], C: [24, 12, 7, 5], F: [26, 0, 5, 3] })
})

test("with a target width, a local layout that would crowd an outside node is offset to the nearest clear place", () => {
  const source = `flowchart\nsubgraph G1\ndirection BT\nB[${"w".repeat(18)}]\nD[${"w".repeat(15)}]\nend\nE`
  expect(boxes(source, { layoutMaxWidth: 44 })).toEqual({ B: [2, 1, 22, 3], D: [3, 9, 19, 3], E: [27, 15, 5, 3] })
})

test("a fork defect, pinned: a self loop widening one frame lets an outside node land on another frame's node", () => {
  // TD, frames G0 {B} and G1 {A}, edges E --> A, A --> F, A --> A: E is placed over B inside G0 (currently-open.md).
  const result = layout("flowchart TD\nsubgraph G0\nB\nend\nsubgraph G1\nA\nend\nE --> A\nA --> F\nA --> A")
  const [b, e] = [result.bounds.get("B")!, result.bounds.get("E")!]
  expect(b.left < e.left + e.width && e.left < b.left + b.width && b.top < e.top + e.height && e.top < b.top + b.height).toBe(true)
})

// The cases below were found by planting each fault the cases above miss into a copy of layout.ts and searching
// random flowcharts for one it changes, each input then shrunk and the fewest kept that tell every such fault
// apart. Each asserts only the parts of its layout (`summary`'s items) those faults change, as drawn today:
// pinned as observed, not derived by hand, though checked for overlapping nodes and nodes outside their frames
// (one input shows the defect pinned above). Some cases above are redundant against these by design (Max,
// 2026-10-30): they stay as the readable statement of each rule.
test("pinned as observed: label gaps across ranks, self loops and back edges", () => {
  expect(parts("flowchart LR\nB -.->|ll<br>l| B\nB -.->|llllllll| A", {})).toEqual(expect.arrayContaining(["B 0,0 5x3 c2,1", "A 22,0 5x3 c24,1", "B>B 5,1 8,1 8,4 2,4 2,3 @9,2", "B>A 5,1 21,1 @8,1", "31x9 LR"]))
  expect(parts("flowchart LR\nsubgraph G0 [tt<br>t]\nend\nsubgraph G1\nend\nC ==>|llllllll| A\nC -->|lllllll| A", {})).toEqual(expect.arrayContaining(["A 22,0 5x3 c24,1", "C>A 2,3 24,3 @8,3 x", "C>A 2,3 2,4 24,4 24,3 @9,4 x", "31x9 LR"]))
  expect(parts("flowchart TD\nB -->|llllllll| B\nA ==>|lll| B", {"compact": true})).toEqual(expect.arrayContaining(["B 0,6 5x3 c2,7", "B>B 5,7 8,7 8,10 2,10 2,9 @9,8", "A>B 2,3 2,5 @3,4", "23x15 TD"]))
})

test("pinned as observed: frame sizes and the side a frame's title takes", () => {
  expect(parts("flowchart TD\nsubgraph G0\nB\nD[Dx]\nE\nend\nsubgraph G1\ndirection BT\nC[wwwwwwwwww]\nend\nE --- C\nC --- D\nB ==> D\nB ==>|lllllll| B", {})).toEqual(expect.arrayContaining(["[G0 0,13 34x28 c17,27 bottom]", "E 14,14 5x3 c16,15", "C 10,7 14x3 c17,8", "D 14,28 6x3 c17,29", "B 14,35 5x3 c16,36", "[G1 8,6 18x5 c17,8 top]", "E>C 13,15 2,15 2,8 9,8", "C>D 24,8 36,8 36,29 20,29", "B>D 13,36 2,36 2,29 13,29", "B>B 19,36 22,36 22,39 16,39 16,38 @23,37", "41x45 TD"]))
  expect(parts("flowchart TD\nsubgraph G0\nB\nend\nsubgraph G1\nD[[Ds]]\nend\nB --> D", {"compact": true})).toEqual(expect.arrayContaining(["[G1 0,6 12x5 c6,8 top]", "D 2,7 8x3 c6,8", "B>D 6,4 6,6", "16x15 TD"]))
  expect(parts("flowchart BT\nsubgraph G0\nend\nsubgraph G1\nA\nend\nB ==>|ll<br>l| A\nA --- D", {})).toEqual(expect.arrayContaining(["[G1 0,6 9x5 c4,8 top]", "B>A 4,13 4,10 @5,11", "A>D 7,8 11,8 11,1 7,1", "16x21 BT"]))
  expect(parts("flowchart LR\nsubgraph G0\nB\nend\nsubgraph G1\ndirection TB\nend\nE -->|ll<br>l| B", {})).toEqual(expect.arrayContaining(["E 0,1 5x3 c2,2", "B 10,1 5x3 c12,2", "[G0 8,0 9x5 c12,2 top]", "E>B 2,4 2,7 12,7 12,4 @5,5", "21x12 LR"]))
})

test("pinned as observed: ranks and crossing sweeps with skipped, self and isolated nodes", () => {
  expect(parts("flowchart TD\nB[Bx]\nA --> D\nC --> A\nB -->|ll<br>l| E", {})).toEqual(expect.arrayContaining(["B 0,0 6x3 c3,1", "C 18,0 5x3 c20,1", "E 0,7 5x3 c2,8", "A 17,7 5x3 c19,8", "D 9,14 5x3 c11,15", "A>D 19,10 19,11 11,11 11,13", "C>A 19,3 19,6", "B>E 2,3 2,6 @3,4", "27x21 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\nend\nsubgraph G1 [t]\nend\nA -->|l| A\nC ~~~ C\nA --> B", {})).toEqual(expect.arrayContaining(["A 0,0 5x3 c2,1", "B 12,0 5x3 c14,1", "C 24,0 5x3 c26,1", "A>A 5,1 8,1 8,4 2,4 2,3 @4,4", "A>B 5,1 11,1", "33x9 LR"]))
  expect(parts("flowchart RL\nC\nD[(Ddb)]\nE ==>|l| B\nC -.-> F\nE -.->|llllll| D", {})).toEqual(expect.arrayContaining(["D 0,0 7x5 c3,2", "B 1,10 5x3 c3,11", "F 1,18 5x3 c3,19", "E 22,5 5x3 c24,6", "C 22,13 5x3 c24,14", "E>B 21,6 18,6 18,11 6,11 @11,11", "E>D 21,6 18,6 18,2 7,2 @9,2", "C>F 21,14 10,14 10,19 6,19"]))
  expect(parts("flowchart LR\nA\nE ==> C\nA ==>|l| D\nA --> C", {})).toEqual(expect.arrayContaining(["A 0,0 5x3 c2,1", "E 0,8 5x3 c2,9", "D 15,0 5x3 c17,1", "C 15,8 5x3 c17,9", "A>D 5,1 8,1 14,1 @10,1", "A>C 5,1 8,1 8,9 14,9", "E>C 5,9 14,9", "24x15 LR"]))
})

test("pinned as observed: bands, label lanes and the target width", () => {
  expect(parts("flowchart TD\nsubgraph G0\nB\nend\nD --> B\nD -.->|l| A\nB -.->|l| B", {"layoutMaxWidth": 17})).toEqual(expect.arrayContaining(["D 7,0 5x3 c9,1", "B 2,7 5x3 c4,8", "A 12,7 5x3 c14,8", "[G0 0,6 13x7 c6,9 bottom]", "D>B 9,3 9,4 4,4 4,6", "D>A 9,3 9,4 14,4 14,6 @10,4", "B>B 7,8 10,8 10,11 4,11 4,10 @6,11", "21x17 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection TB\nA[(Adb)]\nB[[Bs]]\nend\nsubgraph G1 [tt]\ndirection RL\nend", {})).toEqual(expect.arrayContaining(["A 2,4 7x5 c5,6", "B 21,5 8x3 c25,6", "[G0 0,3 31x7 c15,6 top]", "35x14 LR"]))
  expect(parts("flowchart TD\nA[[As]]\nD[(Ddb)]\nB ~~~ A\nE -->|llllllll| D", {"layoutMaxWidth": 33})).toEqual(expect.arrayContaining(["B 2,0 5x3 c4,1", "E 25,0 5x3 c27,1", "A 0,8 8x3 c4,9", "D 26,7 7x5 c29,9", "E>D 27,3 27,4 29,4 29,6 @17,4", "37x16 TD"]))
  expect(parts("flowchart TD\nsubgraph G0 [tt<br>t]\nA[www]\nB[a<br>b]\nE\nend\nsubgraph G1\nsubgraph H\nend\nend\nA ==>|l| A\nB --- A", {"layoutMaxWidth": 16})).toEqual(expect.arrayContaining(["B 2,2 5x4 c4,4", "E 12,2 5x3 c14,3", "A 6,10 7x3 c9,11", "[G0 0,0 19x17 c9,8 top]", "A>A 13,11 16,11 16,14 9,14 9,13 @11,14", "B>A 4,6 4,7 9,7 9,9", "23x21 TD"]))
})

test("pinned as observed: local directions: nested, inherited, offset and routed", () => {
  expect(parts("flowchart TD\nsubgraph G0\nB\nend\nsubgraph G1 [ttttttttttttttt]\ndirection BT\nC[[Cs]]\nend\nB ==>|ll<br>l| C\nB -.-> C\nC ---|ll<br>l| B\nC ---|ll<br>l| A", {"layoutMaxWidth": 86, "compact": true})).toEqual(expect.arrayContaining(["B 5,6 5x3 c7,7", "C 15,12 8x3 c19,13", "A 5,17 5x3 c7,18", "[G1 9,11 20x5 c19,13 bottom]", "[G0 3,5 9x5 c7,7 bottom]", "B>C 10,7 31,7 31,13 23,13 @32,9 y", "B>C 10,7 31,7 31,13 23,13 y", "C>B 19,11 19,2 7,2 7,5 @11,0", "C>A 14,13 0,13 0,18 3,18 4,18 @5,11", "40x24 TD"]))
  expect(parts("flowchart RL\nsubgraph G0\ndirection LR\nB\nD{D}\nE[[Es]]\nend\nA{A}\nC{C}\nC --- F\nC -.-> C\nB ~~~ E\nB --> B", {"layoutMaxWidth": 56})).toEqual(expect.arrayContaining(["F 22,38 5x3 c24,39", "C 21,7 7x5 c24,9", "E 22,20 8x3 c26,21", "B 12,15 5x3 c14,16", "D 11,23 7x5 c14,25", "A 31,31 7x5 c34,33", "[G0 9,14 23x15 c20,21 top]", "C>F 20,9 0,9 0,39 21,39", "C>C 24,6 24,0 40,0 40,9 28,9", "B>B 17,16 20,16 20,19 14,19 14,18", "45x45 BT"]))
  expect(parts("flowchart TD\nsubgraph G0\nend\nsubgraph G1 [ttttttt]\ndirection BT\nA[Ax]\nB[[Bs]]\nsubgraph H\nend\nend\nA -.-> B", {})).toEqual(expect.arrayContaining(["A 3,8 6x3 c6,9", "B 2,1 8x3 c6,2", "[G1 0,0 12x12 c6,6 top]", "A>B 6,7 6,4", "16x16 TD"]))
  expect(parts("flowchart BT\nsubgraph G0\ndirection TB\nB[wwwwwwwwwwwwww]\nend\nsubgraph G1 [t]\ndirection RL\nA[(Adb)]\nsubgraph H\nend\nend\nB -.-> A", {"layoutMaxWidth": 87})).toEqual(expect.arrayContaining(["A 10,16 7x5 c13,18", "B 5,9 18x3 c14,10", "[G1 8,15 11x7 c13,18 top]", "[G0 3,8 22x5 c14,10 top]", "B>A 4,10 0,10 0,18 9,18", "29x26 BT"]))
  expect(parts("flowchart RL\nsubgraph G0 [t]\ndirection TB\nA[a<br>b]\nB[(Bdb)]\nend", {"layoutMaxWidth": 14, "minNodeGap": 4})).toEqual(expect.arrayContaining(["B 2,10 7x5 c5,12", "[G0 0,0 11x16 c5,8 top]", "15x20 BT"]))
  expect(parts("flowchart BT\nsubgraph G0\nC[(Cdb)]\nend\nsubgraph G1\ndirection RL\nB\nend\nB --- A\nB ~~~ B", {"layoutMaxWidth": 61})).toEqual(expect.arrayContaining(["A 6,22 5x3 c8,23", "B 17,7 5x3 c19,8", "C 5,14 7x5 c8,16", "[G1 15,6 9x5 c19,8 top]", "[G0 3,13 11x7 c8,16 top]", "B>A 16,8 0,8 0,20 8,20 8,21", "28x29 BT"]))
  expect(parts("flowchart TD\nsubgraph G0\nA[www]\nend\nsubgraph G1\ndirection LR\nB{B}\nE[Ex]\nend\nC\nD{D}", {"layoutMaxWidth": 46})).toEqual(expect.arrayContaining(["A 2,18 7x3 c5,19", "B 19,1 7x5 c22,3", "E 19,11 6x3 c22,12", "C 37,24 5x3 c39,25", "D 18,29 7x5 c21,31", "[G1 17,0 11x15 c22,7 top]", "[G0 0,17 11x5 c5,19 top]"]))
})

test("pinned as observed: top-level items separated by rank and across, either way", () => {
  expect(parts("flowchart BT\nsubgraph G0 [t]\nB[a<br>b]\nend\nsubgraph G1\nD[a<br>b]\nE\nsubgraph H\nend\nend\nA[(Adb)]\nA -->|ll<br>l| D\nC -.->|ll<br>l| A\nE -.-> B\nC --- C", {"layoutMaxWidth": 35, "compact": true})).toEqual(expect.arrayContaining(["A 7,8 7x5 c10,10", "D 8,21 5x4 c10,23", "B 8,14 5x4 c10,16", "E 8,33 5x3 c10,34", "[G1 6,20 9x17 c10,28 top]", "[G0 6,13 9x6 c10,16 top]", "A>D 6,10 0,10 0,23 7,23 @2,21", "C>A 7,6 7,2 15,2 15,10 14,10 @9,0", "E>B 13,34 17,34 17,16 13,16", "22x41 BT", "C 8,5 5x3 c10,6", "C>C 10,4 10,2 17,2 17,6 13,6"]))
  expect(parts("flowchart LR\nsubgraph G0 [t]\nend\nsubgraph G1 [tt<br>t]\ndirection TB\nend\nC ~~~ B\nA --> C", {})).toEqual(expect.arrayContaining(["A 0,0 5x3 c2,1", "C 8,0 5x3 c10,1", "B 16,0 5x3 c18,1", "A>C 5,1 7,1", "25x7 LR"]))
  expect(parts("flowchart TD\nsubgraph G0 [ttttttttt]\ndirection RL\nA[a<br>b]\nend\nsubgraph G1 [tttttttttttt]\nB\nsubgraph H\nend\nend\nB --> B\nA -->|lllll| A\nA -.-> A", {"compact": true})).toEqual(expect.arrayContaining(["A 4,1 5x4 c6,3", "B 4,11 5x3 c6,12", "[G1 0,10 17x7 c8,13 top]", "[G0 2,0 20x9 c12,4 top]", "A>A 9,3 12,3 12,6 6,6 6,5 @13,4", "A>A 9,3 13,3 13,7 6,7 6,5", "B>B 9,12 12,12 12,15 6,15 6,14", "26x21 TD"]))
  expect(parts("flowchart RL\nsubgraph G0\nC{C}\nend\nsubgraph G1 [tt<br>t]\ndirection RL\nend\nA ==>|ll<br>l| C\nA -.-> B\nC ==> A", {"layoutMaxWidth": 31})).toEqual(expect.arrayContaining(["B 9,21 5x3 c11,22", "A 9,7 5x3 c11,8", "C 8,13 7x5 c11,15", "[G0 6,12 11x7 c11,15 bottom]", "A>C 8,8 0,8 0,15 7,15 @2,6", "A>B 8,8 0,8 0,22 8,22", "C>A 11,12 11,10", "21x28 BT"]))
  expect(parts("flowchart TD\nsubgraph G0\nB[Bx]\nend\nsubgraph G1\nA\nend\nE --> A\nA -.-> F\nA ==> A", {})).toEqual(expect.arrayContaining(["B 21,8 6x3 c24,9", "E 19,8 5x3 c21,9", "A 10,15 5x3 c12,16", "F 10,22 5x3 c12,23", "[G1 0,0 17x19 c8,9 top]", "[G0 19,7 10x5 c24,9 top]", "E>A 21,11 21,12 12,12 12,14", "A>F 12,18 12,21", "A>A 9,16 2,16 2,1 12,1 12,14", "33x29 TD"]))
  expect(parts("flowchart TD\nsubgraph G0 [t]\nend\nsubgraph G1 [tt]\nA[[As]]\nend\nA -->|ll<br>l| A", {})).toEqual(expect.arrayContaining(["A>A 6,8 2,8 2,3 11,3 11,6 @5,1", "21x15 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection RL\nD[(Ddb)]\nend\nA[wwwwwwwwww]\nC[[Cs]]\nA --> D\nA -.-> B\nD --> A", {})).toEqual(expect.arrayContaining(["C 0,5 8x3 c4,6", "D 13,4 7x5 c16,6", "A 25,5 14x3 c32,6", "B 42,5 5x3 c44,6", "[G0 11,3 11x7 c16,6 bottom]", "D>A 12,6 12,0 32,0 32,3 32,4", "A>D 32,8 49,8 49,2 16,2 16,3", "A>B 39,6 41,6", "54x14 LR"]))
  expect(parts("flowchart TD\nsubgraph G0 [t]\nE{E}\nend\nA\nE -.->|ll<br>l| E", {})).toEqual(expect.arrayContaining(["E>E 10,12 10,18 2,18 2,9 6,9 @4,16", "20x24 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\nB[(Bdb)]\nend\nsubgraph G1 [t]\ndirection LR\nA\nend\nA ~~~ A\nA -.-> B", {})).toEqual(expect.arrayContaining(["B 26,1 7x5 c29,3", "A 14,2 5x3 c16,3", "[G1 12,1 9x5 c16,3 top]", "[G0 24,0 11x7 c29,3 top]", "A>B 16,5 16,9 29,9 29,6"]))
  expect(parts("flowchart LR\nsubgraph G0\nC[wwwwwwwwwwwwwwwww]\nend\nsubgraph G1 [tt<br>t]\nB\nend\nC -.-> C", {})).toEqual(expect.arrayContaining(["B 2,2 5x3 c4,3", "C 14,11 21x3 c24,12", "[G1 0,0 9x7 c4,3 top]", "[G0 12,10 29x7 c26,13 top]", "C>C 35,12 38,12 38,15 24,15 24,14", "45x21 LR"]))
})

test("pinned as observed: the whole layout: reroutes after a move, the canvas shift, the responsive turn", () => {
  expect(parts("flowchart LR\nsubgraph G0\ndirection TB\nB[a<br>b]\nend\nA[wwwwwwwwwww]\nB --> B", {})).toEqual(expect.arrayContaining(["A 0,2 15x3 c7,3", "B 20,1 5x4 c22,3", "[G0 18,0 13x8 c24,4 top]", "B>B 25,3 28,3 28,6 22,6 22,5", "35x12 LR"]))
  expect(parts("flowchart TD\nB[Bx]\nA -.-> C\nA --> C", {"layoutMaxWidth": 10})).toEqual(expect.arrayContaining(["A>C 5,9 6,9 6,16 5,16 y", "A>C 5,9 8,9 8,16 5,16 y", "13x22 TD"]))
  expect(parts("flowchart LR\nA -->|ll<br>l| B\nA -.-> B", {"layoutMaxWidth": 12})).toEqual(expect.arrayContaining(["A>B 5,1 6,1 6,8 5,8 @7,4 y", "A>B 5,1 12,1 12,8 5,8 y", "17x14 TD"]))
  expect(parts("flowchart LR\nsubgraph G0 [tttt]\ndirection RL\nC\nD\nend\nD --> B\nB ==> C", {"layoutMaxWidth": 50})).toEqual(expect.arrayContaining(["D 12,12 5x3 c14,13", "B 22,8 5x3 c24,9", "C 12,4 5x3 c14,5", "[G0 10,3 9x13 c14,9 top]", "D>B 11,13 11,0 24,0 24,6 24,7", "B>C 27,9 29,9 29,5 17,5", "34x20 LR"]))
  expect(parts("flowchart RL\nsubgraph G0\ndirection TB\nA[(Adb)]\nend\nsubgraph G1\nB[[Bs]]\nend", {"minRankGap": 1})).toEqual(expect.arrayContaining(["B 14,11 8x3 c18,12", "[G1 12,10 12x5 c18,12 top]", "28x19 RL"]))
  expect(parts("flowchart TD\nsubgraph G0\nB\nend\nA[[As]]\nA -.->|ll<br>l| B", {})).toEqual(expect.arrayContaining(["A 1,0 8x3 c5,1", "B 2,7 5x3 c4,8", "[G0 0,6 9x5 c4,8 bottom]", "A>B 4,3 4,6 @5,4", "13x15 TD"]))
})
