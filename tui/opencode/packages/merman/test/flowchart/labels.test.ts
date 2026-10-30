import { expect, test } from "bun:test"
import type { FlowchartEdge } from "../../src/flowchart/types"
import {
  flowchartEdgeLabelLayout,
  flowchartHorizontalLabelRankGap,
  flowchartLabelText,
  flowchartLabelWidth,
  flowchartRouteLabelLayout,
  flowchartVerticalBranchLabelGap,
} from "../../src/flowchart/labels"

const measure = (text: string) => text.length
const at = (x: number, y: number) => ({ x, y })
const path = (...coordinates: Array<[number, number]>) => coordinates.map(([x, y]) => at(x, y))
const labelAt = (points: ReturnType<typeof path>, label = "go", axis?: "x" | "y", segment?: number) =>
  flowchartEdgeLabelLayout(points, label, measure, axis, segment).point

test("a label's rank gap leaves it two cells of line each side and room for the bus", () => {
  expect([flowchartHorizontalLabelRankGap(4), flowchartHorizontalLabelRankGap(9)]).toEqual([11, 16])
  expect([flowchartVerticalBranchLabelGap(4), flowchartVerticalBranchLabelGap(9)]).toEqual([12, 17])
})

test("on a horizontal run a one-line label is centred inside two cells of clearance, else above, two cells along", () => {
  expect(labelAt(path([3, 5], [23, 5]))).toEqual(at(11, 5))
  expect(labelAt(path([23, 5], [3, 5]))).toEqual(at(11, 5))
  expect(labelAt(path([3, 5], [10, 5]))).toEqual(at(5, 5))
  expect(labelAt(path([3, 5], [9, 5]))).toEqual(at(5, 4))
  expect(labelAt(path([9, 5], [3, 5]))).toEqual(at(7, 4))
  expect(labelAt(path([1, 0], [6, 0]))).toEqual(at(3, 0))
  // A label of several lines sits above the run, centred on it even when it overhangs.
  expect(labelAt(path([3, 5], [23, 5]), "ab<br>c")).toEqual(at(11, 3))
  expect(labelAt(path([3, 5], [8, 5]), "ab<br>c")).toEqual(at(4, 3))
})

test("on a vertical run a label sits one cell right, centred inside one cell of clearance", () => {
  expect(labelAt(path([4, 2], [4, 12]))).toEqual(at(5, 7))
  expect(labelAt(path([4, 12], [4, 2]), "a<br>b")).toEqual(at(5, 6))
  expect(labelAt(path([4, 2], [4, 5]), "a<br>b")).toEqual(at(5, 3))
})

test("on a vertical run too short for it a label is centred on the run's middle, never above the top", () => {
  expect(labelAt(path([4, 2], [4, 4]), "a<br>b")).toEqual(at(5, 3))
  expect(labelAt(path([4, 3], [4, 6]), "a<br>b<br>c<br>d")).toEqual(at(5, 4))
  expect(labelAt(path([4, 10], [4, 11]), "a<br>b<br>c<br>d<br>e")).toEqual(at(5, 9))
  expect(labelAt(path([0, 0], [0, 2]), "a<br>b<br>c<br>d<br>e<br>f")).toEqual(at(1, 0))
})

test("the run chosen is the first roomy horizontal, else the first vertical, else the first longest", () => {
  expect(labelAt(path([0, 0], [0, 10], [20, 10]))).toEqual(at(8, 10))
  expect(labelAt(path([0, 0], [20, 0], [20, 10], [40, 10]))).toEqual(at(8, 0))
  expect(labelAt(path([0, 0], [0, 10], [5, 10]))).toEqual(at(1, 5))
  expect(labelAt(path([0, 0], [0, 10], [3, 10], [3, 20]))).toEqual(at(1, 5))
  expect(labelAt(path([0, 0], [0, 3], [10, 3]), "abcdefghij")).toEqual(at(1, 1))
  expect(labelAt(path([0, 5], [2, 5], [6, 5]))).toEqual(at(4, 4))
  expect(labelAt(path([0, 5], [3, 5], [6, 5]))).toEqual(at(2, 4))
})

test("a preferred segment, then a preferred axis, overrides the choice when the route has it", () => {
  const route = path([0, 0], [0, 10], [20, 10])
  expect(labelAt(route, "go", "y")).toEqual(at(1, 5))
  expect(labelAt(route, "go", "x", 0)).toEqual(at(1, 5))
  expect(labelAt(route, "go", "y", 5)).toEqual(at(1, 5))
  expect(labelAt(route, "go", undefined, 5)).toEqual(at(8, 10))
  expect(labelAt(path([0, 0], [0, 10]), "go", "x")).toEqual(at(1, 5))
})

test("a route with no straight segment puts its label at its first point, or the origin", () => {
  expect(labelAt([])).toEqual(at(0, 0))
  expect(labelAt(path([3, 4]))).toEqual(at(3, 4))
  expect(labelAt(path([3, 4], [3, 4]))).toEqual(at(3, 4))
  expect(labelAt(path([1, 1], [4, 4]))).toEqual(at(1, 1))
})

test("a label carries its lines padded one cell each side and its widest line's width; a route's own point wins", () => {
  expect(flowchartEdgeLabelLayout(path([3, 5], [23, 5]), "ab<br>c", measure)).toEqual({
    lines: [" ab ", " c "],
    point: at(11, 3),
    width: 4,
    height: 2,
  })
  expect(flowchartLabelText("go")).toBe(" go ")
  expect(flowchartLabelWidth("go", measure)).toBe(4)
  expect(flowchartLabelWidth("abc<br>d", measure)).toBe(5)
  expect(flowchartLabelWidth("d<br/>abc", (text) => text.length * 2)).toBe(8)
  const edge: FlowchartEdge = { from: "A", to: "B", label: "go" }
  const points = path([0, 0], [0, 10], [20, 10])
  expect(flowchartRouteLabelLayout({ edge, points, labelPoint: at(7, 7) }, measure)).toEqual({
    lines: [" go "],
    point: at(7, 7),
    width: 4,
    height: 1,
  })
  expect(flowchartRouteLabelLayout({ edge, points }, measure).point).toEqual(at(8, 10))
  expect(flowchartRouteLabelLayout({ edge, points, labelAxis: "y" }, measure).point).toEqual(at(1, 5))
  expect(flowchartRouteLabelLayout({ edge: { ...edge, label: "a<br>bcd" }, points }, measure)).toMatchObject({
    lines: [" a ", " bcd "],
    width: 5,
    height: 2,
  })
})
