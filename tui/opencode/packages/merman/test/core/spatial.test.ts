import { expect, test } from "bun:test"
import { point as p } from "../../src/core/geometry"
import {
  SpatialIndex,
  spatialPathClaim,
  spatialPathSpans,
  spatialRectClaim,
  spatialRectSpans,
  type SpatialClaim,
} from "../../src/core/spatial"

test("a rect is one span per row, left to right edge inclusive, a single cell included", () => {
  expect(spatialRectSpans({ left: 1, top: 2, width: 3, height: 2 })).toEqual([
    { y: 2, fromX: 1, toX: 3 },
    { y: 3, fromX: 1, toX: 3 },
  ])
  expect(spatialRectSpans({ left: -4, top: -1, width: 1, height: 1 })).toEqual([{ y: -1, fromX: -4, toX: -4 }])
})

function rangeError(run: () => unknown): string {
  try {
    run()
  } catch (error) {
    expect(error).toBeInstanceOf(RangeError)
    return (error as RangeError).message
  }
  throw new Error("no error thrown")
}

test("a rect needs finite integer bounds and positive dimensions, each refusal naming the field", () => {
  expect(rangeError(() => spatialRectSpans({ left: 1.5, top: 0, width: 1, height: 1 }))).toBe("bounds.left must be a finite integer")
  expect(rangeError(() => spatialRectSpans({ left: 0, top: Infinity, width: 1, height: 1 }))).toBe("bounds.top must be a finite integer")
  expect(rangeError(() => spatialRectSpans({ left: 0, top: 0, width: Number.NaN, height: 1 }))).toBe("bounds.width must be a finite integer")
  expect(rangeError(() => spatialRectSpans({ left: 0, top: 0, width: 1, height: 0.5 }))).toBe("bounds.height must be a finite integer")
  for (const [width, height] of [[0, 1], [1, 0], [-1, 1], [1, -1]]) {
    expect(rangeError(() => spatialRectSpans({ left: 0, top: 0, width: width!, height: height! }))).toBe("Spatial bounds must have positive dimensions")
  }
})

test("a path is the runs of cells it covers, row by row, split where a row has a gap", () => {
  expect(spatialPathSpans([p(0, 0), p(3, 0), p(3, 2)])).toEqual([
    { y: 0, fromX: 0, toX: 3 },
    { y: 1, fromX: 3, toX: 3 },
    { y: 2, fromX: 3, toX: 3 },
  ])
  expect(spatialPathSpans([p(0, 1), p(0, 0), p(3, 0), p(3, 1)])).toEqual([
    { y: 0, fromX: 0, toX: 3 },
    { y: 1, fromX: 0, toX: 0 },
    { y: 1, fromX: 3, toX: 3 },
  ])
  expect(spatialPathSpans([p(3, 1), p(3, 0), p(0, 0), p(0, 1)])).toEqual([
    { y: 0, fromX: 0, toX: 3 },
    { y: 1, fromX: 0, toX: 0 },
    { y: 1, fromX: 3, toX: 3 },
  ])
  expect(spatialPathSpans([p(5, 5)])).toEqual([{ y: 5, fromX: 5, toX: 5 }])
  expect(spatialPathSpans([])).toEqual([])
})

test("a path must be orthogonal and integral, and says which point is not", () => {
  expect(rangeError(() => spatialPathSpans([p(0, 0), p(1, 1)]))).toBe("Spatial paths must be orthogonal")
  expect(rangeError(() => spatialPathSpans([p(0, 0), p(0.5, 0)]))).toBe("points[1].x must be a finite integer")
  expect(rangeError(() => spatialPathSpans([p(0, Number.NaN)]))).toBe("points[0].y must be a finite integer")
})

const body = (id: string, owner: string, left: number, top: number, width = 3, height = 1) =>
  spatialRectClaim(id, owner, "body", { left, top, width, height })

test("an index is immutable: adding returns a new index, its claims sorted by id with spans sorted, all frozen", () => {
  expect(spatialRectClaim("n", "A", "body", { left: 0, top: 0, width: 2, height: 1 })).toEqual({ id: "n", owner: "A", role: "body", spans: [{ y: 0, fromX: 0, toX: 1 }] })
  expect(spatialPathClaim("e", "B", "route", [p(0, 0), p(0, 1)])).toEqual({ id: "e", owner: "B", role: "route", spans: [{ y: 0, fromX: 0, toX: 0 }, { y: 1, fromX: 0, toX: 0 }] })
  const empty = SpatialIndex.empty()
  const spans = [{ y: 2, fromX: 0, toX: 0 }, { y: 1, fromX: 5, toX: 6 }, { y: 1, fromX: 0, toX: 3 }, { y: 1, fromX: 0, toX: 1 }, { y: 0, fromX: 9, toX: 9 }]
  const claim: SpatialClaim = { id: "b", owner: "B", role: "label", spans }
  const index = empty.add(claim, body("a", "A", 0, 0))
  expect(empty.claims).toEqual([])
  expect(index.claims.map((c) => c.id)).toEqual(["a", "b"])
  expect(index.claims[1]!.spans).toEqual([{ y: 0, fromX: 9, toX: 9 }, { y: 1, fromX: 0, toX: 1 }, { y: 1, fromX: 0, toX: 3 }, { y: 1, fromX: 5, toX: 6 }, { y: 2, fromX: 0, toX: 0 }])
  expect(spans[0]).toEqual({ y: 2, fromX: 0, toX: 0 })
  expect(Object.isFrozen(index.claims)).toBe(true)
  expect(Object.isFrozen(index.claims[0])).toBe(true)
  expect(Object.isFrozen(index.claims[0]!.spans[0])).toBe(true)
})

test("re-adding an identical claim keeps one; the same id with anything different is refused", () => {
  const index = SpatialIndex.empty().add(body("a", "A", 0, 0))
  expect(index.add(body("a", "A", 0, 0)).claims.length).toBe(1)
  expect(index.overlay(SpatialIndex.empty().add(body("c", "C", 9, 9))).claims.map((c) => c.id)).toEqual(["a", "c"])
  for (const changed of [body("a", "B", 0, 0), spatialRectClaim("a", "A", "label", { left: 0, top: 0, width: 3, height: 1 }), body("a", "A", 1, 0), body("a", "A", 0, 1), body("a", "A", 0, 0, 4), body("a", "A", 0, 0, 3, 2)]) {
    expect(() => index.add(changed)).toThrow("Conflicting spatial claim id: a")
  }
})

test("a claim conflicts at every cell it shares with another owner's claim, unless both are routes", () => {
  const index = SpatialIndex.empty().add(body("box", "A", 0, 0, 4, 2))
  const route = spatialPathClaim("r", "B", "route", [p(2, -1), p(2, 3)])
  expect(index.conflicts(route).map((c) => [c.point.x, c.point.y, c.existing.id, c.moving.id])).toEqual([
    [2, 0, "box", "r"],
    [2, 1, "box", "r"],
  ])
  expect(index.isFree(route)).toBe(false)
  expect(index.isFree(spatialPathClaim("r", "A", "route", [p(2, -1), p(2, 3)]))).toBe(true)
  const routes = SpatialIndex.empty().add(spatialPathClaim("e1", "A", "route", [p(0, 1), p(5, 1)]))
  expect(routes.isFree(route)).toBe(true)
  expect(routes.isFree(body("b", "B", 0, 1))).toBe(false)
  const mixed = SpatialIndex.empty().add(body("a", "B", 20, 20), body("b", "A", 0, 0, 4, 2))
  expect(mixed.conflicts(route).map((c) => c.existing.id)).toEqual(["b", "b"])
  const wide = spatialRectClaim("w", "B", "label", { left: -2, top: 1, width: 9, height: 1 })
  expect(index.conflicts(wide).map((c) => c.point.x)).toEqual([0, 1, 2, 3])
  const candidates = [{ name: "on", claim: body("n", "B", 1, 0) }, { name: "off", claim: body("n", "B", 5, 0) }, { name: "far", claim: body("n", "B", 9, 0) }]
  expect(index.firstFit(candidates)?.name).toBe("off")
  expect(index.firstFit(candidates, { clearance: 2 })?.name).toBe("far")
  expect(index.firstFit(candidates.slice(0, 1))).toBeUndefined()
})

test("clearance inflates the moving claim by columns and rows, as one number, per axis, or per role of the claim already there", () => {
  const index = SpatialIndex.empty().add(body("box", "A", 0, 0))
  const beside = body("n", "B", 3, 0)
  const below = body("n", "B", 0, 2)
  expect(index.isFree(beside)).toBe(true)
  expect(index.conflicts(beside, { clearance: 1 }).map((c) => [c.point.x, c.point.y])).toEqual([[2, 0]])
  expect(index.isFree(below, { clearance: 1 })).toBe(true)
  expect(index.isFree(below, { clearance: { x: 0, y: 2 } })).toBe(false)
  expect(index.isFree(beside, { clearance: { x: 0, y: 2 } })).toBe(true)
  expect(index.isFree(beside, { clearance: { x: 1, y: 0 } })).toBe(false)
  expect(index.isFree(below, { clearance: 2 })).toBe(false)
  const roles = index.add(spatialRectClaim("tag", "C", "label", { left: 0, top: 4, width: 3, height: 1 }))
  expect(roles.isFree(body("n", "B", 3, 0), { clearance: { label: 1 } })).toBe(true)
  expect(index.isFree(body("n", "B", 3, 0), { clearance: { label: 1 } })).toBe(true)
  expect(roles.isFree(body("n", "B", 3, 0), { clearance: { body: 1 } })).toBe(false)
  expect(roles.isFree(body("n", "B", 3, 4), { clearance: { label: { x: 1, y: 0 } } })).toBe(false)
  expect(roles.isFree(body("n", "B", 3, 4), { clearance: { body: { x: 1, y: 0 } } })).toBe(true)
})

test("clearance must be a non-negative integer", () => {
  const index = SpatialIndex.empty().add(body("box", "A", 0, 0))
  expect(rangeError(() => index.conflicts(body("n", "B", 9, 9), { clearance: -1 }))).toBe("Spatial clearance cannot be negative")
  expect(rangeError(() => index.conflicts(body("n", "B", 9, 9), { clearance: { x: 0, y: -1 } }))).toBe("Spatial clearance cannot be negative")
  expect(rangeError(() => index.conflicts(body("n", "B", 9, 9), { clearance: 0.5 }))).toBe("clearance.x must be a finite integer")
  expect(rangeError(() => index.conflicts(body("n", "B", 9, 9), { clearance: { x: 0, y: 1.5 } }))).toBe("clearance.y must be a finite integer")
})

test("a contact excuses only a cell the moving claim really occupies, and only on the named owner", () => {
  const index = SpatialIndex.empty().add(body("box", "A", 0, 0, 3, 3))
  const arrow = spatialPathClaim("r", "B", "route", [p(1, -2), p(1, 0)])
  expect(index.isFree(arrow, { contacts: [{ owner: "A", points: [p(1, 0)] }] })).toBe(true)
  expect(index.isFree(arrow, { contacts: [{ owner: "Z", points: [p(1, 0)] }] })).toBe(false)
  expect(index.isFree(arrow, { contacts: [{ owner: "A", points: [p(0, 0)] }] })).toBe(false)
  expect(index.conflicts(arrow, { contacts: [{ owner: "A", points: [p(1, 0)] }], clearance: { x: 1, y: 0 } }).map((c) => [c.point.x, c.point.y])).toEqual([
    [0, 0],
    [2, 0],
  ])
  expect(index.conflicts(arrow, { contacts: [{ owner: "A", points: [p(0, 0), p(1, 0)] }], clearance: { x: 1, y: 0 } }).map((c) => [c.point.x, c.point.y])).toEqual([
    [0, 0],
    [2, 0],
  ])
  const above = spatialPathClaim("r", "B", "route", [p(1, -3), p(1, -1)])
  expect(index.conflicts(above, { contacts: [{ owner: "A", points: [p(1, 0)] }], clearance: { x: 0, y: 1 } }).map((c) => [c.point.x, c.point.y])).toEqual([[1, 0]])
})
