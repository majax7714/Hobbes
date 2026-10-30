import { RGBA } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import {
  DATABASE_EDGE_FADE_STYLES,
  NODE_EDGE_FADE_STYLES,
  renderGridStyledText,
  resolveFlowchartStyleColors,
  type FlowchartCellMetadata,
  type FlowchartCellStyle,
} from "../../src/flowchart/style"

const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))

test("with no colours given, every base style takes the default theme", () => {
  expect(asInts(resolveFlowchartStyleColors())).toMatchObject({
    node: [228, 239, 232, 255],
    nodeBorder: [141, 163, 151, 255],
    database: [228, 239, 232, 255],
    databaseBorder: [141, 163, 151, 255],
    edge: [134, 225, 200, 255],
    label: [134, 225, 200, 255],
    group: [76, 99, 89, 255],
    groupLabel: [76, 99, 89, 255],
  })
})

test("a given colour wins for its own style; only a group label falls back, to the group's colour", () => {
  const styles = ["node", "nodeBorder", "database", "databaseBorder", "edge", "label", "group", "groupLabel"] as const
  const given = Object.fromEntries(styles.map((style, index) => [style, ints(index, index, index)]))
  expect(asInts(resolveFlowchartStyleColors(given))).toMatchObject(
    Object.fromEntries(styles.map((style, index) => [style, [index, index, index, 255]])),
  )
  const grouped = resolveFlowchartStyleColors({ group: ints(1, 2, 3), edge: ints(9, 9, 9) })
  expect([grouped.groupLabel.toInts(), grouped.label.toInts()]).toEqual([[1, 2, 3, 255], [134, 225, 200, 255]])
})

test("the edge fades step in five even sixths from a node's or a database's border to the edge colour", () => {
  expect(NODE_EDGE_FADE_STYLES).toEqual(["nodeEdgeFade1", "nodeEdgeFade2", "nodeEdgeFade3", "nodeEdgeFade4", "nodeEdgeFade5"])
  expect<readonly string[]>(DATABASE_EDGE_FADE_STYLES).toEqual(NODE_EDGE_FADE_STYLES.map((style) => style.replace("node", "database")))
  const colors = resolveFlowchartStyleColors({
    nodeBorder: ints(0, 0, 0),
    databaseBorder: ints(240, 0, 60),
    edge: ints(60, 120, 180),
  })
  for (const step of [1, 2, 3, 4, 5] as const) {
    expect(colors[`nodeEdgeFade${step}`].toInts()).toEqual([10 * step, 20 * step, 30 * step, 255])
    expect(colors[`databaseEdgeFade${step}`].toInts()).toEqual([240 - 30 * step, 20 * step, 60 + 20 * step, 255])
  }
  expect(Object.keys(colors)).toHaveLength(18)
})

test("a grid renders without its blank top and bottom rows or trailing blanks, one run per style and attributes", () => {
  const grid = new DiagramCanvas<FlowchartCellStyle, FlowchartCellMetadata>(4, 4)
  grid.setText(0, 1, "ab", "node")
  grid.setText(2, 1, "c", "node", { attributes: 1 })
  grid.setText(0, 2, "d", "edge")
  const colors = resolveFlowchartStyleColors()
  const text = renderGridStyledText(grid, colors, { edge: ints(1, 1, 1) })
  expect(text.chunks.map((chunk) => [chunk.text, chunk.fg, chunk.bg, chunk.attributes])).toEqual([
    ["ab", colors.node, undefined, undefined],
    ["c", colors.node, undefined, 1],
    ["\n", undefined, undefined, undefined],
    ["d", colors.edge, ints(1, 1, 1), undefined],
  ])
})
