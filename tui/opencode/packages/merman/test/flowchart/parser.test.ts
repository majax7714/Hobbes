import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidFlowchartDiagram, parseMermaidFlowchartDiagram } from "../../src/flowchart/parser"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidFlowchartDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.name).toBe("MermaidSyntaxError")
  expect(error.kind).toBe("flowchart")
  return error
}

const parse = (body: string) => parseMermaidFlowchartDiagram(`flowchart\n${body}`)

test("a flowchart is recognized by its first meaningful line: flowchart or graph, with an optional direction", () => {
  for (const source of ["flowchart LR", "graph", "%% note\n\n  GRAPH td\nA", "flowchart RL"]) {
    expect(isMermaidFlowchartDiagram(source)).toBe(true)
  }
  for (const source of ["flowchartLR", "flowchart XY", "sequenceDiagram", "", "%% only a comment", "A --> B\nflowchart"]) {
    expect(isMermaidFlowchartDiagram(source)).toBe(false)
  }
})

test("the direction defaults to TD, is read in any case, and a later header replaces it", () => {
  expect(parseMermaidFlowchartDiagram("flowchart").direction).toBe("TD")
  expect(parseMermaidFlowchartDiagram("graph lr").direction).toBe("LR")
  expect(parseMermaidFlowchartDiagram("flowchart LR\nflowchart BT").direction).toBe("BT")
  for (const direction of ["TB", "TD", "BT", "LR", "RL"] as const) {
    expect(parseMermaidFlowchartDiagram(`graph ${direction}`).direction).toBe(direction)
  }
  expect(parseMermaidFlowchartDiagram("flowchart TB")).toEqual({ direction: "TB", nodes: [], edges: [], subgraphs: [] })
})

test("each node shape is read from its brackets, and a bare id is a box labelled by its id", () => {
  const diagram = parse("A[(db)]\nB[[sub]]\nC([pill])\nD(round)\nE{choose}\nF[box]\nG")
  expect(diagram.nodes).toEqual([
    { id: "A", label: "db", shape: "database" },
    { id: "B", label: "sub", shape: "subroutine" },
    { id: "C", label: "pill", shape: "rounded" },
    { id: "D", label: "round", shape: "rounded" },
    { id: "E", label: "choose", shape: "decision" },
    { id: "F", label: "box", shape: "box" },
    { id: "G", label: "G", shape: "box" },
  ])
})

test("a label loses its quotes, in every shape, and has its HTML entities decoded", () => {
  expect(parse('A["two words"]\nB[a &amp; b]\nc.d-e_1').nodes).toEqual([
    { id: "A", label: "two words", shape: "box" },
    { id: "B", label: "a & b", shape: "box" },
    { id: "c.d-e_1", label: "c.d-e_1", shape: "box" },
  ])
  const quoted = parse(`A[("db")]\nB[["sub"]]\nC(["pill"])\nD('round')\nE{"choose"}`).nodes
  expect(quoted.map((node) => node.label)).toEqual(["db", "sub", "pill", "round", "choose"])
})

test("a circle node, an edge with a missing end or an unknown statement is refused at its line as written", () => {
  for (const [body, line] of [["A((c))", "A((c))"], ["  A((c)) --> B", "A((c)) --> B"]] as const) {
    const error = syntaxError(`flowchart\n\n%% c\n${body}`)
    expect(error.lineNumber).toBe(4)
    expect(error.sourceLine).toBe(line)
    expect(error.message).toBe(`Unsupported syntax in flowchart diagram at line 4: "${line}"`)
  }
  for (const line of ["A -->", "click A callback", "A[open"]) {
    expect(syntaxError(`flowchart\n${line}`).message).toBe(`Unsupported syntax in flowchart diagram at line 2: "${line}"`)
  }
  expect(syntaxError("flowchart\nsubgraph S\nend\nS((x)) ~~~ B").lineNumber).toBe(4)
  expect(syntaxError("flowchart\nsubgraph S\nA --> direction LR\nend").message).toBe(
    'Unsupported syntax in flowchart diagram at line 3: "A --> direction LR"',
  )
})

test("a later bare reference keeps a node's shape, but a later shape replaces it", () => {
  expect(parse("A{Ask}\nA --> B").nodes[0]).toEqual({ id: "A", label: "Ask", shape: "decision" })
  expect(parse("A[One]\nA --> B\nA(Two)").nodes).toEqual([
    { id: "A", label: "Two", shape: "rounded" },
    { id: "B", label: "B", shape: "box" },
  ])
})

test("each arrow sets an edge's style and heads", () => {
  const edge = (operator: string) => parse(`A ${operator} B`).edges
  expect(edge("-->")).toEqual([{ from: "A", to: "B", label: "" }])
  expect(edge("---")).toEqual([{ from: "A", to: "B", label: "", arrowhead: false }])
  expect(edge("<-->")).toEqual([{ from: "A", to: "B", label: "", sourceArrowhead: true }])
  expect(edge("==>")).toEqual([{ from: "A", to: "B", label: "", style: "thick" }])
  expect(edge("-.->")).toEqual([{ from: "A", to: "B", label: "", style: "dashed" }])
  expect(edge("== x -->")).toEqual([{ from: "A", to: "B", label: "x", style: "thick" }])
})

test("an edge label is read from pipes or from inside the arrow, unquoted", () => {
  const labelled = (operator: string) => parse(`A ${operator} B`).edges
  expect(labelled("-->|yes|")).toEqual([{ from: "A", to: "B", label: "yes" }])
  expect(labelled('-->|"no way"|')).toEqual([{ from: "A", to: "B", label: "no way" }])
  expect(labelled("-- text -->")).toEqual([{ from: "A", to: "B", label: "text" }])
  expect(labelled("== heavy ==>")).toEqual([{ from: "A", to: "B", label: "heavy", style: "thick" }])
  expect(labelled("-. maybe .->")).toEqual([{ from: "A", to: "B", label: "maybe", style: "dashed" }])
  expect(labelled("-. open .-")).toEqual([{ from: "A", to: "B", label: "open", style: "dashed", arrowhead: false }])
  expect(labelled('-- "a --> b" -->')).toEqual([{ from: "A", to: "B", label: "a --> b" }])
  expect(labelled("-- 'a <-> b' -->")).toEqual([{ from: "A", to: "B", label: "a <-> b" }])
})

test("a chain makes one edge per link, and an & group links every pair in order", () => {
  expect(parse("A --> B --> C").edges).toEqual([
    { from: "A", to: "B", label: "" },
    { from: "B", to: "C", label: "" },
  ])
  expect(parse("A & B --> C & D").edges.map((edge) => `${edge.from}${edge.to}`)).toEqual(["AC", "AD", "BC", "BD"])
  expect(parse("A&B --> C").edges.map((edge) => `${edge.from}${edge.to}`)).toEqual(["AC", "BC"])
  expect(parse("A:::hot & B;").nodes.map((node) => node.id)).toEqual(["A", "B"])
  expect(parse("A & B[Bee]").nodes).toEqual([
    { id: "A", label: "A", shape: "box" },
    { id: "B", label: "Bee", shape: "box" },
  ])
})

test("an & or an arrow inside a label or quotes belongs to the label", () => {
  const diagram = parse('A["x & y"] --> B[a --> b] --> C')
  expect(diagram.nodes.map((node) => node.label)).toEqual(["x & y", "a --> b", "C"])
  expect(diagram.edges.map((edge) => `${edge.from}${edge.to}`)).toEqual(["AB", "BC"])
  const group = parse(`A[x] & B(p & q) & C{r & s} & D["t ] & u"] & E('v ) & w') & F["\\" ] & z"] --> G`)
  expect(group.nodes.map((node) => node.label)).toEqual(["x", "p & q", "r & s", "t ] & u", "v ) & w", '\\" ] & z', "G"])
  expect(group.edges.map((edge) => edge.from).join("")).toBe("ABCDEF")
  expect(parse("A(a --> b) --> B{c --> d} --> C").nodes.map((node) => node.label)).toEqual(["a --> b", "c --> d", "C"])
  const masked = parse(`A["x ] --> y"] --> B('p ) --> q') --> C["\\" ] --> z"] --> D`)
  expect(masked.nodes.map((node) => node.label)).toEqual(["x ] --> y", "p ) --> q", '\\" ] --> z', "D"])
  expect(masked.edges.map((edge) => `${edge.from}${edge.to}`)).toEqual(["AB", "BC", "CD"])
})

test("an order-only link has no style, and may name a subgraph without making it a node", () => {
  expect(parse("A ~~~ B").edges).toEqual([{ from: "A", to: "B", label: "", orderOnly: true }])
  const diagram = parse("subgraph S\nA\nend\nS ~~~ B")
  expect(diagram.nodes.map((node) => node.id)).toEqual(["A", "B"])
  expect(diagram.edges).toEqual([{ from: "S", to: "B", label: "", orderOnly: true }])
  expect(parse("subgraph S\nend\nB ~~~ S").nodes.map((node) => node.id)).toEqual(["B"])
})

test("a trailing semicolon ends a statement; one between statements is refused unless it is in a label", () => {
  expect(parse("A --> B;").edges).toEqual([{ from: "A", to: "B", label: "" }])
  expect(parse('A["x; y"] --> B').nodes[0]!.label).toBe("x; y")
  expect(parse("A -->|a;b| B").edges[0]!.label).toBe("a;b")
  expect(parse('A -- "x; y" --> B').edges[0]!.label).toBe("x; y")
  expect(parse(`A["x ]; y"] --> B('p ); q') --> C["\\" ]; z"]`).nodes.map((node) => node.label)).toEqual([
    "x ]; y",
    "p ); q",
    '\\" ]; z',
  ])
  expect(parse("A[x] -->|p;q| B -->|r;s| C").edges.map((edge) => edge.label)).toEqual(["p;q", "r;s"])
  expect(parse("A(x;y) --> B{p;q}").nodes.map((node) => node.label)).toEqual(["x;y", "p;q"])
  for (const line of ["A --> B; B --> C", "A[x]; B[y]", "A[x];]", "A(x); B(y)", "A{x}; B{y}", 'A["x"]; B[y]', "A -->|p| B[x]; C[y]"]) {
    expect(syntaxError(`flowchart\n${line}`).message).toBe(`Unsupported syntax in flowchart diagram at line 2: "${line}"`)
  }
})

test("a statement may be 10 000 characters long and not one more", () => {
  const atLimit = `A[${"x".repeat(9_997)}]`
  expect(parse(atLimit).nodes[0]!.label.length).toBe(9_997)
  const tooLong = `A[${"x".repeat(9_998)}]`
  const error = syntaxError(`flowchart\n${tooLong}`)
  expect(error.message).toBe(`Flowchart statement is too long in flowchart diagram at line 2: "${tooLong}"`)
})

test("a keyword counts only as a whole statement's start, so nodes may be named for one", () => {
  const diagram = parseMermaidFlowchartDiagram("flowchart LR\nA --> graph\nA --> style\nendpoint --> backend\nX[in subgraph b]")
  expect(diagram.direction).toBe("LR")
  expect(diagram.edges.map((edge) => edge.to)).toEqual(["graph", "style", "backend"])
  expect(diagram.subgraphs).toEqual([])
  expect(diagram.nodes.at(-1)).toEqual({ id: "X", label: "in subgraph b", shape: "box" })
  expect(syntaxError("flowchart\nsubgraph S\ndirection TBX\nend").message).toBe(
    'Unsupported syntax in flowchart diagram at line 3: "direction TBX"',
  )
})

test("an arrow with nothing after it leaves a name that is still an id, a node", () => {
  expect(parse("a---").nodes).toEqual([{ id: "a---", label: "a---", shape: "box" }])
  expect(parse("a---").edges).toEqual([])
})

test("styling statements are skipped and a ::: class is dropped from a node", () => {
  const diagram = parse("classDef hot fill:#f00\nclass A hot\nstyle A fill:#0f0\nlinkStyle 0 stroke:#00f\nA:::hot --> B")
  expect(diagram.nodes).toEqual([
    { id: "A", label: "A", shape: "box" },
    { id: "B", label: "B", shape: "box" },
  ])
  expect(diagram.edges).toEqual([{ from: "A", to: "B", label: "" }])
})

test("a subgraph is named by its id and bracketed title, its quoted title, or its id alone", () => {
  const diagram = parse(
    'subgraph one [Title]\nend\nsubgraph "My group"\nend\nsubgraph S:::cls;\nend\nsubgraph "Q"\nend\nsubgraph T ["a;b"];\nend',
  )
  expect(diagram.subgraphs).toEqual([
    { id: "one", label: "Title", nodeIds: [] },
    { id: "subgraph_2", label: "My group", nodeIds: [] },
    { id: "S", label: "S", nodeIds: [] },
    { id: "Q", label: "Q", nodeIds: [] },
    { id: "T", label: "a;b", nodeIds: [] },
  ])
})

test("a subgraph holds the nodes its own statements name, knows its parent, and may set its direction", () => {
  const diagram = parse("X\nsubgraph outer\nX --> A\nsubgraph inner\ndirection lr\nB & C\nend\nend")
  expect(diagram.subgraphs).toEqual([
    { id: "outer", label: "outer", nodeIds: ["X", "A"] },
    { id: "inner", label: "inner", nodeIds: ["B", "C"], parentId: "outer", direction: "LR" },
  ])
  expect(diagram.direction).toBe("TD")
})

test("a stray end, a direction outside a subgraph and an unclosed subgraph are each refused by reason", () => {
  expect(syntaxError("flowchart\nend").message).toBe(
    'Unexpected "end" without an open subgraph in flowchart diagram at line 2: "end"',
  )
  expect(syntaxError("flowchart\ndirection LR").message).toBe(
    'A "direction" statement requires an open subgraph in flowchart diagram at line 2: "direction LR"',
  )
  const unclosed = syntaxError("flowchart\nsubgraph a\nsubgraph b\nend\nA")
  expect(unclosed.message).toBe('Unclosed subgraph; expected "end" in flowchart diagram at line 2: "subgraph a"')
})
