import { BorderChars } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import {
  DIAGRAM_ARROW_HEADS,
  DIAGRAM_DIAMOND_CHARS,
  diagramArrowHead,
  diagramArrowHeadBetween,
  diagramDiamondCharactersFromBorder,
  diagramLineGlyph,
  drawDiagramDiamond,
  drawDiagramFrame,
  drawOrthogonalPath,
  fillDiagramFrameInterior,
  mergeDiagramLineGlyph,
} from "../../src/core/drawing"
import { diagramBoundsFromRect, point as p, type DiagramDirection } from "../../src/core/geometry"

function draw(width: number, height: number, paint: (set: (x: number, y: number, char: string) => void) => void) {
  const canvas = new DiagramCanvas(width, height)
  paint((x, y, char) => canvas.setCell(x, y, char))
  return canvas.toString()
}

const glyph = (dirs: DiagramDirection[], ...rest: Parameters<typeof diagramLineGlyph> extends [unknown, ...infer R] ? R : never) =>
  diagramLineGlyph(new Set(dirs), ...rest)

test("the arrow heads are the four filled and the four line arrows", () => {
  expect([...DIAGRAM_ARROW_HEADS]).toEqual(["▶", "◀", "▼", "▲", "→", "←", "↓", "↑"])
})

test("a line glyph joins the directions it is given, square, rounded or heavy", () => {
  const cases: Array<[DiagramDirection[], string, string, string]> = [
    [["up", "down", "left", "right"], "┼", "┼", "╋"],
    [["up", "down", "right"], "├", "├", "┣"],
    [["up", "down", "left"], "┤", "┤", "┫"],
    [["left", "right", "down"], "┬", "┬", "┳"],
    [["left", "right", "up"], "┴", "┴", "┻"],
    [["up", "right"], "└", "╰", "┗"],
    [["up", "left"], "┘", "╯", "┛"],
    [["down", "right"], "┌", "╭", "┏"],
    [["down", "left"], "┐", "╮", "┓"],
    [["up"], "│", "│", "┃"],
    [["down"], "│", "│", "┃"],
    [["left", "right"], "─", "─", "━"],
    [[], "─", "─", "━"],
  ]
  for (const [dirs, square, rounded, heavy] of cases) {
    expect([glyph(dirs), glyph(dirs, "rounded"), glyph(dirs, "square", "heavy")]).toEqual([square, rounded, heavy])
  }
  expect(glyph(["up", "right"], "rounded", "dashed")).toBe("╰")
})

test("merging two line glyphs joins their directions, heavy only when both are heavy; a non-line glyph does not merge", () => {
  expect(mergeDiagramLineGlyph("─", "│")).toBe("┼")
  expect(mergeDiagramLineGlyph("└", "┐")).toBe("┼")
  expect(mergeDiagramLineGlyph("╭", "┘")).toBe("┼")
  expect(mergeDiagramLineGlyph("┤", "─")).toBe("┼")
  expect(mergeDiagramLineGlyph("├", "┬")).toBe("┼")
  expect(mergeDiagramLineGlyph("┴", "│")).toBe("┼")
  expect(mergeDiagramLineGlyph("┌", "╭", "rounded")).toBe("╭")
  expect(mergeDiagramLineGlyph("╮", "┐")).toBe("┐")
  expect(mergeDiagramLineGlyph("╰", "╰")).toBe("└")
  expect(mergeDiagramLineGlyph("╯", "─")).toBe("┴")
  expect(mergeDiagramLineGlyph("━", "┃")).toBe("╋")
  expect(mergeDiagramLineGlyph("┏", "┛")).toBe("╋")
  expect(mergeDiagramLineGlyph("┓", "┗")).toBe("╋")
  expect(mergeDiagramLineGlyph("┣", "┫")).toBe("╋")
  expect(mergeDiagramLineGlyph("┳", "┻")).toBe("╋")
  expect(mergeDiagramLineGlyph("╋", "━")).toBe("╋")
  expect(mergeDiagramLineGlyph("━", "│")).toBe("┼")
  expect(mergeDiagramLineGlyph("│", "━")).toBe("┼")
  expect(mergeDiagramLineGlyph("├", "└")).toBe("├")
  expect(mergeDiagramLineGlyph("┬", "┐")).toBe("┬")
  expect(mergeDiagramLineGlyph("┼", "┼")).toBe("┼")
  expect(mergeDiagramLineGlyph("─", "A")).toBeUndefined()
  expect(mergeDiagramLineGlyph("▶", "─")).toBeUndefined()
})

test("an arrow head points the direction asked, filled or as a line; between two points it follows them, right when they meet", () => {
  expect((["right", "left", "up", "down"] as const).map((d) => diagramArrowHead(d))).toEqual(["▶", "◀", "▲", "▼"])
  expect((["right", "left", "up", "down"] as const).map((d) => diagramArrowHead(d, "line"))).toEqual(["→", "←", "↑", "↓"])
  expect(diagramArrowHeadBetween(p(0, 3), p(0, 1))).toBe("▲")
  expect(diagramArrowHeadBetween(p(0, 1), p(0, 3), "line")).toBe("↓")
  expect(diagramArrowHeadBetween(p(2, 2), p(2, 2))).toBe("▶")
  expect(diagramArrowHeadBetween(p(2, 2), p(3, 3), "line")).toBe("→")
})

test("a frame is drawn on the bounds' edges and its interior is everything inside them", () => {
  expect(draw(5, 3, (set) => drawDiagramFrame(diagramBoundsFromRect(0, 0, 4, 3), BorderChars.single, set))).toBe("┌──┐\n│  │\n└──┘")
  const inside: string[] = []
  fillDiagramFrameInterior(diagramBoundsFromRect(1, 1, 4, 4), (x, y) => inside.push(`${x},${y}`))
  expect(inside).toEqual(["2,2", "3,2", "2,3", "3,3"])
})

test("a diamond has caps inset by two, shoulders, sides and a foot; its characters map from a border set, rounded by default", () => {
  expect(diagramDiamondCharactersFromBorder(BorderChars.rounded)).toEqual(DIAGRAM_DIAMOND_CHARS)
  expect(draw(7, 5, (set) => drawDiagramDiamond(diagramBoundsFromRect(0, 0, 7, 5), set))).toBe(
    "  ╭─╮\n╭─╯ ╰─╮\n│     │\n╰─╮ ╭─╯\n  ╰─╯",
  )
  expect(draw(9, 6, (set) => drawDiagramDiamond(diagramBoundsFromRect(0, 0, 9, 6), set, diagramDiamondCharactersFromBorder(BorderChars.single)))).toBe(
    "  ┌───┐\n┌─┘   └─┐\n│       │\n│       │\n└─┐   ┌─┘\n  └───┘",
  )
})

test("a narrow diamond insets its caps by half its width less two, at most two, so they stay apart", () => {
  const diamond = (width: number) => draw(width, 4, (set) => drawDiagramDiamond(diagramBoundsFromRect(0, 0, width, 4), set))
  expect(diamond(4)).toBe(" ╭╮\n╭╯╰╮\n╰╮╭╯\n ╰╯")
  expect(diamond(5)).toBe(" ╭─╮\n╭╯ ╰╮\n╰╮ ╭╯\n ╰─╯")
  expect(diamond(6)).toBe("  ╭╮\n╭─╯╰─╮\n╰─╮╭─╯\n  ╰╯")
})

test("a diamond under 4 wide or under 4 tall has no room for caps and shoulders, so it is drawn as a box", () => {
  const diamond = (width: number, height: number) =>
    draw(width, height, (set) => drawDiagramDiamond(diagramBoundsFromRect(0, 0, width, height), set))
  expect(diamond(3, 4)).toBe("╭─╮\n│ │\n│ │\n╰─╯")
  expect(diamond(2, 4)).toBe("╭╮\n││\n││\n╰╯")
  expect(diamond(7, 3)).toBe("╭─────╮\n│     │\n╰─────╯")
})

test("a diamond of any size from 2 by 3 and a frame write each cell once, so a merging canvas sees no stray glyph", () => {
  const diamonds = [2, 3, 4, 5, 6, 7, 8, 9].flatMap((width) =>
    [3, 4, 5, 6].map((height) => (set: (x: number, y: number, char: string) => void) =>
      drawDiagramDiamond(diagramBoundsFromRect(0, 0, width, height), set),
    ),
  )
  for (const paint of [
    ...diamonds,
    (set: (x: number, y: number, char: string) => void) => drawDiagramFrame(diagramBoundsFromRect(0, 0, 5, 4), BorderChars.single, set),
  ]) {
    const writes = new Map<string, number>()
    paint((x, y) => writes.set(`${x},${y}`, (writes.get(`${x},${y}`) ?? 0) + 1))
    expect([...writes.values()].every((count) => count === 1)).toBe(true)
  }
})

test("an orthogonal path draws every cell but its last, with a joined glyph at each corner", () => {
  const path = [p(0, 0), p(3, 0), p(3, 2), p(5, 2)]
  expect(draw(6, 3, (set) => drawOrthogonalPath(path, set))).toBe("───┐\n   │\n   └─")
  expect(draw(6, 3, (set) => drawOrthogonalPath(path, set, { cornerStyle: "rounded" }))).toBe("───╮\n   │\n   ╰─")
  expect(draw(6, 3, (set) => drawOrthogonalPath(path, set, { lineStyle: "heavy", cornerStyle: "rounded" }))).toBe("━━━┓\n   ┃\n   ┗━")
})

test("a dashed path draws every other cell, counted on from one segment to the next, corners always", () => {
  expect(draw(4, 5, (set) => drawOrthogonalPath([p(0, 0), p(3, 0), p(3, 4)], set, { lineStyle: "dashed" }))).toBe("─ ─┐\n\n   │\n\n")
})

test("a diagonal step draws nothing, and the point before it keeps the one direction it has", () => {
  expect(draw(3, 3, (set) => drawOrthogonalPath([p(0, 0), p(2, 2)], set))).toBe("\n\n")
  expect(draw(4, 3, (set) => drawOrthogonalPath([p(0, 0), p(2, 0), p(3, 2)], set))).toBe("───\n\n")
  expect(draw(4, 3, (set) => drawOrthogonalPath([p(0, 0), p(1, 1), p(3, 1)], set))).toBe("\n ──\n")
})
