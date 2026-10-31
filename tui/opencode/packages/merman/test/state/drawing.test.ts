import { expect, test } from "bun:test"
import { createStateDiagramDrawing, drawStateDiagramGrid } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { renderStateGridText, type StateGrid } from "../../src/state/render-grid"
import type { StateDiagramRenderOptions } from "../../src/state/types"
import { drawn } from "./drawing-summary"
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

// The cases below were found by planting each fault the cases above miss into a copy of drawing.ts and searching random
// state diagrams for one it changes (`bench/subsume/pinned.py` with the state harnesses), each input then shrunk and
// the fewest kept that tell every such fault apart. Each asserts only the routes and rows (`drawing-summary.ts`) those
// faults change, and the count of rows where they add or take rows, as drawn today: pinned as observed, not derived by
// hand. None shows a known wrong drawing (`state-defects.ts`: composites crossing, a state outside its composite, a
// route through a state). Cases above that are redundant against these stay as the readable statement of each rule
// (Max, 2026-10-30).
test("pinned as observed: the canvas: its size, the shift off negative cells, and the separation's attempts", () => {
  expect(
    drawn(
      "state P0 {\n}\nP0x --> D : go\nP0x --> B : a<br>b\nP0x --> A : go\nA --> [*]\nnote left of B : a note\nnote left of B : two<br>lines",
      { borderStyle: "heavy", arrowHeadStyle: "line", layoutMaxWidth: 55 },
    ),
  ).toMatchObject({
    "route:0": "P0x>D vertical-elbow 3,8 3,11 2,11 2,13 @7,10",
    "route:1": "P0x>B vertical-elbow 3,6 3,5 4,5 4,0 20,0 20,13 @1,3",
    "route:2": "P0x>A vertical-elbow 3,6 3,5 4,5 4,0 35,0 35,15 @6,5",
    "route:3": "A>__end vertical-elbow 38,16 38,18 3,18 3,20",
    "row:0": "    ╭───────────────┬──────────────╮",
    "row:1": "    │╔═══════╗      │              │",
    "row:10": "   │   go        ║  │              │",
    "row:11": "  ╭╯             ║  │              │",
    "row:12": "  │              ║  │              │",
    "row:13": "  ↓              ║  ↓              │",
    "row:14": "┏━━━┓            ║┏━━━┓            │┏━━━┓",
    "row:15": "┃ D ┃            ║┃ B ┃            →┃ A ┃",
    "row:16": "┗━━━┛             ┗━━━┛             ┗━┬━┛",
    "row:17": "  ╔═══════════════                    │",
    "row:18": "  ║╭──────────────────────────────────╯",
    "row:19": "  ║│",
    "row:2": "    │║ two   ║      │              │",
    "row:20": "  ║↓",
    "row:21": "  ║◎",
    "row:22": "  ╚════════════╗",
    "row:23": "    ╔════════╗ ║",
    "row:24": "    ║ a note ╠═╝",
    "row:25": "    ╚════════╝",
    "row:3": " a  │║ lines ╠═══╗  │              │",
    "row:4": " b  │╚═══════╝   ║  │              │",
    "row:5": "   ╭╯ go         ║  │              │",
    "row:6": "┏━━┴━━┓          ║  │              │",
    "row:7": "┃ P0x ┃          ║  │              │",
    "row:8": "┗━━┬━━┛          ║  │              │",
    "row:9": "   │             ║  │              │",
  })
  expect(
    drawn(
      'state "Outer" as P0 {\nP0x --> P0y\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> D\nP0nw --> P0nz : x<br>yy<br>zzz\nP0n --> P0',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 46,12 59,12",
    "route:1": "P0nz>P0nw horizontal-forward 91,12 104,12",
    "route:2": "__start>D horizontal-forward 1,6 13,6",
    "route:3": "P0nw>P0nz bottom-feedback 109,13 109,21 85,21 85,14 @95,18",
    "route:4": "P0n>P0 top-feedback 98,9 98,0 115,0 115,6",
    "row:0":
      "                                                                                                  ╭────────────────╮",
    "row:1":
      "                                                                                                  │                │",
    "row:10":
      "                                      │                                           │                               │ │",
    "row:11":
      "                                      │ ╭─────╮             ╭─────╮               │ ╭──────╮             ╭──────╮ │ │",
    "row:12":
      "                                      │ │ P0x ├────────────▶│ P0y │               │ │ P0nz ├────────────▶│ P0nw │ │ │",
    "row:13":
      "                                      │ ╰─────╯             ╰─────╯               │ ╰──────╯             ╰───┬──╯ │ │",
    "row:14":
      "                                      │                                           │  ▲                       │    │ │",
    "row:15":
      "                                      │                                           │  │                       │    │ │",
    "row:16":
      "                                      │                                           │  │                       │    │ │",
    "row:17":
      "                                      │                                           │  │                       │    │ │",
    "row:18":
      "                                      │                                           │  │         x             │    │ │",
    "row:19":
      "                                      │                                           │  │         yy            │    │ │",
    "row:2":
      "                                                                                                  │                │",
    "row:20":
      "                                      │                                           │  │         zzz           │    │ │",
    "row:21":
      "                                      │                                           │  ╰───────────────────────╯    │ │",
    "row:22":
      "                                      │                                           ╰───────────────────────────────╯ │",
    "row:23":
      "                                      │                                                                             │",
    "row:24":
      "                                      ╰─────────────────────────────────────────────────────────────────────────────╯",
    "row:3":
      "                                                                                                  │                │",
    "row:4":
      "                                                                                                  │                │",
    "row:5":
      "              ╭───╮                                                                               │                │",
    "row:6":
      "●────────────▶│ D │                                                                               │                ▼",
    "row:7":
      "              ╰───╯                   ╭─ Outer ───────────────────────────────────────────────────│─────────────────╮",
    "row:8":
      "                                      │                                                           │                 │",
    "row:9":
      "                                      │                                           ╭─ P0n ─────────┴───────────────╮ │",
    rows: 25,
  })
  expect(
    drawn(
      "direction TB\nB --> B : a<br>b\nB --> A : a long label here\nB --> A : a long label here\nA --> B : a long label here\nA --> B",
    ),
  ).toMatchObject({
    "route:0": "B>B self 3,2 3,4 6,4 6,3 @1,4",
    "route:1": "B>A vertical 3,2 3,7 @17,4",
    "route:2": "B>A side-parallel 5,1 9,1 9,9 6,9 @17,6",
    "route:3": "A>B side-parallel 5,9 12,9 12,1 6,1 @17,2",
    "route:4": "A>B side-parallel 5,9 15,9 15,1 6,1",
    "row:0": " ╭───╮",
    "row:1": " │ B ├◀──┬──┬──╮",
    "row:10": " ╰───╯",
    "row:2": " ╰─┬─╯   │  │  │ a long label here",
    "row:3": "   │  ▲  │  │  │",
    "row:4": " a ├──╯  │  │  │ a long label here",
    "row:5": " b │     │  │  │",
    "row:6": "   │     │  │  │ a long label here",
    "row:7": "   ▼     │  │  │",
    "row:8": " ╭───╮   │  │  │",
    "row:9": " │ A ├───┴──┴──╯",
  })
  expect(
    drawn(
      'state P0 {\n}\nstate "Outer" as P1 {\nP1x --> P1y : x<br>yy<br>zzz\n}\n[*] --> A\nB --> P1y : a long label here\nP0y --> B : x<br>yy<br>zzz\nP1y --> C : go',
    ),
  ).toMatchObject({
    "route:0": "P1x>P1y horizontal-forward 46,9 59,9 @51,3",
    "route:1": "__start>A horizontal-forward 1,3 13,3",
    "route:2": "B>P1y bottom-feedback 82,10 82,16 61,16 61,11 @64,14",
    "route:3": "P0y>B bottom-feedback 103,10 103,21 81,21 81,11 @90,18",
    "route:4": "P1y>C bottom-parallel 63,10 63,26 123,26 123,11 @92,25",
    "row:0": "              ╭───╮                   ╭─ Outer ─────────────────────╮",
    "row:1": "●────────────▶│ A │                   │            x                │",
    "row:10":
      "                                      ╰──────────────────────│─│────╯            ││                    │                   │",
    "row:11":
      "                                                             │ │                 ││                    │                   │",
    "row:12":
      "                                                             │ │a long label here││                    │                   │",
    "row:13":
      "                                                             │ │                 ││                    │                   │",
    "row:14":
      "                                                             ╰─┼─────────────────┼╯                    │                   │",
    "row:15":
      "                                                               │                 │                     │                   │",
    "row:16":
      "                                                               │                 │        x            │                   │",
    "row:17":
      "                                                               │                 │        yy           │                   │",
    "row:18":
      "                                                               │                 │        zzz          │                   │",
    "row:19":
      "                                                               │                 ╰─────────────────────╯                   │",
    "row:2": "              ╰───╯                   │            yy               │",
    "row:20":
      "                                                               │                                                           │",
    "row:21":
      "                                                               │                                                           │",
    "row:22":
      "                                                               │                                                           │",
    "row:23":
      "                                                               │                            go                             │",
    "row:24":
      "                                                               ╰───────────────────────────────────────────────────────────╯",
    "row:3": "                                      │            zzz              │",
    "row:4": "                                      │                             │",
    "row:5": "                                      │                             │",
    "row:6":
      "                                      │ ╭─────╮             ╭─────╮ │           ╭───╮               ╭─────╮             ╭───╮",
    "row:7":
      "                                      │ │ P1x ├────────────▶│ P1y │ │           │ B │               │ P0y │             │ C │",
    "row:8":
      "                                      │ ╰─────╯             ╰──┬──╯ │           ╰─┬─╯               ╰──┬──╯             ╰───╯",
    "row:9":
      "                                      │                      ▲ │    │            ▲│                    │                   ▲",
    rows: 25,
  })
  expect(
    drawn('direction RL\nstate "A long composite title" as P0 {\n[*] --> P0x\n}\nstate P1 {\n}\nP0 --> P0'),
  ).toMatchObject({
    "row:0": "╭─ A long composite title ╮",
    "row:1": "│                         │",
    "row:2": "│ ╭─────╮                 │",
    "row:3": "┤ │ P0x │◀                │",
    "row:4": "│ ╰─────╯                 │",
    "row:5": "│                         │",
    "row:6": "╰─────────────────────────╯",
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : go\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0 --> A\nP0nw --> P0nw : a long label here",
      { borderStyle: "heavy", arrowHeadStyle: "line", layoutMaxWidth: 55 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 8,4 8,8 @10,6",
    "route:1": "P0nz>P0nw vertical 8,18 8,22",
    "route:2": "P0>A side-parallel 30,18 43,18 43,31 40,31",
    "route:3": "P0nw>P0nw self 6,25 6,27 9,27 9,26 @11,26",
    "row:0": "┏━ P0 ━━━━━━━━━━━━━━━━━━━━━━━━┓",
    "row:1": "┃                             ┃",
    "row:10": "┃    ┃ P0y ┃                  ┃",
    "row:11": "┃    ┗━━━━━┛                  ┃",
    "row:12": "┃                             ┃",
    "row:13": "┃                             ┃",
    "row:14": "┃ ┏━ P0n ━━━━━━━━━━━━━━━━━━━┓ ┃",
    "row:15": "┃ ┃                         ┃ ┃",
    "row:16": "┃ ┃ ┏━━━━━━┓                ┃ ┃",
    "row:17": "┃ ┃ ┃ P0nz ┃                ┃ ┃",
    "row:18": "┃ ┃ ┗━━━┬━━┛                ┃ ├────────────╮",
    "row:19": "┃ ┃     │                   ┃ ┃            │",
    "row:2": "┃    ┏━━━━━┓                  ┃",
    "row:20": "┃ ┃     │                   ┃ ┃            │",
    "row:21": "┃ ┃     │                   ┃ ┃            │",
    "row:22": "┃ ┃     ↓                   ┃ ┃            │",
    "row:23": "┃ ┃ ┏━━━━━━┓                ┃ ┃            │",
    "row:24": "┃ ┃ ┃ P0nw ┃                ┃ ┃            │",
    "row:25": "┃ ┃ ┗━┬━━━━┛                ┃ ┃            │",
    "row:26": "┃ ┃   │  ↑ a long label here┃ ┃            │",
    "row:27": "┃ ┃   ╰──╯                  ┃ ┃            │",
    "row:28": "┃ ┃                         ┃ ┃            │",
    "row:29": "┃ ┃                         ┃ ┃            │",
    "row:3": "┃    ┃ P0x ┃                  ┃",
    "row:30": "┃ ┃                         ┃ ┃    ┏━━━┓   │",
    "row:31": "┃ ┃                         ┃ ┃    ┃ A ┃←──╯",
    "row:32": "┃ ┃                         ┃ ┃    ┗━━━┛",
    "row:33": "┃ ┗━━━━━━━━━━━━━━━━━━━━━━━━━┛ ┃",
    "row:34": "┃                             ┃",
    "row:35": "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛",
    "row:4": "┃    ┗━━┬━━┛                  ┃",
    "row:5": "┃       │                     ┃",
    "row:6": "┃       │ go                  ┃",
    "row:7": "┃       │                     ┃",
    "row:8": "┃       ↓                     ┃",
    "row:9": "┃    ┏━━━━━┓                  ┃",
  })
  expect(
    drawn(
      "direction RL\nstate P0 {\n}\nstate P1 {\n}\nP1x --> P0\nP0x --> P1x : a long label here\nA --> C : a<br>b\nP0 --> C : a long label here",
      { minStateGap: 2 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P1x bottom-feedback 37,12 37,16 90,16 90,7 @55,15",
    "route:1": "A>C top-feedback 21,10 21,0 71,0 71,3 @23,3",
    "row:0": "                     ╭─────────────────────────────────────────────────╮",
    "row:1": "                     │                                                 │",
    "row:10": "                   ╭─┴─╮          ╭─────╮                                                 │",
    "row:11": "                   │ A │          │ P0x │                                                 │",
    "row:12": "                   ╰───╯          ╰──┬──╯                                                 │",
    "row:13": "                                     │                                                    │",
    "row:14": "                                     │                                                    │",
    "row:15": "                                     │                 a long label here                  │",
    "row:16": "                                     ╰────────────────────────────────────────────────────╯",
    "row:2": "                     │                                                 │",
    "row:3": "                     │ a                                               ▼",
    "row:4": "                     │ b                                              ╭───╮          ╭─────╮",
    "row:5": "                     │                                                │ C │          │ P1x │",
    "row:6": "                     │                                                ╰───╯          ╰─────╯",
    "row:7": "                     │                                                                    ▲",
    "row:8": "                     │                                                                    │",
    "row:9": "                     │                                                                    │",
    rows: 17,
  })
})

test("pinned as observed: past the width, left to right turned top to bottom", () => {
  expect(
    drawn("direction RL\nch --> A\nB --> ch", { borderStyle: "double", arrowHeadStyle: "filled", layoutMaxWidth: 42 }),
  ).toMatchObject({
    "route:0": "ch>A vertical 3,14 3,10",
    "route:1": "B>ch side-parallel 5,1 9,1 9,15 6,15",
    "row:0": " ╔═══╗",
    "row:1": " ║ B ├───╮",
    "row:10": "   ▲     │",
    "row:11": "   │     │",
    "row:12": "   │     │",
    "row:13": "   │     │",
    "row:14": "╔══┴═╗   │",
    "row:15": "║ ch ║◀──╯",
    "row:16": "╚════╝",
    "row:2": " ╚═══╝   │",
    "row:3": "         │",
    "row:4": "         │",
    "row:5": "         │",
    "row:6": "         │",
    "row:7": " ╔═══╗   │",
    "row:8": " ║ A ║   │",
    "row:9": " ╚═══╝   │",
  })
  expect(drawn("D --> B", { borderStyle: "single", arrowHeadStyle: "line", layoutMaxWidth: 28 })).toMatchObject({
    "route:0": "D>B horizontal-forward 4,1 17,1",
    "row:0": "┌───┐             ┌───┐",
    "row:1": "│ D ├────────────→│ B │",
    "row:2": "└───┘             └───┘",
    rows: 3,
  })
})

test("pinned as observed: the glyphs of frames, notes and junctions", () => {
  expect(
    drawn("state ch <<choice>>", { borderStyle: "rounded", arrowHeadStyle: "filled", layoutMaxWidth: 52 }),
  ).toMatchObject({ "row:0": "◆" })
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\nP0x --> [*]\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> B\nA --> P0n : x<br>yy<br>zzz\nP0n --> P0x : a long label here\nB --> P0nz : a<br>b\nP0x --> P0nw\nA --> [*]\nnote left of A : two<br>lines",
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 3,3 15,3",
    "route:1": "P0x>P0.__end horizontal-forward 22,3 36,3",
    "route:2": "P0nz>P0nw bottom-feedback 90,10 90,23 16,23 16,11",
    "route:3": "__start>B side-parallel 103,8 103,11 141,11",
    "route:4": "A>P0n side-parallel 162,9 183,9 183,13 96,13 @185,10",
    "route:5": "P0n>P0x bottom-feedback 54,19 54,18 96,18 96,5 17,5 @67,16",
    "route:6":
      "B>P0nz bottom-feedback 140,9 97,9 97,4 37,4 37,2 23,2 23,1 15,1 15,2 2,2 2,4 15,4 15,5 16,5 16,6 85,6 85,9 @114,6",
    "route:7": "P0x>P0nw vertical-elbow 22,3 23,3 23,5 86,5 86,7 94,7 94,11 23,11 23,9",
    "route:8": "A>__end side-parallel 162,9 186,9 186,8 177,8",
    "row:0": "╭─ P0 ───────────────────────────────────────────────────────────────────────────────────────────╮",
    "row:1": "│              ╭───────╮                                                                         │",
    "row:10":
      "│            │ ╰──────╯│                                                              ╰───┬──╯││││     │                                    ╰───╯             ╰───╯                    │ x",
    "row:11":
      "│            │  ▲      ╰──────────────────────────────────────────────────────────────────┼───╯│││     ╰─────────────────────────────────────▲                                         │ yy",
    "row:12":
      "│            │  │                                                                         │    │││                                                                                     │ zzz",
    "row:13":
      "│            │  │                                                                         │    ││──────────────────────────────────────────────────────────────────────────────────────╯",
    "row:14": "│            │  │                                                                         │    │││",
    "row:15": "│            │  │                                                                         │    │││",
    "row:16": "│            │  │                                                  a long label here      │    │││",
    "row:17": "│            │  │                                                                         │    │││",
    "row:18": "│            │  │                                     ╰───────────────────────────────────┼─────╯│",
    "row:19": "│            │  │                                     ┬                                   │    │ │",
    "row:2":
      "│ ╭────────────╯╭─────╮╰─────────────╮                                                           │                                               ╔═══════╗",
    "row:20": "│            │  │                                                                         │    │ │",
    "row:21": "│            │  │                                                                         │    │ │",
    "row:22": "│            │  │                                                                         │    │ │",
    "row:23": "│            │  ╰─────────────────────────────────────────────────────────────────────────╯    │ │",
    "row:24": "│            ╰─────────────────────────────────────────────────────────────────────────────────╯ │",
    "row:25": "│                                                                                                │",
    "row:26": "╰────────────────────────────────────────────────────────────────────────────────────────────────╯",
    "row:3":
      "│ ┼────────────▶│ P0x ├┬─────────────│                                                           │                                               ║ two   ║",
    "row:4":
      "│ ╰────────────╮╰─────╯│             ╰───────────────────────────────────────────────────────────╮                                               ║ lines ╠═══╗",
    "row:5":
      "│              ╰╮▶─────┴──────────────────────────────────────────────────────────────┬─────────╮│                                               ╚═══════╝   ║",
    "row:6":
      "│            ╭─ P0n ─────────────────────────────────────────────────────────────────╮│────────╮││                a                                          ║",
    "row:7":
      "│            │                                                                       │╰───────╮│││                b                                          ║",
    "row:8":
      "│            │ ╭──────╮                                                              │╭──────╮││││    ●│                                    ╭───╮             ╭───╮             ◎◀────────╮",
    "row:9":
      "│            │ │ P0nw │◀                                                             ▶│ P0nz ││││╰─────┼────────────────────────────────────┤ B │             │ A ├────────────────────┬──╯",
    rows: 27,
  })
  expect(
    drawn(
      "direction RL\nstate P0 {\n}\nstate P1 {\nP1x --> P1y\n}\n[*] --> B\nP1x --> D : retry\nC --> C\nA --> [*]\nnote right of C : a note",
    ),
  ).toMatchObject({
    "route:0": "P1x>P1y horizontal-forward 90,7 77,7",
    "route:1": "__start>B horizontal-forward 135,1 123,1",
    "route:2": "P1x>D bottom-parallel 93,8 93,14 53,14 53,9 @70,13",
    "route:3": "C>C self 36,8 36,10 39,10 39,9",
    "route:4": "A>__end side-parallel 20,7 33,7 33,9 35,9 35,11 40,11 40,8 39,8 39,5 34,5 34,4 2,4 2,5",
    "row:0":
      "                                           ╔════════╗                                                                 ╭───╮",
    "row:1":
      "                                         ╔═╣ a note ║                                                                 │ B │◀────────────●",
    "row:10": "                                   │╰──╯│            │              ╰────────────────────────│────╯",
    "row:11": "                                   ╰────╯            │                                       │",
    "row:12": "                                                     │                                       │",
    "row:13": "                                                     │                retry                  │",
    "row:14": "                                                     ╰───────────────────────────────────────╯",
    "row:2":
      "                                         ║ ╚════════╝                                                                 ╰───╯",
    "row:3": " ╔═══════════════════════════════════════╝",
    "row:4": " ║╭───────────────────────────────╮                                 ╭─ P1 ────────────────────────╮",
    "row:5": " ║▼            ╔═════════════════╗╰────╮                            │                             │",
    "row:6": " ║◎            ║╭───╮            ║╭───╮│            ╭───╮           │ ╭─────╮             ╭─────╮ │",
    "row:7": " ╚═════════════╝│ A ├────────────╮│ C ││            │ D │           │ │ P1y │◀────────────┤ P1x │ │",
    "row:8": "                ╰───╯            │╰─┬─╯╰╮           ╰───╯           │ ╰─────╯             ╰──┬──╯ │",
    "row:9": "                                 ╰─╮│  ▲│            ▲              │                        │    │",
    rows: 15,
  })
})
