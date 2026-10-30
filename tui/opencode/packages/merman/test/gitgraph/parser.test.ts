import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../../src/diagnostics"
import { isMermaidGitGraphDiagram, parseMermaidGitGraphDiagram } from "../../src/gitgraph/parser"
import type { GitGraphCommit } from "../../src/gitgraph/types"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

function syntaxError(source: string): MermaidSyntaxError {
  const error = thrown(() => parseMermaidGitGraphDiagram(source)) as MermaidSyntaxError
  expect(error).toBeInstanceOf(MermaidSyntaxError)
  expect(error.kind).toBe("gitGraph")
  return error
}

const where = (error: MermaidSyntaxError) => [error.lineNumber, error.sourceLine, error.message]
// The reason alone, without the line it names.
function reason(body: string): string {
  const error = syntaxError(`gitGraph\n${body}`)
  const suffix = ` in gitGraph diagram at line ${error.lineNumber}: "${error.sourceLine}"`
  expect(error.message.endsWith(suffix)).toBe(true)
  return error.message.slice(0, -suffix.length)
}
const parse = (body: string) => parseMermaidGitGraphDiagram(`gitGraph\n${body}`)
const commit = (
  id: string,
  branch: string,
  parents: string[],
  extra: Partial<GitGraphCommit> = {},
): GitGraphCommit => ({
  id,
  tags: [],
  type: "NORMAL",
  branch,
  parents,
  ...extra,
})

test("a git graph is recognized by its first meaningful line: gitGraph, an optional LR, TB or BT, an optional colon", () => {
  for (const source of [
    "gitGraph",
    "%% c\n\n  GITGRAPH",
    "gitGraph LR",
    "gitgraph tb:",
    "gitGraph:",
    "gitGraph BT :",
  ]) {
    expect(isMermaidGitGraphDiagram(source)).toBe(true)
  }
  for (const source of [
    "gitGraph RL",
    "gitGraphLR",
    "gitGraphs",
    "agitGraph",
    "gitGraph LR x",
    "",
    "commit\ngitGraph",
  ]) {
    expect(isMermaidGitGraphDiagram(source)).toBe(false)
  }
})

test("a bare header is a graph on main alone, laid left to right unless the header says otherwise", () => {
  expect(parseMermaidGitGraphDiagram("gitGraph")).toEqual({
    direction: "LR",
    branches: [{ name: "main", order: 0 }],
    commits: [],
  })
  expect(parseMermaidGitGraphDiagram("gitgraph tb").direction).toBe("TB")
  expect(parseMermaidGitGraphDiagram("gitGraph BT:").direction).toBe("BT")
})

test("the header must be the first meaningful line, and the error names line 1 wherever that line is", () => {
  expect(where(syntaxError("\n\ncommit"))).toEqual([
    1,
    "commit",
    'GitGraph header is required in gitGraph diagram at line 1: "commit"',
  ])
  expect(where(syntaxError(""))).toEqual([1, "", 'GitGraph header is required in gitGraph diagram at line 1: ""'])
  // Pinned as observed: the first line is matched before comments are stripped, and before accessibility lines are skipped.
  expect(where(syntaxError("gitGraph %% note"))[1]).toBe("gitGraph %% note")
  expect(where(syntaxError("accTitle: x\ngitGraph"))[1]).toBe("accTitle: x")
})

test("the header may appear only once", () => {
  expect(where(syntaxError("gitGraph\ncommit\n gitGraph TB"))).toEqual([
    3,
    "gitGraph TB",
    'GitGraph header can only appear once in gitGraph diagram at line 3: "gitGraph TB"',
  ])
})

test("accessibility lines, an accDescr block and title lines are skipped", () => {
  const diagram = parse("accTitle: T\naccDescr x\naccDescr {\ncommit\n}\ntitle Graph\nTITLE\ncommit")
  expect(diagram.commits.map((entry) => entry.id)).toEqual(["commit-1"])
  expect(reason("titled x")).toBe("Unsupported syntax")
  for (const line of ["accTitleX", "noaccTitle: x", "noaccDescr {", "subtitle x"])
    expect(reason(line)).toBe("Unsupported syntax")
  expect(parse("accDescr {one line}\ncommit").commits).toHaveLength(1)
})

test("a %% comment runs to the end of the line, except inside quotes", () => {
  expect(parse('commit %% first\ncommit msg: "50%% off" %% second').commits).toEqual([
    commit("commit-1", "main", []),
    commit("commit-2", "main", ["commit-1"], { message: "50%% off" }),
  ])
  expect(parse(`commit msg: "it's 100%%"`).commits[0]!.message).toBe("it's 100%%")
  expect(parse(`commit msg: '50%% off'`).commits[0]!.message).toBe("50%% off")
  expect(parse("commit tag:v1%% note\ncommit %%").commits.map((entry) => entry.tags)).toEqual([["v1"], []])
  // The line an error names has its comment and the space before it cut, and a quote opening the line counts.
  expect(where(syntaxError("gitGraph\nrebase dev %% x"))[1]).toBe("rebase dev")
  expect(where(syntaxError('gitGraph\n"x" %% c'))[1]).toBe('"x"')
})

test("a commit takes an id, a message, a type and any number of tags; the colon is optional and the key's case free", () => {
  expect(
    parse('commit id: "a" msg: "Fix it" type: highlight tag: v1 TAG:"v 2"\ncommit ID a2 type REVERSE').commits,
  ).toEqual([
    commit("a", "main", [], { message: "Fix it", type: "HIGHLIGHT", tags: ["v1", "v 2"] }),
    commit("a2", "main", ["a"], { type: "REVERSE" }),
  ])
  expect(parse("commit type: Normal").commits[0]!.type).toBe("NORMAL")
})

test("a quoted first word is the message, and a msg attribute wins over it", () => {
  expect(parse("commit 'First one' tag: t").commits[0]).toEqual(
    commit("commit-1", "main", [], { message: "First one", tags: ["t"] }),
  )
  expect(parse('commit "short" msg: "long"').commits[0]!.message).toBe("long")
  expect(reason('commit msg: x "late"')).toBe('Unsupported GitGraph attribute ""late""')
  // Only a word quoted end to end is a message.
  expect(reason('commit x"a"')).toBe('Unsupported GitGraph attribute "x"a""')
  expect(reason('commit "a"b')).toBe('Unsupported GitGraph attribute ""a"b"')
})

test("a commit's attributes are checked: known, given a value, said once, of a known type, a non-empty unused id", () => {
  expect(reason("commit foo: 1")).toBe('Unsupported GitGraph attribute "foo"')
  expect(reason("commit :x")).toBe('Unsupported GitGraph attribute ""')
  expect(reason("commit id:")).toBe('GitGraph attribute "id" requires a value')
  expect(reason("commit msg: a msg: b")).toBe('GitGraph attribute "msg" cannot repeat')
  expect(reason("commit type: big")).toBe('Unknown GitGraph commit type "big"')
  expect(reason('commit id: ""')).toBe("GitGraph commit id cannot be empty")
  expect(reason("commit id: x\ncommit id: x")).toBe('Duplicate commit id "x"')
})

// bench/subsume reads this case as redundant: it cannot move the numbering's increment. Taking a number
// for every commit, id given or not, fails this case alone (planted by hand, 2026-10-30).
test("each commit is on the current branch, its head the parent, numbered from 1 when no id is given; a number is taken only when used", () => {
  expect(parse("commit\ncommit\nCOMMIT")).toEqual({
    direction: "LR",
    branches: [{ name: "main", order: 0, head: "commit-3" }],
    commits: [
      commit("commit-1", "main", []),
      commit("commit-2", "main", ["commit-1"]),
      commit("commit-3", "main", ["commit-2"]),
    ],
  })
  // So a given id can claim the next number's name.
  expect(parse("commit id: commit-2\ncommit").commits.map((entry) => entry.id)).toEqual(["commit-2", "commit-1"])
  expect(reason("commit id: commit-1\ncommit")).toBe('Duplicate commit id "commit-1"')
})

test("an unclosed quote leaves the line one word, which is no command", () => {
  expect(reason('commit msg: "open')).toBe("Unsupported syntax")
})

test("a branch starts at the current head and becomes current; its name is unquoted and must be new", () => {
  const diagram = parse("commit\nbranch 'dev'\ncommit\ncheckout main\nbranch empty")
  expect(diagram.branches).toEqual([
    { name: "main", order: 0, head: "commit-1" },
    { name: "dev", head: "commit-2" },
    { name: "empty", head: "commit-1" },
  ])
  expect(diagram.commits[1]).toEqual(commit("commit-2", "dev", ["commit-1"]))
  expect(parse("branch dev").branches).toEqual([{ name: "main", order: 0 }, { name: "dev" }])
  expect(reason("branch")).toBe("GitGraph branch name cannot be empty")
  expect(reason('branch ""')).toBe("GitGraph branch name cannot be empty")
  expect(reason("branch main")).toBe('Duplicate branch "main"')
  expect(reason("branch dev id: 1")).toBe('Unsupported GitGraph attribute "id"')
})

test("a branch order must be a non-negative integer", () => {
  expect(parse("branch dev order: 3").branches[1]).toEqual({ name: "dev", order: 3 })
  expect(parse("branch dev order 0").branches[1]).toEqual({ name: "dev", order: 0 })
  for (const order of ["-1", "1.5", "x"]) {
    expect(reason(`branch dev order: ${order}`)).toBe("GitGraph branch order must be a non-negative integer")
  }
})

test("main comes first, then the unordered branches as made, then the ordered by order, ties as made", () => {
  const diagram = parse("branch a order: 2\nbranch b\nbranch c order: 1\nbranch d order: 1\nbranch e")
  expect(diagram.branches.map((branch) => branch.name)).toEqual(["main", "b", "e", "c", "d", "a"])
})

test("checkout and switch take exactly one known branch", () => {
  expect(parse("branch dev\ncheckout main\ncommit\nswitch dev\ncommit").commits.map((entry) => entry.branch)).toEqual([
    "main",
    "dev",
  ])
  expect(parse('branch dev\ncheckout "main"\ncommit').commits[0]!.branch).toBe("main")
  expect(reason("checkout")).toBe("GitGraph checkout requires one branch")
  expect(reason("SWITCH a b")).toBe("GitGraph switch requires one branch")
  expect(reason("checkout dev")).toBe('Unknown branch "dev"')
})

test("a merge is a commit on the current branch whose parents are its head and the merged head, and may repeat", () => {
  const diagram = parse(
    "commit\nbranch dev\ncommit\ncheckout main\ncommit\nmerge 'dev' tag: v1 type: reverse\nmerge dev id: m",
  )
  expect(diagram.commits.slice(3)).toEqual([
    commit("commit-4", "main", ["commit-3", "commit-2"], { tags: ["v1"], type: "REVERSE" }),
    commit("m", "main", ["commit-4", "commit-2"]),
  ])
  expect(diagram.branches).toEqual([
    { name: "main", order: 0, head: "m" },
    { name: "dev", head: "commit-2" },
  ])
})

test("a merge needs a known other branch, both with commits and different heads, and takes no message", () => {
  expect(reason("merge")).toBe("GitGraph merge requires a branch")
  expect(reason("merge dev")).toBe('Unknown branch "dev"')
  expect(reason("merge main")).toBe("GitGraph cannot merge a branch into itself")
  expect(reason("branch dev\ncommit\ncheckout main\nmerge dev")).toBe('Branch "main" has no commits')
  expect(reason("commit\nbranch dev\nbranch other\ncheckout main\nmerge other")).toBe(
    'Branches already share head "commit-1"',
  )
  expect(reason("branch dev\ncheckout main\ncommit\nmerge dev")).toBe('Branch "dev" has no commits')
  expect(reason("commit\nbranch dev\ncommit\ncheckout main\nmerge dev msg: x")).toBe(
    'Unsupported GitGraph attribute "msg"',
  )
  expect(reason("commit id: x\nbranch dev\ncommit\ncheckout main\nmerge dev id: x")).toBe('Duplicate commit id "x"')
})

test("cherry-pick is refused by name, any other command as unsupported", () => {
  expect(reason("cherry-pick id: x")).toBe("Cherry-pick is not supported")
  expect(reason("rebase dev")).toBe("Unsupported syntax")
})
