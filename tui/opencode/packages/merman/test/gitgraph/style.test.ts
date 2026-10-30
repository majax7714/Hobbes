import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderGitGraphGridStyledText, renderGitGraphGridText, type GitGraphGrid } from "../../src/gitgraph/render-grid"
import { resolveGitGraphStyleColors } from "../../src/gitgraph/style"

const ints = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const asInts = (colors: Partial<Record<string, RGBA>>) =>
  Object.fromEntries(Object.entries(colors).map(([style, color]) => [style, color?.toInts()]))
const lanes = (color: number[]) => Object.fromEntries(Array.from({ length: 8 }, (_, lane) => [`branch${lane}`, color]))

test("with no colours given, every lane is the muted rail and each mark takes its default", () => {
  expect(asInts(resolveGitGraphStyleColors())).toEqual({
    ...lanes([111, 138, 126, 255]),
    commit: [134, 225, 200, 255],
    merge: [154, 184, 169, 255],
    highlight: [230, 177, 126, 255],
    reverse: [225, 134, 166, 255],
    label: [228, 239, 232, 255],
  })
})

test("muted colours every lane, primary a commit, secondary a merge, warning both a highlight and a reverse, text a label", () => {
  const colors = resolveGitGraphStyleColors({
    muted: ints(1, 1, 1),
    primary: ints(2, 2, 2),
    secondary: ints(3, 3, 3),
    warning: ints(4, 4, 4),
    text: ints(5, 5, 5),
  })
  expect(asInts(colors)).toEqual({
    ...lanes([1, 1, 1, 255]),
    commit: [2, 2, 2, 255],
    merge: [3, 3, 3, 255],
    highlight: [4, 4, 4, 255],
    reverse: [4, 4, 4, 255],
    label: [5, 5, 5, 255],
  })
})

function grid(): GitGraphGrid {
  const canvas: GitGraphGrid = new DiagramCanvas(3, 3)
  canvas.setText(0, 0, "●", "commit")
  canvas.setCell(1, 0, "x")
  canvas.setCell(0, 1, "│", "branch2")
  return canvas
}

test("the grid's text drops trailing blank rows", () => {
  expect(renderGitGraphGridText(grid())).toBe("●x\n│")
})

test("styled text colours each run by its style, leaves an unstyled run uncoloured, and drops trailing blank rows", () => {
  const text = renderGitGraphGridStyledText(
    grid(),
    resolveGitGraphStyleColors({ primary: ints(1, 2, 3), muted: ints(4, 5, 6) }),
  )
  expect(text).toBeInstanceOf(StyledText)
  expect(text.chunks.map((chunk) => [chunk.text, chunk.fg?.toInts()])).toEqual([
    ["●", [1, 2, 3, 255]],
    ["x", undefined],
    ["\n", undefined],
    ["│", [4, 5, 6, 255]],
  ])
})
