import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderSequenceGridStyledText, renderSequenceGridText, type SequenceGrid } from "../../src/sequence/render-grid"
import { resolveSequenceStyleColors, sequenceStyleBackgroundColor, sequenceStyleColor } from "../../src/sequence/style"

const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))
type Ints = [number, number, number, number]
const ramp = (prefix: string, steps: number[][]): Record<string, Ints> =>
  Object.fromEntries(steps.map((rgb, index) => [`${prefix}${index + 1}`, [...rgb, 255] as Ints]))

test("with no colours given each style takes its default", () => {
  const colors = asInts(resolveSequenceStyleColors())
  expect(colors).toMatchObject({
    participant: [228, 239, 232, 255],
    lifeline: [111, 138, 126, 255],
    group: [76, 99, 89, 255],
    request: [134, 225, 200, 255],
    response: [230, 177, 126, 255],
    fragment: [154, 184, 169, 255],
    fragmentLabelBg: [28, 43, 36, 255],
    note: [215, 229, 221, 255],
    noteBg: [36, 56, 47, 255],
  })
  expect(Object.keys(colors)).toHaveLength(9 + 5 + 5 + 3)
})

test("each colour given replaces its default; the fades run from the lifeline to the arrow, the ramp from header to lifeline", () => {
  const given = {
    participant: ints(40, 80, 120),
    lifeline: ints(0, 0, 0),
    group: ints(1, 1, 1),
    request: ints(60, 120, 180),
    response: ints(120, 60, 0),
    fragment: ints(2, 2, 2),
    fragmentLabelBg: ints(3, 3, 3),
    note: ints(4, 4, 4),
    noteBg: ints(5, 5, 5),
  }
  expect(asInts(resolveSequenceStyleColors(given))).toEqual({
    ...asInts(given),
    ...ramp(
      "requestFade",
      [1, 2, 3, 4, 5].map((k) => [10 * k, 20 * k, 30 * k]),
    ),
    ...ramp(
      "responseFade",
      [1, 2, 3, 4, 5].map((k) => [20 * k, 10 * k, 0]),
    ),
    ...ramp("lifelineRamp", [
      [30, 60, 90],
      [20, 40, 60],
      [10, 20, 30],
    ]),
  })
})

test("a note or its badge takes the note colour on the note background; a fragment label the fragment colour on its own", () => {
  const colors = resolveSequenceStyleColors({
    note: ints(1, 1, 1),
    noteBg: ints(2, 2, 2),
    fragment: ints(3, 3, 3),
    fragmentLabelBg: ints(4, 4, 4),
    request: ints(5, 5, 5),
  })
  const fg = (["noteBadge", "note", "fragmentLabel", "fragment", "request", undefined] as const).map((style) =>
    sequenceStyleColor(style, colors)?.toInts(),
  )
  expect(fg).toEqual([[1, 1, 1, 255], [1, 1, 1, 255], [3, 3, 3, 255], [3, 3, 3, 255], [5, 5, 5, 255], undefined])
  const bg = (["noteBadge", "note", "fragmentLabel", "fragment", "request", undefined] as const).map((style) =>
    sequenceStyleBackgroundColor(style, colors)?.toInts(),
  )
  expect(bg).toEqual([[2, 2, 2, 255], [2, 2, 2, 255], [4, 4, 4, 255], undefined, undefined, undefined])
})

function grid(): SequenceGrid {
  const canvas: SequenceGrid = new DiagramCanvas(3, 3)
  canvas.setText(0, 0, "n", "noteBadge")
  canvas.setCell(1, 0, "x")
  canvas.setCell(0, 1, "│", "lifeline")
  canvas.setCell(1, 1, "f", "fragmentLabel")
  return canvas
}

test("the grid's text keeps its trailing blank rows", () => {
  expect(renderSequenceGridText(grid())).toBe("nx\n│f\n")
})

// subsume reads this case as redundant: no fault it plants changes the wiring alone. Planted by hand (the
// background callback dropped), this is the only case that fails.
test("styled text gives each run its colour and background, an unstyled run neither", () => {
  const colors = resolveSequenceStyleColors({
    note: ints(1, 1, 1),
    noteBg: ints(2, 2, 2),
    lifeline: ints(3, 3, 3),
    fragment: ints(4, 4, 4),
    fragmentLabelBg: ints(5, 5, 5),
  })
  const text = renderSequenceGridStyledText(grid(), colors)
  expect(text).toBeInstanceOf(StyledText)
  expect(text.chunks.map((chunk) => [chunk.text, chunk.fg?.toInts(), chunk.bg?.toInts()])).toEqual([
    ["n", [1, 1, 1, 255], [2, 2, 2, 255]],
    ["x", undefined, undefined],
    ["\n", undefined, undefined],
    ["│", [3, 3, 3, 255], undefined],
    ["f", [4, 4, 4, 255], [5, 5, 5, 255]],
    ["\n", undefined, undefined],
  ])
})
