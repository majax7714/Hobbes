import { expect, test } from "bun:test"
import { DIAGRAM_LABEL_PADDING_X, measureDiagramLabelWidth, measureDiagramTextBox, padDiagramLabelLine } from "../../src/core/text"

test("a label line is padded by one column each side, and its width is the widest line plus both pads", () => {
  expect(DIAGRAM_LABEL_PADDING_X).toBe(1)
  expect(padDiagramLabelLine("x")).toBe(" x ")
  expect(measureDiagramLabelWidth("ab<br>abcd")).toBe(6)
  expect(measureDiagramLabelWidth("ab<br>abcd", (line) => line.length * 3)).toBe(14)
})

test("a text box is the widest line in terminal columns by the line count, padded on both sides, never narrower than the minimum", () => {
  expect(measureDiagramTextBox("ab<br>abc")).toEqual({ width: 3, height: 2, lines: ["ab", "abc"] })
  expect(measureDiagramTextBox("中<br>é")).toEqual({ width: 2, height: 2, lines: ["中", "é"] })
  expect(measureDiagramTextBox("ab<br>abc", { paddingX: 2, paddingY: 1 })).toEqual({ width: 7, height: 4, lines: ["ab", "abc"] })
  expect(measureDiagramTextBox("ab", { minInnerWidth: 5 }).width).toBe(5)
  expect(measureDiagramTextBox("")).toEqual({ width: 1, height: 1, lines: [""] })
})
