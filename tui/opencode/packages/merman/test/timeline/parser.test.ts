import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidTimelineDiagram, parseMermaidTimelineDiagram } from "../../src/timeline/parser"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidTimelineDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.kind).toBe("timeline")
  return error
}

const where = (error: MermaidSyntaxError) => [error.lineNumber, error.sourceLine, error.message]
const parse = (body: string) => parseMermaidTimelineDiagram(`timeline\n${body}`)

test("a timeline is recognized by its first meaningful line being timeline, optionally with TD or LR, in any case", () => {
  for (const source of ["timeline", "%% note\n\n  TIMELINE td\n2001", "timeline LR", "Timeline   TD"]) {
    expect(isMermaidTimelineDiagram(source)).toBe(true)
  }
  for (const source of ["timeline TB", "timelines", "a timeline", "", "%% only a comment", "title x\ntimeline"]) {
    expect(isMermaidTimelineDiagram(source)).toBe(false)
  }
})

test("the header is optional and sets the direction, LR by default; a later header replaces an earlier, bare or not", () => {
  expect(parseMermaidTimelineDiagram("timeline")).toEqual({ direction: "LR", sections: [], periods: [], entries: [] })
  expect("title" in parseMermaidTimelineDiagram("timeline")).toBe(false)
  expect(parseMermaidTimelineDiagram("timeline td").direction).toBe("TD")
  expect(parseMermaidTimelineDiagram("2001 : a")).toMatchObject({
    direction: "LR",
    periods: [{ period: "2001", events: ["a"] }],
  })
  expect(parseMermaidTimelineDiagram("timeline TD\n2001\ntimeline")).toMatchObject({
    direction: "LR",
    periods: [{ period: "2001", events: [] }],
  })
})

test("a title is read in any case, unquoted and decoded, and a later one replaces an earlier; an empty one is refused", () => {
  expect(parse('TITLE First\ntitle "A &amp; B"').title).toBe("A & B")
  // The trailing comment is cut before the line is read, so the error quotes the line without it.
  expect(where(syntaxError("timeline\n\ntitle %% none"))).toEqual([
    3,
    "title",
    'Timeline title cannot be empty in timeline diagram at line 3: "title"',
  ])
  expect(parse("titled : x\nsubtitle : y")).toMatchObject({
    periods: [
      { period: "titled", events: ["x"] },
      { period: "subtitle", events: ["y"] },
    ],
  })
  expect("title" in parse("titled : x\nsubtitle : y")).toBe(false)
})

test("a section is an entry of its own and ends the period before it, so a continuation after it is refused", () => {
  const diagram = parse("section 'Early &lt;1900&gt;'\n2001\nSECTION Late")
  expect(diagram).toEqual({
    direction: "LR",
    sections: [{ label: "Early <1900>" }, { label: "Late" }],
    periods: [{ period: "2001", events: [] }],
    entries: [
      { type: "section", section: { label: "Early <1900>" } },
      { type: "period", period: { period: "2001", events: [] } },
      { type: "section", section: { label: "Late" } },
    ],
  })
  // The entries hold the very objects the sections and periods lists hold.
  const held = diagram.entries.map((entry) => (entry.type === "section" ? entry.section : entry.period))
  const listed = [diagram.sections[0], diagram.periods[0], diagram.sections[1]]
  expect(held.map((value, index) => value === listed[index])).toEqual([true, true, true])
  expect(parse("sections : x\nsubsection : y")).toMatchObject({
    sections: [],
    periods: [
      { period: "sections", events: ["x"] },
      { period: "subsection", events: ["y"] },
    ],
  })
  expect(where(syntaxError("timeline\nsection"))).toEqual([
    2,
    "section",
    'Timeline section cannot be empty in timeline diagram at line 2: "section"',
  ])
  expect(where(syntaxError("timeline\n2001 : a\nsection S\n: b"))).toEqual([
    4,
    ": b",
    'Timeline continuation requires a preceding period in timeline diagram at line 4: ": b"',
  ])
  expect(where(syntaxError("timeline\n: a"))[0]).toBe(2)
})

test("a line splits at each colon followed by whitespace or the line's end; another colon, or one inside quotes, stays", () => {
  expect(parse('10:30 : a:b : "c : d" : e\n:f : g\nx :y').periods).toEqual([
    { period: "10:30", events: ["a:b", "c : d", "e", "f", "g"] },
    { period: "x :y", events: [] },
  ])
})

test("a quote opens only at a field's start and closes only on its own kind; one never closed is kept as text", () => {
  expect(parse("it's : x\n'x \" : y' : z\n\"a : b").periods).toEqual([
    { period: "it's", events: ["x"] },
    { period: 'x " : y', events: ["z"] },
    { period: '"a : b', events: [] },
  ])
})

test("an empty event or period is refused at its line, which counts blank and comment lines", () => {
  const reason = (kind: string, line: string, at: number) =>
    `Timeline ${kind} cannot be empty in timeline diagram at line ${at}: "${line}"`
  expect(where(syntaxError("%% c\ntimeline\n\n2001 : a : %% note"))).toEqual([
    4,
    "2001 : a :",
    reason("event", "2001 : a :", 4),
  ])
  expect(where(syntaxError("timeline\n2001 : : b"))).toEqual([2, "2001 : : b", reason("event", "2001 : : b", 2)])
  expect(where(syntaxError("timeline\n2001\n:"))).toEqual([3, ":", reason("event", ":", 3)])
  expect(where(syntaxError('timeline\n"" : a'))).toEqual([2, '"" : a', reason("period", '"" : a', 2)])
})

test("# lines, accTitle and accDescr lines, and an accDescr block are skipped; a trailing %% comment is cut", () => {
  const diagram = parse(
    [
      "# 2000 : hidden",
      "accTitle: T",
      "accDescr: D",
      "ACCDESCR {",
      "title Hidden",
      "2001 : inside",
      "}",
      "2002 : kept %% note",
      "accTitled",
      // Only a line that starts with them is skipped, and only a line that ends in { opens a block.
      "2003 : on accTitle: day",
      "accDescr { inline }",
      "2004 : accDescr {",
      "2005",
    ].join("\n"),
  )
  expect("title" in diagram).toBe(false)
  expect(diagram.periods).toEqual([
    { period: "2002", events: ["kept"] },
    { period: "accTitled", events: [] },
    { period: "2003", events: ["on accTitle", "day"] },
    { period: "2004", events: ["accDescr {"] },
    { period: "2005", events: [] },
  ])
})
