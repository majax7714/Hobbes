import { expect, test } from "bun:test"
import { expandLatexMacros, parseLatex } from "../src/parser"
import { LatexParseError, type MathNode } from "../src/types"

const sym = (value: string, role?: string) => ({ type: "symbol", value, ...(role ? { role } : {}) }) as MathNode
const ord = (value: string) => sym(value, "ordinary")
const text = (value: string) => ({ type: "text", value }) as MathNode
const row = (...body: MathNode[]) => ({ type: "row", body }) as MathNode
const empty = row()

function failure(source: string, options = {}): LatexParseError {
  try {
    parseLatex(source, options)
  } catch (error) {
    if (error instanceof LatexParseError) return error
    throw error
  }
  throw new Error(`${source} parsed`)
}

test("plain characters become symbols whose role comes from the character", () => {
  expect(parseLatex("a+-*/×÷±∓")).toEqual(
    row(ord("a"), ...[..."+-*/×÷±∓"].map((char) => sym(char, "binary"))),
  )
  expect(parseLatex("=<>≤≥≠≈∈∉⊂⊃")).toEqual(row(...[..."=<>≤≥≠≈∈∉⊂⊃"].map((char) => sym(char, "relation"))))
  expect(parseLatex(",;:([)]")).toEqual(
    row(
      sym(",", "punctuation"),
      sym(";", "punctuation"),
      sym(":", "punctuation"),
      sym("(", "opening"),
      sym("[", "opening"),
      sym(")", "closing"),
      sym("]", "closing"),
    ),
  )
})

test("one atom is returned bare, a group is its contents, and whitespace and comments are skipped", () => {
  expect(parseLatex("x")).toEqual(ord("x"))
  expect(parseLatex(" { x } ")).toEqual(ord("x"))
  expect(parseLatex("{}")).toEqual(empty)
  expect(parseLatex("a % comment }\n b")).toEqual(row(ord("a"), ord("b")))
  expect(parseLatex("a % trailing")).toEqual(ord("a"))
  expect(parseLatex("a~b")).toEqual(row(ord("a"), { type: "space", width: 1 }, ord("b")))
})

test("an unopened or unclosed group is an error at the offending offset", () => {
  expect(failure("a}").message).toBe('Unexpected "}" at offset 1')
  expect(failure("{a").message).toBe('Expected "}" at offset 2')
})

test("a superscript and a subscript attach to the atom before them, together and with no base", () => {
  expect(parseLatex("x_i^2")).toEqual({ type: "scripts", base: ord("x"), subscript: ord("i"), superscript: ord("2") })
  expect(parseLatex("^{ab}")).toEqual({ type: "scripts", base: empty, superscript: row(ord("a"), ord("b")) })
  expect(parseLatex("a b_1")).toEqual(row(ord("a"), { type: "scripts", base: ord("b"), subscript: ord("1") }))
  expect(failure("x^").message).toBe("Expected an argument at offset 2")
})

test("frac and its display variants read two arguments under a bar", () => {
  for (const command of ["frac", "dfrac", "tfrac", "cfrac"]) {
    expect(parseLatex(`\\${command} 1 {x}`)).toEqual({
      type: "fraction",
      numerator: ord("1"),
      denominator: ord("x"),
      bar: true,
    })
  }
})

test("cfrac takes a left, right or empty alignment and refuses any other", () => {
  expect(parseLatex("\\cfrac\n[l]{a}{b}")).toMatchObject({ numerator: ord("a"), numeratorAlign: "left" })
  expect(parseLatex("\\cfrac[r]{a}{b}")).toMatchObject({ denominator: ord("b"), numeratorAlign: "right" })
  expect(parseLatex("\\cfrac[]{a}{b}")).not.toHaveProperty("numeratorAlign")
  expect(failure("\\cfrac[c]{[]}{b}").message).toBe(
    "Unsupported \\cfrac alignment; expected [l], [r], or [] at offset 6",
  )
  expect(parseLatex("\\frac[a]")).toEqual(row({ type: "fraction", numerator: sym("[", "opening"), denominator: ord("a"), bar: true }, sym("]", "closing")))
})

test("binomials are barless fractions in parentheses", () => {
  for (const command of ["binom", "dbinom", "tbinom"]) {
    expect(parseLatex(`\\${command}{n}{k}`)).toEqual({
      type: "delimited",
      left: "(",
      body: { type: "fraction", numerator: ord("n"), denominator: ord("k"), bar: false },
      right: ")",
    })
  }
})

test("a root takes an optional index", () => {
  expect(parseLatex("\\sqrt x")).toEqual({ type: "root", body: ord("x") })
  expect(parseLatex("\\sqrt\n[n+1]{x}")).toEqual({
    type: "root",
    index: row(ord("n"), sym("+", "binary"), ord("1")),
    body: ord("x"),
  })
})

test("left and right read their delimiters and the body between, with middle delimiters inside", () => {
  expect(parseLatex("\\left\n( a \\middle| b \\right\\}")).toEqual({
    type: "delimited",
    left: "(",
    body: row(ord("a"), sym("│"), ord("b")),
    right: "}",
  })
  expect(parseLatex("\\left.\\rightarrow\\right\\langle")).toEqual({
    type: "delimited",
    left: "",
    body: sym("→", "relation"),
    right: "⟨",
  })
  expect(parseLatex("\\left\\foo x\\right)")).toMatchObject({ left: "\\foo" })
})

test("a missing or stray right, a missing delimiter, or an unknown one when strict, is an error", () => {
  expect(failure("\\left( a").message).toBe("Missing \\right at offset 8")
  expect(failure("a \\right)").message).toBe("Unexpected \\right at offset 2")
  expect(failure("\\left").message).toBe("Expected a delimiter at offset 5")
  expect(failure("\\left\\foo x\\right)", { strict: true }).message).toBe("Unsupported delimiter \\foo at offset 5")
})

test("every accent command names its accent", () => {
  const accents = {
    hat: "hat",
    widehat: "widehat",
    bar: "bar",
    overline: "overline",
    underline: "underline",
    vec: "vec",
    tilde: "tilde",
    widetilde: "tilde",
    dot: "dot",
    ddot: "ddot",
  }
  for (const [command, accent] of Object.entries(accents)) {
    expect(parseLatex(`\\${command}{x}`)).toEqual({ type: "accent", accent, body: ord("x") } as MathNode)
  }
})

test("every font command names its variant, and textrm reads its argument as text", () => {
  const variants = {
    mathrm: "normal",
    mathnormal: "normal",
    mathbf: "bold",
    boldsymbol: "bold",
    bm: "bold",
    mathit: "italic",
    mathsf: "sans",
    mathtt: "monospace",
    mathbb: "double-struck",
    mathcal: "script",
    mathscr: "script",
    mathfrak: "fraktur",
  }
  for (const [command, variant] of Object.entries(variants)) {
    expect(parseLatex(`\\${command}{x}`)).toEqual({ type: "variant", variant, body: ord("x") } as MathNode)
  }
  expect(parseLatex("\\textrm{a b}")).toEqual({ type: "variant", variant: "normal", body: text("a b") })
})

test("text reads raw characters, unescaping specials and turning spacing commands and ties into spaces", () => {
  expect(parseLatex("\\text{a\\{\\}\\%\\#\\$\\&\\_\\ b}")).toEqual(text("a{}%#$&_ b"))
  expect(parseLatex("\\mbox{\\textbackslash x\\!y~z\\quad w\\,v\\alpha\\~}")).toEqual(text("\\ xy z   w v\\alpha\\ "))
  expect(parseLatex("\\text\n{a{b}c}")).toEqual(text("a{b}c"))
  expect(parseLatex("\\text{a\\\\}")).toEqual(text("a\\\\"))
  expect(parseLatex("\\text{a\\\\\\\\}")).toEqual(text("a\\\\\\\\"))
})

test("an unterminated raw group is an error at the group's start", () => {
  expect(failure("\\text{abc").message).toBe("Unterminated group at offset 6")
  expect(failure("\\text{a\\}").message).toBe("Unterminated group at offset 6")
})

test("operatorname reads its name as text, and a star asks for limits", () => {
  expect(parseLatex("\\operatorname{rank}")).toEqual({ type: "operator", value: "rank", limits: false })
  expect(parseLatex("\\operatorname *{argmax}")).toEqual({ type: "operator", value: "argmax", limits: true })
})

test("overset, stackrel and underset put their first argument over or under the second", () => {
  const over = { type: "overunder", base: sym("=", "relation"), over: ord("d") } as MathNode
  expect(parseLatex("\\overset{d}{=}")).toEqual(over)
  expect(parseLatex("\\stackrel d =")).toEqual(over)
  expect(parseLatex("\\underset{d}{=}")).toEqual({ type: "overunder", base: sym("=", "relation"), under: ord("d") })
})

test("overbrace and underbrace set the brace's side", () => {
  expect(parseLatex("\\overbrace{x}")).toEqual({ type: "brace", body: ord("x"), position: "over" })
  expect(parseLatex("\\underbrace x")).toEqual({ type: "brace", body: ord("x"), position: "under" })
})

test("textcolor colors its argument and color colors the rest of the group", () => {
  expect(parseLatex("\\textcolor{red}{x}y")).toEqual(row({ type: "color", color: "red", body: ord("x") }, ord("y")))
  expect(parseLatex("a{\\color{#0f0} b c}d")).toEqual(
    row(ord("a"), { type: "color", color: "#0f0", body: row(ord("b"), ord("c")) }, ord("d")),
  )
})

test("not negates every relation it knows, strikes others, and prefixes a non-symbol with ¬", () => {
  const pairs = "=≠ ∈∉ ∋∌ ≡≢ ≈≉ ∼≁ <≮ >≯ ≤≰ ≥≱ ⊂⊄ ⊃⊅ ⊆⊈ ⊇⊉ ∣∤ ∥∦".split(" ")
  for (const [value, negated] of pairs.map((pair) => [...pair])) {
    expect(parseLatex(`\\not ${value}`)).toMatchObject({ type: "symbol", value: negated })
  }
  expect(parseLatex("\\not\\in")).toEqual(sym("∉", "relation"))
  expect(parseLatex("\\not a")).toEqual(ord("a\u0338"))
  expect(parseLatex("\\not{a}")).toEqual(ord("a\u0338"))
  expect(parseLatex("\\not{ab}")).toEqual(row(sym("¬"), row(ord("a"), ord("b"))))
})

test("pmod spells out its modulus, while mod and bmod are a plain operator", () => {
  expect(parseLatex("\\pmod{p}")).toEqual(
    row({ type: "space", width: 1 }, text("(mod "), ord("p"), text(")")),
  )
  for (const command of ["mod", "bmod"]) {
    expect(parseLatex(`\\${command}`)).toEqual({ type: "operator", value: "mod", limits: false })
  }
})

test("displaylines stacks its lines as a gathered matrix", () => {
  expect(parseLatex("\\displaylines\n{a\\\\b}")).toEqual({
    type: "matrix",
    environment: "gathered",
    rows: [[ord("a")], [ord("b")]],
  })
})

test("style switches and a leading limits switch draw nothing", () => {
  for (const command of ["limits", "nolimits", "displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle"]) {
    expect(parseLatex(`{\\${command}}`)).toEqual(empty)
    expect(parseLatex(`x^\\${command}`)).toEqual({ type: "scripts", base: ord("x"), superscript: empty })
  }
})

test("limits and nolimits set the limits of the operator before them, even under scripts", () => {
  expect(parseLatex("\\sum\\nolimits x")).toEqual(row({ type: "operator", value: "∑", limits: false }, ord("x")))
  expect(parseLatex("\\int_0\\limits")).toEqual({
    type: "scripts",
    base: { type: "operator", value: "∫", limits: true },
    subscript: ord("0"),
  })
  expect(parseLatex("x\\limits")).toEqual(ord("x"))
  expect(parseLatex("\\limitsx")).toEqual(text("\\limitsx"))
})

test("sized delimiters read the delimiter that follows; other names are not sizes", () => {
  for (const command of ["big", "Big", "bigg", "Bigg", "bigl", "Bigr", "biggm"]) {
    expect(parseLatex(`\\${command}\\lfloor`)).toEqual(sym("⌊"))
  }
  expect(parseLatex("\\bigcup")).toEqual({ type: "operator", value: "⋃", limits: true })
  expect(parseLatex("\\abig")).toEqual(text("\\abig"))
})

test("spacing commands, named symbols and escaped characters come from their tables", () => {
  expect(parseLatex("\\quad")).toEqual({ type: "space", width: 2 })
  expect(parseLatex("\\alpha")).toEqual(ord("α"))
  expect(parseLatex("\\le")).toEqual(sym("≤", "relation"))
  expect(parseLatex("\\backslash")).toEqual(sym("\\"))
  expect(parseLatex("\\langle")).toEqual(sym("⟨"))
  expect(parseLatex("\\{\\|")).toEqual(row(sym("{"), sym("║")))
  expect(parseLatex("\\%\\#\\$\\&\\_")).toEqual(row(...[..."%#$&_"].map((char) => sym(char))))
})

test("large operators take limits unless they are integrals; named operators only for lim, min and max", () => {
  expect(parseLatex("\\sum")).toEqual({ type: "operator", value: "∑", limits: true })
  expect(parseLatex("\\oint")).toEqual({ type: "operator", value: "∮", limits: false })
  for (const name of ["lim", "liminf", "min", "max"]) {
    expect(parseLatex(`\\${name}`)).toEqual({ type: "operator", value: name, limits: true })
  }
  for (const name of ["sin", "inf"]) {
    expect(parseLatex(`\\${name}`)).toEqual({ type: "operator", value: name, limits: false })
  }
})

test("an unknown command is kept as text, or refused at its start when strict", () => {
  expect(parseLatex("a\\foo b")).toEqual(row(ord("a"), text("\\foo"), ord("b")))
  expect(failure("a\\foo", { strict: true }).message).toBe("Unsupported command \\foo at offset 1")
  expect(parseLatex("\\")).toEqual(empty)
})

test("every matrix environment is read, starred or not, into rows of cells", () => {
  const names = [
    "matrix",
    "pmatrix",
    "bmatrix",
    "Bmatrix",
    "vmatrix",
    "Vmatrix",
    "cases",
    "aligned",
    "align",
    "gathered",
    "gather",
    "smallmatrix",
  ]
  for (const name of names) {
    for (const suffix of ["", "*"]) {
      expect(parseLatex(`\\begin{${name}${suffix}}a & b \\\\ c\\end{${name}${suffix}}`)).toEqual({
        type: "matrix",
        environment: name,
        rows: [[ord("a"), ord("b")], [ord("c")]],
      } as MathNode)
    }
  }
})

test("a matrix row break may carry a spacing bracket, and a trailing break adds no row", () => {
  expect(parseLatex("\\begin{matrix}a\\\\ [2pt] b\\\\[[x]] \\end{matrix}")).toEqual({
    type: "matrix",
    environment: "matrix",
    rows: [[ord("a")], [ord("b")]],
  })
  expect(parseLatex("\\begin{matrix} \\end{matrix}")).toEqual({ type: "matrix", environment: "matrix", rows: [[]] })
  expect(parseLatex("\\begin{matrix}&\\end{matrix}")).toEqual({
    type: "matrix",
    environment: "matrix",
    rows: [[empty, empty]],
  })
})

test("an unclosed matrix or one holding a stray brace is an error", () => {
  expect(failure("\\begin{matrix}a&b").message).toBe("Missing \\end{matrix} at offset 17")
  expect(failure("\\begin{matrix}a}\\end{matrix}").message).toBe('Unexpected "}" in matrix at offset 15')
})

test("an array reads its column spec without spaces and refuses a spec with no column or a stray letter", () => {
  expect(parseLatex("\\begin{array}{ l | c }1&2\\end{array}")).toEqual({
    type: "matrix",
    environment: "array",
    columns: "l|c",
    rows: [[ord("1"), ord("2")]],
  })
  for (const spec of ["||", "lx", "xl"]) {
    expect(failure(`\\begin{array}{${spec}}1\\end{array}`).message).toStartWith("Unsupported array columns")
  }
})

test("an unknown environment is kept as its raw text, refused when strict, and needs its end", () => {
  expect(parseLatex("\\begin{tikz}\\draw x;\\end{tikz}y")).toEqual(row(text("\\draw x;"), ord("y")))
  expect(failure("\\begin{tikz}x\\end{tikz}", { strict: true }).message).toBe(
    "Unsupported environment tikz at offset 12",
  )
  expect(failure("\\begin{tikz}x").message).toBe("Missing \\end{tikz} at offset 12")
})

test("macros expand by name with or without the backslash, over as many passes as they need", () => {
  const macros = { "\\R": "\\mathbb{R}", N: "\\mathbb{\\M}", M: "N", "\\,": "!", half: "\\frac12" }
  expect(expandLatexMacros("\\alpha\\R+\\N\\,\\half", { macros })).toBe("\\alpha\\mathbb{R}+\\mathbb{N}!\\frac12")
  expect(parseLatex("\\R", { macros })).toEqual({ type: "variant", variant: "double-struck", body: ord("R") })
  expect(expandLatexMacros("\\R", { macros: {} })).toBe("\\R")
})

test("a macro that is not a string is a TypeError", () => {
  expect(() => expandLatexMacros("\\R", { macros: { R: 1 as unknown as string } })).toThrow(
    new TypeError("Macro \\R must expand to a string"),
  )
})

test("expansion stops after maxExpand passes, counting the pass that finds nothing new", () => {
  expect(expandLatexMacros("\\a", { macros: { a: "\\b", b: "c" }, maxExpand: 3 })).toBe("c")
  expect(() => expandLatexMacros("\\a", { macros: { a: "\\b", b: "c" }, maxExpand: 2 })).toThrow(
    "Macro expansion exceeded 2 passes at offset 0",
  )
  expect(() => expandLatexMacros("\\a", { macros: { a: "\\a" } })).toThrow("Macro expansion exceeded 100 passes")
})

test("the expanded source may reach maxExpandedLength but not pass it", () => {
  const macros = { a: "xyz" }
  expect(expandLatexMacros("1\\a2\\a3", { macros, maxExpandedLength: 9 })).toBe("1xyz2xyz3")
  for (const source of ["1\\a2\\a34", "12\\a2\\a3", "1\\a2\\a"]) {
    expect(() => expandLatexMacros(source, { macros: { a: source.endsWith("a") ? "xyzxyz" : "xyz" }, maxExpandedLength: 9 })).toThrow(
      "Expanded LaTeX source exceeds the 9-character limit",
    )
  }
  expect(() => expandLatexMacros("0123456789", { maxExpandedLength: 9 })).toThrow(
    new LatexParseError("Expanded LaTeX source exceeds the 9-character limit", 9),
  )
  expect(() => expandLatexMacros("0123456789", { maxSourceLength: 9, maxExpandedLength: 20 })).toThrow(
    "LaTeX source exceeds the 9-character limit",
  )
})

test("the expanded source is checked for brace depth again", () => {
  expect(() => expandLatexMacros("\\a", { macros: { a: "{{x}}" }, maxDepth: 1 })).toThrow(
    "LaTeX nesting exceeds the 1-level limit at offset 1",
  )
})

test("maxDepth bounds nested atoms as well as braces, and siblings do not add up", () => {
  expect(parseLatex("\\sqrt\\sqrt x", { maxDepth: 3 })).toEqual({ type: "root", body: { type: "root", body: ord("x") } })
  expect(failure("\\sqrt\\sqrt x", { maxDepth: 2 }).message).toBe("LaTeX nesting exceeds the 2-level limit at offset 11")
  expect(parseLatex("\\sqrt x\\sqrt y\\sqrt z", { maxDepth: 2 })).toMatchObject({ type: "row" })
  expect(parseLatex("\\frac{a}{b}", { maxDepth: 2 })).toMatchObject({ type: "fraction" })
})

test("every limit option must be a positive safe integer, and is refused by name before parsing", () => {
  for (const name of ["maxDepth", "maxSourceLength", "maxExpandedLength", "maxExpand"]) {
    for (const value of [0, -1, 1.5, Number.NaN, Number.MAX_SAFE_INTEGER + 1]) {
      expect(() => parseLatex("x", { [name]: value })).toThrow(new RangeError(`${name} must be a positive safe integer`))
    }
    expect(parseLatex("x", { [name]: Number.MAX_SAFE_INTEGER })).toEqual(ord("x"))
  }
  expect(parseLatex("x", { maxDepth: 1, maxSourceLength: 1, maxExpandedLength: 1, maxExpand: 1 })).toEqual(ord("x"))
})
