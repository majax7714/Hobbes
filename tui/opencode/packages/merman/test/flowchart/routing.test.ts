import { expect, test } from "bun:test"
import type {
  FlowchartDiagram,
  FlowchartDirection,
  FlowchartEdge,
  FlowchartEdgeRoute,
  FlowchartNodeBounds,
  FlowchartSubgraphBounds,
} from "../../src/flowchart/types"
import {
  avoidFlowchartFrameBorders,
  flowchartDirectionBetween,
  flowchartSourceConnector,
  routeFlowchartEdges,
} from "../../src/flowchart/routing"
import { layoutFlowchartDiagram } from "../../src/flowchart/layout"
import { parseMermaidFlowchartDiagram } from "../../src/flowchart/parser"
import type { FlowchartDiagramRenderOptions } from "../../src/flowchart/options"
import { summary } from "./layout-summary"

function node(id: string, left: number, top: number, width = 5, height = 3): FlowchartNodeBounds {
  return {
    id,
    left,
    top,
    width,
    height,
    centerX: left + Math.floor(width / 2),
    centerY: top + Math.floor(height / 2),
    lines: [id],
  }
}

function frame(id: string, left: number, top: number, width: number, height: number, label = ""): FlowchartSubgraphBounds {
  return {
    id,
    label,
    left,
    top,
    width,
    height,
    centerX: left + Math.floor(width / 2),
    centerY: top + Math.floor(height / 2),
    labelSide: "top",
  }
}

const parts = (source: string, options: FlowchartDiagramRenderOptions) =>
  summary(layoutFlowchartDiagram(parseMermaidFlowchartDiagram(source), options)).split("; ")

const edge = (from: string, to: string, label = ""): FlowchartEdge => ({ from, to, label })
type Point = [number, number]

/** Route `edges` between `nodes` and give each route's points as [x, y] pairs. */
function route(
  direction: FlowchartDirection,
  nodes: FlowchartNodeBounds[],
  edges: FlowchartEdge[],
  options: { frames?: Map<string, FlowchartSubgraphBounds>; aligned?: boolean } = {},
): Point[][] {
  const diagram: FlowchartDiagram = {
    direction,
    nodes: nodes.map((bound) => ({ id: bound.id, label: bound.id, shape: "box" })),
    edges,
  }
  const bounds = new Map(nodes.map((bound) => [bound.id, bound]))
  return routeFlowchartEdges(diagram, bounds, undefined, options.frames, undefined, options.aligned).map((routed) =>
    routed.points.map((point): Point => [point.x, point.y]),
  )
}

test("top-down, an edge leaves a node's bottom and enters the next one's top, snapping one column to stay straight", () => {
  expect(route("TD", [node("A", 0, 0), node("B", 0, 7)], [edge("A", "B")])).toEqual([[[2, 3], [2, 6]]])
  expect(route("TD", [node("A", 0, 0), node("B", 1, 7)], [edge("A", "B")])).toEqual([[[3, 3], [3, 6]]])
  expect(route("TD", [node("A", 0, 0), node("B", 2, 7)], [edge("A", "B")])).toEqual([[[2, 3], [2, 4], [4, 4], [4, 6]]])
  expect(route("BT", [node("A", 0, 7), node("B", 0, 0)], [edge("A", "B")])).toEqual([[[2, 6], [2, 3]]])
})

test("top-down, a back edge runs up a bus three cells left of both nodes, or of everything when frames are routed", () => {
  const nodes = [node("A", 0, 0), node("B", 0, 7)]
  expect(route("TD", nodes, [edge("B", "A")])).toEqual([[[-1, 8], [-4, 8], [-4, 1], [-1, 1]]])
  expect(route("TD", nodes, [edge("B", "A")], { frames: new Map() })).toEqual([[[-1, 8], [-6, 8], [-6, 1], [-1, 1]]])
  expect(route("BT", nodes, [edge("A", "B")])).toEqual([[[-1, 1], [-4, 1], [-4, 8], [-1, 8]]])
})

test("top-down, nodes side by side are joined straight across, either way", () => {
  const nodes = [node("A", 0, 0), node("B", 10, 0)]
  expect(route("TD", nodes, [edge("A", "B")])).toEqual([[[5, 1], [9, 1]]])
  expect(route("TD", nodes, [edge("B", "A")])).toEqual([[[9, 1], [5, 1]]])
})

test("left to right, an edge joins right side to left side, a back edge loops over the top, and RL runs leftward", () => {
  const nodes = [node("A", 0, 0), node("B", 12, 0)]
  expect(route("LR", nodes, [edge("A", "B")])).toEqual([[[5, 1], [11, 1]]])
  expect(route("LR", nodes, [edge("B", "A")])).toEqual([[[14, -1], [14, -4], [2, -4], [2, -1]]])
  expect(route("RL", nodes, [edge("B", "A")])).toEqual([[[11, 1], [5, 1]]])
  expect(route("RL", nodes, [edge("A", "B")])).toEqual([[[2, -1], [2, -4], [14, -4], [14, -1]]])
  expect(route("LR", [node("A", 0, 0), node("B", 0, 8)], [edge("A", "B")])).toEqual([[[2, 3], [2, 7]]])
})

test("a self edge loops from the right side round to the bottom, and each repeat one lane further out", () => {
  expect(route("TD", [node("A", 0, 0)], [edge("A", "A")])).toEqual([[[5, 1], [8, 1], [8, 4], [2, 4], [2, 3]]])
  expect(route("TD", [node("A", 0, 0)], [edge("A", "A"), edge("A", "A")])).toEqual([
    [[5, 1], [8, 1], [8, 4], [2, 4], [2, 3]],
    [[5, 1], [9, 1], [9, 5], [2, 5], [2, 3]],
  ])
})

test("top-down, a node's edges fan out from one bus two rows above the nearest target, and fan in the same way", () => {
  expect(route("TD", [node("A", 10, 0), node("B", 0, 8), node("C", 20, 8)], [edge("A", "B"), edge("A", "C")])).toEqual([
    [[12, 3], [12, 5], [2, 5], [2, 7]],
    [[12, 3], [12, 5], [22, 5], [22, 7]],
  ])
  expect(route("TD", [node("B", 0, 0), node("C", 20, 0), node("A", 10, 8)], [edge("B", "A"), edge("C", "A")])).toEqual([
    [[2, 3], [2, 5], [12, 5], [12, 7]],
    [[22, 3], [22, 5], [12, 5], [12, 7]],
  ])
  expect(route("TD", [node("A", 10, 0), node("B", 0, 12), node("C", 20, 12)], [edge("A", "B"), edge("A", "C")])[0]).toEqual([
    [12, 3], [12, 6], [2, 6], [2, 11],
  ])
})

test("left to right, fans run on a column bus, and a second source's fan takes the next free column", () => {
  expect(route("LR", [node("A", 0, 4), node("B", 12, 0), node("C", 12, 8)], [edge("A", "B"), edge("A", "C")])).toEqual([
    [[5, 5], [8, 5], [8, 1], [11, 1]],
    [[5, 5], [8, 5], [8, 9], [11, 9]],
  ])
  expect(route("LR", [node("B", 0, 0), node("C", 0, 8), node("A", 12, 4)], [edge("B", "A"), edge("C", "A")])).toEqual([
    [[5, 1], [8, 1], [8, 5], [11, 5]],
    [[5, 9], [8, 9], [8, 5], [11, 5]],
  ])
  const nodes = [node("A", 0, 0), node("C", 12, 0), node("D", 12, 8), node("B", 0, 16), node("E", 12, 16), node("F", 12, 24)]
  const fans = route("LR", nodes, [edge("A", "C"), edge("A", "D"), edge("B", "E"), edge("B", "F")])
  expect(fans.map((points) => points[1]![0])).toEqual([8, 8, 9, 9])
})

test("parallel edges between two nodes take side lanes, each past the last one's extent", () => {
  const stacked = [node("A", 0, 0), node("B", 0, 7)]
  expect(route("TD", stacked, [edge("A", "B"), edge("A", "B")])).toEqual([
    [[5, 1], [5, 8]],
    [[5, 1], [7, 1], [7, 8], [5, 8]],
  ])
  expect(route("TD", stacked, [edge("A", "B"), edge("A", "B")], { aligned: true })[0]).toEqual([[5, 1], [6, 1], [6, 8], [5, 8]])
  const beside = [node("A", 0, 0), node("B", 12, 0)]
  expect(route("LR", beside, [edge("A", "B"), edge("A", "B")])).toEqual([
    [[2, 3], [14, 3]],
    [[2, 3], [2, 4], [14, 4], [14, 3]],
  ])
})

test("an edge whose path would cross another node goes round it on a bus three cells clear of everything", () => {
  const nodes = [node("A", 10, 0), node("B", 10, 8), node("C", 10, 16)]
  expect(route("TD", nodes, [edge("A", "C")])).toEqual([[[15, 1], [17, 1], [17, 17], [15, 17]]])
})

test("a source connector sits on the border the edge leaves by, with that side's tee", () => {
  const bounds = node("A", 0, 0)
  expect(flowchartSourceConnector(bounds, { x: 5, y: 1 })).toEqual({ x: 4, y: 1, char: "├" })
  expect(flowchartSourceConnector(bounds, { x: -1, y: 1 })).toEqual({ x: 0, y: 1, char: "┤" })
  expect(flowchartSourceConnector(bounds, { x: 3, y: -1 })).toEqual({ x: 3, y: 0, char: "┴" })
  expect(flowchartSourceConnector(bounds, { x: 1, y: 3 })).toEqual({ x: 1, y: 2, char: "┬" })
  expect(flowchartSourceConnector(bounds, { x: 2, y: 1 })).toEqual({ x: 2, y: 2, char: "┬" })
  expect(flowchartDirectionBetween({ x: 0, y: 0 }, { x: 0, y: 3 })).toBe("down")
})

test("a route along a frame's border steps one cell off it: outward for an outside edge, inward for one inside", () => {
  const box = frame("F", 0, 0, 20, 10)
  const nudged = (points: Point[], ends: [FlowchartNodeBounds, FlowchartNodeBounds]) => {
    const routed: FlowchartEdgeRoute = { edge: edge("A", "B"), points: points.map(([x, y]) => ({ x, y })) }
    avoidFlowchartFrameBorders([routed], new Map(ends.map((bound) => [bound.id, bound])), new Map([["F", box]]))
    return routed.points.map((point): Point => [point.x, point.y])
  }
  const outside: [FlowchartNodeBounds, FlowchartNodeBounds] = [node("A", 30, 0), node("B", 30, 20)]
  const inside: [FlowchartNodeBounds, FlowchartNodeBounds] = [node("A", 2, 2), node("B", 12, 5)]
  expect(nudged([[2, 0], [15, 0]], outside)).toEqual([[2, 0], [2, -1], [15, -1], [15, 0]])
  expect(nudged([[2, 0], [15, 0]], inside)).toEqual([[2, 0], [2, 1], [15, 1], [15, 0]])
  expect(nudged([[2, 9], [15, 9]], outside)).toEqual([[2, 9], [2, 10], [15, 10], [15, 9]])
  expect(nudged([[2, 9], [15, 9]], inside)).toEqual([[2, 9], [2, 8], [15, 8], [15, 9]])
  expect(nudged([[0, 2], [0, 8]], outside)).toEqual([[0, 2], [-1, 2], [-1, 8], [0, 8]])
  expect(nudged([[0, 2], [0, 8]], inside)).toEqual([[0, 2], [1, 2], [1, 8], [0, 8]])
  expect(nudged([[19, 2], [19, 8]], outside)).toEqual([[19, 2], [20, 2], [20, 8], [19, 8]])
  expect(nudged([[19, 2], [19, 8]], inside)).toEqual([[19, 2], [18, 2], [18, 8], [19, 8]])
  expect(nudged([[19, 0], [25, 0]], outside)).toEqual([[19, 0], [25, 0]])
  expect(nudged([[5, 5], [5, 5], [5, 7]], outside)).toEqual([[5, 5], [5, 7]])
})

// The cases below were found as the layout file's pinned cases were: each fault the cases above miss planted in a
// copy of routing.ts, random flowcharts searched for one it changes, each input shrunk and the fewest kept that tell
// every such fault apart. Each asserts only the parts of its layout (`summary`'s items) those faults change, as
// drawn today: pinned as observed, not derived by hand, though checked for overlapping nodes and nodes outside
// their frames. Cases above that are redundant against these stay as the readable statement of each rule (Max,
// 2026-10-30).

test("pinned as observed: fans out and in, lanes reserved, targets owned", () => {
  expect(parts("flowchart RL\nA{A}\nD[Dx]\nD ==> C\nA -->|ll<br>l| D\nA --> B\nB ==> A\nD --> B", {})).toEqual(expect.arrayContaining(["B>A 17,12 17,14 35,14 35,9", "C 3,5 5x3 c5,6", "D 15,1 6x3 c18,2", "B 15,9 5x3 c17,10", "A 32,4 7x5 c35,6", "D>C 14,2 14,6 8,6", "D>B 14,2 0,2 0,10 14,10", "A>D 31,6 28,6 28,2 21,2 @23,0", "A>B 31,6 28,6 28,7 17,7 17,8", "43x19 RL"]))
  expect(parts("flowchart LR\nsubgraph G0\nend\nsubgraph G1\nsubgraph H\nend\nend\nF -->|l| E\nC ==>|ll<br>l| E", {"layoutMaxWidth": 13})).toEqual(expect.arrayContaining(["F>E 5,1 7,1 7,16 5,16 @8,8", "15x22 TD", "C>E 2,11 2,13 2,14 @3,12", "F 0,0 5x3 c2,1", "C 0,8 5x3 c2,9", "E 0,15 5x3 c2,16"]))
  expect(parts("flowchart RL\nsubgraph G0\nend\nB -.-> E\nD --- E\nD -->|llllllll| A", {})).toEqual(expect.arrayContaining(["D>E 21,9 18,9 18,1 5,1", "D>A 21,9 18,9 5,9 @7,9", "B>E 21,1 5,1", "31x15 RL"]))
  expect(parts("flowchart TD\nA --> D\nB -->|ll<br>l| E\nB ==>|ll<br>l| D", {})).toEqual(expect.arrayContaining(["B>E 19,3 19,4 19,6 @20,4", "B>D 19,3 19,4 2,4 2,6 @9,2", "A>D 2,3 2,6"]))
  expect(parts("flowchart TD\nD --> C\nB --> A\nE --> A", {})).toEqual(expect.arrayContaining(["B>A 19,3 19,5 27,5 27,6", "E>A 36,3 36,5 27,5 27,6"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection RL\nA\nend\nA -.-> C\nA --> C\nA --> B", {})).toEqual(expect.arrayContaining(["A 2,7 5x3 c4,8", "C 12,3 5x3 c14,4", "B 20,11 5x3 c22,12", "[G0 0,6 9x5 c4,8 top]", "A>C 4,10 4,16 14,16 14,7 14,6 x", "A>C 4,10 4,11 14,11 14,6 x", "A>B 1,8 1,0 22,0 22,9 22,10", "29x21 LR"]))
})

test("pinned as observed: parallel lanes and self loops, labelled", () => {
  expect(parts("flowchart TD\nA{A}\nC ==>|ll<br>l| E\nC -.-> E\nD ---|ll<br>l| C", {})).toEqual(expect.arrayContaining(["C>E 14,10 20,10 20,17 14,17 y", "28x23 TD", "C>E 14,10 14,17 @15,13 y"]))
  expect(parts("flowchart LR\nA -.-> B\nA ---|ll<br>l| B", {})).toEqual(expect.arrayContaining(["A 0,0 5x3 c2,1", "B 16,0 5x3 c18,1", "A>B 2,3 18,3 x", "A>B 2,3 2,6 18,6 18,3 @8,4 x", "25x11 LR"]))
  expect(parts("flowchart TD\nsubgraph G0\nend\nsubgraph G1\ndirection LR\nC[a<br>b]\nend\nB[(Bdb)]\nC -.-> A\nC --> A", {"layoutMaxWidth": 29, "compact": true, "minNodeGap": 6})).toEqual(expect.arrayContaining(["C>A 4,5 4,16 15,16 x", "C>A 4,5 4,17 15,17 15,16 x", "32x22 TD"]))
  expect(parts("flowchart LR\nC --> A\nC ---|l| B\nC -->|l| B", {})).toEqual(expect.arrayContaining(["C>B 2,7 2,12 17,12 17,11 @8,12 x", "24x17 LR", "C>B 2,7 2,11 17,11 @8,11 x"]))
  expect(parts("flowchart TD\nsubgraph G0 [ttttttttt]\nend\nsubgraph G1 [tttttttttttt]\nsubgraph H\nend\nend\nB --> B\nA -->|lllll| A\nB --> B\nA -.-> A", {})).toEqual(expect.arrayContaining(["A>A 5,8 9,8 9,12 2,12 2,10", "20x17 TD"]))
  expect(parts("flowchart TD\nD[wwwwwwwwwww]\nD --> A\nD ==> A", {})).toEqual(expect.arrayContaining(["D>A 15,1 15,8 10,8 y"]))
})

test("pinned as observed: edges leaving and entering a frame with its own direction", () => {
  expect(parts("flowchart LR\nsubgraph G0\ndirection LR\nA\nend\nsubgraph G1\nsubgraph H\nend\nend\nA --> B\nB ==>|l| A\nA --- A", {})).toEqual(expect.arrayContaining(["A 2,4 5x3 c4,5", "B 17,4 5x3 c19,5", "[G0 0,3 13x7 c6,6 bottom]", "A>B 7,5 16,5 16,8 19,8 19,7", "B>A 19,3 19,0 4,0 4,3 @10,0", "A>A 7,5 10,5 10,8 4,8 4,7", "26x14 LR"]))
  expect(parts("flowchart TD\nsubgraph G0 [tttttttttttt]\nD\nE[[Es]]\nend\nsubgraph G1\nend\nE ~~~|ll<br>l| E\nE -->|l| D", {})).toEqual(expect.arrayContaining(["D 3,1 5x3 c5,2", "E 2,8 8x3 c6,9", "[G0 0,0 18x12 c9,6 top]", "E>D 10,9 15,9 15,5 5,5 5,4 @9,5", "22x16 TD"]))
  expect(parts("flowchart TD\nsubgraph G0\ndirection LR\nB\nend\nA{A}\nB --> C", {})).toEqual(expect.arrayContaining(["B>C 7,2 12,2 12,10 13,10 13,13"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection RL\nC[(Cdb)]\nend\nsubgraph G1 [tt<br>t]\ndirection RL\nA[Ax]\nsubgraph H\nend\nend\nC --- A", {})).toEqual(expect.arrayContaining(["C 5,1 7x5 c8,3", "A 19,2 6x3 c22,3", "[G1 17,0 10x7 c22,3 top]", "[G0 3,0 11x7 c8,3 top]", "C>A 4,3 0,3 0,7 30,7 30,3 25,3", "35x12 LR"]))
  expect(parts("flowchart BT\nsubgraph G0 [tt<br>t]\ndirection LR\nB\nend\nB ==> C\nC ~~~ B", {})).toEqual(expect.arrayContaining(["[G0 0,5 9x7 c4,8 top]", "B>C 7,8 12,8 12,4 4,4 4,3"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection LR\nA[(Adb)]\nend\nB --> A", {})).toEqual(expect.arrayContaining(["B>A 2,5 7,5 7,3 11,3", "25x11 LR"]))
  expect(parts("flowchart TD\nsubgraph G0\ndirection LR\nB\nend\nB --> C", {})).toEqual(expect.arrayContaining(["B>C 7,2 12,2 12,5 4,5 4,6", "17x14 TD"]))
})

test("pinned as observed: detours round nodes, frames, titles, labels and other routes", () => {
  expect(parts("flowchart TD\nsubgraph G0 [tt<br>t]\ndirection RL\nB[[Bs]]\nE{E}\nF[(Fdb)]\nend\nD[[Ds]]\nF ==> F\nC ==>|llll| B\nE ---|l| C\nB --- A\nE ==> F", {})).toEqual(expect.arrayContaining(["E>C 23,28 23,45 33,45 33,36 34,36 @27,45", "B>A 28,21 43,21 43,41 31,41 30,41", "E>F 23,28 0,28 0,24 11,24 12,24", "E 24,26 7x5 c27,28", "D 33,1 8x3 c37,2", "F 13,22 7x5 c16,24", "C 35,35 5x3 c37,36", "B 24,18 8x3 c28,19", "A 25,40 5x3 c27,41", "[G0 3,6 31x27 c18,19 top]", "C>B 40,36 43,36 43,19 32,19 @35,19", "F>F 16,27 16,45 0,45 0,24 12,24", "48x50 TD"]))
  expect(parts("flowchart BT\nA\nB[wwwwww]\nE[(Edb)]\nB --- C\nB ==>|llllllll| D\nB -.->|l| C", {"layoutMaxWidth": 28})).toEqual(expect.arrayContaining(["B>C 19,11 19,0 2,0 2,4 x", "B>C 19,11 19,2 2,2 2,4 @9,2 x", "B>D 24,13 30,13 30,6 28,6 @18,15", "35x29 BT", "C 0,5 5x3 c2,6", "D 23,5 5x3 c25,6", "A 4,12 5x3 c6,13", "B 14,12 10x3 c19,13", "E 10,20 7x5 c13,22"]))
  expect(parts("flowchart RL\nsubgraph G0\ndirection RL\nB[Bx]\nend\nsubgraph G1\nend\nB -.-> C\nC -.-> B", {})).toEqual(expect.arrayContaining(["C 3,2 5x3 c5,3", "B 15,2 6x3 c18,3", "[G0 13,1 10x5 c18,3 bottom]", "B>C 14,3 10,3 10,0 5,0 5,1", "C>B 5,5 0,5 0,0 18,0 18,1", "27x10 RL"]))
  expect(parts("flowchart TD\nsubgraph G0\nB\nend\nsubgraph G1 [ttttttttttttttt]\ndirection BT\nC[[Cs]]\nend\nB ==>|ll<br>l| C\nB -.-> C\nC ---|ll<br>l| A", {"layoutMaxWidth": 86, "compact": true})).toEqual(expect.arrayContaining(["C>A 14,8 0,8 0,13 3,13 4,13 @5,6", "B 5,1 5x3 c7,2", "C 15,7 8x3 c19,8", "A 5,12 5x3 c7,13", "[G1 9,6 20x5 c19,8 top]", "[G0 3,0 9x5 c7,2 top]", "B>C 10,2 31,2 31,8 23,8 @32,4 y", "B>C 10,2 31,2 31,8 23,8 y", "40x19 TD"]))
  expect(parts("flowchart TD\nsubgraph G0\nend\nsubgraph G1\nsubgraph H\nend\nend\nA[wwwwwwww]\nB -->|ll<br>l| B\nB ==> B\nB -.-> B", {})).toEqual(expect.arrayContaining(["A 0,0 12x3 c6,1", "B 3,7 5x3 c5,8", "B>B 8,8 11,8 11,11 5,11 5,10 @12,9", "B>B 8,8 12,8 12,12 5,12 5,10", "B>B 8,8 17,8 17,12 5,12 5,10", "22x17 TD"]))
  expect(parts("flowchart BT\nsubgraph G0\nF{F}\nend\nsubgraph G1\nC\nend\nA ==> B\nA ~~~|lll| C\nC --> C\nC ==> E\nC ~~~|ll<br>l| F", {})).toEqual(expect.arrayContaining(["F 2,1 7x5 c5,3", "E 21,2 5x3 c23,3", "C 2,10 5x3 c4,11", "B 20,10 5x3 c22,11", "A 11,17 5x3 c13,18", "[G1 0,9 13x7 c6,12 bottom]", "[G0 0,0 11x7 c5,3 top]", "A>B 13,16 13,15 22,15 22,13", "C>C 7,11 10,11 10,14 4,14 4,13", "C>E 4,9 4,8 23,8 23,5", "30x24 BT"]))
  expect(parts("flowchart BT\nsubgraph G0\ndirection LR\nC\nend\nsubgraph G1\nsubgraph H\nend\nend\nB -->|ll<br>l| C", {})).toEqual(expect.arrayContaining(["C 2,13 5x3 c4,14", "B 2,7 5x3 c4,8", "[G0 0,12 9x5 c4,14 top]", "B>C 7,8 11,8 11,14 7,14 @12,10", "20x21 BT"]))
  expect(parts("flowchart LR\nsubgraph G0\nF[a<br>b]\nend\nsubgraph G1\nB[Bx]\nsubgraph H\nend\nend\nE[wwwwwwwwwwwwww]\nB -.-> B\nF --- F\nC ==> E\nC ==>|ll<br>l| E", {"layoutMaxWidth": 13})).toEqual(expect.arrayContaining(["C>E 11,2 19,2 19,9 18,9 y", "37x33 TD"]))
  expect(parts("flowchart LR\nsubgraph G0 [tttttttttttt]\ndirection RL\nB\nend\nsubgraph G1 [t]\nend\nB -.-> A\nB --> A", {})).toEqual(expect.arrayContaining(["B>A 8,4 8,7 22,7 22,5 22,4 x"]))
  expect(parts("flowchart LR\nA\nB ---|ll<br>l| A\nB --> B\nA -.-> B", {"layoutMaxWidth": 12})).toEqual(expect.arrayContaining(["A>B 6,3 11,3 11,5 6,5 6,6"]))
  expect(parts("flowchart TD\nsubgraph G0 [t]\nE{E}\nend\nE -.->|ll<br>l| E", {})).toEqual(expect.arrayContaining(["E 7,7 7x5 c10,9", "[G0 0,0 16x13 c8,6 top]", "E>E 6,9 2,9 2,3 10,3 10,6 @4,1", "20x17 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\ndirection RL\nC[(Cdb)]\nend\nsubgraph G1 [tt<br>t]\ndirection RL\nA[Ax]\nsubgraph H\nend\nend\nA -.-> B\nB --> C\nC --- A", {})).toEqual(expect.arrayContaining(["[G1 14,3 10x7 c19,6 top]", "C>A 1,6 1,12 19,12 19,9 19,8", "39x17 LR"]))
  expect(parts("flowchart BT\nsubgraph G0 [t]\nB[a<br>b]\nend\nsubgraph G1\nD[a<br>b]\nE\nsubgraph H\nend\nend\nA[(Adb)]\nA -->|ll<br>l| D\nC -.->|ll<br>l| A\nE -.-> B\nC --- C", {"layoutMaxWidth": 35, "compact": true})).toEqual(expect.arrayContaining(["E>B 13,34 17,34 17,16 13,16"]))
  expect(parts("flowchart RL\nA{A}\nD[a<br>b]\nA --> E\nC -.->|ll<br>l| B\nA -.->|l| A\nA -.->|l| B\nA ~~~|ll<br>l| D", {})).toEqual(expect.arrayContaining(["E 0,5 5x3 c2,6", "D 12,4 5x4 c14,6", "A 28,4 7x5 c31,6", "B 45,5 5x3 c47,6", "C 61,5 5x3 c63,6", "A>E 31,3 31,1 2,1 2,4", "C>B 60,6 50,6 @53,4", "A>A 35,6 38,6 38,10 31,10 31,9 @33,10", "A>B 31,3 31,0 47,0 47,4 @38,0", "70x15 RL"]))
})

test("pinned as observed: a label moved off whatever it would cover", () => {
  expect(parts("flowchart LR\nsubgraph G0\nA[wwwww]\nB{B}\nD[[Ds]]\nend\nsubgraph G1\nF[a<br>b]\nsubgraph H\nend\nend\nE --> A\nF ==>|l| F\nA -->|ll<br>l| E\nF -.->|l| D\nC --> A\nB --> E", {"layoutMaxWidth": 56})).toEqual(expect.arrayContaining(["B 9,33 7x5 c12,35", "C 28,1 5x3 c30,2", "A 8,42 9x3 c12,43", "E 29,9 5x3 c31,10", "D 17,49 8x3 c21,50", "F 18,23 5x4 c20,25", "[G1 16,22 13x8 c22,26 top]", "[G0 6,32 21x21 c16,42 top]", "E>A 31,12 3,12 3,40 12,40 12,41", "C>A 31,4 36,4 36,43 18,43 17,43", "F>F 23,25 26,25 26,28 20,28 20,27 @22,28", "A>E 7,43 0,43 0,10 28,10 @2,41", "F>D 21,27 36,27 36,50 26,50 25,50 @21,27", "B>E 8,35 0,35 0,10 28,10", "41x57 TD"]))
  expect(parts("flowchart LR\nsubgraph G0\nC[www]\nF[a<br>b]\nend\nsubgraph G1\nsubgraph H\nend\nend\nE[wwwwwwwwwwwwww]\nF --- F\nC ==> E\nC ==>|ll<br>l| E", {"layoutMaxWidth": 13})).toEqual(expect.arrayContaining(["C>E 12,2 21,2 21,9 18,9 @12,3 y", "26x26 TD", "C>E 12,2 19,2 19,9 18,9 y", "C 5,1 7x3 c8,2", "E 0,8 18x3 c9,9", "F 6,15 5x4 c8,17", "[G0 3,0 14x22 c10,11 top]", "F>F 11,17 14,17 14,20 8,20 8,19"]))
  expect(parts("flowchart BT\nsubgraph G0\nB{B}\nend\nA[wwwwwwwwwwwwwwwwwww]\nD -.->|l| B\nB -->|l| B", {"layoutMaxWidth": 20})).toEqual(expect.arrayContaining(["D>B 14,17 0,17 0,7 14,7 14,6 @6,17", "B>B 18,3 21,3 21,7 14,7 14,6 @14,7", "B 11,1 7x5 c14,3", "A 3,10 23x3 c14,11", "D 12,18 5x3 c14,19", "[G0 9,0 15x9 c16,4 top]", "30x25 BT"]))
  expect(parts("flowchart RL\nB[Bx]\nC\nD[(Ddb)]\nE ==>|l| B\nA -.-> A\nA --- F\nF ==> D\nE --> B\nE -.->|llllll| D", {"compact": true, "minNodeGap": 2})).toEqual(expect.arrayContaining(["E>B 40,10 40,0 26,0 26,4 25,4 @37,5 x", "E>B 40,10 40,0 26,0 26,4 25,4 x", "50x17 RL", "F 1,7 5x3 c3,8", "A 10,7 5x3 c12,8", "B 19,3 6x3 c22,4", "D 19,8 7x5 c22,10", "C 41,4 5x3 c43,5", "E 41,9 5x3 c43,10", "A>A 15,8 18,8 18,11 12,11 12,10", "A>F 9,8 6,8", "F>D 0,8 0,0 27,0 27,10 26,10", "E>D 40,10 26,10 @29,10"]))
  expect(parts("flowchart TD\nA[[As]]\nB -->|llllllll| B", {"layoutMaxWidth": 17})).toEqual(expect.arrayContaining(["A 1,0 8x3 c5,1", "B 2,7 5x3 c4,8", "B>B 7,8 10,8 10,11 4,11 4,10 @0,10", "15x16 TD"]))
  expect(parts("flowchart BT\nA\nD --> D\nB --- C\nB ==>|llllllll| D\nB -.->|l| C", {"layoutMaxWidth": 28})).toEqual(expect.arrayContaining(["B>C 28,8 30,8 30,1 28,1 @28,7 y"]))
  expect(parts("flowchart LR\nsubgraph G0 [tttttttttttttt]\nA\nC[wwwwwwwwwwwwww]\nend\nB[Bx]\nC -.-> C\nA ==>|ll<br>l| D\nA ==>|ll<br>l| F\nD --- A", {"layoutMaxWidth": 58})).toEqual(expect.arrayContaining(["A>D 16,10 3,10 3,22 12,22 13,22 @8,11"]))
  expect(parts("flowchart LR\nsubgraph G0 [t]\nD[[Ds]]\nend\nD -->|l| D\nA -->|l| C", {"layoutMaxWidth": 13})).toEqual(expect.arrayContaining(["D>D 10,15 13,15 13,18 6,18 6,17 @8,18"]))
  expect(parts("flowchart BT\nC -->|ll<br>l| A\nB --- B\nC -.-> D", {})).toEqual(expect.arrayContaining([]))
})

test("pinned as observed: routes stepped off a frame border", () => {
  expect(parts("flowchart LR\nsubgraph G0\nend\nsubgraph G1 [tttttttttttttttttt]\ndirection TB\nC[(Cdb)]\nend\nA ==> C\nB --> B", {})).toEqual(expect.arrayContaining(["B>B 13,6 16,6 15,6 15,9 16,9 10,9 10,8"]))
})
