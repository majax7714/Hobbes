import { expect, test } from "bun:test"
import { drawTimelineDiagramGrid } from "../../src/timeline/drawing"
import { parseMermaidTimelineDiagram } from "../../src/timeline/parser"
import { renderTimelineGridText, type TimelineGrid } from "../../src/timeline/render-grid"
import type { TimelineDiagramRenderOptions } from "../../src/timeline/types"

const draw = (body: string, options?: TimelineDiagramRenderOptions) =>
  drawTimelineDiagramGrid(parseMermaidTimelineDiagram(`timeline\n${body}`), options)
const lines = (grid: TimelineGrid) => renderTimelineGridText(grid).split("\n")
const size = (grid: TimelineGrid) => [grid.width, grid.height]

// One row's styles as runs, e.g. "period×4 -×1 periodFade1×1".
function styleRuns(grid: TimelineGrid, y: number): string {
  const runs: Array<[string, number]> = []
  for (const cell of grid.rows[y]!) {
    const style = cell.style ?? "-"
    const last = runs.at(-1)
    if (last && last[0] === style) last[1] += 1
    else runs.push([style, 1])
  }
  return runs.map(([style, count]) => `${style}×${count}`).join(" ")
}

test("a timeline with no entries draws only its title, each line centred, with no blank row after it", () => {
  expect(size(draw(""))).toEqual([0, 0])
  const titled = draw("title History")
  expect(size(titled)).toEqual([7, 1])
  expect(lines(titled)).toEqual(["History"])
  expect(styleRuns(titled, 0)).toBe("title×7")
  expect(lines(draw("title Longer<br>A"))).toEqual(["Longer", "  A"])
  expect(lines(draw("title A"))).toEqual(["A"])
  // A title of only a line break has no width, so nothing is drawn.
  expect(size(draw("title <br>"))).toEqual([0, 0])
})

test("a period is its label, a gap, a three-cell join, a dot on the spine, two cells, then its event; the spine runs one row past", () => {
  const grid = draw("2001 : One")
  // The label's 4, the spine's offset 4 and the events' 3, the event's 3, and one cell spare.
  expect(size(grid)).toEqual([15, 2])
  expect(lines(grid)).toEqual(["2001 ───●  One", "        │"])
  expect(styleRuns(grid, 0)).toBe("period×4 -×1 periodFade1×1 periodFade2×1 periodFade3×1 spine×1 -×2 event×3 -×1")
  expect(styleRuns(grid, 1)).toBe("-×8 spine×1 -×6")
  // The events' column is as wide as the widest event, not the last.
  expect(size(draw("2001 : One : B"))).toEqual([15, 3])
  // The direction is parsed for Mermaid but never changes the drawing.
  expect(lines(draw("2001 : One", { direction: "TD" }))).toEqual(lines(grid))
  expect(lines(drawTimelineDiagramGrid(parseMermaidTimelineDiagram("timeline TD\n2001 : One")))).toEqual(lines(grid))
})

test("labels are right-aligned to the widest; a section opens the spine with ┐, and one after anything else joins it with ┤", () => {
  const grid = draw("section Early\n2001 : One\nsection Later\n2002")
  expect(size(grid)).toEqual([16, 8])
  expect(lines(grid)).toEqual([
    "Early ───┐",
    "         │",
    " 2001 ───●  One",
    "         │",
    "Later ───┤",
    "         │",
    " 2002 ───●",
    "         │",
  ])
  expect(styleRuns(grid, 0)).toBe("section×5 -×1 sectionFade1×1 sectionFade2×1 sectionFade3×1 spine×1 -×6")
  expect(styleRuns(grid, 1)).toBe("-×9 spine×1 -×6")
  // A period opens the spine too, so a first section after it joins, and so does a section after a section.
  expect(lines(draw("2001\nsection S"))).toEqual(["2001 ───●", "        │", "   S ───┤", "        │"])
  expect(lines(draw("section A\nsection B"))).toEqual(["A ───┐", "     │", "B ───┤", "     │"])
})

test("a period is as tall as the taller of its label's lines and its events' lines; the join is on its first row only", () => {
  expect(lines(draw("a<br>bb : X : Y<br>Z\n2002 : W"))).toEqual([
    "   a ───●  X",
    "  bb    │  Y",
    "        │  Z",
    "        │",
    "2002 ───●  W",
    "        │",
  ])
  expect(lines(draw("a<br>b<br>c : X"))).toEqual(["a ───●  X", "b    │", "c    │", "     │"])
})

test("a section of several lines carries the spine beside each line after its first", () => {
  const grid = draw("section A<br>Bee\n2001")
  expect(lines(grid)).toEqual(["   A ───┐", " Bee    │", "        │", "2001 ───●", "        │"])
  expect(styleRuns(grid, 1)).toBe("-×1 section×3 -×4 spine×1 -×3")
})

test("a title is centred over the body with a blank row after it; a wider title widens the grid, and the body stays left", () => {
  expect(lines(draw("title History\n2001 : One"))).toEqual(["    History", "", "2001 ───●  One", "        │"])
  const wide = draw("title Twelve chars\n1 : x")
  expect(size(wide)).toEqual([12, 4])
  expect(lines(wide)).toEqual(["Twelve chars", "", "1 ───●  x", "     │"])
})

test("widths are terminal cells: a wide character counts two, and a label of only line breaks none", () => {
  const grid = draw("section 年代\n2001 : 事件")
  expect(size(grid)).toEqual([16, 4])
  expect(lines(grid)).toEqual(["年代 ───┐", "        │", "2001 ───●  事件", "        │"])
  expect(lines(draw("<br> : x"))).toEqual([" ───●  x", "    │", "    │"])
})
