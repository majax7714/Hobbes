import { expect, test } from "bun:test"
import { layoutMath } from "../src/layout"
import type { MathNode, RenderLatexOptions } from "../src/types"

// Trees are built by hand so these cases judge the layout alone, not the parser.
const s = (value: string, role?: string) => ({ type: "symbol", value, ...(role ? { role } : {}) }) as MathNode
const bin = (value: string) => s(value, "binary")
const rel = (value: string) => s(value, "relation")
const t = (value: string) => ({ type: "text", value }) as MathNode
const r = (...body: MathNode[]) => ({ type: "row", body }) as MathNode
const op = (value: string, limits = false) => ({ type: "operator", value, limits }) as MathNode
const space = (width: number) => ({ type: "space", width }) as MathNode
const frac = (numerator: MathNode, denominator: MathNode, extra = {}) =>
  ({ type: "fraction", numerator, denominator, bar: true, ...extra }) as MathNode
const scripts = (base: MathNode, superscript?: MathNode, subscript?: MathNode) =>
  ({ type: "scripts", base, ...(superscript ? { superscript } : {}), ...(subscript ? { subscript } : {}) }) as MathNode
const matrix = (environment: string, rows: MathNode[][], columns?: string) =>
  ({ type: "matrix", environment, rows, ...(columns ? { columns } : {}) }) as MathNode
const draw = (node: MathNode, options?: RenderLatexOptions) => layoutMath(node, options).toString()
const lines = (...rows: string[]) => rows.join("\n")

test("text is one cell per character, an empty row one empty line, and a lone node in a row is drawn as itself", () => {
  const layout = layoutMath(t("ab"))
  expect([layout.width, layout.height, layout.baseline]).toEqual([2, 1, 0])
  expect(layout.cells).toEqual([[{ char: "a" }, { char: "b" }]])
  expect(layoutMath(t("a\u0000")).cells).toEqual([[{ char: "a" }]])
  const empty = layoutMath(r())
  expect([empty.width, empty.height, empty.baseline, empty.toString()]).toEqual([0, 1, 0, ""])
  expect(empty.cells).toHaveLength(1)
  expect(empty.cells[0]).toHaveLength(0)
  expect(draw(r(op("sin")))).toBe("sin")
  const spaced = layoutMath(r(s("a"), space(2), s("b")))
  expect([spaced.width, spaced.height, spaced.toString()]).toEqual([4, 1, "a  b"])
})

test("binary and relation symbols and operators get a space each side; punctuation, openings and closings do not", () => {
  expect(draw(r(s("a"), bin("+"), s("b"), rel("="), s("c")))).toBe("a + b = c")
  expect(draw(r(op("sin"), s("x"), op("cos")))).toBe("sin x cos")
  expect(draw(r(s("a"), s(",", "punctuation"), s("b")))).toBe("a,b")
  expect(draw(r(s(",", "punctuation"), rel("="), s(";", "punctuation")))).toBe(",=;")
  expect(draw(r(s("(", "opening"), rel("="), s(")", "closing")))).toBe("(=)")
  expect(draw(r(rel("="), op("lim")))).toBe("= lim")
})

test("a binary sign is drawn unary at the start, after a relation, operator, punctuation or opening, and before the end, a sign, a relation, punctuation or a closing", () => {
  expect(draw(r(bin("-"), s("a")))).toBe("-a")
  expect(draw(r(s("x"), rel("="), bin("-"), s("1")))).toBe("x = -1")
  expect(draw(r(op("sin"), bin("-"), s("x")))).toBe("sin -x")
  expect(draw(r(s(",", "punctuation"), bin("-"), s("x")))).toBe(",-x")
  expect(draw(r(s("(", "opening"), bin("-"), s("x")))).toBe("(-x")
  expect(draw(r(s("x"), bin("-")))).toBe("x-")
  expect(draw(r(s("a"), bin("+"), bin("-"), s("b")))).toBe("a+ - b")
  expect(draw(r(s("x"), bin("-"), rel("=")))).toBe("x- =")
  expect(draw(r(s("x"), bin("-"), s(",", "punctuation")))).toBe("x-,")
  expect(draw(r(s("x"), bin("-"), s(")", "closing")))).toBe("x-)")
})

test("a space neither ends the run of roles nor counts as the next sign", () => {
  expect(draw(r(rel("="), space(1), bin("-"), s("x")))).toBe("=   -x")
  expect(draw(r(s("a"), bin("-"), space(1), rel("=")))).toBe("a-  =")
  expect(draw(r(s("a"), bin("-"), t("b")))).toBe("a - b")
  expect(draw(r(s("a"), bin("-"), space(1), s("b")))).toBe("a -   b")
})

test("a fraction, root or matrix stands one cell apart from its neighbors, and scripts take their base's role", () => {
  const half = frac(s("1"), s("2"))
  expect(draw(r(s("x"), half, s("y")))).toBe(lines("   1", "x ─── y", "   2"))
  expect(draw(r(s("x"), { type: "root", body: s("y") }))).toBe(lines("   ╭─", "x ╰╯y"))
  expect(draw(r(s("x"), matrix("matrix", [[s("y")]])))).toBe("x y")
  expect(draw(r(s("a"), scripts(rel("="), s("2"))))).toBe("a =²")
})

test("a fraction centers its parts over a rule two cells wider, with the axis on the rule", () => {
  const layout = layoutMath(frac(s("a"), t("bc")))
  expect(layout.toString()).toBe(lines(" a", "────", " bc"))
  expect([layout.width, layout.height, layout.baseline]).toEqual([4, 3, 1])
  expect(draw(frac(t("bc"), s("a")))).toBe(lines(" bc", "────", " a"))
  const tall = layoutMath(frac(frac(s("a"), s("b")), s("c")))
  expect([tall.height, tall.baseline]).toEqual([5, 3])
  expect(tall.toString()).toBe(lines("  a", " ───", "  b", "─────", "  c"))
})

test("a fraction's numerator may sit left or right, and a binomial keeps an empty axis row", () => {
  expect(draw(frac(s("a"), t("bcd"), { numeratorAlign: "left" }))).toBe(lines(" a", "─────", " bcd"))
  expect(draw(frac(s("a"), t("bcd"), { numeratorAlign: "right" }))).toBe(lines("   a", "─────", " bcd"))
  expect(draw({ type: "fraction", numerator: s("n"), denominator: s("k"), bar: false })).toBe(lines(" n", "", " k"))
})

test("a root draws a hook and an overbar, and a tall radicand extends the hook upward", () => {
  const plain = layoutMath({ type: "root", body: t("xy") })
  expect(plain.toString()).toBe(lines(" ╭──", "╰╯xy"))
  expect([plain.width, plain.height, plain.baseline]).toEqual([4, 2, 1])
  const tall = layoutMath({ type: "root", body: frac(s("1"), s("2")) })
  expect(tall.toString()).toBe(lines(" ╭───", " │ 1", " │───", "╰╯ 2"))
  expect([tall.height, tall.baseline]).toEqual([4, 2])
})

test("a root's index ends beside the overbar, and a tall index lifts the root", () => {
  expect(draw({ type: "root", body: s("x"), index: s("3") })).toBe(lines("3╭─", "╰╯x"))
  expect(draw({ type: "root", body: s("x"), index: r() })).toBe(lines(" ╭─", "╰╯x"))
  expect(draw({ type: "root", body: s("x"), index: t("abc") })).toBe(lines("abc╭─", "  ╰╯x"))
  const lifted = layoutMath({ type: "root", body: s("x"), index: frac(s("1"), s("2")) })
  expect(lifted.toString()).toBe(lines(" 1", "───", " 2 ╭─", "  ╰╯x"))
  expect([lifted.width, lifted.height, lifted.baseline]).toEqual([5, 4, 3])
})

test("digits, signs, parentheses and a few letters become compact script characters", () => {
  expect(draw(scripts(s("x"), t("0123456789+-=()ni")))).toBe("x⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
  expect(draw(scripts(s("x"), undefined, t("0123456789+-=()aehijklmnoprstuvx")))).toBe(
    "x₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
  )
  expect(draw(scripts(s("x"), s("2"), s("i")))).toBe("x²ᵢ")
  expect(draw(scripts(s("x"), r(s("1"), op("n"))))).toBe("x¹ⁿ")
})

test("scripts with any unmappable character, or compact scripts turned off, stack beside the base", () => {
  const stacked = layoutMath(scripts(s("x"), t("ab"), s("i")))
  expect(stacked.toString()).toBe(lines(" ab", "x", " i"))
  expect([stacked.width, stacked.height, stacked.baseline]).toEqual([3, 3, 1])
  expect(draw(scripts(s("x"), s("2")), { compactScripts: false })).toBe(lines(" 2", "x"))
  expect(draw(scripts(s("x"), undefined, s("2")), { compactScripts: false })).toBe(lines("x", " 2"))
  const blank = layoutMath(scripts(s("x"), space(0)))
  expect([blank.width, blank.height, blank.toString()]).toEqual([1, 2, "\nx"])
  expect(layoutMath(scripts(s("x"), undefined, space(0))).width).toBe(1)
  expect(draw(scripts(s("x"), s("2"), r(s("1"), frac(s("a"), s("b")))))).toMatch(/^ 2\nx\n/)
})

test("a tall base stacks its scripts on its top and bottom edges", () => {
  const layout = layoutMath(scripts(frac(s("a"), s("b")), s("2"), s("3")))
  expect(layout.toString()).toBe(lines("   2", " a", "───", " b", "   3"))
  expect([layout.width, layout.height, layout.baseline]).toEqual([4, 5, 2])
})

test("an empty script is dropped, and a script on nothing hangs off an empty base", () => {
  expect(draw(scripts(s("x"), t(""), s("1")))).toBe("x₁")
  expect(draw(scripts(s("x"), s("1"), r()))).toBe("x¹")
  expect(draw(scripts(s("x"), t("ab"), t("")))).toBe(lines(" ab", "x"))
  expect(draw(scripts(s("x"), t(""), t("ab")))).toBe(lines("x", " ab"))
  expect(draw(scripts(r(), s("2")))).toBe("²")
})

test("an operator with limits takes its scripts above and below in display mode only", () => {
  const sum = scripts(op("∑", true), s("n"), t("i=1"))
  const display = layoutMath(sum)
  expect(display.toString()).toBe(lines(" n", " ∑", "i=1"))
  expect([display.width, display.height, display.baseline]).toEqual([3, 3, 1])
  expect(draw(sum, { displayMode: false })).toBe("∑ⁿᵢ₌₁")
  expect(draw(scripts(op("∫"), s("1"), s("0")))).toBe("∫¹₀")
})

test("over and under parts are centered on the widest of the three", () => {
  const over = layoutMath({ type: "overunder", base: rel("="), over: t("def") })
  expect(over.toString()).toBe(lines("def", " ="))
  expect([over.width, over.height, over.baseline]).toEqual([3, 2, 1])
  expect(draw({ type: "overunder", base: t("ab"), under: s("x") })).toBe(lines("ab", "x"))
  expect(draw({ type: "overunder", base: s("x"), over: t("ab"), under: t("abcd") })).toBe(lines(" ab", " x", "abcd"))
  expect(draw({ type: "overunder", base: t("abcd"), under: t("ab") })).toBe(lines("abcd", " ab"))
  expect(draw({ type: "overunder", base: t("abcd"), over: s("x") })).toBe(lines(" x", "abcd"))
  expect(layoutMath({ type: "overunder", base: frac(s("a"), s("b")), over: s("x") }).baseline).toBe(2)
  expect(layoutMath({ type: "overunder", base: r(), over: r() }).width).toBe(0)
  expect(layoutMath({ type: "overunder", base: r(), under: r() }).width).toBe(0)
})

test("a brace spans at least three cells with its tip at the middle, over or under its body", () => {
  const over = layoutMath({ type: "brace", body: t("abcd"), position: "over" })
  expect(over.toString()).toBe(lines("╭┴─╮", "abcd"))
  expect([over.width, over.height, over.baseline]).toEqual([4, 2, 1])
  const under = layoutMath({ type: "brace", body: s("x"), position: "under" })
  expect(under.toString()).toBe(lines(" x", "╰┬╯"))
  expect([under.width, under.height, under.baseline]).toEqual([3, 2, 0])
  expect(draw({ type: "brace", body: t("abcde"), position: "under" })).toBe(lines("abcde", "╰─┬─╯"))
  expect(draw({ type: "brace", body: t("ab"), position: "under" })).toBe(lines("ab", "╰┬╯"))
})

test("a braced base takes its scripts as labels on the brace's side", () => {
  expect(draw(scripts({ type: "brace", body: s("x"), position: "under" }, undefined, s("n")))).toBe(
    lines(" x", "╰┬╯", " n"),
  )
})

test("each accent draws its mark centered above the body, and underline draws a rule below", () => {
  const accent = (kind: string, body = s("x")) => draw({ type: "accent", accent: kind, body } as MathNode)
  expect(accent("hat")).toBe(lines("^", "x"))
  expect(accent("widehat")).toBe(lines("^", "x"))
  expect(accent("hat", t("xyz"))).toBe(lines(" ⌢", "xyz"))
  expect(accent("widehat", t("xyzw"))).toBe(lines(" ⌢", "xyzw"))
  expect(accent("vec")).toBe(lines("→", "x"))
  expect(accent("tilde")).toBe(lines("~", "x"))
  expect(accent("dot")).toBe(lines("·", "x"))
  expect(accent("ddot")).toBe(lines("¨", "x"))
  expect(accent("bar", t("xy"))).toBe(lines("──", "xy"))
  expect(accent("overline", t("xy"))).toBe(lines("──", "xy"))
  expect(accent("vec", t("中"))).toBe(lines("→", "中"))
  const under = layoutMath({ type: "accent", accent: "underline", body: t("xy") })
  expect(under.toString()).toBe(lines("xy", "──"))
  expect([under.height, under.baseline]).toEqual([2, 0])
  const over = layoutMath({ type: "accent", accent: "dot", body: s("x") })
  expect([over.height, over.baseline]).toEqual([2, 1])
})

test("delimiters around a one-line body are plain characters, and an empty one takes no room", () => {
  expect(draw({ type: "delimited", left: "(", body: s("x"), right: ")" })).toBe("(x)")
  expect(draw({ type: "delimited", left: "", body: s("x"), right: "|" })).toBe("x|")
})

test("delimiters around a tall body stretch with their own top, middle and bottom pieces", () => {
  const around = (left: string, right: string, body = frac(s("a"), s("b"))) =>
    draw({ type: "delimited", left, body, right })
  expect(around("(", ")")).toBe(lines("⎛ a ⎞", "⎜───⎟", "⎝ b ⎠"))
  expect(around("[", "]")).toBe(lines("⎡ a ⎤", "⎢───⎥", "⎣ b ⎦"))
  expect(around("{", "}")).toBe(lines("⎧ a ⎫", "⎨───⎬", "⎩ b ⎭"))
  expect(around("⌊", "⌋")).toBe(lines("│ a │", "│───│", "⌊ b ⌋"))
  expect(around("⌈", "⌉")).toBe(lines("⌈ a ⌉", "│───│", "│ b │"))
  expect(around("⟨", "⟩")).toBe(lines("/ a \\", "│───│", "\\ b /"))
  expect(around("║", "‖")).toBe(lines("║ a ‖", "║───‖", "║ b ‖"))
  expect(draw({ type: "delimited", left: "{", body: matrix("matrix", [[s("a")], [s("b")]]), right: "" })).toBe(
    lines("⎧a", "⎨", "⎩b"),
  )
  const tall = frac(frac(s("a"), s("b")), s("c"))
  expect(around("{", "}", tall)).toBe(lines("⎧  a  ⎫", "⎪ ─── ⎪", "⎨  b  ⎬", "⎪─────⎪", "⎩  c  ⎭"))
})

test("a two-row brace has no middle piece", () => {
  const body = scripts(s("x"), t("ab"))
  expect(draw({ type: "delimited", left: "{", body, right: "}" })).toBe(lines("⎧ ab⎫", "⎩x  ⎭"))
})

test("matrix rows align their cells on a shared baseline and grow to the tallest cell", () => {
  const layout = layoutMath(matrix("matrix", [[frac(s("a"), s("b")), s("x"), scripts(s("y"), undefined, t("ab"))], [s("z")]]))
  expect(layout.toString()).toBe(lines(" a", "─── x y", " b     ab", "", " z"))
  expect([layout.height, layout.baseline]).toEqual([5, 2])
})

test("cases align left two cells apart, and aligned alternates right and left columns", () => {
  expect(draw(matrix("cases", [[s("a"), t("if x")], [t("bb"), s("y")]]))).toBe(
    lines("⎧a   if x", "⎨", "⎩bb  y"),
  )
  expect(draw(matrix("aligned", [[s("a"), t("=b"), s("c"), t("=d")], [t("xx"), s("="), t("cc"), s("e")]]))).toBe(
    lines(" a  =b   c  =d", "", "xx  =   cc  e"),
  )
  expect(draw(matrix("align", [[s("a"), t("=bb")], [t("xx"), s("=")]]))).toBe(lines(" a  =bb", "", "xx  ="))
})

test("an array aligns columns by its spec and draws its vertical rules through every row", () => {
  const layout = layoutMath(matrix("array", [[s("a"), t("bb")], [t("ccc"), s("d")]], "|l|r|"))
  expect(layout.toString()).toBe(lines("│ a   │ bb │", "│     │    │", "│ ccc │  d │"))
  expect(layout.width).toBe(12)
  expect(draw(matrix("array", [[s("a"), s("b"), s("c")]], "c||l"))).toBe("a ││ b c")
  expect(draw(matrix("array", [[s("a")]], "||c"))).toBe("││ a")
  expect(draw(matrix("array", [[t("a"), t("bb")], [t("aaa"), t("b")]], "rc"))).toBe(lines("  a bb", "", "aaa b"))
})

test("an empty matrix is one blank line, and its columns can come from the spec alone", () => {
  const empty = layoutMath(matrix("matrix", [[]]))
  expect([empty.width, empty.height, empty.baseline]).toEqual([0, 1, 0])
  expect(layoutMath(matrix("array", [[]], "lc")).width).toBe(1)
})

test("each fenced matrix environment draws its own delimiters", () => {
  const body = [[s("a")], [s("b")]]
  expect(draw(matrix("pmatrix", body))).toBe(lines("⎛a⎞", "⎜ ⎟", "⎝b⎠"))
  expect(draw(matrix("bmatrix", body))).toBe(lines("⎡a⎤", "⎢ ⎥", "⎣b⎦"))
  expect(draw(matrix("Bmatrix", body))).toBe(lines("⎧a⎫", "⎨ ⎬", "⎩b⎭"))
  expect(draw(matrix("vmatrix", body))).toBe(lines("│a│", "│ │", "│b│"))
  expect(draw(matrix("Vmatrix", body))).toBe(lines("║a║", "║ ║", "║b║"))
  expect(draw(matrix("smallmatrix", body))).toBe(lines("a", "", "b"))
  expect(draw(matrix("pmatrix", [[s("a"), s("b")]]))).toBe("(a b)")
})

test("letter variants map A-Z, a-z and digits to their Unicode alphabets, with the letterlike exceptions", () => {
  const variant = (name: string, value: string) => draw({ type: "variant", variant: name, body: t(value) } as MathNode)
  const edges = "@AZ[`az{/09:"
  expect(variant("double-struck", edges)).toBe("@𝔸ℤ[`𝕒𝕫{/𝟘𝟡:")
  expect(variant("double-struck", "CHNPQRZ")).toBe("ℂℍℕℙℚℝℤ")
  expect(variant("script", edges)).toBe("@𝒜𝒵[`𝒶𝓏{/09:")
  expect(variant("script", "BEFHILMRego")).toBe("ℬℰℱℋℐℒℳℛℯℊℴ")
  expect(variant("fraktur", edges)).toBe("@𝔄ℨ[`𝔞𝔷{/09:")
  expect(variant("fraktur", "CHIRZ")).toBe("ℭℌℑℜℨ")
  expect(variant("sans", edges)).toBe("@𝖠𝖹[`𝖺𝗓{/𝟢𝟫:")
  expect(variant("monospace", edges)).toBe("@𝙰𝚉[`𝚊𝚣{/𝟶𝟿:")
  expect(variant("bold", "Ab1")).toBe("Ab1")
  expect(variant("italic", "Ab1")).toBe("Ab1")
  expect(variant("normal", "Ab1")).toBe("Ab1")
  expect(variant("unknown", "Ab1")).toBe("Ab1")
})

test("a color applies to every cell drawn inside it, rules included, and the option colors the whole formula", () => {
  const colored = layoutMath({ type: "color", color: "red", body: frac(s("a"), s("b")) })
  expect(colored.cells[1][0]).toEqual({ char: "─", style: { color: "red" } })
  expect(colored.cells[0][1]).toEqual({ char: "a", style: { color: "red" } })
  const option = layoutMath(r(s("a"), { type: "variant", variant: "bold", body: s("b") }), { color: "blue" })
  expect(option.cells[0][0]?.style).toEqual({ color: "blue" })
  expect(option.cells[0][1]?.style).toEqual({ color: "blue", bold: true })
  const variant = (name: string) => layoutMath({ type: "variant", variant: name, body: s("x") } as MathNode).cells[0][0]
  expect(variant("italic")).toEqual({ char: "x", style: { italic: true } })
  expect(variant("normal")).toEqual({ char: "x", style: {} })
  const styled = (node: MathNode) =>
    layoutMath(node, { color: "c" })
      .cells.flat()
      .filter((cell) => cell !== undefined)
      .every((cell) => cell?.style?.color === "c")
  expect(styled({ type: "root", body: frac(s("1"), s("2")), index: s("3") })).toBe(true)
  expect(styled({ type: "brace", body: s("x"), position: "over" })).toBe(true)
  expect(styled({ type: "accent", accent: "bar", body: s("x") })).toBe(true)
  expect(styled({ type: "accent", accent: "underline", body: s("x") })).toBe(true)
  expect(styled({ type: "accent", accent: "dot", body: s("x") })).toBe(true)
  expect(styled(matrix("array", [[s("a")], [s("b")]], "|c|"))).toBe(true)
  expect(styled(matrix("pmatrix", [[s("a")], [s("b")]]))).toBe(true)
  expect(styled(matrix("pmatrix", [[s("a")]]))).toBe(true)
  expect(styled(scripts(s("x"), s("2")))).toBe(true)
  expect(styled({ type: "delimited", left: "(", body: frac(s("1"), s("2")), right: "{" })).toBe(true)
})

test("wide characters take two cells, combining marks and controls none", () => {
  const wide = [0x1100, 0x115f, 0x2329, 0x232a, 0x2e80, 0xa4cf, 0xac00, 0xd7a3, 0xf900, 0xfaff, 0xfe10, 0xfe6f, 0xff00, 0xff60, 0xffe0, 0xffe6, 0x1f300, 0x1faff]
  for (const code of wide) expect(layoutMath(t(String.fromCodePoint(code))).width).toBe(2)
  const narrow = [0x10ff, 0x1160, 0x2328, 0x232b, 0x2e7f, 0xa4d0, 0xabff, 0xd7a4, 0xf8ff, 0xfb00, 0xfe70, 0xfeff, 0xff61, 0xffdf, 0xffe7, 0x1f2ff, 0x1fb00]
  for (const code of narrow) expect(layoutMath(t(String.fromCodePoint(code))).width).toBe(1)
  expect(layoutMath(t("a\u0301")).width).toBe(1)
  for (const mark of ["\u0300", "\u036f", "\ufe00", "\ufe0f", "\u0000", "\u001f", "\u007f", "\u009f"]) {
    expect(layoutMath(t(mark)).width).toBe(0)
  }
  expect(layoutMath(t("x\u0300y")).width).toBe(2)
  expect(layoutMath(t("\r\n")).width).toBe(1)
})

test("a wide character's second cell is skipped in the text, and trailing blanks are trimmed", () => {
  const layout = layoutMath(r(t("中"), s("x")))
  expect(layout.width).toBe(3)
  expect(layout.toString()).toBe("中x")
  expect(draw(frac(t("中文"), s("a")))).toBe(lines(" 中文", "──────", "  a"))
})

test("an unknown node type is refused", () => {
  expect(() => layoutMath({ type: "bogus" } as unknown as MathNode)).toThrow(new Error("Unsupported math node"))
})
