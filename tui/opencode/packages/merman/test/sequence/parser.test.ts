import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidSequenceDiagram, parseMermaidSequenceDiagram } from "../../src/sequence/parser"
import type { SequenceMessage } from "../../src/sequence/types"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidSequenceDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.kind).toBe("sequence")
  return error
}

const where = (error: MermaidSyntaxError) => [error.lineNumber, error.sourceLine, error.message]
const parse = (body: string) => parseMermaidSequenceDiagram(`sequenceDiagram\n${body}`)
const message = (from: string, to: string, label: string, extra: Partial<SequenceMessage> = {}): SequenceMessage => ({
  from,
  to,
  label,
  style: "solid",
  ...extra,
})

test("a sequence diagram is recognized by its first meaningful line, sequenceDiagram in any case, which parsing skips", () => {
  for (const source of ["sequenceDiagram", "%% c\n\n  SEQUENCEDIAGRAM  \nA->>B: x", "sequencediagram"]) {
    expect(isMermaidSequenceDiagram(source)).toBe(true)
  }
  for (const source of ["", "%% only", "sequenceDiagram LR", "sequence", "A->>B: x\nsequenceDiagram"]) {
    expect(isMermaidSequenceDiagram(source)).toBe(false)
  }
  // The parser skips the header wherever it is: a body without one parses, and a repeated one is ignored.
  const expected = parse("A->>B: hi")
  expect(parseMermaidSequenceDiagram("A->>B: hi")).toEqual(expected)
  expect(parse("SequenceDiagram\nA->>B: hi")).toEqual(expected)
})

test("each arrow sets a line style and a head: two dashes are dashed, >> the default head, > open, x cross, ) async", () => {
  const diagram = parse(
    ["A->>B: a", "A-->>B: b", "A->B: c", "A-->B: d", "A-xB: e", "A--xB: f", "A-)B: g", "A--)B: h"].join("\n"),
  )
  expect(diagram.messages).toEqual([
    message("A", "B", "a"),
    message("A", "B", "b", { style: "dashed" }),
    message("A", "B", "c", { head: "open" }),
    message("A", "B", "d", { style: "dashed", head: "open" }),
    message("A", "B", "e", { head: "cross" }),
    message("A", "B", "f", { style: "dashed", head: "cross" }),
    message("A", "B", "g", { head: "async" }),
    message("A", "B", "h", { style: "dashed", head: "async" }),
  ])
  expect(diagram.participants).toEqual([
    { id: "A", label: "A" },
    { id: "B", label: "B" },
  ])
})

test("a message's ends and label are trimmed, unquoted and entity-decoded; the label runs from the first colon to the line's end", () => {
  const diagram = parse(
    ['"Web App"  -->>  "API" :  "a: b"  ', "A-B->>C:", "A->>A: x &lt; y: z %% kept", "A->>B: x->y"].join("\n"),
  )
  expect(diagram.messages).toEqual([
    message("Web App", "API", "a: b", { style: "dashed" }),
    message("A-B", "C", ""),
    message("A", "A", "x < y: z %% kept"),
    message("A", "B", "x->y"),
  ])
  expect(diagram.participants.map((participant) => participant.id)).toEqual(["Web App", "API", "A-B", "C", "A", "B"])
})

test("a keyword inside a label, or starting a longer name, leaves a message a message", () => {
  const lines = [
    "A->>B: write a note over C: x",
    "A->>B: ask the actor C",
    "A->>B: then activate C",
    "A->>B: in a box",
    "Boxer->>B: x",
    "A->>B: halt now",
    "A->>B: or else",
    "Elsewhere->>B: x",
    "A->>B: a loop here",
    "A->>B: autonumber",
  ]
  expect(parse(lines.join("\n")).steps.map((step) => step.type)).toEqual(lines.map(() => "message"))
})

test("a + after the arrow activates the receiver; a - deactivates the sender", () => {
  expect(parse("A->>+B: go\nB-->>-A: done\nA->B: plain").messages).toEqual([
    message("A", "B", "go", { activate: "B" }),
    message("B", "A", "done", { style: "dashed", deactivate: "B" }),
    message("A", "B", "plain", { head: "open" }),
  ])
})

test("autonumber numbers the messages after it from a start by a step; notes take no number; a second one restarts", () => {
  const diagram = parse(
    [
      "A->>B: before",
      "autonumber",
      "A->>B: one",
      "Note over A: n",
      "A->>B: two",
      "AUTONUMBER 10 5",
      "A->>B: ten",
      "A->>B: fifteen",
      "autonumber 3",
      "A->>B: three",
      "A->>B: four",
      "autonumber 1 10",
      "A->>B: one again",
      "A->>B: eleven",
    ].join("\n"),
  )
  expect(diagram.messages.map((message) => [message.label, message.number])).toEqual([
    ["before", undefined],
    ["one", 1],
    ["two", 2],
    ["ten", 10],
    ["fifteen", 15],
    ["three", 3],
    ["four", 4],
    ["one again", 1],
    ["eleven", 11],
  ])
  expect("number" in diagram.messages[0]!).toBe(false)
})

test("participant and actor declare alike, in order of first mention; a later declaration replaces the label in place", () => {
  const diagram = parse(
    [
      "B->>C: x",
      "participant A",
      'actor "C" as "The &amp; C"',
      "Participant B as Bee",
      "ACTOR D as Dee",
      "participant D",
      "B->>C: again",
    ].join("\n"),
  )
  // Only a declaration replaces a label; a later message keeps it.
  expect(diagram.participants).toEqual([
    { id: "B", label: "Bee" },
    { id: "C", label: "The & C" },
    { id: "A", label: "A" },
    { id: "D", label: "D" },
  ])
  expect(diagram.steps).toHaveLength(2)
})

test("a note sits over one or more participants, or left or right of one, adding any it names in order", () => {
  const diagram = parse(
    [
      "Note over A: one",
      "note over B , ,C : two: three",
      "NOTE LEFT  OF D: left",
      "note right of 'A':",
      "note left of B,C: &gt; x",
    ].join("\n"),
  )
  expect(diagram.steps).toEqual([
    { type: "note", note: { over: ["A"], label: "one" } },
    { type: "note", note: { over: ["B", "C"], label: "two: three" } },
    { type: "note", note: { over: ["D"], label: "left", position: "left" } },
    { type: "note", note: { over: ["A"], label: "", position: "right" } },
    { type: "note", note: { over: ["B", "C"], label: "> x", position: "left" } },
  ])
  expect(diagram.participants.map((participant) => participant.id)).toEqual(["A", "B", "C", "D"])
  expect(diagram.messages).toEqual([])
})

test("activate and deactivate are steps of their own and add the participant they name", () => {
  const diagram = parse('Activate "A"\nA->>B: x\ndeactivate A\nactivate C')
  expect(diagram.steps.filter((step) => step.type === "activation")).toEqual([
    { type: "activation", activation: { participant: "A", active: true } },
    { type: "activation", activation: { participant: "A", active: false } },
    { type: "activation", activation: { participant: "C", active: true } },
  ])
  expect(diagram.participants.map((participant) => participant.id)).toEqual(["A", "B", "C"])
})

test("alt, else and loop open fragments that end closes, the end labelled by the block it closes", () => {
  const diagram = parse(
    ["ALT 'ok'", "A->>B: x", "else", "Else failed &amp; retried", "loop 'every 5s'", "A->>B: y", "END", "end"].join(
      "\n",
    ),
  )
  expect(diagram.steps.map((step) => (step.type === "fragment" ? step.fragment : step.type))).toEqual([
    { kind: "alt", label: "ok" },
    "message",
    { kind: "else", label: "" },
    { kind: "else", label: "failed & retried" },
    { kind: "loop", label: "every 5s" },
    "message",
    { kind: "end", label: "loop" },
    { kind: "end", label: "alt" },
  ])
})

test("a box groups the participants declared or messaged inside it; its end draws no fragment", () => {
  const diagram = parse(
    [
      "participant Z",
      "box Team",
      "participant A",
      "A->>Z: x",
      "A->>Z: again",
      "Note over Q: not a member",
      "activate R",
      "box Inner",
      "participant B",
      "end",
      "participant C",
      "end",
      "participant D",
      "D->>A: outside",
    ].join("\n"),
  )
  expect(diagram.groups).toEqual([
    { label: "Team", participantIds: ["A", "Z", "C"] },
    { label: "Inner", participantIds: ["B"] },
  ])
  expect(diagram.steps.some((step) => step.type === "fragment")).toBe(false)
})

test("a box's label drops a leading colour: a CSS name, transparent, #rgb to #rrggbbaa, or rgb() and rgba() with spaces", () => {
  const label = (line: string) => parse(`${line}\nend`).groups[0]!.label
  expect(
    [
      "box",
      "box Team",
      "box Purple Team",
      "box BrightCyan  Team",
      "box transparent",
      "box #0a0 Team",
      "box #AABBCCDD Team",
      "box rgb(1, 2, 3) Team",
      "box rgba(0,0,0,0.5)",
      "box rgb(1,2,3)Team",
      'box aqua "My Team"',
      "box navy 'Ops'",
      "box red rgb(1, 2) Team",
      "box Team &amp; Co",
    ].map(label),
  ).toEqual([
    "",
    "Team",
    "Team",
    "Team",
    "",
    "Team",
    "Team",
    "Team",
    "",
    "Team",
    "My Team",
    "Ops",
    "rgb(1, 2) Team",
    "Team & Co",
  ])
  const names = ["black", "white", "red", "green", "blue", "yellow", "cyan", "magenta", "silver", "gray", "grey"]
  names.push("maroon", "olive", "lime", "aqua", "teal", "navy", "fuchsia", "purple", "orange")
  names.push("brightblack", "brightred", "brightgreen", "brightblue", "brightyellow", "brightcyan", "brightmagenta")
  names.push("brightwhite")
  expect(names.map((name) => label(`box ${name} Team`))).toEqual(names.map(() => "Team"))
  // Not colours, so kept as the label: too few or too many hex digits, an unclosed rgb(, a word that is not a
  // colour name, and a quoted label, kept whole even when it starts with a colour.
  expect(
    ["box #ab Team", "box #abcdefabc Team", "box rgb(1, 2", "box Redd Team", 'box "red Team"', "box 'Navy'"].map(label),
  ).toEqual(["#ab Team", "#abcdefabc Team", "rgb(1, 2", "Redd Team", "red Team", "Navy"])
})

test("an else needs an alt directly open; an end needs any block open", () => {
  expect(where(syntaxError("sequenceDiagram\nelse x"))).toEqual([
    2,
    "else x",
    'Unexpected "else" without an open "alt" block in sequence diagram at line 2: "else x"',
  ])
  expect(where(syntaxError("sequenceDiagram\nalt a\nloop b\nelse c\nend\nend"))[0]).toBe(4)
  expect(where(syntaxError("sequenceDiagram\nalt a\nbox\nelse c\nend\nend"))[0]).toBe(4)
  expect(where(syntaxError("sequenceDiagram\n%% c\n\n  end  "))).toEqual([
    4,
    "end",
    'Unexpected "end" without an open block in sequence diagram at line 4: "end"',
  ])
})

test("an unclosed block is reported at the innermost one still open", () => {
  expect(where(syntaxError("sequenceDiagram\nalt a\nloop b\nend"))).toEqual([
    2,
    "alt a",
    'Unclosed alt block; expected "end" in sequence diagram at line 2: "alt a"',
  ])
  expect(where(syntaxError("sequenceDiagram\nloop a\nbox Team\n"))).toEqual([
    3,
    "box Team",
    'Unclosed box block; expected "end" in sequence diagram at line 3: "box Team"',
  ])
  expect(where(syntaxError("sequenceDiagram\nloop forever"))[2]).toBe(
    'Unclosed loop block; expected "end" in sequence diagram at line 2: "loop forever"',
  )
})

test("a two-headed arrow is refused on any line, before the line is otherwise read", () => {
  for (const line of ["A<<->>B: x", "A<<-->>B: x", "Note over A: a <<->> b"]) {
    expect(where(syntaxError(`sequenceDiagram\n${line}`))).toEqual([
      2,
      line,
      `Unsupported syntax in sequence diagram at line 2: "${line}"`,
    ])
  }
})

test("a line no statement matches is refused: an arrow inside an end, no colon, a bare alt or loop, an unsupported block", () => {
  for (const line of [
    "A->>B->>C: x",
    '"A->B"->>C: x',
    "A->>B",
    "alt",
    "loop",
    "opt maybe",
    "par a",
    "autonumber off",
    "participant Alice Smith",
    "participant A as",
    "Note over A",
  ]) {
    expect(where(syntaxError(`sequenceDiagram\n${line}`))).toEqual([
      2,
      line,
      `Unsupported syntax in sequence diagram at line 2: "${line}"`,
    ])
  }
})

// subsume reads this case as redundant: it cannot plant a change in the order statements are tried. Planted by
// hand (messages matched before loop and activate), this is the only case that fails.
test("statements are matched before messages, so a keyword-named sender followed by a space reads as that keyword", () => {
  expect(parse("loop ->> B: x\nend").steps[0]).toEqual({
    type: "fragment",
    fragment: { kind: "loop", label: "->> B: x" },
  })
  expect(parse("activate ->> B: x").steps[0]).toEqual({
    type: "activation",
    activation: { participant: "->> B: x", active: true },
  })
  // Without the space it is a message.
  expect(parse("loop->>B: x").messages).toEqual([message("loop", "B", "x")])
})
