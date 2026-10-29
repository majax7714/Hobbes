import { expect, test } from "bun:test"
import { DiagramCanvas, DiagramCanvasSizeError } from "../../src/core/canvas"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

test("a canvas refuses negative, fractional or unsafe dimensions, by name and size", () => {
  for (const [width, height] of [[-1, 2], [1.5, 1], [Number.MAX_SAFE_INTEGER + 1, 1], [2, Number.NaN]]) {
    const error = thrown(() => new DiagramCanvas(width!, height!)) as DiagramCanvasSizeError
    expect(error).toBeInstanceOf(DiagramCanvasSizeError)
    expect(error.name).toBe("DiagramCanvasSizeError")
    expect(error.message).toBe(`Diagram canvas dimensions must be non-negative safe integers, received ${width}x${height}`)
    expect([error.width, error.height]).toEqual([width!, height!])
  }
})

test("a canvas may hold exactly 250 000 cells and not one more", () => {
  expect(new DiagramCanvas(500, 500).rows.length).toBe(500)
  const error = thrown(() => new DiagramCanvas(501, 500)) as DiagramCanvasSizeError
  expect(error).toBeInstanceOf(DiagramCanvasSizeError)
  expect(error.message).toBe(`Diagram canvas 501x500 exceeds the ${(250_000).toLocaleString()} cell limit`)
})

test("an empty canvas has no rows and prints nothing", () => {
  const canvas = new DiagramCanvas(0, 0)
  expect(canvas.rows).toEqual([])
  expect(canvas.toString()).toBe("")
  expect(canvas.getTextSize()).toEqual({ width: 0, height: 0 })
})

test("a fresh cell is a space, a write outside the canvas is dropped, and a read outside is undefined", () => {
  const canvas = new DiagramCanvas<"s", { id: number }>(3, 2)
  expect(canvas.getCell(2, 1)).toEqual({ char: " " })
  for (const [x, y] of [[-1, 0], [3, 0], [0, -1], [0, 2]]) canvas.setCell(x!, y!, "x")
  expect(canvas.toString()).toBe("\n")
  expect(canvas.getCell(3, 0)).toBeUndefined()
  expect(canvas.getCell(0, 2)).toBeUndefined()
  canvas.setCell(1, 0, "a", "s", { id: 7 })
  expect(canvas.getCell(1, 0)).toEqual({ char: "a", style: "s", id: 7 })
})

test("erasing a row's last character gives its width back to the character left before it", () => {
  const canvas = new DiagramCanvas(6, 1)
  canvas.setCell(1, 0, "a")
  canvas.setCell(4, 0, "b")
  canvas.setCell(4, 0, " ")
  expect(canvas.toString()).toBe(" a")
  expect(canvas.getTextSize()).toEqual({ width: 2, height: 1 })
  canvas.setCell(2, 0, "c")
  canvas.setCell(4, 0, "b")
  canvas.setCell(4, 0, " ")
  expect(canvas.toString()).toBe(" ac")
})

test("a row prints up to its last non-space cell, and erasing that cell gives the width back to the last one left", () => {
  const canvas = new DiagramCanvas(6, 3)
  canvas.setCell(1, 0, "a")
  canvas.setCell(3, 2, "b")
  expect(canvas.toString()).toBe(" a\n\n   b")
  canvas.setCell(2, 1, "x")
  canvas.setCell(4, 1, "y")
  canvas.setCell(2, 1, " ")
  expect(canvas.toString().split("\n")[1]).toBe("    y")
  canvas.setCell(4, 1, " ")
  expect(canvas.toString().split("\n")[1]).toBe("")
  canvas.setCell(1, 0, "a")
  canvas.setCell(0, 0, " ")
  expect(canvas.toString().split("\n")[0]).toBe(" a")
})

test("setCell goes through the merge rule and replaceCell does not", () => {
  const canvas = new DiagramCanvas(2, 1, { mergeCell: (existing, incoming) => (existing.char === " " ? incoming : existing) })
  canvas.setCell(0, 0, "a")
  canvas.setCell(0, 0, "b")
  expect(canvas.getCell(0, 0)!.char).toBe("a")
  canvas.replaceCell(0, 0, "c")
  expect(canvas.getCell(0, 0)!.char).toBe("c")
})

test("ASCII text is written a cell per character, clipped at both edges", () => {
  const canvas = new DiagramCanvas<string, { at: string }>(5, 2)
  canvas.setText(3, 0, "abcd")
  canvas.setText(-1, 1, "xyz", undefined, (x, y) => ({ at: `${x},${y}` }))
  expect(canvas.toString()).toBe("   ab\nyz")
  expect(canvas.getCell(1, 1)).toEqual({ char: "z", style: undefined, at: "1,1" })
})

test("a wide grapheme takes its width in cells, the rest empty, and is skipped whole where it does not fit", () => {
  const canvas = new DiagramCanvas(4, 3)
  canvas.setText(0, 0, "中a", "s")
  expect(canvas.rows[0]!.map((cell) => cell.char)).toEqual(["中", "", "a", " "])
  expect(canvas.getCell(1, 0)!.style).toBe("s")
  canvas.setText(3, 1, "中")
  canvas.setText(-1, 2, "éa")
  expect(canvas.toString()).toBe("中a\n\na")
  canvas.setText(2, 1, "中")
  expect(canvas.toString()).toBe("中a\n  中\na")
  const edge = new DiagramCanvas(4, 2)
  edge.setText(1, 0, "ab中")
  edge.setText(0, 1, "é中")
  expect(edge.rows.map((row) => row.map((cell) => cell.char))).toEqual([
    [" ", "a", "b", " "],
    ["é", "中", "", " "],
  ])
})

test("off the ASCII path a cell holds a whole grapheme, a zero-width one still takes a cell, and metadata follows each cell's x", () => {
  const canvas = new DiagramCanvas<"s", { at: number }>(6, 2)
  canvas.setText(0, 0, "e\u0301x\u200By")
  expect(canvas.rows[0]!.map((cell) => cell.char)).toEqual(["e\u0301", "x", "\u200B", "y", " ", " "])
  canvas.setText(1, 1, "a中", "s", (x) => ({ at: x }))
  expect(canvas.rows[1]!.slice(1, 4)).toEqual([
    { char: "a", style: "s", at: 1 },
    { char: "中", style: "s", at: 2 },
    { char: "", style: "s", at: 3 },
  ])
})

test("a custom measure takes the grapheme path even for ASCII, and sizes the text by it", () => {
  const canvas = new DiagramCanvas(5, 2, { measure: () => 2 })
  canvas.setText(0, 0, "ab")
  expect(canvas.rows[0]!.map((cell) => cell.char)).toEqual(["a", "", "b", "", " "])
  expect(canvas.getTextSize()).toEqual({ width: 2, height: 2 })
})

test("the text size is the widest printed row by the row count, with blank rows trimmed at either end on request", () => {
  const canvas = new DiagramCanvas(8, 5)
  canvas.setText(2, 1, "中中")
  canvas.setText(0, 3, "abc")
  expect(canvas.getTextSize()).toEqual({ width: 6, height: 5 })
  expect(canvas.getTextSize({ trimTop: true, trimBottom: true })).toEqual({ width: 6, height: 3 })
  expect(canvas.getTextHeight({ trimTop: true })).toBe(4)
  expect(canvas.getTextHeight({ trimBottom: true })).toBe(4)
  expect(canvas.toString({ trimTop: true, trimBottom: true })).toBe("  中中\n\nabc")
  expect(new DiagramCanvas(3, 2).getTextHeight({ trimTop: true, trimBottom: true })).toBe(0)
  const one = new DiagramCanvas(3, 1)
  one.setCell(0, 0, "x")
  expect(one.getTextSize()).toEqual({ width: 1, height: 1 })
})

test("runs group a row's cells by style, reach past the last character over styled spaces, and end lines between rows", () => {
  const canvas = new DiagramCanvas<"x" | "y">(8, 5)
  canvas.setText(0, 1, "ab", "x")
  canvas.setText(3, 1, "c", "y")
  canvas.setCell(4, 1, " ", "y")
  canvas.setCell(0, 3, "z")
  const events: string[] = []
  canvas.forEachRun(
    (run) => events.push(`${run.text}|${run.style ?? "-"}|${run.cell.char}`),
    () => events.push("eol"),
  )
  expect(events).toEqual(["eol", "ab|x|a", " |-| ", "c |y|c", "eol", "eol", "z|-|z", "eol"])
})

test("a run key groups by what it returns instead of the style, and trimming drops blank rows' line ends", () => {
  const canvas = new DiagramCanvas<"s", { id: number }>(4, 3)
  canvas.setCell(0, 1, "a", "s", { id: 1 })
  canvas.setCell(1, 1, "b", "s", { id: 1 })
  canvas.setCell(2, 1, "c", "s", { id: 2 })
  const events: string[] = []
  canvas.forEachRun(
    (run) => events.push(run.text),
    () => events.push("eol"),
    { key: (cell) => [cell.id], trimTop: true, trimBottom: true },
  )
  expect(events).toEqual(["ab", "c"])
})
