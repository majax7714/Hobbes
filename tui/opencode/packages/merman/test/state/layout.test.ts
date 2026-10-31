import { expect, test } from "bun:test"
import { createStateDiagramLayout } from "../../src/state/layout"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { prepareVisibleStateDiagram } from "../../src/state/visible-model"
import { summary } from "./layout-summary"

// Laid out as the drawing lays it out: from the visible model, composite markers passed through.
const layout = (body: string, minStateGap = 5) =>
  summary(
    createStateDiagramLayout(prepareVisibleStateDiagram(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`)), {
      minStateGap,
    }),
  )

test("left to right, the main path runs on one row: a box is its label plus 2 each side, a marker 1 cell on the row below the top", () => {
  expect(layout("[*] --> A\nA --> B : go\nB --> [*]")).toEqual({
    __start: "0,1 1x1 c0,1",
    A: "14,0 5x3 c16,1",
    B: "32,0 5x3 c34,1",
    __end: "50,1 1x1 c50,1",
  })
})

test("neighbours on the main path sit the minimum gap plus 8 apart, or the label between them plus 2 if wider", () => {
  expect(layout("A --> B")).toEqual({ A: "0,0 5x3 c2,1", B: "18,0 5x3 c20,1" })
  expect(layout("A --> B", 1)).toMatchObject({ B: "14,0 5x3 c16,1" })
  expect(layout("A --> B : abcdefghijklmnopqrst")).toMatchObject({ B: "27,0 5x3 c29,1" })
  // The row drops to fit the tallest label anywhere, a marker's top on it.
  expect(layout("[*] --> A\nA --> B : a<br>b<br>c")).toEqual({
    __start: "0,3 1x1 c0,3",
    A: "14,2 5x3 c16,3",
    B: "32,2 5x3 c34,3",
  })
})

test("a label into a composite needs 6 more, not 2, and the composite frames its states 2 out", () => {
  const placed = layout('A --> B : abcdefghijkl\nstate P {\nstate "B" as B\n}')
  expect(placed).toEqual({ A: "0,2 5x3 c2,3", B: "23,2 5x3 c25,3", "[P]": "21,0 9x7 c25,3" })
})

test("the main path takes an end first, then a state that does not lead back, then one with no transition back", () => {
  expect(layout("A --> B\nA --> [*]")).toEqual({ A: "0,0 5x3 c2,1", __end: "18,1 1x1 c18,1", B: "0,6 5x3 c2,7" })
  expect(layout("A --> B\nA --> C\nB --> A")).toEqual({ A: "0,0 5x3 c2,1", C: "18,0 5x3 c20,1", B: "0,6 5x3 c2,7" })
  expect(layout("A --> B\nB --> C\nC --> A\nA --> D\nD --> A")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "18,0 5x3 c20,1",
    C: "36,0 5x3 c38,1",
    D: "0,6 5x3 c2,7",
  })
})

test("with no clear way on, the main path stops; the rest branch beneath, centred under their parent, the canvas shifted", () => {
  expect(layout("A --> B\nB --> A\nA --> C\nC --> A")).toEqual({
    A: "9,0 5x3 c11,1",
    B: "0,6 5x3 c2,7",
    C: "18,6 5x3 c20,7",
  })
})

test("branches that rejoin the path further on sit one row lower, under the state after their parent", () => {
  expect(layout("[*] --> A\nA --> B\nB --> C\nA --> D\nD --> C")).toEqual({
    __start: "0,1 1x1 c0,1",
    A: "14,0 5x3 c16,1",
    B: "32,0 5x3 c34,1",
    C: "50,0 5x3 c52,1",
    D: "32,7 5x3 c34,8",
  })
})

test("a state off the path and off every branch sits on the lower row at its rank's column", () => {
  expect(layout("A --> B\nC --> D")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "18,0 5x3 c20,1",
    C: "36,6 5x3 c38,7",
    D: "54,6 5x3 c56,7",
  })
})

test("right to left mirrors left to right, then shifts right by the widest label on a transition between rows, plus 2", () => {
  expect(layout("direction RL\nA --> B")).toEqual({ A: "18,0 5x3 c20,1", B: "0,0 5x3 c2,1" })
  expect(layout("direction RL\nA --> B\nA --> C : abcd")).toEqual({
    A: "24,0 5x3 c26,1",
    B: "6,0 5x3 c8,1",
    C: "24,6 5x3 c26,7",
  })
})

test("top to bottom, ranks are rows: a lone state centred on the widest lone one, rows 4 apart", () => {
  const down = { __start: "2,0 1x1 c2,0", A: "0,5 5x3 c2,6", B: "0,12 5x3 c2,13", __end: "2,19 1x1 c2,19" }
  expect(layout("direction TB\n[*] --> A\nA --> B\nB --> [*]")).toEqual(down)
  // Bottom to top turns the ranks over.
  expect(layout("direction BT\n[*] --> A\nA --> B\nB --> [*]")).toEqual({
    __end: "2,0 1x1 c2,0",
    B: "0,5 5x3 c2,6",
    A: "0,12 5x3 c2,13",
    __start: "2,19 1x1 c2,19",
  })
})

test("top to bottom, states sharing a rank sit left to right; a row's gap grows for labels, self loops and a choice", () => {
  expect(layout("direction TB\nA --> B : x<br>y\nA --> C")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "0,8 5x3 c2,9",
    C: "18,8 5x3 c20,9",
  })
  expect(layout("direction TB\nA --> A\nA --> A\nA --> B")).toMatchObject({ B: "0,10 5x3 c2,11" })
  // An unreached state takes the next free rank.
  expect(layout("direction TB\nstate c <<choice>>\nA --> c\nc --> B")).toEqual({
    c: "2,0 1x1 c2,0",
    B: "0,7 5x3 c2,8",
    A: "0,14 5x3 c2,15",
  })
})

test("a composite is at least its title plus 5 wide", () => {
  expect(layout('state "A long composite title" as P {\nstate "A" as A\n}')).toEqual({
    A: "2,2 5x3 c4,3",
    "[P]": "0,0 27x7 c13,3",
  })
  expect(layout("state P {\nA --> B\n}")).toEqual({ A: "2,2 5x3 c4,3", B: "20,2 5x3 c22,3", "[P]": "0,0 27x7 c13,3" })
})
