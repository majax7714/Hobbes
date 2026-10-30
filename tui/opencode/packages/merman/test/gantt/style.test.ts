import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderGanttGridStyledText, renderGanttGridText, type GanttGrid } from "../../src/gantt/render-grid"
import { resolveGanttStyleColors } from "../../src/gantt/style"

const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))

test("with no colours given, every base style takes the default theme", () => {
  expect(asInts(resolveGanttStyleColors())).toMatchObject({
    title: [228, 239, 232, 255],
    axis: [111, 138, 126, 255],
    section: [154, 184, 169, 255],
    task: [134, 225, 200, 255],
    active: [134, 225, 200, 255],
    critical: [230, 177, 126, 255],
    done: [111, 138, 126, 255],
    milestone: [198, 160, 246, 255],
  })
})

test("a given colour wins for its own style", () => {
  const styles = ["title", "axis", "section", "task", "active", "critical", "done", "milestone"] as const
  const given = Object.fromEntries(styles.map((style, index) => [style, ints(index, index, index)]))
  expect(asInts(resolveGanttStyleColors(given))).toMatchObject(
    Object.fromEntries(styles.map((style, index) => [style, [index, index, index, 255]])),
  )
})

test("the track tones blend the axis colour 35%, 55% and 72% of the way to the background", () => {
  const tones = (colors: Parameters<typeof resolveGanttStyleColors>[0]) => {
    const resolved = resolveGanttStyleColors(colors)
    return [resolved.trackMedium, resolved.trackDim, resolved.trackFaint].map((color) => color.toInts())
  }
  expect(tones({ axis: ints(200, 100, 0), background: ints(0, 100, 200) })).toEqual([
    [130, 100, 70, 255],
    [90, 100, 110, 255],
    [56, 100, 144, 255],
  ])
  // With no background given the dark default, [13, 17, 23], is the far end.
  expect(tones({ axis: ints(213, 217, 223) })).toEqual([
    [143, 147, 153, 255],
    [103, 107, 113, 255],
    [69, 73, 79, 255],
  ])
})

function grid(): GanttGrid {
  const canvas: GanttGrid = new DiagramCanvas(3, 3)
  canvas.setText(0, 0, "ab", "axis")
  canvas.setCell(2, 0, "c")
  canvas.setCell(0, 1, "d", "done")
  return canvas
}

test("the grid's text drops trailing blank rows", () => {
  expect(renderGanttGridText(grid())).toBe("abc\nd")
})

test("styled text colours each run by its style, leaves an unstyled run uncoloured, and drops trailing blank rows", () => {
  const colors = resolveGanttStyleColors({ axis: ints(1, 2, 3), done: ints(4, 5, 6) })
  const text = renderGanttGridStyledText(grid(), colors)
  expect(text).toBeInstanceOf(StyledText)
  expect(text.chunks.map((chunk) => [chunk.text, chunk.fg?.toInts()])).toEqual([
    ["ab", [1, 2, 3, 255]],
    ["c", undefined],
    ["\n", undefined],
    ["d", [4, 5, 6, 255]],
  ])
})
