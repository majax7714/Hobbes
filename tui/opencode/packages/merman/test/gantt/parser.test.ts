import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidGanttDiagram, parseMermaidGanttDiagram } from "../../src/gantt/parser"
import type { GanttSection } from "../../src/gantt/types"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidGanttDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.kind).toBe("gantt")
  return error
}

const where = (error: MermaidSyntaxError) => [error.lineNumber, error.sourceLine, error.message]
const parse = (body: string) => parseMermaidGanttDiagram(`gantt\n${body}`)
const day = 86_400_000
const jan = (date: number, hours = 0, minutes = 0, seconds = 0) => Date.UTC(2024, 0, date, hours, minutes, seconds)

test("a gantt chart is recognized by its first meaningful line being exactly gantt, in any case", () => {
  for (const source of ["gantt", "%% note\n\n  GANTT\ntitle x", "Gantt"])
    expect(isMermaidGanttDiagram(source)).toBe(true)
  for (const source of ["gantt chart", "ganttx", "agantt", "", "%% only a comment", "title x\ngantt", "flowchart"]) {
    expect(isMermaidGanttDiagram(source)).toBe(false)
  }
})

test("the header is required before anything else and only once, and alone is an empty chart with the default formats", () => {
  expect(parseMermaidGanttDiagram("gantt")).toEqual({
    dateFormat: "YYYY-MM-DD",
    axisFormat: "%Y-%m-%d",
    tasks: [],
    entries: [],
  })
  expect("title" in parseMermaidGanttDiagram("gantt")).toBe(false)
  expect(where(syntaxError("\ntitle x\ngantt"))).toEqual([
    2,
    "title x",
    'Gantt header is required in gantt diagram at line 2: "title x"',
  ])
  expect(where(syntaxError("gantt\n\nGANTT"))).toEqual([
    3,
    "GANTT",
    'Gantt header can only appear once in gantt diagram at line 3: "GANTT"',
  ])
  expect(where(syntaxError(""))).toEqual([1, "", 'Gantt header is required in gantt diagram at line 1: ""'])
  expect(where(syntaxError("%% only\n\n"))).toEqual([1, "", 'Gantt header is required in gantt diagram at line 1: ""'])
})

test("title, dateFormat and axisFormat are read in any case; a later one replaces an earlier; the title is unquoted and decoded", () => {
  expect(parse('TITLE "Q1 &amp; Q2"\ndateformat x\nAXISFORMAT %H:%M\nTitle Plan\naxisFormat %d')).toEqual({
    title: "Plan",
    dateFormat: "x",
    axisFormat: "%d",
    tasks: [],
    entries: [],
  })
  expect(parse("title 'A &lt; B'").title).toBe("A < B")
  expect(parse("dateFormat   YYYY-MM-DD HH:mm  ").dateFormat).toBe("YYYY-MM-DD HH:mm")
})

test("the directives merman cannot draw are refused by name, as written; a directive with no value is not a directive", () => {
  for (const [line, name] of [
    ["tickInterval 1week", "tickInterval"],
    ["EXCLUDES weekends", "EXCLUDES"],
    ["todayMarker off", "todayMarker"],
  ]) {
    expect(where(syntaxError(`gantt\n${line}`))).toEqual([
      2,
      line,
      `${name} is not supported in gantt diagram at line 2: "${line}"`,
    ])
  }
  expect(where(syntaxError("gantt\ntitle"))).toEqual([
    2,
    "title",
    'Unsupported syntax in gantt diagram at line 2: "title"',
  ])
})

test("a %% comment runs to the end of the line, and a line that is only a comment is skipped", () => {
  expect(parse("title Plan %% the plan\n   %% aside\nsection A %% first").title).toBe("Plan")
  expect(parse("section A %% first").entries).toEqual([{ type: "section", section: { label: "A" } }])
  expect(where(syntaxError("gantt\nA: 2024-01-01 %% , 1d"))[1]).toBe("A: 2024-01-01")
})

test("accessibility lines and an accDescr block are skipped, even before the header", () => {
  const source = [
    "accTitle: Chart",
    "gantt",
    "accDescr: one line",
    "ACCTITLE plain",
    "accDescr",
    "accDescr {",
    "gantt",
    "anything: at all",
    "}",
    "title Kept",
  ].join("\n")
  expect(parseMermaidGanttDiagram(source)).toEqual({
    title: "Kept",
    dateFormat: "YYYY-MM-DD",
    axisFormat: "%Y-%m-%d",
    tasks: [],
    entries: [],
  })
  expect(parse("accDescr {one line}\ntitle Kept").title).toBe("Kept")
  expect(where(syntaxError("gantt\nnotaccDescr {"))[2]).toStartWith("Unsupported syntax")
})

test("a keyword inside a task's label, or the start of a longer word, does not make the line a directive, section or accessibility line", () => {
  const labels = ["accTitleX", "Write title page", "Review section 2", "sections", "Draft accDescr notes"]
  expect(
    parse(labels.map((label) => `${label}: 2024-01-01, 1d`).join("\n")).entries.map(
      (entry) => entry.type === "task" && entry.task.label,
    ),
  ).toEqual(labels)
})

test("a section is named by the rest of its line, unquoted; a section with no name is refused", () => {
  const diagram = parse('section Build\nSECTION "Ship &amp; run"')
  expect(diagram.entries).toEqual([
    { type: "section", section: { label: "Build" } },
    { type: "section", section: { label: "Ship & run" } },
  ])
  expect(diagram.tasks).toEqual([])
  expect(where(syntaxError("gantt\nsection   "))).toEqual([
    2,
    "section",
    'Gantt section cannot be empty in gantt diagram at line 2: "section"',
  ])
})

// bench/subsume reads this case as redundant: it plants no fault in the section spread. Dropping that spread
// fails this case alone (planted by hand, 2026-10-30).
test("a task takes the section above it, the same section object; a task before any section has none", () => {
  const diagram = parse("Early: 2024-01-01, 1d\nsection S\nOne: 2024-01-02, 1d\nTwo: 2024-01-03, 1d")
  const [early, one, two] = diagram.tasks
  expect("section" in early!).toBe(false)
  expect(one!.section).toBe((diagram.entries[1] as { section: GanttSection }).section)
  expect(two!.section).toBe(one!.section)
  expect(diagram.entries.map((entry) => entry.type)).toEqual(["task", "section", "task", "task"])
  expect(diagram.entries[0]).toEqual({ type: "task", task: early! })
})

test("a task is a label, a colon, then start and end; the label is unquoted and may not be empty", () => {
  expect(parse('"Write &amp; test" : 2024-01-01, 2024-01-03').tasks).toEqual([
    { label: "Write & test", start: jan(1), end: jan(3), state: "task" },
  ])
  expect(where(syntaxError("gantt\na:b: 2024-01-01, 1d"))[2]).toStartWith('Unsupported date "b: 2024-01-01"')
  for (const line of [": 2024-01-01, 1d", "no colon here"]) {
    expect(where(syntaxError(`gantt\n${line}`))).toEqual([
      2,
      line,
      `Unsupported syntax in gantt diagram at line 2: "${line}"`,
    ])
  }
})

// bench/subsume reads this case as redundant: it does not drop a call with arguments. Dropping
// `.filter(Boolean)` fails this case alone (planted by hand, 2026-10-30).
test("fields are trimmed and empty ones dropped; there must be two, or three with an id first", () => {
  expect(parse("A:  2024-01-01 ,, 2d ,").tasks[0]).toEqual({ label: "A", start: jan(1), end: jan(3), state: "task" })
  expect(parse("A: a1, 2024-01-01, 2d").tasks[0]).toEqual({
    label: "A",
    id: "a1",
    start: jan(1),
    end: jan(3),
    state: "task",
  })
  for (const line of ["A: 2024-01-01", "A: a1, b, 2024-01-01, 1d", "A:"]) {
    expect(where(syntaxError(`gantt\n${line}`))).toEqual([
      2,
      line,
      `Gantt tasks require a start and end or duration in gantt diagram at line 2: "${line}"`,
    ])
  }
})

test("leading state flags are read in any case; milestone outranks crit, crit done, done active; vert is read and drops", () => {
  const states = parse(
    [
      "A: active, done, crit, milestone, 2024-01-01, 1d",
      "B: ACTIVE, Done, CRIT, 2024-01-01, 1d",
      "C: active, done, 2024-01-01, 1d",
      "D: active, 2024-01-01, 1d",
      "E: vert, 2024-01-01, 1d",
      "F: 2024-01-01, 1d",
    ].join("\n"),
  ).tasks.map((task) => task.state)
  expect(states).toEqual(["milestone", "critical", "done", "active", "task", "task"])
  expect(parse("A: done, a1, 2024-01-01, 1d").tasks[0]!.id).toBe("a1")
  expect(parse("E: vert, 2024-01-01, 1d").tasks[0]).toEqual({ label: "E", start: jan(1), end: jan(2), state: "task" })
  // A flag after the id is not a flag, so the task has too many fields.
  expect(where(syntaxError("gantt\nA: a1, done, 2024-01-01, 1d"))[2]).toStartWith("Gantt tasks require a start and end")
})

test("a task id may be used once", () => {
  expect(where(syntaxError("gantt\nA: a1, 2024-01-01, 1d\nB: a1, 2024-01-02, 1d"))).toEqual([
    3,
    "B: a1, 2024-01-02, 1d",
    'Duplicate task id "a1" in gantt diagram at line 3: "B: a1, 2024-01-02, 1d"',
  ])
})

test("after starts a task at the latest end among the ids it names, which must already be defined", () => {
  const diagram = parse("A: a, 2024-01-01, 3d\nB: b, 2024-01-02, 1d\nC: AFTER   b a, 1d\nD: after b, 2024-01-05")
  expect(diagram.tasks.slice(2).map((task) => [task.start, task.end])).toEqual([
    [jan(4), jan(5)],
    [jan(3), jan(5)],
  ])
  expect(where(syntaxError("gantt\nA: a, 2024-01-01, 1d\nB: after a z, 1d"))).toEqual([
    3,
    "B: after a z, 1d",
    'Unknown Gantt task id "z" in gantt diagram at line 3: "B: after a z, 1d"',
  ])
  expect(where(syntaxError("gantt\nB: after later, 1d\nA: later, 2024-01-01, 1d"))[2]).toStartWith(
    'Unknown Gantt task id "later"',
  )
  expect(where(syntaxError("gantt\nB: after , 1d"))[2]).toStartWith(
    'Unsupported date "after" for dateFormat YYYY-MM-DD',
  )
  expect(where(syntaxError("gantt\nA: a, 2024-01-01, 1d\nB: xafter a, 1d"))[2]).toStartWith(
    'Unsupported date "xafter a"',
  )
})

test("an end may be a duration in ms, s, m, h, d or w, in any case, decimals allowed, a space between", () => {
  const ends = parse(
    ["1ms", "2 S", "1.5m", "3h", "2D", "1w", "0d"].map((end, index) => `T${index}: 2024-01-01, ${end}`).join("\n"),
  ).tasks.map((task) => task.end - task.start)
  expect(ends).toEqual([1, 2_000, 90_000, 3 * 3_600_000, 2 * day, 7 * day, 0])
  expect(where(syntaxError("gantt\nA: 2024-01-01, 2y"))[2]).toStartWith('Unsupported date "2y"')
  for (const end of ["-1d", "2days", "5min"]) {
    expect(where(syntaxError(`gantt\nA: 2024-01-01, ${end}`))[2]).toStartWith(`Unsupported date "${end}"`)
  }
})

test("a task may end where it starts but not before", () => {
  expect(parse("A: 2024-01-02, 2024-01-02").tasks[0]!.end).toBe(jan(2))
  expect(where(syntaxError("gantt\nA: 2024-01-02, 2024-01-01"))).toEqual([
    2,
    "A: 2024-01-02, 2024-01-01",
    'Gantt task cannot end before it starts in gantt diagram at line 2: "A: 2024-01-02, 2024-01-01"',
  ])
})

test("a calendar date is read as UTC under any of the three YYYY-MM-DD formats, with or without a time", () => {
  for (const format of ["YYYY-MM-DD", "YYYY-MM-DD HH:mm", "YYYY-MM-DD HH:mm:ss"]) {
    const tasks = parse(`dateFormat ${format}\nA: 2024-01-02, 2024-01-03 04:05\nB: 2024-01-02T06:07:08, 1s`).tasks
    expect(tasks.map((task) => [task.start, task.end])).toEqual([
      [jan(2), jan(3, 4, 5)],
      [jan(2, 6, 7, 8), jan(2, 6, 7, 9)],
    ])
  }
  expect(parse("A: 2024-02-30, 1d").tasks[0]!.start).toBe(Date.UTC(2024, 2, 1))
  for (const value of ["2024-1-02", "2024-01-02 4:05", "20240102", "1704153600"]) {
    expect(where(syntaxError(`gantt\nA: ${value}, 1d`))[2]).toStartWith(
      `Unsupported date "${value}" for dateFormat YYYY-MM-DD`,
    )
  }
})

test("s and X read seconds, x reads milliseconds, any other format nothing, each for the tasks after it", () => {
  expect(parse("dateFormat s\nA: 1.5, 2").tasks[0]).toMatchObject({ start: 1_500, end: 2_000 })
  expect(parse("dateFormat X\nA: 10, 1s").tasks[0]).toMatchObject({ start: 10_000, end: 11_000 })
  expect(parse("dateFormat x\nA: 1e3, 2000").tasks[0]).toMatchObject({ start: 1_000, end: 2_000 })
  expect(where(syntaxError("gantt\ndateFormat s\nA: 2024-01-01, 1d"))[2]).toStartWith(
    'Unsupported date "2024-01-01" for dateFormat s',
  )
  expect(where(syntaxError("gantt\ndateFormat DD-MM-YYYY\nA: 01-02-2024, 1d"))).toEqual([
    3,
    "A: 01-02-2024, 1d",
    'Unsupported date "01-02-2024" for dateFormat DD-MM-YYYY in gantt diagram at line 3: "A: 01-02-2024, 1d"',
  ])
  // A dateFormat applies only to the tasks after it.
  expect(parse("A: 2024-01-01, 1d\ndateFormat x\nB: 5, 6").tasks.map((task) => task.start)).toEqual([jan(1), 5])
})
