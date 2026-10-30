import { TextAttributes } from "@opentui/core"
import { expect, test } from "bun:test"
import type { FlowchartDiagramRenderOptions } from "../../src/flowchart/options"
import { DEFAULT_BORDER_STYLE, drawFlowchartDiagramGrid } from "../../src/flowchart/drawing"
import { parseMermaidFlowchartDiagram } from "../../src/flowchart/parser"

const CODES: Record<string, string> = {
  node: "n",
  nodeBorder: "N",
  database: "d",
  databaseBorder: "D",
  edge: "e",
  label: "l",
  group: "g",
  groupLabel: "G",
}

function draw(source: string, options: FlowchartDiagramRenderOptions = {}) {
  return drawFlowchartDiagramGrid(parseMermaidFlowchartDiagram(source), options)
}

/** The drawn rows, each trimmed on the right, and under each its styles: a node fade as 1–5, a database fade as v–z. */
function picture(source: string, options: FlowchartDiagramRenderOptions = {}): string[] {
  const rows: string[] = []
  for (const row of draw(source, options).rows) {
    const text = row.map((cell) => cell.char).join("").trimEnd()
    if (!text) continue
    const styles = row.slice(0, text.length).map((cell) => {
      const style = cell.style
      if (!style) return "."
      if (style.startsWith("nodeEdgeFade")) return style.at(-1)!
      if (style.startsWith("databaseEdgeFade")) return "vwxyz"[Number(style.at(-1)) - 1]!
      return CODES[style]!
    })
    rows.push(`${text}  ${styles.join("")}`)
  }
  return rows
}

test("a box is a filled frame, a subroutine adds two rails, a database a rail under its top and over its bottom", () => {
  expect(DEFAULT_BORDER_STYLE).toBe("rounded")
  expect(picture("flowchart LR\nA[[sub]] --> B[(db)]")).toEqual([
    "                ╭────╮  ................DDDDDD",
    "╭─┬───┬─╮       ├────┤  NNNNNNNNN.......DDDDDD",
    "│ │sub│ ├──────▶│ db │  NnNnnnNn1223445eDddddD",
    "╰─┴───┴─╯       ├────┤  NNNNNNNNN.......DDDDDD",
    "                ╰────╯  ................DDDDDD",
  ])
  expect(picture("flowchart\nA[box]\nB(box)")).toEqual([
    "╭─────╮            ╭─────╮  NNNNNNN............NNNNNNN",
    "│ box │            │ box │  NnnnnnN............NnnnnnN",
    "╰─────╯            ╰─────╯  NNNNNNN............NNNNNNN",
  ])
})

test("a decision is an unfilled diamond, its label on the middle row; the border style draws every frame, caps included", () => {
  expect(picture("flowchart\nA{dec}")).toEqual([
    "  ╭───╮  ..NNNNN",
    "╭─╯   ╰─╮  NNN...NNN",
    "│  dec  │  N..nnn..N",
    "╰─╮   ╭─╯  NNN...NNN",
    "  ╰───╯  ..NNNNN",
  ])
  expect(picture("flowchart\nA[[s]]\nB{d}", { borderStyle: "double" })).toEqual([
    "                     ╔═╗  .....................NNN",
    "╔═╦═╦═╗            ╔═╝ ╚═╗  NNNNNNN............NNN.NNN",
    "║ ║s║ ║            ║  d  ║  NnNnNnN............N..n..N",
    "╚═╩═╩═╝            ╚═╗ ╔═╝  NNNNNNN............NNN.NNN",
    "                     ╚═╝  .....................NNN",
  ])
})

test("a label's lines are centred in the node, an italic run drawn italic", () => {
  const grid = draw("flowchart\nA[<i>it</i> x<br>longer]")
  expect(grid.rows.slice(0, 4).map((row) => row.map((cell) => cell.char).join("").trimEnd())).toEqual([
    "╭────────╮",
    "│  it x  │",
    "│ longer │",
    "╰────────╯",
  ])
  expect(grid.rows[1]!.slice(3, 7).map((cell) => cell.attributes)).toEqual([TextAttributes.ITALIC, TextAttributes.ITALIC, undefined, undefined])
  expect(grid.rows[2]!.slice(2, 8).map((cell) => cell.attributes)).toEqual(Array(6).fill(undefined))
  expect(picture("flowchart\nA[ab<br>bcd]").slice(1, 3)).toEqual(["│ ab  │  NnnnnnN", "│ bcd │  NnnnnnN"])
})

test("an edge leaves through a tee on its source's border and fades from the border colour along the cells it alone owns", () => {
  expect(picture("flowchart\nA --> B").slice(2, 7)).toEqual(["╰─┬─╯  NN2NN", "  │  ..3", "  │  ..4", "  │  ..5", "  ▼  ..e"])
  expect(picture("flowchart LR\nA[(db)] --> B").slice(2, 3)).toEqual(["│ db ├──────▶│ B │  Ddddd" + "vwwxyyz" + "eNnnnN"])
})

test("a thick edge is heavy but for its tee, an open one ends in its line, a two-headed one has a head at each end", () => {
  expect(picture("flowchart\nA ==> B").slice(2, 7)).toEqual(["╰─┬─╯  NN2NN", "  ┃  ..3", "  ┃  ..4", "  ┃  ..5", "  ▼  ..e"])
  expect(picture("flowchart\nA --- B").slice(6, 7)).toEqual(["  │  ..e"])
  expect(picture("flowchart\nA -.-> B")).toEqual(picture("flowchart\nA --> B"))
  expect(picture("flowchart\nA <--> B").slice(3, 7)).toEqual(["  ▲  ..e", "  │  ..4", "  │  ..5", "  ▼  ..e"])
})

test("an edge label is drawn padded in the label style beside its line, a line per row, or on a line across", () => {
  expect(picture("flowchart\nA -->|go| B").slice(3, 6)).toEqual(["  │  ..3", "  │ go  ..4lll", "  │  ..5"])
  expect(picture("flowchart\nA -->|ab<br>c| B").slice(4, 6)).toEqual(["  │ ab  ..4lll", "  │ c  ..5ll"])
  // The fade stops where the label covers the line.
  expect(picture("flowchart LR\nA -->|go| B")[1]).toBe("│ A ├─── go ───▶│ B │  Nnnn2345lllleeeeNnnnN")
})

test("a fan shares one bus whose junctions merge, each branch its own weight, the stem heavy only when every edge is; only the tee fades", () => {
  expect(picture("flowchart\nA --> B & C").slice(2, 7)).toEqual([
    "        ╰─┬─╯  ........NN3NN",
    "          │  ..........e",
    "  ╭───────┴────────╮  ..eeeeeeeeeeeeeeeeee",
    "  │                │  ..e................e",
    "  ▼                ▼  ..e................e",
  ])
  expect(picture("flowchart\nA ==> B & C").slice(3, 5)).toEqual(["          ┃  ..........e", "  ┏━━━━━━━┻━━━━━━━━┓  ..eeeeeeeeeeeeeeeeee"])
  expect(picture("flowchart\nA ==> B\nA --> C").slice(3, 5)).toEqual(["          │  ..........e", "  ┏━━━━━━━┴────────╮  ..eeeeeeeeeeeeeeeeee"])
  expect(picture("flowchart\nA --> B\nA ==> C").slice(3, 5)).toEqual(["          │  ..........e", "  ╭───────┴━━━━━━━━┓  ..eeeeeeeeeeeeeeeeee"])
})

test("a subgraph is a frame in the group style with its title set into the side the layout chose", () => {
  expect(picture("flowchart\nX --> A\nsubgraph S [Group]\nA\nend").slice(6)).toEqual([
    "╭───▼────╮  ggggeggggg",
    "│ ╭───╮  │  g.NNNNN..g",
    "│ │ A │  │  g.NnnnN..g",
    "│ ╰───╯  │  g.NNNNN..g",
    "╰─ Group ╯  ggGGGGGGGg",
  ])
  expect(picture("flowchart\nsubgraph S [Group]\nA\nend")[0]).toBe("╭─ Group ╮  ggGGGGGGGg")
  expect(picture("flowchart\nsubgraph S\nA\nend")[0]).toBe("╭─ S ───╮  ggGGGgggg")
  expect(picture("flowchart\nsubgraph S1\nA\nend\nsubgraph S2 [two<br>lines]\nB\nend").slice(0, 2)).toEqual([
    "                 ╭─ two ──╮  .................ggGGGGGggg",
    "╭─ S1 ──╮        │  lines │  ggGGGGggg........g.GGGGGGGg",
  ])
})

test("a fork defect, pinned: the first of two parallel edges ends beside its target with its head pointing past it", () => {
  // Both lanes end on the target's right side; the first, a straight run down, draws ▼ there (currently-open.md).
  expect(picture("flowchart\nA --> B\nA --> B").slice(1, 9)).toEqual([
    "│ A ├┬─╮  Nnnn3eee",
    "╰───╯│ │  NNNNNe.e",
    "     │ │  .....e.e",
    "     │ │  .....e.e",
    "     │ │  .....e.e",
    "     │ │  .....e.e",
    "╭───╮│ │  NNNNNe.e",
    "│ B │▼─╯  NnnnNeee",
  ])
})

test("a drawn cell merges by rule: labels and arrowheads hold, a blank edge cell yields, crossing lines join", () => {
  const grid = draw("flowchart\nA")
  const at = (x: number, y: number) => [grid.getCell(x, y)!.char, grid.getCell(x, y)!.style]
  grid.setCell(0, 5, "x", "label")
  grid.setCell(0, 5, "─", "edge")
  grid.setCell(1, 5, "─", "edge")
  grid.setCell(1, 5, " ", "edge")
  grid.setCell(2, 5, "▶", "edge")
  grid.setCell(2, 5, "│", "edge")
  grid.setCell(3, 5, "─", "edge")
  grid.setCell(3, 5, "▼", "edge")
  grid.setCell(4, 5, "─", "edge")
  grid.setCell(4, 5, "│", "edge")
  grid.setCell(5, 5, "─", "edge")
  grid.setCell(5, 5, "y", "node")
  grid.setCell(6, 5, "q", "node")
  grid.setCell(6, 5, "─", "edge")
  grid.setCell(7, 5, "─", "nodeBorder")
  grid.setCell(7, 5, "│", "edge")
  expect([0, 1, 2, 3, 4, 5, 6, 7].map((x) => at(x, 5))).toEqual([
    ["x", "label"],
    ["─", "edge"],
    ["▶", "edge"],
    ["▼", "edge"],
    ["┼", "edge"],
    ["y", "node"],
    ["─", "edge"],
    ["│", "edge"],
  ])
})
