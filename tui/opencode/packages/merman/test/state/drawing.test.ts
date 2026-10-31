import { expect, test } from "bun:test"
import { createStateDiagramDrawing, drawStateDiagramGrid } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { renderStateGridText, type StateGrid } from "../../src/state/render-grid"
import type { StateDiagramRenderOptions } from "../../src/state/types"
import { summary } from "./layout-summary"

const draw = (body: string, options?: StateDiagramRenderOptions) =>
  drawStateDiagramGrid(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`), options)
const lines = (grid: StateGrid) => renderStateGridText(grid).split("\n")
// The styles of a row's cells from x to x + count - 1, a dash for an unstyled one.
const styles = (grid: StateGrid, y: number, x: number, count: number) =>
  Array.from({ length: count }, (_, offset) => grid.getCell(x + offset, y)!.style ?? "-")

test("a transition: rounded boxes, a tee on the source, a filled head, the label above with a blank each side", () => {
  const grid = draw("A --> B : go")
  expect(lines(grid)).toEqual(["╭───╮     go      ╭───╮", "│ A ├────────────▶│ B │", "╰───╯             ╰───╯"])
  // The line ramps away from a state over its first three cells.
  expect(styles(grid, 1, 3, 6)).toEqual([
    "state",
    "stateDepartureRamp1",
    "stateDepartureRamp2",
    "stateDepartureRamp3",
    "transition",
    "transition",
  ])
  expect(styles(grid, 1, 17, 2)).toEqual(["transition", "stateBorder"])
  expect(styles(grid, 0, 9, 4)).toEqual(["label", "label", "label", "label"])
  expect(styles(grid, 0, 0, 1)).toEqual(["stateBorder"])
})

test("the border and head styles are options", () => {
  expect(lines(draw("A --> B", { borderStyle: "single", arrowHeadStyle: "line" }))).toEqual([
    "┌───┐             ┌───┐",
    "│ A ├────────────→│ B │",
    "└───┘             └───┘",
  ])
})

test("start and end markers are drawn as ● and ◎; a line from a marker does not ramp", () => {
  const grid = draw("[*] --> A\nA --> [*]")
  expect(lines(grid)).toEqual(["              ╭───╮", "●────────────▶│ A ├────────────▶◎", "              ╰───╯"])
  expect(styles(grid, 1, 0, 2)).toEqual(["start", "transition"])
  expect(styles(grid, 1, 32, 1)).toEqual(["end"])
})

test("a composite is a frame with its title on the top edge, around its states", () => {
  const grid = draw("state P {\nA --> B\n}")
  expect(lines(grid)).toEqual([
    "╭─ P ─────────────────────╮",
    "│                         │",
    "│ ╭───╮             ╭───╮ │",
    "│ │ A ├────────────▶│ B │ │",
    "│ ╰───╯             ╰───╯ │",
    "│                         │",
    "╰─────────────────────────╯",
  ])
  expect(styles(grid, 0, 0, 4)).toEqual(["composite", "composite", "compositeLabel", "compositeLabel"])
})

test("a note is a double frame beside its target, joined by a double line into a tee on its side", () => {
  const grid = draw("A --> B\nnote right of B : hi")
  expect(lines(grid)).toEqual([
    "╭───╮             ╭───╮    ╔════╗",
    "│ A ├────────────▶│ B │════╣ hi ║",
    "╰───╯             ╰───╯    ╚════╝",
  ])
  expect(styles(grid, 1, 23, 7)).toEqual([
    "noteConnector",
    "noteConnectorRamp1",
    "noteConnectorRamp2",
    "noteConnectorRamp3",
    "noteBorder",
    "-",
    "noteText",
  ])
})

test("a fork defect, pinned: a self loop's head is not kept under its box", () => {
  // On a box 5 wide (a one-letter state) the head comes up one column past the right edge; on one 6 wide, under
  // the corner; each further loop goes 4 wider, so on a box 10 wide the second's head is two columns past it
  // (currently-open.md). A fix changes these.
  expect(lines(draw("A --> A"))).toEqual(["╭───╮", "│ A │", "╰─┬─╯", "  │  ▲", "  ╰──╯"])
  expect(lines(draw('state "AB" as A\nA --> A'))).toEqual(["╭────╮", "│ AB │", "╰─┬──╯", "  │  ▲", "  ╰──╯"])
  expect(lines(draw('state "Longer" as A\nA --> A\nA --> A'))).toEqual([
    "╭────────╮",
    "│ Longer │",
    "╰──┬─────╯",
    "   │   ▲   ▲",
    "   ├───╯   │",
    "   │       │",
    "   │       │",
    "   ╰───────╯",
  ])
})

test("a fork defect, pinned: left to right, a marker or choice off the main path sits on its target's top row", () => {
  // The fallback row places every state off the main path at the same top, a 1-cell one too (`layout.ts:764`), so
  // `ch` is not level with B's centre and its route runs along B's top border, over it, into its far side
  // (currently-open.md). A fix changes this.
  expect(lines(draw("state ch <<choice>>\n[*] --> A\nch --> B"))).toEqual([
    "              ╭───╮",
    "●────────────▶│ A │",
    "              ╰───╯",
    "",
    "",
    "",
    "                            ◆─────────────────────────────────╮",
    "                                                      │ B │◀──╯",
    "                                                      ╰───╯",
  ])
})

test("a fork defect, pinned: two composites off each other's path are drawn crossing, a state outside its own", () => {
  // P1 is placed by the fallback row (currently-open.md): its frame starts inside P0's, and P1y runs out past P1's
  // right side. A fix changes this.
  const { layout } = createStateDiagramDrawing(
    parseMermaidStateDiagram(
      "stateDiagram-v2\nstate P0 {\n[*] --> P0x\nP0x --> P0y : x<br>yy<br>zzz\n}\nstate P1 {\n[*] --> P1x\nP1x --> P1y\n}",
    ),
  )
  expect(summary(layout)).toMatchObject({
    "[P0]": "0,0 45x11 c22,5",
    "[P1]": "42,6 69x7 c76,9",
    P1y: "107,8 7x3 c110,9",
  })
})

test("a fork defect, pinned: a valid diagram with two composites is refused, the separation not converging", () => {
  // Each of these seven lines is needed for the refusal (currently-open.md). A fix draws it.
  expect(() => draw("state P0 {\nP0x --> [*]\n}\nstate P1 {\n[*] --> P1x\nP1y --> [*]\n}")).toThrow(
    "State composite separation did not converge",
  )
})
