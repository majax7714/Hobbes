import { RGBA, StyledText } from "@opentui/core"
import { expect, test } from "bun:test"
import { DiagramCanvas } from "../../src/core/canvas"
import { renderDiagramGridStyledText, renderDiagramGridStyledTextByStyle } from "../../src/core/render-grid"

const red = RGBA.fromInts(255, 0, 0, 255)
const blue = RGBA.fromInts(0, 0, 255, 255)

function grid() {
  const canvas = new DiagramCanvas<"a" | "b">(4, 2)
  canvas.setText(0, 0, "xy", "a")
  canvas.setText(2, 0, "z")
  canvas.setText(0, 1, "w", "b")
  return canvas
}

test("each run is one chunk coloured by the callbacks, with a newline chunk between rows", () => {
  const text = renderDiagramGridStyledText(
    grid(),
    (run) => (run.style === "a" ? red : blue),
    (run) => (run.style === "b" ? red : undefined),
    { attributes: (run) => (run.style ? 1 : 0) },
  )
  expect(text).toBeInstanceOf(StyledText)
  expect(text.chunks).toEqual([
    { __isChunk: true, text: "xy", fg: red, bg: undefined, attributes: 1 },
    { __isChunk: true, text: "z", fg: blue, bg: undefined, attributes: 0 },
    { __isChunk: true, text: "\n" },
    { __isChunk: true, text: "w", fg: blue, bg: red, attributes: 1 },
  ])
})

test("by style, an unstyled run gets no colour, and backgrounds apply only when one is set", () => {
  expect(renderDiagramGridStyledTextByStyle(grid(), { a: red, b: blue }).chunks.map((chunk) => chunk.bg)).toEqual([undefined, undefined, undefined, undefined])
  const plain = renderDiagramGridStyledTextByStyle(grid(), { a: red, b: blue }, { a: undefined })
  expect(plain.chunks.map((chunk) => [chunk.text, chunk.fg, chunk.bg])).toEqual([
    ["xy", red, undefined],
    ["z", undefined, undefined],
    ["\n", undefined, undefined],
    ["w", blue, undefined],
  ])
  const shaded = renderDiagramGridStyledTextByStyle(grid(), { a: red, b: blue }, { b: red }, { trimTop: true })
  expect(shaded.chunks.map((chunk) => chunk.bg)).toEqual([undefined, undefined, undefined, red])
})
