import { expect, test } from "bun:test"
import {
  BoxRenderable,
  CodeRenderable,
  parseColor,
  type Renderable,
  ScrollBoxRenderable,
  SyntaxStyle,
  TextRenderable,
  type MarkdownCodeBlockRenderer,
} from "@opentui/core"
import { createTestRenderer } from "@opentui/core/testing"
import { createLatexCodeBlockRenderer } from "../src/markdown"

type CodeToken = Parameters<MarkdownCodeBlockRenderer>[0]

const setup = await createTestRenderer({ width: 24, height: 10, useThread: false })
const renderer = setup.renderer
// Every code renderable listens for selection; this file makes more than the default ten.
renderer.setMaxListeners(64)
const syntaxStyle = SyntaxStyle.create()
const palette = { text: "#ffffff", subdued: "#808080" }
const TEXT = parseColor(palette.text)
const SUBDUED = parseColor(palette.subdued)

function latex() {
  return createLatexCodeBlockRenderer(renderer, () => palette)
}

function token(text: string, raw = "```latex\n" + text + "\n```"): CodeToken {
  return { type: "code", raw, text, lang: "latex" } as CodeToken
}

/** The open fence of a block still streaming in. */
const open = (text: string) => token(text, "```latex\n" + text)

function code(id: string, streaming: boolean) {
  return new CodeRenderable(renderer, { id, content: "", syntaxStyle, streaming })
}

function call(render: ReturnType<typeof latex>, tok: CodeToken, fallback: Renderable | null) {
  return render(tok, { syntaxStyle, conceal: false, concealCode: false, defaultRender: () => fallback })
}

function formula(viewport: Renderable | null | undefined) {
  expect(viewport).toBeInstanceOf(ScrollBoxRenderable)
  return (viewport as ScrollBoxRenderable).content.getChildren()[0] as TextRenderable
}

const drawn = (viewport: Renderable | null | undefined) =>
  formula(viewport)
    .chunks.map((chunk) => chunk.text)
    .join("")

test("a formula becomes a scroll box one row down, as tall as the formula, holding its every cell", async () => {
  const viewport = call(latex(), token("\\frac{a}{b}"), code("frac", false)) as ScrollBoxRenderable
  expect(drawn(viewport)).toBe(" a \n───\n b ")
  expect([viewport.height, viewport.marginTop]).toEqual([3, 1])
  expect(viewport.horizontalScrollBar.visible).toBe(false)
  expect(viewport.verticalScrollBar.visible).toBe(false)
  expect(formula(viewport).selectable).toBe(false)
  // In a row the box still spans the full width, not just the formula's.
  const holder = new BoxRenderable(renderer, { width: 24, flexDirection: "row" })
  holder.add(viewport)
  renderer.root.add(holder)
  await setup.renderOnce()
  expect(viewport.width).toBe(24)
  const rows = setup.captureCharFrame().split("\n").map((line) => line.trimEnd())
  renderer.root.remove(holder)
  expect(rows.slice(0, 5)).toEqual(["", " a", "───", " b", ""])
})

test("delimiters and rules are drawn subdued, relations bold, and the layout's bold and italic kept", () => {
  const chunks = formula(call(latex(), token("\\sqrt{(x)}=\\mathbf{b}\\mathit{c}"), null)).chunks
  const at = (text: string) => chunks.find((chunk) => chunk.text === text)!
  for (const char of ["(", ")", "╭", "─", "╰", "╯"]) expect(at(char).fg).toEqual(SUBDUED)
  for (const char of ["x", "=", "b", "c"]) expect(at(char).fg).toEqual(TEXT)
  const bold = 1
  const italic = 4
  expect([at("x").attributes, at("=").attributes, at("b").attributes, at("c").attributes]).toEqual([0, bold, bold, italic])
})

test("a tall delimiter piece is subdued, but a character carrying a mark is not taken for a delimiter or relation", () => {
  const tall = formula(call(latex(), token("\\left(\\frac{a}{b}\\right]"), null)).chunks
  for (const char of ["⎛", "⎜", "⎝", "⎤", "⎥", "⎦"]) expect(tall.find((chunk) => chunk.text === char)?.fg).toEqual(SUBDUED)
  const marked = formula(call(latex(), token("\\text{(\u0301 \u0600( =\u0301 \u0600=}"), null)).chunks
  for (const grapheme of ["(\u0301", "\u0600(", "=\u0301", "\u0600="]) {
    const chunk = marked.find((item) => item.text === grapheme)!
    expect([grapheme, chunk.fg, chunk.attributes]).toEqual([grapheme, TEXT, 0])
  }
})

test("a wide glyph's covered cell is not drawn again", () => {
  expect(drawn(call(latex(), token("\\text{中}x"), null))).toBe("中x")
})

test("the formula is laid out in display mode, and kept as code when it does not parse or uses an unknown command", () => {
  expect(drawn(call(latex(), token("\\sum_{i}^{n}"), null))).toBe("n\n∑\ni")
  const fallback = code("bad", false)
  expect(call(latex(), token("\\frac{a}"), fallback)).toBe(fallback)
  expect(call(latex(), token("\\foo"), fallback)).toBe(fallback)
  expect(call(latex(), token("\\frac{a}"), null)).toBeUndefined()
})

test("a range error falls back like a parse error, and any other error is thrown", () => {
  const failing = (error: Error) =>
    token({
      get length(): number {
        throw error
      },
    } as unknown as string)
  const fallback = code("thrown", false)
  expect(call(latex(), failing(new RangeError("too big")), fallback)).toBe(fallback)
  expect(() => call(latex(), failing(new TypeError("bug")), fallback)).toThrow("bug")
})

test("a closed fence, a block not streaming, or one not fenced at all falls back to code", () => {
  const render = latex()
  call(render, open("\\frac{a}{b}"), code("s3", true))
  for (const [tok, fallback] of [
    [token("\\frac{a}{b}+\\frac{"), code("s3", true)],
    [token("\\frac{a}{b}+\\frac{", "```latex\n\\frac{a}{b}+\\frac{\n````"), code("s3", true)],
    [open("\\frac{a}{b}+\\frac{"), code("s3", false)],
    [token("\\frac{a}{b}+\\frac{", "    ```latex\n\\frac{a}{b}+\\frac{"), code("s3", true)],
    [open("\\frac{a}{b}+\\frac{"), new TextRenderable(renderer, { id: "s3", content: "" })],
  ] as const) {
    expect(call(render, tok, fallback)).toBe(fallback)
  }
})

test("while a block streams, a broken continuation keeps the last formula that drew, until the block is destroyed", async () => {
  const render = latex()
  call(render, open("\\frac{a}{b}"), code("s1", true))
  expect(drawn(call(render, open("\\frac{a}{b}+\\frac{"), code("s1", true)))).toBe(" a \n───\n b ")
  expect(drawn(call(render, open("\\frac{a}{b}+\\frac{c"), code("s1", true)))).toBe(" a \n───\n b ")
  // A broken rewrite, rather than a continuation, is shown as code.
  const rewrite = code("s1", true)
  expect(call(render, open("x+\\frac{"), rewrite)).toBe(rewrite)
  // A closing fence shorter than the opening one does not end the block.
  call(render, token("\\frac{a}{b}", "````latex\n\\frac{a}{b}"), code("s2", true))
  const raw = "````latex\n\\frac{a}{b}+\\frac{\n```"
  expect(drawn(call(render, token("\\frac{a}{b}+\\frac{", raw), code("s2", true)))).toBe(" a \n───\n b ")

  // Destroying the block forgets its formula, unless a newer one has replaced it.
  const first = call(render, open("a"), code("d1", true))!
  first.destroy()
  await Promise.resolve()
  const fallback = code("d1", true)
  expect(call(render, open("a\\frac{"), fallback)).toBe(fallback)
  const older = call(render, open("b"), code("d2", true))!
  call(render, open("bc"), code("d2", true))
  older.destroy()
  await Promise.resolve()
  expect(drawn(call(render, open("bc\\frac{"), code("d2", true)))).toBe("bc")
})

test("a wide formula scrolls sideways in a box too short for it, and keeps sideways or shift-held scrolls to itself", async () => {
  const seen: string[] = []
  const outer = new BoxRenderable(renderer, {
    width: 24,
    height: 3,
    flexDirection: "column",
    onMouseScroll(event) {
      seen.push(event.scroll!.direction)
    },
  })
  const viewport = call(latex(), token("\\frac{\\text{0123456789abcdefghijklmnopqrstuvwxyz}}{b}"), null) as ScrollBoxRenderable
  outer.add(viewport)
  renderer.root.add(outer)
  await setup.renderOnce()
  viewport.scrollLeft = 5
  await setup.renderOnce()
  expect([viewport.height, viewport.scrollLeft]).toEqual([3, 5])
  await setup.mockMouse.scroll(2, 2, "down")
  await setup.mockMouse.scroll(2, 2, "left")
  await setup.mockMouse.scroll(2, 2, "right")
  await setup.mockMouse.scroll(2, 2, "up", { modifiers: { shift: true } })
  expect(seen).toEqual(["down"])
  renderer.root.remove(outer)
})
