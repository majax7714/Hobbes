import { expect, test } from "bun:test"
import { drawGanttDiagramGrid } from "../../src/gantt/drawing"
import { parseMermaidGanttDiagram } from "../../src/gantt/parser"
import { renderGanttGridText, type GanttGrid } from "../../src/gantt/render-grid"
import type { GanttDiagramRenderOptions } from "../../src/gantt/types"

const draw = (body: string, options: GanttDiagramRenderOptions = {}) =>
  drawGanttDiagramGrid(parseMermaidGanttDiagram(`gantt\n${body}`), options)
const lines = (grid: GanttGrid) => renderGanttGridText(grid).split("\n")

// One row's styles as runs, e.g. "trackFaint×6 task×12".
function styleRuns(grid: GanttGrid, y: number, from = 0): string {
  const runs: Array<[string, number]> = []
  for (const cell of grid.rows[y]!.slice(from)) {
    const style = cell.style ?? "-"
    const last = runs.at(-1)
    if (last && last[0] === style) last[1] += 1
    else runs.push([style, 1])
  }
  return runs.map(([style, count]) => `${style}×${count}`).join(" ")
}

// Label "A" (width 1) and a 27-cell limit give a 24-cell chart starting at x = 3.
const narrow = { layoutMaxWidth: 27 }
// Z spans the four days, so T, from the 2nd to the 4th, runs from offset 6 to 17 of the 24.
const SPAN = "Z: 2024-01-01, 4d\nT: 2024-01-02, 2d"
const taskRow = (options: GanttDiagramRenderOptions) => lines(draw(SPAN, { ...narrow, ...options }))[3]!.slice(3)

test("a chart with no entries draws nothing, title or not", () => {
  for (const body of ["", "title Plan"]) {
    const grid = draw(body)
    expect([grid.width, grid.height]).toEqual([0, 0])
  }
})

test("a blank row comes before every section but the first unless compact; with no tasks the labels are the whole chart", () => {
  const spaced = draw("title Plan\nsection Alpha\nsection B\nsection Gamma")
  expect([spaced.width, spaced.height]).toEqual([5, 5])
  expect(lines(spaced)).toEqual(["Alpha", "", "B", "", "Gamma"])
  expect(styleRuns(spaced, 0)).toBe("section×5")
  const compact = draw("section Alpha\nsection B", { sections: "compact" })
  expect(lines(compact)).toEqual(["Alpha", "B"])
  const body = "section S1\nA: 2024-01-01, 1d\nsection S2\nB: 2024-01-01, 1d"
  const heads = (options: GanttDiagramRenderOptions) =>
    lines(draw(body, { ...narrow, ...options }))
      .slice(2)
      .map((line) => line.slice(0, 2))
  expect(heads({})).toEqual(["S1", "A ", "", "S2", "B "])
  expect(heads({ sections: "compact" })).toEqual(["S1", "A ", "S2", "B "])
})

test("the chart is the room left after the labels and a two-cell gap, held between 24 and 64 cells", () => {
  const sizes = [undefined, 40, 10, 66, 68].map((layoutMaxWidth) => {
    const grid = draw("A: 2024-01-01, 1d", { layoutMaxWidth })
    return [grid.width, grid.height]
  })
  expect(sizes).toEqual([
    [67, 3],
    [40, 3],
    [27, 3],
    [66, 3],
    [67, 3],
  ])
  expect(draw("Longer: 2024-01-01, 1d", narrow).width).toBe(6 + 2 + 24)
  // With no limit given the room is 120 cells, so a 55-cell label leaves 63 for the chart.
  expect(draw(`${"x".repeat(55)}: 2024-01-01, 1d`).width).toBe(55 + 2 + 63)
})

test("the axis is a rule with a tick and a date label centred at each step, leaning left when even, the end labels held inside", () => {
  const grid = draw("axisFormat %d\nA: 2024-01-01, 4d", narrow)
  expect(lines(grid)).toEqual([
    "   01   02    03   04    05",
    "   ┬─────┬─────┬────┬─────┬",
    "A  ────────────────────────",
  ])
  expect([styleRuns(grid, 0, 3), styleRuns(grid, 1, 3)]).toEqual([
    "axis×2 -×3 axis×2 -×4 axis×2 -×3 axis×2 -×4 axis×2",
    "axis×24",
  ])
  expect(lines(draw("axisFormat %d.\nA: 2024-01-01, 4d", narrow))[0]).toBe("   01.  02.   03.  04.  05.")
})

test("the step is the smallest of the fixed steps covering a quarter of the span, with ticks on its multiples from the epoch", () => {
  // Five days: a quarter is 1.25 days, so the step is two days, and 2024-01-01 is an odd day from the epoch.
  const grid = draw("axisFormat %d\nA: 2024-01-01, 5d", narrow)
  expect(lines(grid).slice(0, 2)).toEqual(["       02       04       06", "   ─────┬────────┬────────┬"])
  // Past four years a quarter outruns every step, and the largest, a 365-day year, is used.
  const years = draw("dateFormat x\naxisFormat %Y\nA: 0, 200000000000", narrow)
  expect([...lines(years)[1]!].filter((char) => char === "┬")).toHaveLength(7)
})

test("when no step multiple falls in the span, the two ends are ticked", () => {
  const grid = draw("dateFormat x\naxisFormat t%S\nA: 1, 2", narrow)
  expect(lines(grid).slice(0, 2)).toEqual(["   t00                  t00", "   ┬──────────────────────┬"])
})

test("the axis format replaces %Y, %m, %d, %H, %M and %S with the UTC date's parts, zero-padded, and keeps the rest", () => {
  const grid = draw(
    "dateFormat YYYY-MM-DD HH:mm:ss\naxisFormat [%Y/%m/%d %H:%M:%S %q]\nA: 2024-03-04 05:06:07, 2024-03-04 05:06:07",
    {
      layoutMaxWidth: 120,
    },
  )
  expect(lines(grid)[0]!.trim()).toBe("[2024/03/04 05:06:07 %q]")
})

test("a title is centred over the chart with a blank row beneath, and held at the left edge when too wide", () => {
  // Five cells in a 24-cell chart at x = 3: the odd cell left over goes to the right.
  const grid = draw("title Plans\nA: 2024-01-01, 1d", narrow)
  expect(grid.height).toBe(5)
  expect(lines(grid)[0]).toBe(`${" ".repeat(12)}Plans`)
  expect(lines(grid)[1]).toBe("")
  expect(styleRuns(grid, 0, 12)).toBe("title×5 -×10")
  const wide = draw(`title ${"abcdefghij".repeat(4)}\nA: 2024-01-01, 1d`, narrow)
  expect(lines(wide)[0]).toBe("abcdefghij".repeat(4).slice(0, 27))
})

test("labels sit left by default, right-aligned when asked, with sections always at the left edge", () => {
  const body = "section Sec\nA: 2024-01-01, 1d\nLonger: 2024-01-01, 1d"
  const label = (options: GanttDiagramRenderOptions) =>
    lines(draw(body, options))
      .slice(2)
      .map((line) => line.slice(0, 6))
  expect(label({})).toEqual(["Sec", "A     ", "Longer"])
  expect(label({ labels: "left" })).toEqual(["Sec", "A     ", "Longer"])
  expect(label({ labels: "right" })).toEqual(["Sec", "     A", "Longer"])
})

test("as a tree, a task hangs off its section by ├─, the last before a section or the end by └─", () => {
  const grid = draw("A: 2024-01-01, 1d\nsection S\nB: 2024-01-01, 1d\nC: 2024-01-01, 1d", { labels: "tree" })
  expect(
    lines(grid)
      .slice(2)
      .map((line) => line.slice(0, 7).trimEnd()),
  ).toEqual(["  └─ A", "", "S", "  ├─ B", "  └─ C"])
  expect(grid.width).toBe(6 + 2 + 64)
})

test("a task's label is drawn in its state's style, a section's in the section style", () => {
  const grid = draw("section S\nA: crit, 2024-01-01, 1d\nB: done, 2024-01-01, 1d", narrow)
  expect([
    styleRuns(grid, 2, 0).split(" ")[0],
    styleRuns(grid, 3, 0).split(" ")[0],
    styleRuns(grid, 4, 0).split(" ")[0],
  ]).toEqual(["section×1", "critical×1", "done×1"])
})

test("by default a task is a thin line on a faint line track; the track may be dots, in a medium, dim or faint tone, and may mark the task's ends with points in the track's tone", () => {
  expect(taskRow({})).toBe("─".repeat(24))
  expect(styleRuns(draw(SPAN, narrow), 3, 3)).toBe("trackFaint×6 task×12 trackFaint×6")
  expect(taskRow({ track: "dots" })).toBe(`${"·".repeat(6)}${"─".repeat(12)}${"·".repeat(6)}`)
  for (const [trackTone, style] of [
    ["medium", "trackMedium"],
    ["dim", "trackDim"],
    ["faint", "trackFaint"],
  ] as const) {
    expect(styleRuns(draw(SPAN, { ...narrow, trackTone }), 3, 3)).toBe(`${style}×6 task×12 ${style}×6`)
  }
  expect(taskRow({ endpoints: "points" })).toBe(`${"─".repeat(6)}●${"─".repeat(10)}●${"─".repeat(6)}`)
  expect(styleRuns(draw(SPAN, { ...narrow, endpoints: "points" }), 3, 3)).toBe("trackFaint×7 task×10 trackFaint×7")
})

// bench/subsume reads this case as redundant: it plants no fault in the track's glyph. Drawing the track
// thin whatever the line fails this case alone (planted by hand, 2026-10-30).
test("the line may be thin, heavy, double or dashed, on the task and on a line track alike", () => {
  for (const [line, glyph] of [
    ["thin", "─"],
    ["heavy", "━"],
    ["double", "═"],
    ["dashed", "╌"],
  ] as const) {
    expect(taskRow({ line })).toBe(glyph.repeat(24))
  }
})

test("block, capsule, points and rail draw no track, only the task's span with its own ends", () => {
  const pad = " ".repeat(6)
  expect(taskRow({ style: "block" })).toBe(`${pad}${"█".repeat(12)}`)
  expect(taskRow({ style: "points" })).toBe(`${pad}●${"─".repeat(10)}●`)
  expect(taskRow({ style: "rail" })).toBe(`${pad}┣${"─".repeat(10)}┫`)
  expect(taskRow({ style: "capsule" })).toBe(`${pad}╶${"─".repeat(10)}╴`)
  expect(taskRow({ style: "rail", line: "double" })).toBe(`${pad}┣${"═".repeat(10)}┫`)
  for (const [line, row] of [
    ["thin", `╶${"─".repeat(10)}╴`],
    ["dashed", `╶${"╌".repeat(10)}╴`],
    ["double", `╞${"═".repeat(10)}╡`],
    ["heavy", `╺${"━".repeat(10)}╸`],
  ] as const) {
    expect(taskRow({ style: "capsule", line })).toBe(`${pad}${row}`)
  }
  expect(styleRuns(draw(`${SPAN.replace("T:", "T: active,")}`, { ...narrow, style: "points" }), 3, 3)).toBe(
    "-×6 active×12 -×6",
  )
})

test("a milestone, or a task that ends where it starts, is a diamond at its start with no track", () => {
  const grid = draw("Z: 2024-01-01, 4d\nM: milestone, 2024-01-02, 2d\nP: 2024-01-03, 0d", narrow)
  expect(lines(grid).slice(3)).toEqual([`M  ${" ".repeat(6)}◆`, `P  ${" ".repeat(12)}◆`])
  expect([grid.getCell(9, 3)!.style, grid.getCell(15, 4)!.style]).toEqual(["milestone", "task"])
})

test("the span is at least a millisecond: tasks all on one instant sit at its start, and a one-millisecond task fills it", () => {
  const grid = draw("A: 2024-01-01, 0d\nB: 2024-01-01, 0d", narrow)
  expect(lines(grid)).toEqual(["   2024-01-01", "   ┬───────────────────────", "A  ◆", "B  ◆"])
  expect(styleRuns(draw("dateFormat x\nA: 0, 1", narrow), 2, 3)).toBe("task×24")
})
