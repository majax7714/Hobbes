import { expect, test } from "bun:test"
import { SessionTitleFallback } from "../src/session-title-fallback"

const created = Date.UTC(2026, 0, 2, 3, 4, 5, 6)

test("withTimestampedFallback keeps a title or stamps root and child fallbacks", () => {
  expect(SessionTitleFallback.withTimestampedFallback({ title: "Mine", time: { created } })).toBe("Mine")
  expect(SessionTitleFallback.withTimestampedFallback({ time: { created } })).toBe("New session - 2026-01-02T03:04:05.006Z")
  expect(SessionTitleFallback.withTimestampedFallback({ parentID: "p", time: { created } })).toBe(
    "Child session - 2026-01-02T03:04:05.006Z",
  )
})

test("displayLabel collapses a stamped fallback and keeps a real title", () => {
  expect(SessionTitleFallback.displayLabel({})).toBe("New session")
  expect(SessionTitleFallback.displayLabel({ parentID: "p" })).toBe("Child session")
  expect(SessionTitleFallback.displayLabel({ title: "Child session - 2026-01-02T03:04:05.006Z" })).toBe("Child session")
  expect(SessionTitleFallback.displayLabel({ title: "New session - today" })).toBe("New session - today")
})

test("isFallbackTitle matches only a missing or fully stamped title", () => {
  expect(SessionTitleFallback.isFallbackTitle()).toBe(true)
  expect(SessionTitleFallback.isFallbackTitle("New session - 2026-01-02T03:04:05.006Z")).toBe(true)
  expect(SessionTitleFallback.isFallbackTitle("x New session - 2026-01-02T03:04:05.006Z")).toBe(false)
  expect(SessionTitleFallback.isFallbackTitle("New session - 2026-01-02T03:04:05.006Z!")).toBe(false)
})

test("isExactRootFallback needs this session's own root stamp", () => {
  expect(SessionTitleFallback.isExactRootFallback({ time: { created } })).toBe(true)
  expect(SessionTitleFallback.isExactRootFallback({ title: "New session - 2026-01-02T03:04:05.006Z", time: { created } })).toBe(true)
  expect(SessionTitleFallback.isExactRootFallback({ title: "New session - 2026-01-02T03:04:05.007Z", time: { created } })).toBe(false)
})
