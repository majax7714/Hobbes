import { expect, test } from "bun:test"
import type { SpatialIndex, SpatialRole } from "../../src/core/spatial"
import { createStateSearchBudget, createStateSearchSpace, findStateManhattanPath } from "../../src/state/search"

const index = (...claims: Array<{ role: SpatialRole; spans: Array<{ y: number; fromX: number; toX: number }> }>) =>
  ({ claims: claims.map((claim, n) => ({ id: `c${n}`, owner: `o${n}`, ...claim })) }) as unknown as SpatialIndex
const sorted = (keys: ReadonlySet<string>) => [...keys].sort()
const open = { blocked: new Set<string>() }
const grid = { minX: 0, minY: 0, maxX: 3, maxY: 3 }
const p = (x: number, y: number) => ({ x, y })

test("a search space blocks each claimed cell, padded by its role's clearance, and spans them and the origin", () => {
  const space = createStateSearchSpace(
    index(
      { role: "body", spans: [{ y: 1, fromX: 2, toX: 3 }] },
      { role: "route", spans: [{ y: -1, fromX: 0, toX: 0 }] },
    ),
    (role) => (role === "body" ? 1 : 0),
  )
  expect(space.blocked.size).toBe(4 * 3 + 1)
  expect(["1:0", "4:2", "0:-1"].every((key) => space.blocked.has(key))).toBe(true)
  expect([space.minX, space.minY, space.maxX, space.maxY]).toEqual([0, -1, 4, 2])
  const negative = createStateSearchSpace(index({ role: "body", spans: [{ y: -2, fromX: -3, toX: -2 }] }))
  expect([negative.minX, negative.minY, negative.maxX, negative.maxY]).toEqual([-3, -2, 0, 0])
  const far = createStateSearchSpace(index({ role: "label", spans: [{ y: 3, fromX: 5, toX: 6 }] }))
  expect(sorted(far.blocked)).toEqual(["5:3", "6:3"])
  expect([far.minX, far.minY, far.maxX, far.maxY]).toEqual([0, 0, 6, 3])
})

test("a path is the shortest, stepping toward the goal across before up or down when both are as short", () => {
  expect(findStateManhattanPath([p(0, 0)], p(2, 1), open, grid, createStateSearchBudget())).toEqual([
    p(0, 0),
    p(1, 0),
    p(2, 0),
    p(2, 1),
  ])
  expect(findStateManhattanPath([p(2, 1)], p(0, 0), open, grid, createStateSearchBudget())).toEqual([
    p(2, 1),
    p(1, 1),
    p(0, 1),
    p(0, 0),
  ])
})

test("there is no path to a blocked goal, one outside the bounds, or past the visits the budget allows", () => {
  expect(createStateSearchBudget().remaining).toBe(250_000)
  const blockedGoal = { blocked: new Set(["1:0"]) }
  expect(findStateManhattanPath([p(0, 0)], p(1, 0), blockedGoal, grid, createStateSearchBudget())).toBeUndefined()
  expect(findStateManhattanPath([p(0, 0)], p(4, 0), open, grid, createStateSearchBudget())).toBeUndefined()
  expect(findStateManhattanPath([p(0, 0)], p(0, 4), open, grid, createStateSearchBudget())).toBeUndefined()
  expect(findStateManhattanPath([p(3, 3)], p(-1, 3), open, grid, createStateSearchBudget())).toBeUndefined()
  expect(findStateManhattanPath([p(3, 3)], p(3, -1), open, grid, createStateSearchBudget())).toBeUndefined()
  const one = { remaining: 1 }
  expect(findStateManhattanPath([p(0, 0)], p(2, 0), open, grid, one)).toBeUndefined()
  expect(one.remaining).toBe(0)
  // One visit is enough to reach a neighbour, and visiting the goal ends the search before it costs one.
  const two = { remaining: 10 }
  expect(findStateManhattanPath([p(0, 0)], p(1, 0), open, grid, two)).toEqual([p(0, 0), p(1, 0)])
  expect(two.remaining).toBe(9)
  // A repeated start costs no second visit.
  expect(findStateManhattanPath([p(0, 0), p(0, 0)], p(2, 0), open, grid, { remaining: 2 })).toEqual([
    p(0, 0),
    p(1, 0),
    p(2, 0),
  ])
})

test("a path goes around blocked cells, detouring away from the goal in any of the four directions", () => {
  const detour = (start: ReturnType<typeof p>, goal: ReturnType<typeof p>, cell: string, box = grid) =>
    findStateManhattanPath([start], goal, { blocked: new Set([cell]) }, box, createStateSearchBudget())
  expect(detour(p(0, 0), p(0, 2), "0:1")).toEqual([p(0, 0), p(1, 0), p(1, 1), p(1, 2), p(0, 2)])
  expect(detour(p(0, 0), p(2, 0), "1:0", { minX: 0, minY: 0, maxX: 2, maxY: 1 })).toEqual([
    p(0, 0),
    p(0, 1),
    p(1, 1),
    p(2, 1),
    p(2, 0),
  ])
  expect(detour(p(2, 0), p(2, 2), "2:1", { minX: 0, minY: 0, maxX: 2, maxY: 2 })).toEqual([
    p(2, 0),
    p(1, 0),
    p(1, 1),
    p(1, 2),
    p(2, 2),
  ])
  expect(detour(p(0, 2), p(2, 2), "1:2", { minX: 0, minY: 0, maxX: 2, maxY: 2 })).toEqual([
    p(0, 2),
    p(0, 1),
    p(1, 1),
    p(2, 1),
    p(2, 2),
  ])
  // A blocked start is dropped; a start on the goal is the whole path.
  const blocked = { blocked: new Set(["1:0"]) }
  expect(findStateManhattanPath([p(1, 0), p(3, 3)], p(3, 1), blocked, grid, createStateSearchBudget())).toEqual([
    p(3, 3),
    p(3, 2),
    p(3, 1),
  ])
  expect(findStateManhattanPath([p(2, 2)], p(2, 2), open, grid, createStateSearchBudget())).toEqual([p(2, 2)])
})

test("the step toward the goal's row is tried first, up or down, which sets how many visits a search spends", () => {
  // Up: (3,3), then (3,2), then (2,3) before the goal (3,1) comes off the queue.
  const up = { remaining: 8 }
  expect(findStateManhattanPath([p(3, 3)], p(3, 1), open, grid, up)).toEqual([p(3, 3), p(3, 2), p(3, 1)])
  expect(up.remaining).toBe(5)
  // Down, on a 5 by 5 grid: twelve cells come off the queue before the goal.
  const down = { remaining: 30 }
  expect(findStateManhattanPath([p(2, 1)], p(2, 4), open, { minX: 0, minY: 0, maxX: 4, maxY: 4 }, down)).toEqual([
    p(2, 1),
    p(2, 2),
    p(2, 3),
    p(2, 4),
  ])
  expect(down.remaining).toBe(18)
})

// subsume reads this case as redundant: no fault it plants drops the argument alone. Planted by hand (the
// argument ignored for the blocked set), this is the only case that fails.
test("a free test given in place of the blocked set decides alone", () => {
  const evenOnly = (point: { x: number; y: number }) => point.y % 2 === 0
  expect(
    findStateManhattanPath(
      [p(0, 0)],
      p(2, 0),
      { blocked: new Set(["1:0"]) },
      grid,
      createStateSearchBudget(),
      evenOnly,
    ),
  ).toEqual([p(0, 0), p(1, 0), p(2, 0)])
})
