import { expect, test } from "bun:test"
import { activityCalendar } from "../src/activity-calendar"

// Local midnights, as the calendar reads dates in local time.
const day = (year: number, month: number, date: number) => new Date(year, month - 1, date).getTime()

test("weeks start on Monday and days outside the range are -1", () => {
  // 2026-01-07 is a Wednesday.
  const result = activityCalendar({ activity: [], from: day(2026, 1, 7), to: day(2026, 1, 9), maxWeeks: 10 })
  expect(result.weeks).toHaveLength(1)
  expect(result.weeks[0]!.map((cell) => cell.date)).toEqual([
    "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10", "2026-01-11",
  ])
  expect(result.weeks[0]!.map((cell) => cell.level)).toEqual([-1, -1, 0, 0, -1, -1, -1])
  expect(result.clipped).toBe(false)
})

test("levels rank distinct step counts into quarters 1..4, by rank, not by order of days", () => {
  const activity = [
    { date: "2026-01-05", steps: 9 },
    { date: "2026-01-06", steps: 1 },
    { date: "2026-01-07", steps: 5 },
    { date: "2026-01-08", steps: 5 },
    { date: "2026-01-09", steps: 0 },
  ]
  const result = activityCalendar({ activity, from: day(2026, 1, 5), to: day(2026, 1, 12), maxWeeks: 1 })
  // Three distinct counts: ranks 1..3 of 3 scale up to 2, 3 and 4.
  expect(result.weeks[0]!.map((cell) => [cell.steps, cell.level])).toEqual([
    [9, 4], [1, 2], [5, 3], [5, 3], [0, 0], [0, 0], [0, 0],
  ])
  // Four distinct counts map one to one; a zero day is not a count.
  const four = [1, 2, 3, 4, 0].map((steps, index) => ({ date: `2026-01-0${index + 5}`, steps }))
  const ranked = activityCalendar({ activity: four, from: day(2026, 1, 5), to: day(2026, 1, 12), maxWeeks: 1 })
  expect(ranked.weeks[0]!.slice(0, 5).map((cell) => cell.level)).toEqual([1, 2, 3, 4, 0])
})

test("maxWeeks keeps the latest weeks and says it clipped", () => {
  const result = activityCalendar({ activity: [], from: day(2026, 1, 5), to: day(2026, 2, 2), maxWeeks: 2.9 })
  expect(result.weeks).toHaveLength(2)
  expect(result.weeks[0]![0]!.date).toBe("2026-01-19")
  expect(result.weeks[1]![6]!.date).toBe("2026-02-01")
  expect(result.clipped).toBe(true)
  expect(activityCalendar({ activity: [], from: day(2026, 1, 5), to: day(2026, 2, 2), maxWeeks: 0 }).weeks).toHaveLength(1)
})

test("an empty range has no weeks, a range reaching the next Monday has two, and a year is capped at 53", () => {
  expect(activityCalendar({ activity: [], from: day(2026, 1, 7), to: day(2026, 1, 7), maxWeeks: 5 }).weeks).toHaveLength(0)
  expect(activityCalendar({ activity: [], from: day(2026, 1, 5), to: day(2026, 1, 13), maxWeeks: 5 }).weeks).toHaveLength(2)
  expect(activityCalendar({ activity: [], from: day(2024, 1, 1), to: day(2026, 1, 1), maxWeeks: 500 }).weeks).toHaveLength(53)
})

test("a month label belongs to the week whose Thursday it holds, with its span", () => {
  // Mon 2026-01-26 .. Sun 2026-02-22: the week of Jan 26 has Thursday Jan 29.
  const result = activityCalendar({ activity: [], from: day(2026, 1, 26), to: day(2026, 2, 23), maxWeeks: 10 })
  expect(result.months).toEqual([
    { week: 0, label: "Jan", span: 1 },
    { week: 1, label: "Feb", span: 3 },
  ])
  // Thursday 2026-04-30 keeps its week in April, though Friday is May 1.
  const april = activityCalendar({ activity: [], from: day(2026, 3, 30), to: day(2026, 5, 4), maxWeeks: 10 })
  expect(april.months).toEqual([{ week: 0, label: "Apr", span: 5 }])
})

test("an edge week's label is read from inside the range", () => {
  // Sun 2026-02-01: its week's Thursday is Jan 29, before the range.
  const start = activityCalendar({ activity: [], from: day(2026, 2, 1), to: day(2026, 2, 4), maxWeeks: 10 })
  expect(start.months).toEqual([{ week: 0, label: "Feb", span: 2 }])
  // Ends Tue 2026-06-30: its week's Thursday is Jul 2, after the range.
  const end = activityCalendar({ activity: [], from: day(2026, 6, 22), to: day(2026, 7, 1), maxWeeks: 10 })
  expect(end.months).toEqual([{ week: 0, label: "Jun", span: 2 }])
})
