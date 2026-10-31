import { expect, test } from "bun:test"
import { stateDiagramNoteConnector } from "../../src/state/note"
import type { StateDiagramNote } from "../../src/state/types"

const note = (position: "left" | "right"): StateDiagramNote => ({ target: "A", position, lines: ["n"] })
const box = (left: number, top: number, width: number, height: number) => ({
  left,
  top,
  width,
  height,
  centerY: top + Math.floor(height / 2),
})

test("beside its target, a note's connector runs straight across at the target's middle row", () => {
  const target = box(0, 0, 8, 3)
  expect(stateDiagramNoteConnector({ ...box(20, 0, 10, 3), note: note("right") }, target)).toEqual({
    connectorY: 1,
    points: [
      { x: 8, y: 1 },
      { x: 19, y: 1 },
    ],
  })
  expect(stateDiagramNoteConnector({ ...box(0, 0, 10, 3), note: note("left") }, box(20, 0, 8, 3))).toEqual({
    connectorY: 1,
    points: [
      { x: 19, y: 1 },
      { x: 10, y: 1 },
    ],
  })
})

test("the straight connector keeps off the note's top and bottom rows", () => {
  const right = (top: number, height: number, target: ReturnType<typeof box>) =>
    stateDiagramNoteConnector({ ...box(20, top, 10, height), note: note("right") }, target).connectorY
  // The target's middle is below the note's last inner row, then above its first.
  expect(right(0, 4, box(0, 0, 8, 11))).toBe(2)
  expect(right(3, 5, box(0, 0, 8, 6))).toBe(4)
  expect(right(0, 5, box(0, 0, 8, 5))).toBe(2)
})

test("above or below its target, a note's connector leaves the target's edge, turns at the note's middle row and runs across", () => {
  const target = box(0, 5, 8, 3)
  expect(stateDiagramNoteConnector({ ...box(20, 0, 10, 3), note: note("right") }, target)).toEqual({
    connectorY: 1,
    points: [
      { x: 8, y: 4 },
      { x: 8, y: 1 },
      { x: 19, y: 1 },
    ],
  })
  expect(stateDiagramNoteConnector({ ...box(20, 10, 10, 3), note: note("right") }, target)).toEqual({
    connectorY: 11,
    points: [
      { x: 8, y: 8 },
      { x: 8, y: 11 },
      { x: 19, y: 11 },
    ],
  })
})

test("a note whose rows touch its target's at either end is beside it, not above or below", () => {
  const kind = (top: number, height: number, target: ReturnType<typeof box>) =>
    stateDiagramNoteConnector({ ...box(20, top, 10, height), note: note("right") }, target).points.length
  const target = box(0, 5, 8, 3)
  // A note ending on the row above the target's top is above it; one ending on that top row is beside it.
  expect([kind(0, 5, target), kind(0, 6, target)]).toEqual([3, 2])
  // A note starting on the target's last row is beside it; one starting below is below it.
  expect([kind(7, 3, target), kind(8, 3, target)]).toEqual([2, 3])
})

test("a connector already placed is returned as it is", () => {
  const connector = { connectorY: 7, points: [{ x: 1, y: 7 }] }
  expect(stateDiagramNoteConnector({ ...box(20, 0, 10, 3), note: note("left"), connector }, box(0, 0, 8, 3))).toBe(
    connector,
  )
})
