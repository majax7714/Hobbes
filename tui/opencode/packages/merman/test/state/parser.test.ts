import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidStateDiagram, parseMermaidStateDiagram } from "../../src/state/parser"
import type { StateDiagramState } from "../../src/state/types"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidStateDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.kind).toBe("state")
  return error
}

const where = (error: MermaidSyntaxError) => [error.lineNumber, error.sourceLine, error.message]
const parse = (body: string) => parseMermaidStateDiagram(`stateDiagram-v2\n${body}`)
const state = (id: string, extra: Partial<StateDiagramState> = {}): StateDiagramState => ({
  id,
  label: id,
  kind: "state",
  ...extra,
})

test("a state diagram is recognized by its first meaningful line, stateDiagram or stateDiagram-v2 in any case", () => {
  for (const source of ["stateDiagram", "stateDiagram-v2", "%% c\n\n  STATEDIAGRAM-V2  \nA --> B"]) {
    expect(isMermaidStateDiagram(source)).toBe(true)
  }
  for (const source of ["", "%% only", "stateDiagram LR", "stateDiagram-v3", "A --> B\nstateDiagram"]) {
    expect(isMermaidStateDiagram(source)).toBe(false)
  }
  // The parser skips either header wherever it is.
  const expected = parse("A --> B")
  expect(parseMermaidStateDiagram("A --> B")).toEqual(expected)
  expect(parse("stateDiagram\nA --> B")).toEqual(expected)
})

test("a transition names its ends, spaced or not, with an optional label after a colon, trimmed and decoded", () => {
  const diagram = parse("A --> B\nB-->C\nC --> A :  x &amp; y: z  \nA --> A:")
  expect(diagram.transitions).toEqual([
    { from: "A", to: "B", label: "" },
    { from: "B", to: "C", label: "" },
    { from: "C", to: "A", label: "x & y: z" },
    { from: "A", to: "A", label: "" },
  ])
  expect(diagram.states).toEqual([state("A"), state("B"), state("C")])
  expect(diagram).toMatchObject({ direction: "LR", composites: [], notes: [] })
  // [*] is a start marker as a source and an end marker as a target, drawn ● and ◎.
  const markers = parse("[*] --> A\n%% a comment\nA --> [*]\n[*] --> B")
  expect(markers.transitions).toEqual([
    { from: "__start", to: "A", label: "" },
    { from: "A", to: "__end", label: "" },
    { from: "__start", to: "B", label: "" },
  ])
  expect(markers.states).toEqual([
    { id: "__start", label: "●", kind: "start" },
    state("A"),
    { id: "__end", label: "◎", kind: "end" },
    state("B"),
  ])
})

test("a keyword inside a transition's label leaves it a transition", () => {
  const lines = [
    'A --> B : state "x" as Y',
    "A --> B : state X {",
    "A --> B : state c <<choice>>",
    "A --> B : direction TB",
    "A --> B : note left of C: x",
    "A --> B : note left of C",
  ]
  const diagram = parse(lines.join("\n"))
  expect(diagram.transitions.map((t) => t.label)).toEqual(lines.map((line) => line.slice("A --> B : ".length)))
  expect(diagram).toMatchObject({ direction: "LR", composites: [], notes: [] })
})

test("a declared label replaces only the id; the first one stays; a choice takes the kind and an empty label", () => {
  const diagram = parse(
    [
      "A --> B",
      'state "First &lt;A&gt;" as A',
      'STATE "Second" as A',
      "state c <<choice>>",
      "B --> c",
      "c --> d",
      "state d <<choice>>",
    ].join("\n"),
  )
  expect(diagram.states).toEqual([
    state("A", { label: "First <A>" }),
    state("B"),
    { id: "c", label: "", kind: "choice" },
    { id: "d", label: "", kind: "choice" },
  ])
})

test("direction sets the diagram's, in any case; LR when none is given", () => {
  expect(parse("A --> B").direction).toBe("LR")
  expect(["TB", "TD", "BT", "LR", "RL"].map((d) => parse(`direction ${d.toLowerCase()}\nA --> B`).direction)).toEqual([
    "TB",
    "TD",
    "BT",
    "LR",
    "RL",
  ])
  expect(parse("direction TB\ndirection RL").direction).toBe("RL")
})

test("an inline note is split on <br> with italics dropped, decoded first, and adds no state", () => {
  const diagram = parse(
    [
      "note left of A: one<br/>two",
      "Note RIGHT of B :  <i>it</i> &amp; <em>em</em>  ",
      "note left of A: a &lt;br&gt; b",
    ].join("\n"),
  )
  expect(diagram.notes).toEqual([
    { position: "left", target: "A", lines: ["one", "two"] },
    { position: "right", target: "B", lines: ["it & em"] },
    { position: "left", target: "A", lines: ["a", "b"] },
  ])
  expect(diagram.states).toEqual([])
})

test("a block note keeps its lines verbatim to end note, past leading blanks, comments and <br> included", () => {
  const diagram = parse(
    [
      "NOTE Right of A",
      "",
      "  first &amp;  ",
      "",
      "%% kept",
      "a<br>b",
      "stateDiagram",
      "the end note",
      "end notes",
      "END  NOTE",
      "A --> B",
    ].join("\n"),
  )
  expect(diagram.notes).toEqual([
    {
      position: "right",
      target: "A",
      lines: ["first &", "", "%% kept", "a<br>b", "stateDiagram", "the end note", "end notes"],
    },
  ])
  expect(diagram.transitions).toHaveLength(1)
})

test("a composite opens with state … { and closes with }; its states and markers take it as their parent", () => {
  const diagram = parse(
    [
      'state "Outer &amp; more" as P {',
      "  [*] --> X",
      "  state Q{",
      '    state "Why" as Y',
      "  }",
      "  X --> [*]",
      "}",
    ].join("\n"),
  )
  expect(diagram.composites).toEqual([
    { id: "P", label: "Outer & more" },
    { id: "Q", label: "Q", parentId: "P" },
  ])
  expect(diagram.states).toEqual([
    { id: "P.__start", label: "●", kind: "start", parentId: "P" },
    state("X", { parentId: "P" }),
    state("Y", { label: "Why", parentId: "Q" }),
    { id: "P.__end", label: "◎", kind: "end", parentId: "P" },
  ])
})

test("a transition to a composite enters at its start marker and one from it leaves at its end marker, if it has them", () => {
  const diagram = parse(
    [
      "state P {",
      "  [*] --> X",
      "  X --> [*]",
      "}",
      "state Q {",
      "  Z --> Z",
      "}",
      "A --> P",
      "P --> B",
      "A --> Q",
      "Q --> B",
    ].join("\n"),
  )
  expect(diagram.transitions.slice(3)).toEqual([
    { from: "A", to: "P.__start", label: "" },
    { from: "P.__end", to: "B", label: "" },
    { from: "A", to: "Q", label: "" },
    { from: "Q", to: "B", label: "" },
  ])
  // A composite is not a state of its own.
  expect(diagram.states.map((s) => s.id)).toEqual(["P.__start", "X", "P.__end", "Z", "A", "B"])
  // So too with one composite.
  const one = parse("state P {\n  [*] --> X\n}\nA --> P")
  expect(one.transitions[1]).toEqual({ from: "A", to: "P.__start", label: "" })
  expect(one.states.map((s) => s.id)).toEqual(["P.__start", "X", "A"])
})

test("a state takes the first composite it is named in, even after it is first seen outside one", () => {
  const diagram = parse('A --> B\nstate P {\n  state "Bee" as B\n}\nstate Q {\n  B --> C\n}')
  expect(diagram.states).toEqual([
    state("A"),
    state("B", { label: "Bee", parentId: "P" }),
    state("C", { parentId: "Q" }),
  ])
})

test("a } with no composite open, a direction inside one, and an unclosed composite or note are refused", () => {
  expect(where(syntaxError("stateDiagram\n}"))).toEqual([
    2,
    "}",
    'Unexpected "}" without an open composite state in state diagram at line 2: "}"',
  ])
  expect(where(syntaxError("stateDiagram\nstate P {\n  direction TB\n}"))).toEqual([
    3,
    "direction TB",
    'Composite-local direction is not supported in state diagram at line 3: "direction TB"',
  ])
  expect(where(syntaxError("stateDiagram\nstate P {\nstate Q {\n}"))).toEqual([
    2,
    "state P {",
    'Unclosed composite state; expected "}" in state diagram at line 2: "state P {"',
  ])
  expect(where(syntaxError("stateDiagram\nnote left of A\nx\nstate P {"))).toEqual([
    2,
    "note left of A",
    'Unclosed note; expected "end note" in state diagram at line 2: "note left of A"',
  ])
})

test("a line no statement matches is refused: a chained arrow, a bare state, trailing text, a description, a fork", () => {
  for (const line of [
    "A --> B --> C",
    "A-->B-->C",
    "A --> B-->C",
    "state A",
    'state "x" as Y extra',
    "state P {}",
    "state c <<choice>> x",
    "direction LRX",
    "note left of A B",
    "A : waiting",
    "state f <<fork>>",
    "A -> B",
    "--> B",
  ]) {
    expect(where(syntaxError(`stateDiagram\n\n${line}`))).toEqual([
      3,
      line,
      `Unsupported syntax in state diagram at line 3: "${line}"`,
    ])
  }
})
