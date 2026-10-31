import { expect, test } from "bun:test"
import { drawStateDiagramGrid } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { renderStateGridText, type StateGrid } from "../../src/state/render-grid"
import type { StateDiagramRenderOptions } from "../../src/state/types"

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
