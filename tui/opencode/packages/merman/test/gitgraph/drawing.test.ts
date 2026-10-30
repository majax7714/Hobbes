import { expect, test } from "bun:test"
import { drawGitGraphDiagramGrid } from "../../src/gitgraph/drawing"
import { parseMermaidGitGraphDiagram } from "../../src/gitgraph/parser"
import { renderGitGraphGridText, type GitGraphGrid } from "../../src/gitgraph/render-grid"

const draw = (body: string) => drawGitGraphDiagramGrid(parseMermaidGitGraphDiagram(`gitGraph\n${body}`))
const lines = (grid: GitGraphGrid) => renderGitGraphGridText(grid).split("\n")
// The styles of a row's graph cells, a dash for an empty one.
const styles = (grid: GitGraphGrid, y: number, width: number) =>
  Array.from({ length: width }, (_, x) => grid.getCell(x, y)!.style ?? "-")

test("a graph with no commits draws nothing, branches or not", () => {
  for (const body of ["", "branch dev\nbranch other"]) {
    const grid = draw(body)
    expect([grid.width, grid.height]).toEqual([0, 0])
  }
})

test("one branch is one lane: a row per commit, its label two cells right, the head's branch named after it", () => {
  const grid = draw("commit\ncommit\ncommit")
  expect([grid.width, grid.height]).toEqual([1 + 2 + 16, 3])
  expect(lines(grid)).toEqual(["●  commit-1", "●  commit-2", "●  commit-3  [main]"])
  expect(styles(grid, 0, 4)).toEqual(["commit", "-", "-", "label"])
  // The direction is read but not drawn: a git graph is always laid top to bottom.
  const bt = drawGitGraphDiagramGrid(parseMermaidGitGraphDiagram("gitGraph BT\ncommit\ncommit\ncommit"), {
    direction: "BT",
  })
  expect(lines(bt)).toEqual(lines(grid))
})

test("a fork takes a row of its own; a lane's rail runs to its last commit or the merge that takes it", () => {
  const grid = draw("commit\nbranch dev\ncommit\ncheckout main\ncommit\nmerge dev")
  expect(lines(grid)).toEqual([
    "●    commit-1",
    "├─╮",
    "│ ●  commit-2  [dev]",
    "● │  commit-3",
    "◎─╯  commit-4  [main]",
  ])
  expect([grid.width, grid.height]).toEqual([3 + 2 + 16, 5])
})

test("a fork is drawn in the new lane's style and a merge in the merged lane's, a shared cell keeping its first style", () => {
  const grid = draw("commit\nbranch dev\ncommit\ncheckout main\ncommit\nmerge dev")
  expect(styles(grid, 1, 3)).toEqual(["branch0", "branch1", "branch1"])
  expect(styles(grid, 2, 3)).toEqual(["branch0", "-", "commit"])
  expect(styles(grid, 3, 3)).toEqual(["commit", "-", "branch1"])
  expect(styles(grid, 4, 3)).toEqual(["merge", "branch1", "branch1"])
})

test("lanes follow the branch order, and a fork or merge toward a lane on the left turns the other way", () => {
  // Lanes: main, feat (unordered, so first), dev (ordered). feat forks from dev, leftward, and merges back.
  const grid = draw("commit\nbranch dev order: 5\ncommit\nbranch feat\ncommit\ncheckout dev\nmerge feat")
  expect(lines(grid)).toEqual([
    "●      commit-1  [main]",
    "├───╮",
    "    ●  commit-2",
    "  ╭─┤",
    "  ● │  commit-3  [feat]",
    "  ╰─◎  commit-4  [dev]",
  ])
})

test("a fork that passes a live lane crosses its rail", () => {
  const grid = draw("commit\nbranch a\ncommit\ncheckout main\nbranch b\ncommit\ncheckout a\ncommit")
  expect(lines(grid).slice(3, 5)).toEqual(["├─┼─╮", "  │ ●  commit-3  [b]"])
  expect(styles(grid, 3, 5)).toEqual(["branch0", "branch2", "branch1", "branch2", "branch2"])
})

test("a fork crosses every lane live at its row, whichever lanes ended before", () => {
  // main ends at row 2; a forks b, then c, which passes b.
  const grid = draw(
    "commit\nbranch a\ncommit\ncommit\nbranch b\ncommit\ncheckout a\nbranch c\ncommit\ncheckout b\ncommit",
  )
  expect(lines(grid)).toEqual([
    "●        commit-1  [main]",
    "├─╮",
    "  ●      commit-2",
    "  ●      commit-3  [a]",
    "  ├─╮",
    "  │ ●    commit-4",
    "  ├─┼─╮",
    "    │ ●  commit-5  [c]",
    "    ●    commit-6  [b]",
  ])
})

// bench/subsume reads this case as redundant: it plants no fault inside the style's template. Taking the lane
// modulo nine fails this case alone (planted by hand, 2026-10-30).
test("a lane's style is its index modulo eight", () => {
  const branches = Array.from({ length: 8 }, (_, index) => `branch b${index + 1}`).join("\n")
  const grid = draw(`commit\n${branches}\ncommit`)
  expect(lines(grid)[1]).toBe(`├${"─".repeat(15)}╮`)
  expect(styles(grid, 1, 17)).toEqual(["branch0", ...Array(16).fill("branch0")])
  const third = draw("commit\nbranch b1\nbranch b2\nbranch b3\ncommit")
  expect(styles(third, 1, 7)).toEqual(["branch0", ...Array(6).fill("branch3")])
})

test("a commit is ● and a merge ◎, a reversed one ⊗ and a highlighted one ◆, merge or not", () => {
  const grid = draw(
    "commit\ncommit type: REVERSE\ncommit type: HIGHLIGHT\nbranch dev\ncommit\ncheckout main\ncommit\nmerge dev type: HIGHLIGHT\nmerge dev type: REVERSE",
  )
  const marks = lines(grid).map((line) => line[0])
  expect(marks).toEqual(["●", "⊗", "◆", "├", "│", "●", "◆", "⊗"])
  expect([0, 1, 2, 5, 6, 7].map((y) => grid.getCell(0, y)!.style)).toEqual([
    "commit",
    "reverse",
    "highlight",
    "commit",
    "highlight",
    "reverse",
  ])
})

test("a label is the message or the id, then the branches headed there in lane order, then the tags", () => {
  // main has no head here; dev, after it, still names its own.
  expect(lines(draw("branch dev\ncommit"))).toEqual(["  ●  commit-1  [dev]"])
  const grid = draw('commit msg: "Fix" tag: v1 tag: v2\nbranch dev\nbranch qa order: 1\ncheckout main\ncommit id: two')
  expect(lines(grid)).toEqual(["●      Fix  [dev] [qa] [v1] [v2]", "●      two  [main]"])
  // Three lanes, though only main has commits: the graph is five cells wide.
  expect(grid.width).toBe(5 + 2 + 25)
})
