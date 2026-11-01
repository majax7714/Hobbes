import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderStateGridStyledText, renderStateGridText, type StateGrid } from "../../src/state/render-grid"
import { resolveStateStyleColors } from "../../src/state/style"

type Ints = [number, number, number, number]
const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))
const ramp = (prefix: string, steps: number[][]): Record<string, Ints> =>
  Object.fromEntries(steps.map((rgb, index) => [`${prefix}${index + 1}`, [...rgb, 255] as Ints]))

test("with no colours given each style takes its default", () => {
  const colors = asInts(resolveStateStyleColors())
  expect(colors).toMatchObject({
    state: [228, 239, 232, 255],
    stateBorder: [228, 239, 232, 255],
    composite: [111, 138, 126, 255],
    compositeLabel: [111, 138, 126, 255],
    transition: [134, 225, 200, 255],
    label: [134, 225, 200, 255],
    noteBorder: [141, 169, 155, 255],
    noteText: [215, 229, 221, 255],
    noteConnector: [141, 169, 155, 255],
    start: [134, 225, 200, 255],
    end: [230, 177, 126, 255],
    choice: [134, 225, 200, 255],
  })
  expect(Object.keys(colors)).toHaveLength(12 + 3 + 3)
})

test("a border takes the state's colour and a composite's label the composite's, unless given; the ramps blend", () => {
  const given = {
    state: ints(40, 80, 120),
    composite: ints(1, 1, 1),
    transition: ints(0, 0, 0),
    label: ints(2, 2, 2),
    noteBorder: ints(40, 80, 120),
    noteText: ints(3, 3, 3),
    noteConnector: ints(0, 0, 0),
    start: ints(4, 4, 4),
    end: ints(5, 5, 5),
    choice: ints(6, 6, 6),
  }
  expect(asInts(resolveStateStyleColors(given))).toEqual({
    ...asInts(given),
    stateBorder: [40, 80, 120, 255],
    compositeLabel: [1, 1, 1, 255],
    // From the connector to the note's border, and from the state's border to the transition.
    ...ramp(
      "noteConnectorRamp",
      [1, 2, 3].map((k) => [10 * k, 20 * k, 30 * k]),
    ),
    ...ramp("stateDepartureRamp", [
      [30, 60, 90],
      [20, 40, 60],
      [10, 20, 30],
    ]),
  })
  const own = resolveStateStyleColors({
    state: ints(1, 1, 1),
    stateBorder: ints(7, 7, 7),
    compositeLabel: ints(8, 8, 8),
  })
  expect([own.stateBorder.toInts(), own.compositeLabel.toInts()]).toEqual([
    [7, 7, 7, 255],
    [8, 8, 8, 255],
  ])
})

function grid(): StateGrid {
  const canvas: StateGrid = new DiagramCanvas(3, 4)
  canvas.setCell(0, 1, "╭", "stateBorder")
  canvas.setCell(1, 1, "x")
  canvas.setCell(0, 2, "n", "noteText")
  return canvas
}

test("the grid's text drops blank rows at the top and the bottom", () => {
  expect(renderStateGridText(grid())).toBe("╭x\nn")
})

test("styled text colours each run by its style, with a background only where one is given for it", () => {
  const colors = resolveStateStyleColors({ stateBorder: ints(1, 1, 1), noteText: ints(2, 2, 2) })
  const chunks = (backgrounds?: Parameters<typeof renderStateGridStyledText>[2]) => {
    const text = renderStateGridStyledText(grid(), colors, backgrounds)
    expect(text).toBeInstanceOf(StyledText)
    return text.chunks.map((chunk) => [chunk.text, chunk.fg?.toInts(), chunk.bg?.toInts()])
  }
  expect(chunks()).toEqual([
    ["╭", [1, 1, 1, 255], undefined],
    ["x", undefined, undefined],
    ["\n", undefined, undefined],
    ["n", [2, 2, 2, 255], undefined],
  ])
  expect(chunks({ noteText: ints(9, 9, 9) })).toEqual([
    ["╭", [1, 1, 1, 255], undefined],
    ["x", undefined, undefined],
    ["\n", undefined, undefined],
    ["n", [2, 2, 2, 255], [9, 9, 9, 255]],
  ])
})
