import { expect, test } from "bun:test"
import { renderLatex, renderLatexToString } from "../src/render"

test("rendering parses with the options, lays out with them, and the string form is the layout's text", () => {
  const layout = renderLatex("\\R^2", { macros: { R: "\\mathbb{R}" }, compactScripts: false })
  expect(layout.toString()).toBe(" 2\nℝ")
  expect(renderLatexToString("\\R^2", { macros: { R: "\\mathbb{R}" } })).toBe("ℝ²")
})
