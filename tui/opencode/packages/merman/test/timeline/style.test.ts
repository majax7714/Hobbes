import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderTimelineGridStyledText, renderTimelineGridText, type TimelineGrid } from "../../src/timeline/render-grid"
import {
  resolveTimelineStyleColors,
  TIMELINE_PERIOD_FADE_STYLES,
  TIMELINE_SECTION_FADE_STYLES,
} from "../../src/timeline/style"

const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))

test("with no colours given, every base style takes the default theme", () => {
  expect(asInts(resolveTimelineStyleColors())).toMatchObject({
    title: [228, 239, 232, 255],
    section: [154, 184, 169, 255],
    period: [230, 177, 126, 255],
    spine: [111, 138, 126, 255],
    event: [134, 225, 200, 255],
  })
})

test("a given colour wins for its own style", () => {
  const styles = ["title", "section", "period", "spine", "event"] as const
  const given = Object.fromEntries(styles.map((style, index) => [style, ints(index, index, index)]))
  expect(asInts(resolveTimelineStyleColors(given))).toMatchObject(
    Object.fromEntries(styles.map((style, index) => [style, [index, index, index, 255]])),
  )
})

// The only case on the blend amounts, which subsume never plants (it skips decimals); 0.67 -> 0.6 by hand fails it alone.
test("the three section and three period fades blend their colour 50%, 67% and 83% of the way to the spine's", () => {
  expect([TIMELINE_SECTION_FADE_STYLES, TIMELINE_PERIOD_FADE_STYLES]).toEqual([
    ["sectionFade1", "sectionFade2", "sectionFade3"],
    ["periodFade1", "periodFade2", "periodFade3"],
  ])
  const fades = (colors: Parameters<typeof resolveTimelineStyleColors>[0]) => {
    const resolved = resolveTimelineStyleColors(colors)
    return [
      [resolved.sectionFade1, resolved.sectionFade2, resolved.sectionFade3].map((color) => color.toInts()),
      [resolved.periodFade1, resolved.periodFade2, resolved.periodFade3].map((color) => color.toInts()),
    ]
  }
  expect(fades({ section: ints(200, 100, 0), period: ints(0, 0, 0), spine: ints(0, 100, 200) })).toEqual([
    [
      [100, 100, 100, 255],
      [66, 100, 134, 255],
      [34, 100, 166, 255],
    ],
    [
      [0, 50, 100, 255],
      [0, 67, 134, 255],
      [0, 83, 166, 255],
    ],
  ])
  // With no spine given, the default spine, [111, 138, 126], is the far end.
  expect(fades({ section: ints(211, 238, 226), period: ints(11, 38, 26) })).toEqual([
    [
      [161, 188, 176, 255],
      [144, 171, 159, 255],
      [128, 155, 143, 255],
    ],
    [
      [61, 88, 76, 255],
      [78, 105, 93, 255],
      [94, 121, 109, 255],
    ],
  ])
})

function grid(): TimelineGrid {
  const canvas: TimelineGrid = new DiagramCanvas(3, 3)
  canvas.setText(0, 0, "ab", "spine")
  canvas.setCell(2, 0, "c")
  canvas.setCell(0, 1, "d", "periodFade2")
  return canvas
}

test("the grid's text drops trailing blank rows", () => {
  expect(renderTimelineGridText(grid())).toBe("abc\nd")
})

test("styled text colours each run by its style, leaves an unstyled run uncoloured, and drops trailing blank rows", () => {
  const colors = resolveTimelineStyleColors({ spine: ints(1, 2, 3) })
  const text = renderTimelineGridStyledText(grid(), colors)
  expect(text).toBeInstanceOf(StyledText)
  expect(text.chunks.map((chunk) => [chunk.text, chunk.fg?.toInts()])).toEqual([
    ["ab", [1, 2, 3, 255]],
    ["c", undefined],
    ["\n", undefined],
    ["d", colors.periodFade2.toInts()],
  ])
})
