import { expect, test } from "bun:test"
import { drawSequenceDiagramGrid } from "../../src/sequence/drawing"
import { parseMermaidSequenceDiagram } from "../../src/sequence/parser"
import { renderSequenceGridText, type SequenceGrid } from "../../src/sequence/render-grid"
import type { SequenceDiagramRenderOptions } from "../../src/sequence/types"

const draw = (body: string, options?: SequenceDiagramRenderOptions) =>
  drawSequenceDiagramGrid(parseMermaidSequenceDiagram(`sequenceDiagram\n${body}`), options)
const lines = (grid: SequenceGrid) => renderSequenceGridText(grid).split("\n")
// The styles of a row's cells from x to x + count - 1, a dash for an unstyled one.
const styles = (grid: SequenceGrid, y: number, x: number, count: number) =>
  Array.from({ length: count }, (_, offset) => grid.getCell(x + offset, y)!.style ?? "-")
// The row through each lifeline's column at x.
const column = (grid: SequenceGrid, x: number) =>
  Array.from({ length: grid.height }, (_, y) => grid.getCell(x, y)!.char).join("")

test("a diagram with no participants draws nothing", () => {
  const grid = draw("")
  expect([grid.width, grid.height]).toEqual([0, 0])
})

test("a message: headers over a rule, lifelines, the label two right of the sender, the arrow from a tee to a head", () => {
  const grid = draw("A->>B: hi")
  expect([grid.width, grid.height]).toEqual([21, 6])
  expect(lines(grid)).toEqual([
    " A                 B",
    "─┬─               ─┬─",
    " │                 │",
    " │ hi              │",
    " ├─────────────────►",
    " │                 │",
  ])
  expect(styles(grid, 0, 0, 3)).toEqual(["-", "participant", "-"])
  expect(styles(grid, 1, 0, 3)).toEqual(["participant", "participant", "participant"])
  expect(styles(grid, 3, 3, 2)).toEqual(["request", "request"])
  // The arrow fades in from the sender over five cells.
  expect(styles(grid, 4, 1, 7)).toEqual([
    "requestFade1",
    "requestFade2",
    "requestFade3",
    "requestFade4",
    "requestFade5",
    "request",
    "request",
  ])
  expect(styles(grid, 4, 19, 1)).toEqual(["request"])
  // Below the rule a lifeline ramps up over three rows.
  expect([2, 3, 5].map((y) => grid.getCell(19, y)!.style)).toEqual(["lifelineRamp1", "lifelineRamp2", "lifeline"])
})

test("an open, cross or async head stops a cell short and leaves the target's lifeline; the default head covers it", () => {
  const arrow = (line: string) => lines(draw(`participant A\nparticipant B\n${line}`))[4]
  expect(
    ["A->>B: x", "A->B: x", "A-xB: x", "A-)B: x", "B->>A: x", "B->A: x", "B--xA: x", "B-)A: x"].map(arrow),
  ).toEqual([
    " ├─────────────────►",
    " ├────────────────>│",
    " ├────────────────✕│",
    " ├────────────────)│",
    " ◄─────────────────┤",
    " │<────────────────┤",
    " │✕────────────────┤",
    " │(────────────────┤",
  ])
  // A dashed message is drawn as a response, fading in from its sender whichever way it runs.
  const dashed = draw("participant A\nparticipant B\nB-->>A: ok")
  expect(styles(dashed, 4, 15, 5)).toEqual([
    "responseFade5",
    "responseFade4",
    "responseFade3",
    "responseFade2",
    "responseFade1",
  ])
  expect(styles(dashed, 4, 1, 1)).toEqual(["response"])
  expect(styles(dashed, 3, 3, 2)).toEqual(["response", "response"])
})

test("a self message loops right of its lifeline, the label inside, and returns with a leftward head", () => {
  const grid = draw("A->>A: hi")
  expect(lines(grid)).toEqual([" A", "─┬─", " │", " ├─────────╮", " │ hi      │", " ◄─────────╯", " │"])
  expect(styles(grid, 4, 1, 1)).toEqual(["lifeline"])
  expect(styles(grid, 4, 11, 1)).toEqual(["request"])
  expect(styles(grid, 3, 6, 1)).toEqual(["request"])
  // Another head sits one right of the lifeline, which stays.
  expect(lines(draw("A--)A: hi"))[5]).toBe(" │(────────╯")
  expect(styles(draw("A-->>A: hi"), 5, 1, 2)).toEqual(["response", "response"])
})

test("each label line takes a row: inside a self message's loop, and above a message's arrow", () => {
  expect(lines(draw("A->>A: one<br>two\nA->>B: x<br>y"))).toEqual([
    " A                 B",
    "─┬─               ─┬─",
    " │                 │",
    " ├─────────╮       │",
    " │ one     │       │",
    " │ two     │       │",
    " ◄─────────╯       │",
    " │                 │",
    " │ x               │",
    " │ y               │",
    " ├─────────────────►",
    " │                 │",
  ])
})

test("a note is a padded badge over the lifelines it sits between, a row per line", () => {
  const grid = draw("Note over A,B: one<br>two\nA->>B: x")
  expect(lines(grid)).toEqual([
    " A                 B",
    "─┬─               ─┬─",
    " │                 │",
    " │                 │",
    " │       one       │",
    " │       two       │",
    " │                 │",
    " │ x               │",
    " ├─────────────────►",
    " │                 │",
  ])
  expect(styles(grid, 5, 6, 9)).toEqual(["-", ...Array(7).fill("noteBadge"), "-"])
})

test("compact draws no rule and no ramp, and writes a label that fits inside its arrow", () => {
  const grid = draw("participant A as Web<br>Server\nA->>B: hi", { compact: true })
  expect(lines(grid)).toEqual([
    "  Web                B",
    "Server",
    "   │                 │",
    "   ├────── hi ───────►",
    "   │                 │",
  ])
  expect(styles(grid, 1, 0, 6)).toEqual(Array(6).fill("participant"))
  expect([2, 4].map((y) => grid.getCell(21, y)!.style)).toEqual(["lifeline", "lifeline"])
  expect(styles(grid, 3, 10, 4)).toEqual(["request", "request", "request", "request"])
})

test("each line of a participant's label is centred on its lifeline above one rule", () => {
  const grid = draw("participant A as Web<br/>Server")
  expect(lines(grid)).toEqual(["  Web", "Server", "───┬──", "   │"])
})

test("a box is a rounded frame, its label on the top edge, around its members from the top row to the last", () => {
  const grid = draw("box Team\nA->>B: hi\nend")
  expect(lines(grid)).toEqual([
    "╭─ Team ────────────────╮",
    "│  A                 B  │",
    "│ ─┬─               ─┬─ │",
    "│  │                 │  │",
    "│  │ hi              │  │",
    "│  ├─────────────────►  │",
    "│  │                 │  │",
    "╰───────────────────────╯",
  ])
  expect(styles(grid, 0, 0, 3)).toEqual(["group", "group", "group"])
  expect(styles(grid, 0, 24, 1)).toEqual(["group"])
  expect(styles(grid, 3, 0, 1)).toEqual(["group"])
  expect(styles(grid, 7, 0, 25)).toEqual(Array(25).fill("group"))
})

test("a loop frames its rows across every lifeline, labelled on its top edge, walls down its sides to its end", () => {
  const grid = draw("loop every 5s\nA->>B: hi\nend")
  expect(lines(grid)).toEqual([
    "   A                 B",
    "  ─┬─               ─┬─",
    "   │                 │",
    "╭─ ↻ loop: every 5s ────╮",
    "│  │                 │  │",
    "│  │ hi              │  │",
    "│  ├─────────────────►  │",
    "│  │                 │  │",
    "╰───────────────────────╯",
    "   │                 │",
  ])
  expect(styles(grid, 3, 0, 3)).toEqual(["fragment", "fragment", "fragmentLabel"])
  expect(styles(grid, 3, 24, 1)).toEqual(["fragment"])
  expect(styles(grid, 4, 0, 1)).toEqual(["fragment"])
  expect(styles(grid, 4, 24, 1)).toEqual(["fragment"])
})

test("an else divides its alt with tees; the frame takes the border style asked for", () => {
  const grid = draw("alt ok\nA->>B: x\nelse no\nB-->>A: y\nend", { fragmentBorderStyle: "single" })
  expect(lines(grid).slice(3)).toEqual([
    "┌─ alt: ok ─────────────┐",
    "│  │                 │  │",
    "│  │ x               │  │",
    "│  ├─────────────────►  │",
    "│  │                 │  │",
    "├─ else: no ────────────┤",
    "│  │                 │  │",
    "│  │ y               │  │",
    "│  ◄─────────────────┤  │",
    "│  │                 │  │",
    "└───────────────────────┘",
    "   │                 │",
  ])
  // An empty section still has its one row of walls.
  expect(lines(draw("participant A\nparticipant B\nalt a\nelse b\nend")).slice(3)).toEqual([
    "╭─ alt: a ──────────────╮",
    "│  │                 │  │",
    "├─ else: b ─────────────┤",
    "│  │                 │  │",
    "╰───────────────────────╯",
    "   │                 │",
  ])
})

test("an active lifeline is drawn heavy where it is a plain line, from the activating arrow to the closing one", () => {
  const grid = draw("A->>+B: go\nB-->>-A: done")
  expect(lines(grid)).toEqual([
    " A                 B",
    "─┬─               ─┬─",
    " │                 │",
    " │ go              │",
    " ├─────────────────►",
    " │                 ┃",
    " │ done            ┃",
    " ◄─────────────────┤",
    " │                 │",
  ])
  expect(column(grid, 19)).toBe("B┬││►┃┃┤│")
  // One left open runs heavy to the lifeline's last row.
  expect(column(draw("A->>+B: go"), 19)).toBe("B┬││►┃")
  expect(styles(grid, 5, 19, 1)).toEqual(["lifeline"])
})
