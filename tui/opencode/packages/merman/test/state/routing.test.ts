import { expect, test } from "bun:test"
import { createStateDiagramDrawing } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import type { StateTransitionPathPoint } from "../../src/state/routing"

// A path's ends and turning points.
function corners(path: readonly StateTransitionPathPoint[]): string {
  const kept = path.filter((point, index) => {
    const before = path[index - 1]
    const after = path[index + 1]
    if (!before || !after) return true
    return (before[0] === point[0]) !== (point[0] === after[0])
  })
  return kept.map(([x, y]) => `${x},${y}`).join(" ")
}

// Each transition as drawn: its ends, its route's kind, its corners and its label's top left.
const routes = (body: string) =>
  createStateDiagramDrawing(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`)).transitionPlans.map(
    (plan) =>
      `${plan.route.transition.from}>${plan.route.transition.to} ${plan.route.kind} ${corners(plan.path)}` +
      (plan.label ? ` @${plan.label.x},${plan.label.y}` : ""),
  )

test("on one row a transition runs from a tee on the source's facing side to an arrow at the target, its label centred above", () => {
  expect(routes("A --> B : go")).toEqual(["A>B horizontal-forward 4,1 17,1 @10,0"])
  expect(routes("direction RL\nA --> B")).toEqual(["A>B horizontal-forward 18,1 5,1"])
})

test("top to bottom a transition runs straight down the column, its label two right of it on the row after the source", () => {
  expect(routes("direction TB\nA --> B : go")).toEqual(["A>B vertical 2,2 2,6 @4,4"])
  expect(routes("direction BT\nA --> B")).toEqual(["A>B vertical 2,7 2,3"])
})

test("left to right, a transition back runs under the row, the shorter on the higher lane, 3 apart, into the target's second cell", () => {
  expect(routes("A --> B\nB --> C\nC --> A\nB --> A")).toEqual([
    "A>B horizontal-forward 4,1 17,1",
    "B>C horizontal-forward 22,1 35,1",
    "C>A bottom-feedback 38,2 38,9 1,9 1,3",
    "B>A bottom-feedback 20,2 20,6 1,6 1,3",
  ])
})

test("a self transition leaves the bottom a third in and comes back up two thirds in; another loops 3 lower and 4 wider", () => {
  expect(routes('state "Longer" as A\nA --> A\nA --> A')).toEqual([
    "A>A self 3,2 3,4 7,4 7,3",
    "A>A self 3,2 3,7 11,7 11,3",
  ])
})
