import { expect, test } from "bun:test"
import * as g from "../../src/core/geometry"

const p = g.point

test("bounds from a rect put the centre at the floor of half the size, and translating moves the centre too", () => {
  const bounds = g.diagramBoundsFromRect(2, 3, 5, 5)
  expect(bounds).toEqual({ left: 2, top: 3, width: 5, height: 5, centerX: 4, centerY: 5 })
  g.translateDiagramBounds(bounds, -2, 1)
  expect(bounds).toEqual({ left: 0, top: 4, width: 5, height: 5, centerX: 2, centerY: 6 })
  expect(g.boundsCenter(bounds)).toEqual(p(2, 6))
  expect([g.centerCoordinate(bounds, "x"), g.centerCoordinate(bounds, "y")]).toEqual([2, 6])
})

test("the union of bounds spans all of them, and of points spans them inclusively; none is undefined", () => {
  expect(g.diagramBoundsFromBounds([g.diagramBoundsFromRect(1, 1, 2, 2), g.diagramBoundsFromRect(4, 2, 2, 3)])).toEqual(
    g.diagramBoundsFromRect(1, 1, 5, 4),
  )
  expect(g.diagramBoundsFromBounds([])).toBeUndefined()
  expect(g.diagramBoundsFromPoints([p(1, 5), p(4, 2)])).toEqual(g.diagramBoundsFromRect(1, 2, 4, 4))
  expect(g.diagramBoundsFromPoints([])).toBeUndefined()
})

test("points: read and set an axis, shift by a direction, clamp to a minimum, compare", () => {
  expect([g.coordinate(p(3, 7), "x"), g.coordinate(p(3, 7), "y")]).toEqual([3, 7])
  expect(g.withCoordinate(p(3, 7), "x", 9)).toEqual(p(9, 7))
  expect(g.withCoordinate(p(3, 7), "y", 9)).toEqual(p(3, 9))
  expect([g.shiftPoint(p(5, 5), "left"), g.shiftPoint(p(5, 5), "right", 2), g.shiftPoint(p(5, 5), "up", 3), g.shiftPoint(p(5, 5), "down")]).toEqual([
    p(4, 5),
    p(7, 5),
    p(5, 2),
    p(5, 6),
  ])
  expect(g.clampPoint(p(-2, -3))).toEqual(p(0, 0))
  expect(g.clampPoint(p(2, 3))).toEqual(p(2, 3))
  expect(g.clampPoint(p(4, 1), p(5, 2))).toEqual(p(5, 2))
  expect(g.clampPoint(p(7, 9), p(5, 2))).toEqual(p(7, 9))
  expect(g.samePoint(p(1, 2), p(1, 2))).toBe(true)
  expect(g.samePoint(p(1, 2), p(1, 3))).toBe(false)
  expect(g.samePoint(p(1, 2), p(0, 2))).toBe(false)
})

test("each direction has its axis, sign and side, and each side its opposite", () => {
  expect((["left", "right", "up", "down"] as const).map((d) => [g.directionAxis(d), g.directionSign(d), g.sideForDirection(d)])).toEqual([
    ["x", -1, "left"],
    ["x", 1, "right"],
    ["y", -1, "top"],
    ["y", 1, "bottom"],
  ])
  expect((["left", "right", "top", "bottom"] as const).map(g.oppositeSide)).toEqual(["right", "left", "bottom", "top"])
})

test("the direction between two points is named only when they share a row or a column and differ; a segment has its axis, direction and length", () => {
  expect(g.segmentBetween(p(1, 5), p(1, 1))).toEqual({ from: p(1, 5), to: p(1, 1), axis: "y", direction: "up", length: 4 })
  expect(g.segmentBetween(p(4, 0), p(1, 0))).toMatchObject({ axis: "x", direction: "left", length: 3 })
  expect(g.segmentBetween(p(0, 0), p(1, 1))).toBeUndefined()
  expect([g.directionBetween(p(1, 1), p(4, 1)), g.directionBetween(p(1, 1), p(0, 1)), g.directionBetween(p(1, 1), p(1, 5)), g.directionBetween(p(1, 1), p(1, 0))]).toEqual([
    "right",
    "left",
    "down",
    "up",
  ])
  expect(g.directionBetween(p(1, 1), p(1, 1))).toBeUndefined()
  expect(g.directionBetween(p(1, 1), p(2, 2))).toBeUndefined()
})

test("a side point sits one cell outside the bounds by default, or on the border", () => {
  const bounds = g.diagramBoundsFromRect(2, 3, 5, 4)
  expect((["left", "right", "top", "bottom"] as const).map((side) => g.boundsSidePoint(bounds, side))).toEqual([p(1, 5), p(7, 5), p(4, 2), p(4, 7)])
  expect((["left", "right", "top", "bottom"] as const).map((side) => g.boundsSidePoint(bounds, side, "border"))).toEqual([p(2, 5), p(6, 5), p(4, 3), p(4, 6)])
})

test("a coordinate snaps to the target within the tolerance, inclusive, and stays otherwise", () => {
  expect(g.snapCoordinate(5, 7, 2)).toBe(7)
  expect(g.snapCoordinate(9, 7, 2)).toBe(7)
  expect(g.snapCoordinate(5, 8, 2)).toBe(5)
})

test("an orthogonal path turns on the longer axis, short of the end by the clearance, or on the axis asked for", () => {
  const first = p(0, 0)
  const path = g.pathThrough([first, p(0, 0), p(2, 0), p(2, 0), p(0, 0)])
  expect(path).toEqual([p(0, 0), p(2, 0), p(0, 0)])
  expect(path[0]).not.toBe(first)
  expect(g.lane("x", 3)).toEqual({ axis: "x", coordinate: 3 })
  expect(g.pathViaLane(p(0, 0), g.lane("x", 3), p(6, 4))).toEqual([p(0, 0), p(3, 0), p(3, 4), p(6, 4)])
  expect(g.pathViaLane(p(0, 2), g.lane("y", 2), p(5, 7))).toEqual([p(0, 2), p(5, 2), p(5, 7)])
  expect(g.orthogonalPath(p(5, 0), p(7, 6))).toEqual([p(5, 0), p(5, 2), p(7, 2), p(7, 6)])
  expect(g.orthogonalPath(p(0, 5), p(6, 7))).toEqual([p(0, 5), p(2, 5), p(2, 7), p(6, 7)])
  expect(g.orthogonalPath(p(0, 0), p(5, 1), { preferredAxis: "y" })).toEqual([p(0, 0), p(5, 0), p(5, 1)])
  expect(g.orthogonalPath(p(0, 0), p(10, 3))).toEqual([p(0, 0), p(6, 0), p(6, 3), p(10, 3)])
  expect(g.orthogonalPath(p(10, 3), p(0, 0))).toEqual([p(10, 3), p(4, 3), p(4, 0), p(0, 0)])
  expect(g.orthogonalPath(p(0, 0), p(10, 3), { terminalClearance: 1 })).toEqual([p(0, 0), p(9, 0), p(9, 3), p(10, 3)])
  expect(g.orthogonalPath(p(0, 0), p(10, 3), { preferredAxis: "y" })).toEqual([p(0, 0), p(0, 1), p(10, 1), p(10, 3)])
  expect(g.orthogonalPath(p(0, 0), p(2, 2))).toEqual([p(0, 0), p(1, 0), p(1, 2), p(2, 2)])
  expect(g.orthogonalPath(p(0, 0), p(3, 9))).toEqual([p(0, 0), p(0, 5), p(3, 5), p(3, 9)])
})

test("a straight or degenerate path is just its ends", () => {
  expect(g.orthogonalPath(p(0, 2), p(5, 2))).toEqual([p(0, 2), p(5, 2)])
  expect(g.orthogonalPath(p(4, 0), p(4, 3))).toEqual([p(4, 0), p(4, 3)])
  expect(g.orthogonalPath(p(1, 1), p(1, 1))).toEqual([p(1, 1)])
})

test("walking a segment visits each cell before its end, from its start or the next one, until told to stop", () => {
  const seen: string[] = []
  g.walkOrthogonalSegment(p(0, 0), p(3, 0), true, (at) => void seen.push(`${at.x},${at.y}`))
  expect(seen).toEqual(["0,0", "1,0", "2,0"])
  seen.length = 0
  g.walkOrthogonalSegment(p(0, 3), p(0, 0), false, (at) => void seen.push(`${at.x},${at.y}`))
  expect(seen).toEqual(["0,2", "0,1"])
  seen.length = 0
  g.walkOrthogonalSegment(p(4, 1), p(0, 1), false, (at) => void seen.push(`${at.x},${at.y}`))
  expect(seen).toEqual(["3,1", "2,1", "1,1"])
  seen.length = 0
  g.walkOrthogonalSegment(p(1, 0), p(1, 4), false, (at) => void seen.push(`${at.x},${at.y}`))
  expect(seen).toEqual(["1,1", "1,2", "1,3"])
  seen.length = 0
  g.walkOrthogonalSegment(p(0, 0), p(5, 0), true, (at) => {
    seen.push(`${at.x}`)
    return at.x < 1
  })
  expect(seen).toEqual(["0", "1"])
  seen.length = 0
  g.walkOrthogonalSegment(p(0, 0), p(2, 2), true, () => void seen.push("x"))
  expect(seen).toEqual([])
})

test("a path's points are every cell along it, each corner once, diagonal and empty steps skipped", () => {
  expect(g.orthogonalPathPoints([p(0, 0), p(2, 0), p(2, 2)])).toEqual([p(0, 0), p(1, 0), p(2, 0), p(2, 1), p(2, 2)])
  expect(g.orthogonalPathPoints([p(3, 1), p(1, 1), p(1, 1), p(0, 0), p(0, 0)])).toEqual([p(3, 1), p(2, 1), p(1, 1)])
  expect(g.orthogonalPathPoints([p(0, 0)])).toEqual([])
  expect(g.orthogonalPathPoints([p(0, 0), p(0, 0), p(2, 0)])).toEqual([p(0, 0), p(1, 0), p(2, 0)])
  expect(g.orthogonalPathPoints([p(0, 0), p(1, 1), p(3, 1)])).toEqual([p(1, 1), p(2, 1), p(3, 1)])
  expect(g.orthogonalPathPoints([p(4, 2), p(0, 2), p(0, 0)])).toEqual([p(4, 2), p(3, 2), p(2, 2), p(1, 2), p(0, 2), p(0, 1), p(0, 0)])
})

test("spans: ordered, read off a segment, inset, measured inclusively, centred, halved", () => {
  expect(g.orderedSpan(5, 2)).toEqual({ start: 2, end: 5 })
  expect(g.orderedSpan(2, 5)).toEqual({ start: 2, end: 5 })
  const segment = g.segmentBetween(p(7, 3), p(2, 3))!
  expect(g.segmentSpan(segment)).toEqual({ start: 2, end: 7 })
  expect(g.pointOnSegment(segment, 4)).toEqual(p(4, 3))
  expect(g.insetSpan({ start: 2, end: 9 }, 2)).toEqual({ start: 4, end: 7 })
  expect(g.spanCapacity({ start: 2, end: 5 })).toBe(4)
  expect(g.spanCapacity({ start: 5, end: 3 })).toBe(0)
  expect(g.centeredSpanStart({ start: 0, end: 9 }, 4)).toBe(3)
  expect(g.centeredSpanStart({ start: 0, end: 9 }, 5)).toBe(2)
  expect(g.midpoint({ start: 1, end: 4 })).toBe(3)
  expect(g.midpoint({ start: -3, end: 0 })).toBe(-1)
})

test("coordinates advance with the direction's sign and stay before the nearest or after the farthest point", () => {
  expect([g.advanceCoordinate(5, "left", 2), g.advanceCoordinate(5, "down", 2)]).toEqual([3, 7])
  const points = [p(2, 5), p(7, 1)]
  expect(g.beforeNearestCoordinate(points, "x", "right", 1)).toBe(1)
  expect(g.beforeNearestCoordinate(points, "x", "left", 1)).toBe(8)
  expect(g.afterFarthestCoordinate(points, "x", "right", 1)).toBe(8)
  expect(g.afterFarthestCoordinate(points, "y", "up", 2)).toBe(-1)
  expect([g.keepBefore(5, 3, "right"), g.keepBefore(5, 3, "left"), g.keepAfter(5, 3, "right"), g.keepAfter(5, 3, "left")]).toEqual([3, 5, 5, 3])
  expect([g.keepBefore(2, 3, "down"), g.keepBefore(2, 3, "up"), g.keepAfter(2, 3, "down"), g.keepAfter(2, 3, "up")]).toEqual([2, 3, 3, 2])
})
