import { describe, expect, test } from "bun:test"
import { ShellScan } from "../../src/shell/scan"

type Dialect = ShellScan.Dialect
const DIALECTS: Dialect[] = ["bash", "zsh", "posix"]

// What a scan comes to: the reason it refused, or each command's words.
const read = (result: ShellScan.Result) =>
  result.kind === "opaque" ? result.reason : result.commands.map((command) => command.words)
const bash = (input: string, dialect: Dialect = "bash") => read(ShellScan.scan(input, dialect))
const ps = (input: string) => read(ShellScan.scanPowerShell(input))
const commands = (input: string, dialect: Dialect = "bash") => {
  const result = ShellScan.scan(input, dialect)
  if (result.kind === "opaque") throw new Error(result.reason)
  return result.commands
}
const psCommands = (input: string) => {
  const result = ShellScan.scanPowerShell(input)
  if (result.kind === "opaque") throw new Error(result.reason)
  return result.commands
}
const reasons = (run: (input: string) => unknown, table: Record<string, string[]>) => {
  for (const [reason, inputs] of Object.entries(table))
    for (const input of inputs) expect({ input, got: run(input) }).toEqual({ input, got: reason })
}
const names = (run: (input: string) => unknown, table: [string, string[][]][]) => {
  for (const [input, want] of table) expect({ input, got: run(input) }).toEqual({ input, got: want })
}

describe("a POSIX-family command", () => {
  test("is its words, cooked, its raw words as written, its resource trimmed", () => {
    expect(commands("  foo  bar  ")).toEqual([
      { resource: "foo  bar", words: ["foo", "bar"], rawWords: ["foo", "bar"] },
    ])
    expect(commands(`foo 'a b' "c d" e\\ f`)).toEqual([
      {
        resource: `foo 'a b' "c d" e\\ f`,
        words: ["foo", "a b", "c d", "e f"],
        rawWords: ["foo", "'a b'", '"c d"', "e\\ f"],
      },
    ])
  })

  test("the dialect defaults to POSIX, which has no arrays", () => {
    expect(read(ShellScan.scan("a[$b]=1"))).toBe("invalid-structure")
  })

  test("a line continuation is no word break, and a comment no word", () => {
    expect(bash("foo a\\\nb")).toEqual([["foo", "ab"]])
    expect(commands("foo a\\\nb")[0].rawWords).toEqual(["foo", "a\\\nb"])
    expect(bash("foo # x y")).toEqual([["foo"]])
    expect(bash("foo a#b")).toEqual([["foo", "a#b"]])
    expect(bash("# only")).toEqual([])
    expect(bash("# one\nfoo")).toEqual([["foo"]])
    expect(bash("")).toEqual([])
    expect(bash(" \t\n")).toEqual([])
  })

  test("ANSI quoting is decoded", () => {
    names(bash, [
      ["foo $'a\\tb'", [["foo", "a\tb"]]],
      ["foo $'\\a\\b\\e\\E\\f\\n\\r\\v'", [["foo", "\x07\b\x1b\x1b\f\n\r\v"]]],
      [`foo $'\\\\\\'\\"\\?'`, [["foo", `\\'"?`]]],
      ["foo $'\\x41\\x4a'", [["foo", "AJ"]]],
      ["foo $'\\101\\7'", [["foo", "A\x07"]]],
    ])
    reasons(bash, {
      "unterminated-quote": ["foo $'a", "foo $'\\0'", "foo $'\\x00'", "foo $'\\q'", "foo $'\\x'", "foo $'\\"],
    })
  })

  test("a list's commands come in order; a command's own comes before its substitutions'", () => {
    names(bash, [
      ["a; b", [["a"], ["b"]]],
      ["a\nb", [["a"], ["b"]]],
      ["a & b", [["a"], ["b"]]],
      ["a && b || c | d |& e", [["a"], ["b"], ["c"], ["d"], ["e"]]],
      ["a;", [["a"]]],
      ["a &", [["a"]]],
      ["a |\nb", [["a"], ["b"]]],
      [
        "echo $(foo x) y",
        [
          ["echo", "$(foo x)", "y"],
          ["foo", "x"],
        ],
      ],
      ['echo "$(foo)"', [["echo", "$(foo)"], ["foo"]]],
      ["echo `foo`", [["echo", "`foo`"], ["foo"]]],
      ["echo <(foo)", [["echo", "<(foo)"], ["foo"]]],
      ["echo >(foo)", [["echo", ">(foo)"], ["foo"]]],
      ["echo ${x:-$(foo)}", [["echo", "${x:-$(foo)}"], ["foo"]]],
      ["echo $(( 1 + $(foo) ))", [["echo", "$(( 1 + $(foo) ))"], ["foo"]]],
      ["echo $(a $(b))", [["echo", "$(a $(b))"], ["a", "$(b)"], ["b"]]],
      ["echo `a \\`b\\``", [["echo", "`a \\`b\\``"], ["a", "`b`"], ["b"]]],
    ])
  })

  test("a leading assignment is no command word, though its text is in the resource", () => {
    expect(commands("A=1 foo x")).toEqual([{ resource: "A=1 foo x", words: ["foo", "x"], rawWords: ["foo", "x"] }])
    expect(bash("A=1")).toEqual([])
    expect(bash("A+=1 B=2")).toEqual([])
    expect(bash("A=$(foo)")).toEqual([["foo"]])
    expect(bash("'A'=1")).toEqual([["A=1"]])
    expect(bash("foo A=1")).toEqual([["foo", "A=1"]])
    expect(bash("a[1]=x")).toEqual([])
    expect(bash("a[$(foo)]=x")).toEqual([["foo"]])
    expect(bash("a=(b c)")).toEqual([])
    expect(bash("a=(b $(foo))")).toEqual([["foo"]])
    expect(bash("a[1]b")).toEqual([["a[1]b"]])
  })

  test("a declaration says so only when it heads the command as written", () => {
    expect(commands("export A=1")[0]).toEqual({
      resource: "export A=1",
      words: ["export", "A=1"],
      rawWords: ["export", "A=1"],
      declaration: true,
    })
    for (const name of ["declare", "typeset", "readonly", "local", "unset", "unsetenv"])
      expect(commands(`${name} x`)[0].declaration).toBe(true)
    expect(commands("A=1 export B")[0].declaration).toBeUndefined()
    expect(commands("foo x")[0].declaration).toBeUndefined()
    expect(commands("'export' x")[0].declaration).toBeUndefined()
  })

  test("a redirection's target is no word, and a word past it is counted", () => {
    expect(commands("foo > out x")[0]).toEqual({
      resource: "foo > out x",
      words: ["foo", "x"],
      rawWords: ["foo", "x"],
      redirectWordCount: 1,
    })
    expect(commands("foo x > out")[0].redirectWordCount).toBeUndefined()
    expect(commands("A=1 foo > out x")[0].redirectWordCount).toBe(1)
    expect(commands("> out foo x")[0]).toEqual({ resource: "> out foo x", words: ["foo", "x"], rawWords: ["foo", "x"] })
    expect(bash("> out")).toEqual([])
    for (const op of ["&>>", "&>", "<<<", "<>", "<&", ">&", ">|", ">>", ">", "<"])
      expect(bash(`foo ${op} x`)).toEqual([["foo"]])
  })

  test("a number or {name} right before a redirection is its descriptor; other words are not", () => {
    names(bash, [
      ["foo 2> e", [["foo"]]],
      ["foo {fd}> e", [["foo"]]],
      ["foo a2> e", [["foo", "a2"]]],
      ["foo 2 > e", [["foo", "2"]]],
      ["foo '2'> e", [["foo", "2"]]],
      ["foo {a-b}> e", [["foo", "{a-b}"]]],
    ])
  })

  test("a trailing redirection on a pipeline's last command is outside its resource", () => {
    expect(commands("a | b > out").map((command) => command.resource)).toEqual(["a", "b"])
    expect(commands("a > out | b").map((command) => command.resource)).toEqual(["a > out", "b"])
    expect(commands("a; b > out").map((command) => command.resource)).toEqual(["a", "b > out"])
  })
})

describe("what a POSIX-family scan refuses", () => {
  test("text it cannot end, or that ends wrongly", () => {
    reasons(bash, {
      "unterminated-quote": ["foo 'a", 'foo "a', "foo $'a", '$"a'],
      "unterminated-escape": ["foo \\"],
      "command-substitution": ["foo $(bar", "foo `bar", "foo ${bar", "foo `)`", "(", "( a"],
      "invalid-redirect": ["foo >", "foo > > x", "foo > ;", "foo <<", "foo << ;"],
      "invalid-structure": [
        "a &&",
        "a ||",
        "a |",
        "; a",
        "a;;",
        "a && ; b",
        "& a",
        '"" x',
        "foo a b",
        "foo a\u000bb",
        "}",
        "a=(b)c",
        "foo &\\\n& bar",
      ],
      "compound-command": [")", "foo )", "fi", "then", "done", "else", "esac", "do", "elif"],
      "dynamic-execution": ["foo a(b)"],
    })
  })

  test("what is too long, or nested too deep, at the limits", () => {
    expect(bash("a".repeat(64 * 1024))).toEqual([["a".repeat(64 * 1024)]])
    expect(bash("a".repeat(64 * 1024 + 1))).toBe("invalid-structure")
    const nested = (depth: number) => `echo ${"$(echo ".repeat(depth)}${")".repeat(depth)}`
    expect(Array.isArray(bash(nested(31)))).toBe(true)
    expect(bash(nested(33))).toBe("command-substitution")
    const grouped = (depth: number) => `${"( ".repeat(depth)}a${" )".repeat(depth)}`
    expect(bash(grouped(32))).toEqual([["a"]])
    expect(bash(grouped(33))).toBe("invalid-structure")
    const ifs = (depth: number) => `${"if a; then ".repeat(depth)}b${"; fi".repeat(depth)}`
    expect(Array.isArray(bash(ifs(32)))).toBe(true)
    expect(bash(ifs(33))).toBe("compound-command")
  })
})

describe("compound commands", () => {
  test("their bodies are read; a header's words are no command", () => {
    names(bash, [
      ["if a; then b; fi", [["a"], ["b"]]],
      ["if a; then b; elif c; then d; else e; fi", [["a"], ["b"], ["c"], ["d"], ["e"]]],
      ["while a; do b; done", [["a"], ["b"]]],
      ["until a; do b; done", [["a"], ["b"]]],
      ["for x in a b; do c; done", [["c"]]],
      ["for x in $(a); do c; done", [["a"], ["c"]]],
      ["for x; do c; done", [["c"]]],
      ["for x do c; done", [["c"]]],
      ["for x\ndo c; done", [["c"]]],
      ["select x in a; do c; done", [["c"]]],
      ["for ((i=0;i<1;i++)); do c; done", [["c"]]],
      ["case x in a) b;; esac", [["b"]]],
      ["case x in a) b;; c|d) e;; esac", [["b"], ["e"]]],
      ["case $(x) in (a) b;& c) d;;& *) e; esac", [["x"], ["b"], ["d"], ["e"]]],
      ["case x in\na) b;;\nesac", [["b"]]],
      ["case x in esac", []],
      ["case x in a) esac", []],
      ["{ a; b; }", [["a"], ["b"]]],
      ["(a; b)", [["a"], ["b"]]],
      ["(a) | b", [["a"], ["b"]]],
      ["a && { b; }", [["a"], ["b"]]],
      ["a && if b; then c; fi", [["a"], ["b"], ["c"]]],
      ["f() { a; }", [["a"]]],
      ["function f { a; }", [["a"]]],
      ["function f() { a; }", [["a"]]],
      ["f () (a)", [["a"]]],
      ["! a", [["a"]]],
      ["time { a; }", [["a"]]],
      ["time -p ( a )", [["a"]]],
      ["time if a; then b; fi", [["a"], ["b"]]],
      ["coproc { a; }", [["a"]]],
      ["coproc n { a; }", [["a"]]],
      // Before a simple command they stay words, which the builtin checks see past.
      ["time a", [["time", "a"]]],
      ["coproc a", [["coproc", "a"]]],
      ["[[ -n x ]]", []],
      ["[[ $(a) == b ]]", [["a"]]],
      ["[[ a && (b || c) ]]", []],
      ["[[ a == (b|c) ]]", []],
      ["[[ # x\n a ]]", []],
      ["(( 1 + 1 ))", []],
      ["(( 1 + $(a) ))", [["a"]]],
      ["{ a; } > out", [["a"]]],
      ["if a; then b; fi > out", [["a"], ["b"]]],
      ["{a", [["{a"]]],
      ["[[a", [["[[a"]]],
    ])
  })

  test("a keyword away from its place is a word", () => {
    names(bash, [
      ["echo if then fi", [["echo", "if", "then", "fi"]]],
      ["foo in", [["foo", "in"]]],
      ["ifx", [["ifx"]]],
      ["do_it", [["do_it"]]],
    ])
  })

  test("what is left open or out of order is refused", () => {
    reasons(bash, {
      "compound-command": [
        "if",
        "if a",
        "if a; then b",
        "if a; fi",
        "if; then b; fi",
        "if a; then fi",
        "if a; then b; else c; else d; fi",
        "if a; then b; else fi",
        "if a; then b; elif; then c; fi",
        "while a",
        "while a; done",
        "while; do b; done",
        "while a; do done",
        "until a; then b; fi",
        "for",
        "for; do a; done",
        "for x | y; do a; done",
        "for x in a | b; do c; done",
        "for x in a; c; done",
        "for (a b) c; done",
        "case x; esac",
        "case x y in esac",
        "case x in | a) b;; esac",
        "case x in ) b;; esac",
        "case x in a b",
        "case; esac",
        "if a; then b; esac",
        "while a; do b; fi",
        "( a; if b; then c; )",
      ],
      "invalid-structure": ["{ }", "( )", "{ a", "[[ a", "[[ a ]", "[[ ) ]]", "[[ a; ]]", "[[ ( a ]]", "[[ # x"],
      "invalid-redirect": ["case x > y in esac", "case x in a > b) c;; esac"],
    })
    expect(bash("if a; then }")).toBe("compound-command")
    expect(bash("}")).toBe("invalid-structure")
    expect(bash("{ a; } b")).toBe("invalid-structure")
    expect(bash("(a) b")).toBe("invalid-structure")
    expect(bash("( a; ) b")).toBe("invalid-structure")
    expect(bash("{ a; } | b")).toEqual([["a"], ["b"]])
  })

  test("a keyword after a redirect is a word to bash and dash, a keyword to zsh", () => {
    expect(bash("if a; then b; > x fi", "bash")).toBe("compound-command")
    expect(bash("if a; then b; > x fi", "posix")).toBe("compound-command")
    expect(bash("if a; then b; > x fi", "zsh")).toEqual([["a"], ["b"]])
  })

  test("only zsh has repeat", () => {
    expect(bash("repeat 3 do a; done", "zsh")).toEqual([["a"]])
    expect(bash("repeat 3 a", "zsh")).toEqual([["a"]])
    expect(bash("repeat 3 { a; }", "zsh")).toEqual([["a"]])
    expect(bash("repeat 3 a", "posix")).toEqual([["a"]])
    expect(bash("repeat 3 a", "bash")).toEqual([["repeat", "3", "a"]])
    expect(bash("repeat 3 do a; done", "bash")).toBe("compound-command")
  })

  test("zsh's for may take its list in parentheses, and needs no do", () => {
    expect(bash("for x (a b); do c; done", "zsh")).toEqual([["c"]])
    expect(bash("for x (a b) c", "zsh")).toEqual([["c"]])
    expect(bash("for x (a b) { c; }", "zsh")).toEqual([["c"]])
    expect(bash("for x in a; { c; }", "zsh")).toEqual([["c"]])
    expect(bash("for x in a { c; }", "zsh")).toBe("compound-command")
    expect(bash("for x in a; c", "zsh")).toBe("compound-command")
  })

  test("((…)) is arithmetic to bash and zsh, two subshells to dash", () => {
    expect(bash("(( a ))", "bash")).toEqual([])
    expect(bash("(( a ))", "zsh")).toEqual([])
    expect(bash("(( a ))", "posix")).toEqual([["a"]])
    expect(bash("(( a; b ))", "bash")).toBe("invalid-structure")
    expect(bash("(( $(a) ))", "posix")).toEqual([["a"], ["$(a)"]])
    expect(bash("(a) (b)")).toBe("compound-command")
    expect(bash("((a) )", "bash")).toEqual([["a"]])
    expect(bash("((a) )", "posix")).toEqual([["a"]])
  })

  test("functions need a body, and a keyword is no name", () => {
    expect(bash("f()")).toBe("dynamic-execution")
    expect(bash("if() { a; }")).toBe("compound-command")
    expect(bash("function if { a; }")).toEqual([["a"]])
    expect(bash("f() a")).toBe("dynamic-execution")
  })
})

describe("words the shells read differently", () => {
  test("a pattern group after a glob character is bash's, and zsh's only in a case pattern", () => {
    expect(bash("echo @(a|b)", "bash")).toEqual([["echo", "@(a|b)"]])
    expect(bash("echo @(a|$(b))", "bash")).toEqual([["echo", "@(a|$(b))"], ["b"]])
    expect(bash("echo @(a|b)", "zsh")).toBe("dynamic-execution")
    expect(bash("echo @(a|b)", "posix")).toBe("dynamic-execution")
    expect(bash("case x in @(a|b)) c;; esac", "zsh")).toEqual([["c"]])
    expect(bash("echo x(a)", "bash")).toBe("dynamic-execution")
    expect(bash("echo @(a", "bash")).toBe("command-substitution")
    expect(bash("echo @(a;b)", "bash")).toBe("command-substitution")
  })

  test("an array assignment holds words, and refuses what would glob or end it", () => {
    expect(bash("a=(b c\nd # e\n)")).toEqual([])
    expect(bash("a=(b) c")).toEqual([["c"]])
    expect(bash("declare a=(b)")).toEqual([["declare", "a=(b)"]])
    reasons(bash, {
      "command-substitution": ["a=(b", "a=(b;c)", "a=(b&c)", "a=(b|c)", "a=(b(c))", "a=(# x"],
    })
    expect(bash("a=(=(b))", "zsh")).toEqual([["b"]])
    expect(bash("a=([1]=b)")).toEqual([])
    expect(bash("foo a=(b)")).toBe("dynamic-execution")
    expect(bash("foo =(b)", "zsh")).toEqual([["foo", "=(b)"], ["b"]])
  })

  test("$[…] is arithmetic, but at a command's head dash splits it, and that is refused", () => {
    expect(bash("$[1] foo", "bash")).toEqual([["$[1]", "foo"]])
    expect(bash("$[1] foo", "zsh")).toEqual([["$[1]", "foo"]])
    expect(bash("$[1] foo", "posix")).toBe("command-substitution")
    expect(bash("foo $[1]", "posix")).toEqual([["foo", "$[1]"]])
    expect(bash("foo $[1;2]")).toBe("invalid-structure")
    expect(bash("foo $[1")).toBe("unterminated-quote")
  })

  test("a subscript's expansion splits in dash, and &> in dash starts another command", () => {
    expect(bash("a[$b]=1", "bash")).toEqual([])
    expect(bash("a[$b]=1", "zsh")).toEqual([])
    expect(bash("a[$b]=1", "posix")).toBe("invalid-structure")
    expect(bash("a[1]=1", "posix")).toEqual([])
    expect(bash("foo &> x y", "bash")).toEqual([["foo", "y"]])
    expect(bash("foo &> x y", "zsh")).toEqual([["foo", "y"]])
    expect(bash("foo &> x y", "posix")).toBe("invalid-redirect")
    expect(bash("foo &> x", "posix")).toEqual([["foo"]])
  })

  test("an operator split by a continuation is read differently by the shells, and refused", () => {
    reasons(bash, { "invalid-structure": ["foo &\\\n& bar", "foo |\\\n| bar", "foo >\\\n> x", "foo $\\\n(bar)"] })
    expect(bash("foo &&\\\nbar")).toEqual([["foo"], ["bar"]])
  })

  test("$$ is the process id, unless an escape in a following quote could read otherwise", () => {
    expect(bash("foo $$")).toEqual([["foo", "$$"]])
    expect(bash("foo $$'a'")).toEqual([["foo", "$$a"]])
    expect(bash("foo $$'a")).toBe("unterminated-quote")
    expect(bash("foo $$'\\a' 'b'")).toBe("unterminated-quote")
    expect(bash("foo $$'\\a'")).toEqual([["foo", "$$\\a"]])
  })

  // Dash reads `$'a\\'` and then an open quote, which alone is a syntax error and runs nothing, so only text after it
  // that dash could read another way is refused.
  test("dash closes $'…' at its first quote, so an escaped one is refused where that changes the words", () => {
    for (const input of ["foo $'a\\'b' #", "foo $'a\\'b\\'c'", `foo $'a\\'b' "x"`]) {
      expect(Array.isArray(bash(input, "bash"))).toBe(true)
      expect(Array.isArray(bash(input, "zsh"))).toBe(true)
      expect(bash(input, "posix")).toBe("unterminated-quote")
    }
    expect(bash("foo $'a\\'b'", "posix")).toEqual([["foo", "a'b"]])
    expect(bash("foo $'a'", "posix")).toEqual([["foo", "a"]])
  })

  test("a parameter's name and words", () => {
    expect(bash("foo ${x}")).toEqual([["foo", "${x}"]])
    expect(bash("foo $x")).toEqual([["foo", "$x"]])
    expect(bash("foo $")).toEqual([["foo", "$"]])
    expect(bash("foo ${x:-a b}")).toEqual([["foo", "${x:-a b}"]])
    expect(bash('foo "${x:-$(a)}"')).toEqual([["foo", "${x:-$(a)}"], ["a"]])
    expect(bash("foo ${ a; }")).toEqual([["foo", "${ a; }"], ["a"]])
    expect(bash("foo ${|a; }")).toEqual([["foo", "${|a; }"], ["a"]])
    expect(bash('foo "${x:-$(a})}"')).toBe("command-substitution")
  })
})

describe("what could evaluate text, refused as dynamic execution", () => {
  const dynamic = "dynamic-execution"
  const everywhere = (input: string) => {
    for (const dialect of DIALECTS)
      expect({ input, dialect, got: bash(input, dialect) }).toEqual({ input, dialect, got: dynamic })
  }
  const nowhere = (input: string) => {
    for (const dialect of DIALECTS)
      expect({ input, dialect, got: Array.isArray(bash(input, dialect)) }).toEqual({ input, dialect, got: true })
  }
  // Each shell's own: refused in zsh and posix, read in bash.
  const notBash = (input: string) => {
    expect({ input, got: Array.isArray(bash(input, "bash")) }).toEqual({ input, got: true })
    expect({ input, got: bash(input, "zsh") }).toEqual({ input, got: dynamic })
    expect({ input, got: bash(input, "posix") }).toEqual({ input, got: dynamic })
  }

  test("an expansion in text a shell evaluates as arithmetic", () => {
    for (const input of ["let 'a[$(x)]'", "let 'a[`x`]'", "(( a[$b] )) ; let 'c[$(d)]'"]) everywhere(input)
    for (const input of ["let a", "let 'a[1]'", "echo 'a[$(x)]'", "(( a ))"]) nowhere(input)
    expect(bash("echo $(( a[$(x)] ))")).toEqual([["echo", "$(( a[$(x)] ))"], ["x"]])
  })

  test("an expansion in a name a builtin binds, once the operand has a bracket", () => {
    for (const input of [
      "declare -n 'x[$(y)]'",
      "read 'x[$(y)]'",
      "printf -v 'x[$(y)]' a",
      "test -v 'a[$(x)]'",
      "[ -v 'a[$(x)]' ]",
      "wait -p 'a[$(x)]'",
    ])
      everywhere(input)
    for (const input of ["printf 'x[$(y)]'", "test -n 'a[$(x)]'", "wait 'a[$(x)]'", "read x", "read 'x[1]'"])
      nowhere(input)
  })

  test("a precommand does not hide the builtin", () => {
    for (const input of [
      "command let 'a[$(x)]'",
      "builtin let 'a[$(x)]'",
      "command -p let 'a[$(x)]'",
      "time let 'a[$(x)]'",
    ])
      everywhere(input)
    expect(bash("exec -a x let 'a[$(y)]'", "bash")).toEqual([["exec", "-a", "x", "let", "a[$(y)]"]])
    expect(bash("exec -a x let 'a[$(y)]'", "zsh")).toBe(dynamic)
    expect(bash("noglob let 'a[$(x)]'", "zsh")).toBe(dynamic)
    expect(Array.isArray(bash("noglob let 'a[$(x)]'", "bash"))).toBe(true)
  })

  test("[[ ]] names a variable with -v, and evaluates arithmetic comparisons", () => {
    for (const input of ["[[ -v 'a[$(x)]' ]]", "[[ 'a[$(x)]' -eq 1 ]]", "[[ 1 -lt 'a[$(x)]' ]]"]) everywhere(input)
    for (const input of ["[[ -n 'a[$(x)]' ]]", "[[ 'a[$(x)]' == 1 ]]", "[[ a -eq 1 ]]"]) nowhere(input)
    expect(Array.isArray(bash("[[ -t 'a[$(x)]' ]]", "bash"))).toBe(true)
    expect(bash("[[ -t 'a[$(x)]' ]]", "zsh")).toBe(dynamic)
  })

  test("a bound value, only once something later can evaluate it", () => {
    for (const input of [
      "a='$(x)'; eval b",
      "a='`x`'; eval b",
      "a=('$(x)'); eval b",
      "for i in '$(x)'; do eval b; done",
      "foo <<< '$(x)'; eval b",
      "a='$(x)'; echo ${!b}",
      "a='$(x)'; (( c ))",
      "a='$(x)'; PS4=b",
      "a='$(x)'; echo ${PS4}",
    ])
      everywhere(input)
    for (const input of ["a='$(x)'", "a='$(x)'; echo b", "a='plain'; eval b", "eval b"]) nowhere(input)
  })

  test("what enables evaluation", () => {
    for (const input of ["set -k", "set -ek", "set -o keyword", "alias a=b", "command alias a=b", "echo ${x@P}"])
      everywhere(input)
    for (const input of ["set -e", "alias a", "echo ${x@Q}", "foo -k", "foo a=b"]) nowhere(input)
  })

  test("compgen -C or -F runs its argument, except in zsh", () => {
    for (const input of ["compgen -C x", "compgen -F x", "compgen -abC x"]) {
      expect(bash(input, "bash")).toBe(dynamic)
      expect(bash(input, "posix")).toBe(dynamic)
      expect(Array.isArray(bash(input, "zsh"))).toBe(true)
    }
    nowhere("compgen -W x")
    nowhere("compgen C")
  })

  test("zsh's flags that evaluate, and the modifier that globs", () => {
    for (const input of [
      "echo ${(e)x}",
      "echo ${(P)x}",
      "echo $^~x",
      "echo $~x",
      "echo ${~x}",
      "echo ${(f)~x}",
      "echo ${\\\n(q)x}",
    ])
      notBash(input)
    for (const input of ["echo ${(q)x}", "echo ${(U)x}", "echo ${(s:,:)x}", "echo ${=x}", "echo ${x}"]) nowhere(input)
  })

  test("zsh's options, modules and hashes that run code", () => {
    for (const input of [
      "setopt globsubst",
      "setopt GLOB_SUBST",
      "setopt no_prompt_subst",
      "unsetopt kshglob",
      "setopt -m x",
      "set -o promptsubst",
      "set +o aliases",
      "emulate sh",
      "NULLCMD=x",
      "READNULLCMD=x",
      "functions[a]=b",
      "aliases=(a b)",
      "galiases[a]=b",
      "dis_functions[a]=b",
      "options[a]=b",
      "commands[a]=b",
      "echo ${NULLCMD}",
      "echo ${functions[a]}",
      "typeset functions",
      "typeset -v functions",
    ])
      notBash(input)
    for (const input of ["setopt nullglob", "set -o errexit", "set -o", "echo ${functions}", "foo=functions"])
      nowhere(input)
  })

  test("zsh's arithmetic builtins, and its globbing of an unquoted parameter's words", () => {
    for (const input of ["echo ${x:-(a)}", "integer 'a[$(x)]'", "float 'a[$(x)]'"]) notBash(input)
    expect(Array.isArray(bash('echo "${x:-(a)}"', "zsh"))).toBe(true)
  })

  test("a parameter's offset is arithmetic, and a subscript evaluates", () => {
    expect(bash("echo ${a:$(b)}", "bash")).toEqual([["echo", "${a:$(b)}"], ["b"]])
    expect(bash("echo ${a:'$(b)'}", "bash")).toBe(dynamic)
    expect(bash("echo ${a:='$(b)'}", "bash")).toEqual([["echo", "${a:='$(b)'}"]])
    expect(bash("echo ${a:-'$(b)'}", "bash")).toEqual([["echo", "${a:-'$(b)'}"]])
    expect(bash("echo ${a['$(b)']}", "bash")).toEqual([["echo", "${a['$(b)']}"], ["b"]])
    expect(bash("echo ${a[1]}", "bash")).toEqual([["echo", "${a[1]}"]])
    expect(bash('echo "$a[1]"', "zsh")).toEqual([["echo", "$a[1]"]])
  })
})

describe("heredocs", () => {
  test("the body is no command, is in the resource, and later lines are read", () => {
    expect(commands("cat <<EOF\nbody\nEOF\nfoo")).toEqual([
      { resource: "cat <<EOF\nbody\nEOF", words: ["cat"], rawWords: ["cat"] },
      { resource: "foo", words: ["foo"], rawWords: ["foo"] },
    ])
    expect(bash("cat <<EOF\nEOF")).toEqual([["cat"]])
    expect(bash("cat <<EOF && foo\nbody\nEOF\nbar")).toEqual([["cat"], ["foo"], ["bar"]])
  })

  test("an unquoted delimiter's body is read for substitutions; a quoted one's is not", () => {
    expect(bash("cat <<EOF\n$(foo)\nEOF")).toEqual([["cat"], ["foo"]])
    for (const open of ["<<'EOF'", '<<"EOF"', "<<\\EOF", "<<E'O'F", "<<$'EOF'"])
      expect({ open, got: bash(`cat ${open}\n$(foo)\nEOF`) }).toEqual({ open, got: [["cat"]] })
  })

  test("<<- strips the tabs before a body line and its end", () => {
    expect(bash("cat <<-EOF\n\tbody\n\tEOF")).toEqual([["cat"]])
    expect(bash("cat <<EOF\n\tEOF")).toBe("heredoc")
    expect(bash("cat <<-EOF\n  EOF")).toBe("heredoc")
  })

  test("two on a line are read in order; a group shares its parent's", () => {
    expect(bash("cat <<A <<B\n1\nA\n2\nB\nfoo")).toEqual([["cat"], ["foo"]])
    expect(bash("{ cat <<A\n1\nA\n}\nfoo")).toEqual([["cat"], ["foo"]])
    // The body starts at the next line, so the `}` is in it and the group stays open.
    expect(bash("{ cat <<A\n}\n1\nA\nfoo")).toBe("invalid-structure")
  })

  test("a backslash joins an unquoted delimiter's lines, and dash would not", () => {
    expect(bash("cat <<EOF\nE\\\nOF\nfoo")).toEqual([["cat"], ["foo"]])
    expect(bash("cat <<EOF\nE\\\nOF\nEOF")).toBe("heredoc")
    expect(bash("cat <<'EOF'\nE\\\nOF\nEOF")).toEqual([["cat"]])
    expect(bash("cat <<EOF\nE\\\\\nOF\nEOF")).toEqual([["cat"]])
  })

  test("an unended or ill-named delimiter is refused", () => {
    reasons(bash, {
      heredoc: ["cat <<EOF", "cat <<EOF\nbody", "cat <<'EOF'\n$(foo)", "$(cat <<EOF\n)"],
      "invalid-redirect": [
        "cat <<",
        "cat << #",
        "cat <<\n",
        "cat <<$\\\nEOF",
        'cat <<$"EOF"',
        "cat <<'EOF",
        "cat <<$'a\\'b'",
        "cat <<EOF\\",
      ],
    })
  })

  test("dash keeps the $ of $'…', so a body that ends that delimiter is refused", () => {
    expect(bash("cat <<$'E'\n$E\nE")).toBe("heredoc")
  })

  test("a binding builtin's body counts as a bound value", () => {
    expect(bash("read a <<'EOF'\n$(x)\nEOF\neval b")).toBe("dynamic-execution")
    expect(bash("cat <<'EOF'\n$(x)\nEOF\neval b")).toEqual([["cat"], ["eval", "b"]])
  })

  test("a construct read as one unit may not cross a pending body", () => {
    reasons(bash, {
      heredoc: ["cat <<A; (( 1\n))\nA", "cat <<A; [[ a\n]]\nA", "cat <<A; a=(b\nc)\nA"],
    })
  })
})

describe("a PowerShell command", () => {
  test("is its words, raw words, word ends and whether it heads a statement", () => {
    expect(psCommands("foo bar")).toEqual([
      { resource: "foo bar", words: ["foo", "bar"], rawWords: ["foo", "bar"], wordEnds: [3, 7], statementHead: true },
    ])
    expect(psCommands("  foo  bar  ")).toEqual([
      { resource: "foo  bar", words: ["foo", "bar"], rawWords: ["foo", "bar"], wordEnds: [3, 8], statementHead: true },
    ])
    expect(psCommands("a | b").map((command) => command.statementHead)).toEqual([true, undefined])
    expect(psCommands("a; b").map((command) => command.statementHead)).toEqual([true, true])
    expect(psCommands("a && b").map((command) => command.statementHead)).toEqual([true, undefined])
    expect(psCommands("a\nb").map((command) => command.statementHead)).toEqual([true, true])
    expect(psCommands("a & b").map((command) => command.statementHead)).toEqual([true, true])
  })

  test("a call operator is in the resource and its word ends count from it, heading no statement", () => {
    expect(psCommands("& foo bar")).toEqual([
      { resource: "& foo bar", words: ["foo", "bar"], rawWords: ["foo", "bar"], wordEnds: [5, 9] },
    ])
    expect(ps(". foo")).toEqual([["foo"]])
    expect(ps("& $x")).toEqual([["$x"]])
    expect(ps(".foo")).toEqual([[".foo"]])
    reasons(ps, {
      "invalid-structure": ["&", "& &", ".", "& ;"],
      "dynamic-command-name": ['& ""', "& ''"],
    })
  })

  test("quoting and escapes are decoded", () => {
    names(ps, [
      ["foo 'a''b'", [["foo", "a'b"]]],
      ['foo "a""b"', [["foo", 'a"b']]],
      ['foo "a`tb"', [["foo", "a\tb"]]],
      ["foo a`tb", [["foo", "a\tb"]]],
      ["foo a`qb", [["foo", "aqb"]]],
      ["foo `$a", [["foo", "$a"]]],
      ["foo `u{41}", [["foo", "A"]]],
      ["foo `0", [["foo", "\0"]]],
      ["foo `a`b`e`f`n`r`v", [["foo", "\x07\b\x1b\f\n\r\v"]]],
      ["foo a'b c'", [["foo", "ab c"]]],
      ["foo 'a'b", [["foo", "a", "b"]]],
    ])
    expect(psCommands("foo 'a b'")[0].rawWords).toEqual(["foo", "'a b'"])
  })

  test("a backtick at a line's end continues it", () => {
    expect(ps("foo `\n bar")).toEqual([["foo", "bar"]])
    expect(ps("foo `\r\n bar")).toEqual([["foo", "bar"]])
    expect(ps('foo "a`\nb"')).toEqual([["foo", "a\nb"]])
  })

  test("a line ends a command, unless a comma or a member operator awaits", () => {
    names(ps, [
      ["a\nb", [["a"], ["b"]]],
      ["a\r\nb", [["a"], ["b"]]],
      ["a\rb", [["a"], ["b"]]],
      ["\n\na", [["a"]]],
      ["foo a,\nb", [["foo", "a,", "b"]]],
      ["foo $a.# x\nb", [["foo", "$a.", "b"]]],
      ["foo $a.<#c#>\nb", [["foo", "$a.", "b"]]],
      ["foo $a.\nb", [["foo", "$a."], ["b"]]],
    ])
  })

  test("a list's commands come in order, a command's own before those nested in it", () => {
    names(ps, [
      ["a; b", [["a"], ["b"]]],
      ["a | b", [["a"], ["b"]]],
      ["a && b || c", [["a"], ["b"], ["c"]]],
      ["foo (bar)", [["foo", "(bar)"], ["bar"]]],
      ["foo $(bar)", [["foo", "$(bar)"], ["bar"]]],
      ["foo @(bar)", [["foo", "@(bar)"], ["bar"]]],
      ["foo {bar}", [["foo", "{bar}"], ["bar"]]],
      ['foo "a$(bar)b"', [["foo", "a$(bar)b"], ["bar"]]],
      ["(foo)", [["foo"]]],
      ["$(foo)", [["foo"]]],
      ["@(foo)", [["foo"]]],
      ["{foo}", [["foo"]]],
      ["@{a=foo}", [["foo"]]],
      ["@{a=1}", []],
      ["@{a=(foo)}", [["foo"]]],
      ["[x](foo)", [["foo"]]],
      ["foo $x[0]", [["foo", "$x[0]"]]],
      ["foo $x[(bar)]", [["foo", "$x[(bar)]"], ["bar"]]],
      ["foo a[0]", [["foo", "a[0]"]]],
      ['foo "${a}"', [["foo", "${a}"]]],
      ["foo ${a}", [["foo", "${a}"]]],
    ])
  })

  test("an expression is no command", () => {
    for (const input of [
      '"a"',
      "'a' b",
      "1",
      "1 + 2",
      "$x",
      "$x.y",
      "$x y",
      "${x}",
      "-not $x",
      "!$x",
      "--$x",
      "0x10",
      "1.5kb",
    ])
      expect({ input, got: ps(input) }).toEqual({ input, got: [] })
    expect(ps("a1")).toEqual([["a1"]])
    expect(ps("-foo")).toEqual([["-foo"]])
  })

  test("an assignment reads what it assigns", () => {
    names(ps, [
      ["$x = foo bar", [["foo", "bar"]]],
      ["$x += foo", [["foo"]]],
      ["$x -= foo", [["foo"]]],
      ["$x *= foo", [["foo"]]],
      ["$x /= foo", [["foo"]]],
      ["$x %= foo", [["foo"]]],
      ["[int]$x = foo", [["foo"]]],
      ["$x = 1", []],
      ["$x = (foo)", [["foo"]]],
      ["foo a=b", [["foo", "a=b"]]],
    ])
    expect(psCommands("$x = foo bar")[0].resource).toBe("foo bar")
  })

  test("a statement's keywords head clauses, whose blocks are read", () => {
    names(ps, [
      ["if (a) { b }", [["a"], ["b"]]],
      ["if (a) { b } elseif (c) { d } else { e }", [["a"], ["b"], ["c"], ["d"], ["e"]]],
      ["while (a) { b }", [["a"], ["b"]]],
      ["for ($i = 0; a; b) { c }", [["a"], ["b"], ["c"]]],
      ["foreach ($x in a) { b }", [["a"], ["b"]]],
      ["do { a } while (b)", [["a"], ["b"]]],
      ["do { a } until (b)", [["a"], ["b"]]],
      ["try { a } catch { b } finally { c }", [["a"], ["b"], ["c"]]],
      ["try { a } catch [X] { b }", [["a"], ["b"]]],
      ["switch (a) { b { c } }", [["a"], ["c"]]],
      ["function f { a }", [["a"]]],
      ["function f($x) { a }", [["a"]]],
      ["filter f { a }", [["a"]]],
      ["begin { a }", [["a"]]],
      ["trap { a }", [["a"]]],
      ["data { a }", [["a"]]],
      ["class C { }", []],
      ["enum E { A }", []],
      ["param($x)", []],
      ["param($x = (a))", [["a"]]],
      [":l while (a) { b }", [["a"], ["b"]]],
      ["using namespace a", []],
      ["break", []],
      ["continue l", []],
      ["return a b", [["a", "b"]]],
      ["throw a", [["a"]]],
      ["exit", []],
      ["return", []],
      ["else { a }", [["else", "{ a }"], ["a"]]],
      ["until (a)", [["until", "(a)"], ["a"]]],
      ["catch", [["catch"]]],
      ["foreach x", [["foreach", "x"]]],
      ["FOREACH ($x in a) { b }", [["a"], ["b"]]],
      ["IF (a) { b }", [["a"], ["b"]]],
      ["ifx", [["ifx"]]],
      ["echo if", [["echo", "if"]]],
    ])
    reasons(ps, { "invalid-structure": ["if", "if (a)", "while (a)", "do", "try", "function f"] })
  })

  test("--% stops parsing to the line's end, a pipe or &&", () => {
    names(ps, [
      ["foo --% a; b $c", [["foo", "--%", "a; b $c"]]],
      ["foo --% a | b", [["foo", "--%", "a"], ["b"]]],
      ["foo --% a && b", [["foo", "--%", "a"], ["b"]]],
      ["foo --% a\nb", [["foo", "--%", "a"], ["b"]]],
      ['foo --% "a | b" | c', [["foo", "--%", '"a | b"'], ["c"]]],
      ["foo --%", [["foo", "--%"]]],
      ["foo '--%' a; b", [["foo", "--%", "a"], ["b"]]],
      ["foo --`% a; b", [["foo", "--%", "a; b"]]],
      ["foo a, --`% b; c", [["foo", "a,", "--%", "b"], ["c"]]],
      ["foo -a: --`% b; c", [["foo", "-a:", "--%", "b"], ["c"]]],
      ["--% a", []],
    ])
  })

  test("comments", () => {
    names(ps, [
      ["foo # x\nbar", [["foo"], ["bar"]]],
      ["foo # x\r\nbar", [["foo"], ["bar"]]],
      ["foo # x\rbar", [["foo"], ["bar"]]],
      ["foo # x", [["foo"]]],
      ["foo a#b", [["foo", "a#b"]]],
      ["<# c #> foo", [["foo"]]],
      ["foo <# c #> bar", [["foo", "bar"]]],
      ["foo a<#b", [["foo", "a<#b"]]],
      ["# only", []],
      ["foo a, # x\nb", [["foo", "a,", "b"]]],
    ])
    expect(ps("foo <# x")).toBe("invalid-structure")
  })

  test("a redirection's target is no word", () => {
    names(ps, [
      ["foo > out", [["foo"]]],
      ["foo >> out", [["foo"]]],
      ["foo 2> out", [["foo"]]],
      ["foo *> out", [["foo"]]],
      ["foo 2>&1", [["foo"]]],
      ["foo *>&1", [["foo"]]],
      ["foo > out x", [["foo", "x"]]],
      ["foo 2", [["foo", "2"]]],
      ["foo *", [["foo", "*"]]],
    ])
    expect(psCommands("foo > out x")[0].resource).toBe("foo > out x")
    expect(psCommands("foo > out")[0].resource).toBe("foo > out")
    reasons(ps, {
      "invalid-redirect": ["> x", "foo > > x", "foo 7> x", "foo 1>&2", "foo 2>&2", "foo >&1", "2>&1"],
      "invalid-structure": ["foo >", "foo > ;"],
    })
  })

  test("here-strings", () => {
    names(ps, [
      ["foo @'\nabc\n'@", [["foo", "abc"]]],
      ["foo @'\r\nabc\r\n'@", [["foo", "abc"]]],
      ["foo @'\n'@", [["foo", ""]]],
      ["foo @'\n$(bar)\n'@", [["foo", "$(bar)"]]],
      ['foo @"\n$(bar)\n"@', [["foo", "$(bar)"], ["bar"]]],
      ['foo @"\n${a}\n"@', [["foo", "${a}"]]],
      ['foo @"\n`a\n"@', [["foo", "`a"]]],
      ["@'\nabc\n'@", []],
    ])
    reasons(ps, {
      "unterminated-quote": ["foo @'x", "foo @'\nabc", 'foo @"\nabc', 'foo @"\n`\n"@'],
      "unterminated-escape": ['foo @"\n`'],
      "invalid-structure": ['foo @"\n${', "foo @", "foo @ x"],
    })
  })
})

describe("what a PowerShell scan refuses", () => {
  test("text it cannot end, or that ends wrongly", () => {
    reasons(ps, {
      "unterminated-quote": ["foo 'a", 'foo "a'],
      "unterminated-escape": ["foo `", 'foo "`', "foo `u{110000}", "foo `u{"],
      "invalid-structure": [
        "foo )",
        "foo }",
        "foo (",
        "foo {",
        "(foo",
        'foo "$(a"',
        "a &&",
        "a ||",
        "a |",
        "| a",
        "&& a",
        "a; | b",
        "foo ${",
        "foo ${}",
        'foo "${',
        'foo "${}"',
        "$x[;]",
        "$x[a|b]",
      ],
      "dynamic-command-name": ["& ''"],
    })
  })

  test("characters whose tokens PowerShell reads differently from JavaScript", () => {
    for (const char of ["\0", "\u0085", "–", "—", "―", "‘", "„", "﻿"])
      expect(ps(`foo ${char}a`)).toBe("invalid-structure")
  })

  test("what is too long, or nested too deep, at the limits", () => {
    expect(ps("a".repeat(64 * 1024))).toEqual([["a".repeat(64 * 1024)]])
    expect(ps("a".repeat(64 * 1024 + 1))).toBe("invalid-structure")
    const nested = (depth: number) => `${"(".repeat(depth)}a${")".repeat(depth)}`
    expect(ps(nested(31))).toEqual([["a"]])
    expect(ps(nested(32))).toBe("invalid-structure")
  })
})

describe("how a POSIX-family builtin's operand is evaluated", () => {
  const dynamic = "dynamic-execution"
  const refused = (...inputs: string[]) => {
    for (const input of inputs) expect({ input, got: bash(input) }).toEqual({ input, got: dynamic })
  }
  const read = (...inputs: string[]) => {
    for (const input of inputs) expect({ input, got: Array.isArray(bash(input)) }).toEqual({ input, got: true })
  }

  test("set binds only with -A; its other words wait for a sink", () => {
    refused("set -A 'a[$(x)]'", "set +A 'a[$(x)]'", "set -eA 'a[$(x)]'", "set -A1 'a[$(x)]'")
    read("set 'a[$(x)]'", "set -e 'a[$(x)]'", "set A 'a[$(x)]'", "set x-A 'a[$(x)]'")
    refused("set '$(x)'; eval b")
  })

  test("a binding builtin's option that types its operand makes it arithmetic", () => {
    for (const flag of ["-E", "-F", "-i", "-n"]) refused(`declare ${flag} 'a[$(x)]'`)
    refused("declare -i '$(x)'", "export -x 'a[$(x)]'")
    read("declare -a x", "declare i", "declare x-i y", "read -r x")
    expect(bash("declare -i '$(x)'; let a")).toBe(dynamic)
  })

  test("a declaration's plain value is bound for later, unless bash re-parses it as an array's", () => {
    read(
      "declare a='x[$(y)]'",
      "typeset a='x[$(y)]'",
      "local a='x[$(y)]'",
      "export a='$(y)[1]'",
      "readonly a='$(y)[1]'",
    )
    refused("declare a='$(y)[1]'", "typeset a='$(y)[1]'", "local a='`y`[1]'", "declare a+='$(y)[1]'")
    refused("declare -x a='x[$(y)]'", "export -x a='$(y)[1]'", "readonly -x a='$(y)[1]'")
    read("declare x-y a='x[$(y)]'")
    expect(bash("declare a='$(y)[1]'", "zsh")).toEqual([["declare", "a=$(y)[1]"]])
    expect(bash("declare a='$(y)[1]'", "posix")).toBe(dynamic)
    expect(bash("declare 'a[$(y)]'")).toBe(dynamic)
  })

  test("printf and print bind with -v, print's among other letters", () => {
    refused(
      "printf -v 'x[$(y)]' a",
      "printf a -v 'x[$(y)]'",
      "print -v 'x[$(y)]'",
      "print -nv 'x[$(y)]'",
      "print -v'x[$(y)]'",
    )
    read("printf -nv 'x[$(y)]'", "printf x-v 'y[$(z)]'", "print x-v 'y[$(z)]'", "print 'x[$(y)]'")
    refused("printf -v'x[$(y)]'")
  })

  test("wait binds with -p, or a word holding it", () => {
    refused("wait -p 'a[$(x)]'", "wait -np 'a[$(x)]'", "wait -fnp 'a[$(x)]'", "wait '-p a[$(x)]'")
    read("wait -n 'a[$(x)]'", "wait x-p 'a[$(y)]'")
  })

  test("test's -t is arithmetic only outside bash; its -v names a variable in all", () => {
    for (const name of ["test", "["]) {
      const close = name === "[" ? " ]" : ""
      expect(Array.isArray(bash(`${name} -t 'a[$(x)]'${close}`, "bash"))).toBe(true)
      expect(bash(`${name} -t 'a[$(x)]'${close}`, "zsh")).toBe(dynamic)
      expect(bash(`${name} -t 'a[$(x)]'${close}`, "posix")).toBe(dynamic)
      expect(Array.isArray(bash(`${name} -n -t${close}`, "zsh"))).toBe(true)
      expect(Array.isArray(bash(`${name} a 'a[$(x)]'${close}`, "zsh"))).toBe(true)
    }
    expect(bash("test -t 'a'", "zsh")).toEqual([["test", "-t", "a"]])
  })

  test("a precommand's options are stepped over; exec's -a takes a name, zsh's - ends them", () => {
    for (const input of [
      "exec -a x let 'a[$(y)]'",
      "exec -cla x let 'a[$(y)]'",
      "exec -c let 'a[$(y)]'",
      "- let 'a[$(y)]'",
      "nocorrect let 'a[$(y)]'",
    ]) {
      expect({ input, got: bash(input, "zsh") }).toEqual({ input, got: dynamic })
      expect({ input, got: Array.isArray(bash(input, "bash")) }).toEqual({ input, got: true })
    }
    expect(Array.isArray(bash("exec -x-a let 'a[$(y)]'", "zsh"))).toBe(false)
    expect(Array.isArray(bash("- -x 'a[$(y)]'", "zsh"))).toBe(true)
    refused("command let 'a[$(y)]'", "coproc let 'a[$(y)]'")
  })

  test("[[ ]]'s other tests, patterns and groups", () => {
    refused(
      "[[ 1 -ne 'a[$(x)]' ]]",
      "[[ 1 -le 'a[$(x)]' ]]",
      "[[ 1 -gt 'a[$(x)]' ]]",
      "[[ 1 -ge 'a[$(x)]' ]]",
      "[[ 'a[$(x)]' -eq 1 && b ]]",
    )
    read(
      "[[ -v a ]]",
      "[[ a\\\nb ]]",
      "[[ a == (b c) ]]",
      "[[ a != (b) ]]",
      "[[ a = (b) ]]",
      "[[ a =~ (b) ]]",
      "[[ ((a)) ]]",
      "[[ a < b ]]",
      "[[ a || b ]]",
      "[[ !a ]]",
      "[[ a#b ]]",
      "[[ a\tb\nc ]]",
    )
    expect(bash("[[ a ]] b")).toBe("invalid-structure")
    expect(bash("[[ ]]x ]]")).toEqual([])
    expect(bash("[[ a ]\\\n]")).toBe("invalid-structure")
    expect(bash("[[ a == ) ]]")).toBe("invalid-structure")
    expect(bash("[[ a < ) ]]")).toBe("invalid-structure")
    expect(bash("[[ $(b) == (c) ]]")).toEqual([["b"]])
    expect(bash("[[ -n a ]] && [[ b ]]")).toEqual([])
    expect(bash("[[ # x\n ]]")).toEqual([])
    expect(bash("[[ a #\n ]]")).toEqual([])
  })

  test("a sink read inside a parameter, a bound value's escape, and an unbound $", () => {
    refused("a='\\x41'; a='('; eval b", "a='$'; a='{'; eval b", "a='`'; eval b")
    read("a='\\x41'", "a='$'; eval b", "a='('; eval b")
    refused("a='$(x)'; ${!b}", "a='$(x)'; echo ${PS4}", "a='$(x)'; echo ${PS4:-c}", "PS4='$(x)'", "a='$(x)'; set PS4")
    refused("echo ${!'a[$(x)]'}", "echo ${!\\\n'a[$(x)]'}")
    read("echo ${!a}", "echo ${!a[1]}")
  })

  test("a parameter's name decides what it may hold", () => {
    // NULLCMD anywhere in a word is refused, a wider net than the name's.
    expect(bash("echo ${aNULLCMD}", "zsh")).toBe(dynamic)
    expect(bash("echo aNULLCMDb", "zsh")).toBe(dynamic)
    expect(bash("echo aNULLCMDb", "bash")).toEqual([["echo", "aNULLCMDb"]])
    expect(bash("echo ${xfunctions[a]}", "zsh")).toEqual([["echo", "${xfunctions[a]}"]])
    expect(bash("echo ${functionsx[a]}", "zsh")).toEqual([["echo", "${functionsx[a]}"]])
    for (const input of [
      "echo ${functions=a}",
      "echo ${functions:-a}",
      "echo ${READNULLCMD}",
      "echo ${options[a]}",
      "echo ${commands[a]}",
    ])
      expect({ input, got: bash(input, "zsh") }).toEqual({ input, got: dynamic })
    expect(bash("echo ${functions-a}", "zsh")).toEqual([["echo", "${functions-a}"]])
    expect(bash("echo ${functions\\\n[a]}", "zsh")).toBe(dynamic)
  })

  test("a parameter's offset follows its name, a nested one or a subscript counting", () => {
    expect(bash("echo ${a[1]:'$(b)'}")).toBe(dynamic)
    expect(bash("echo ${${a}:'$(b)'}")).toBe(dynamic)
    expect(bash("echo ${a:-'$(b)'}")).toEqual([["echo", "${a:-'$(b)'}"]])
    expect(bash("echo ${a:+'$(b)'}")).toEqual([["echo", "${a:+'$(b)'}"]])
    expect(bash("echo ${a:?'$(b)'}")).toEqual([["echo", "${a:?'$(b)'}"]])
    expect(bash("echo ${a='$(b)'}; eval c")).toBe(dynamic)
    expect(bash("echo ${1:'$(b)'}")).toBe(dynamic)
    expect(bash("echo ${#a}")).toEqual([["echo", "${#a}"]])
    expect(bash("echo \"${a:'$(b)'}\"")).toEqual([["echo", "${a:'$(b)'}"], ["b"]])
  })

  test("a double-quoted parameter's quotes and $'…'", () => {
    expect(bash("echo \"${a:-$'b'}\"")).toEqual([["echo", "${a:-$'b'}"]])
    expect(bash('echo "${a:-$\'b}"')).toBe("unterminated-quote")
    expect(bash("echo \"${a:-'b'}\"")).toEqual([["echo", "${a:-'b'}"]])
    expect(bash('echo "${a:-"b"}"')).toEqual([["echo", '${a:-"b"}']])
    expect(bash('echo "${a:-$(b)}"')).toEqual([["echo", "${a:-$(b)}"], ["b"]])
    expect(bash("echo \"${a:-'}'}\"")).toBe("invalid-structure")
    expect(bash("echo \"${a:-'['}\"")).toBe("invalid-structure")
  })
})

describe("the POSIX-family edges of a word", () => {
  test("a continuation inside a construct is dropped, in a backtick too", () => {
    names(bash, [
      ["echo `a\\\nb`", [["echo", "`a\\\nb`"], ["ab"]]],
      ["a=(b\\\nc)", []],
      ["echo `\\$a`", [["echo", "`\\$a`"], ["$a"]]],
      ["echo `\\\\a`", [["echo", "`\\\\a`"], ["a"]]],
      ["echo `a\\b`", [["echo", "`a\\b`"], ["ab"]]],
      ['echo "`\\"a\\"`"', [["echo", '`\\"a\\"`'], ["a"]]],
      ['echo `\\"a\\"`', [["echo", '`\\"a\\"`'], ['"a"']]],
      ['echo "a\\b\\$c\\`d\\"e\\\\f"', [["echo", 'a\\b$c`d"e\\f']]],
      ['echo "a\\\nb"', [["echo", "ab"]]],
      ["echo a\\\tb", [["echo", "a\tb"]]],
      ["\techo\ta", [["echo", "a"]]],
    ])
  })

  test("what a substitution's words leave behind counts as its output", () => {
    expect(bash("let a[$(echo '$(x)')]")).toBe("dynamic-execution")
    expect(bash("read 'a[1]'$(echo '$(x)')")).toBe("dynamic-execution")
    expect(bash("echo $(echo '$(x)')")).toEqual([
      ["echo", "$(echo '$(x)')"],
      ["echo", "$(x)"],
    ])
  })

  test("a subscript in an assignment has no blanks to dash and bash alike", () => {
    expect(bash("a[1 2]=b", "bash")).toBe("invalid-structure")
    expect(bash("a[1;2]=b", "bash")).toBe("invalid-structure")
    expect(bash("a[$'1']=b", "bash")).toEqual([])
    expect(bash("a[$'(']=b", "bash")).toBe("invalid-structure")
    expect(bash("a['1']=b", "bash")).toEqual([])
    expect(bash('a["1"]=b', "bash")).toEqual([])
    expect(bash("a[1]+=b", "bash")).toEqual([])
    expect(bash("a[1]\\\n=b", "bash")).toBe("invalid-structure")
    expect(bash("a[1]x=b", "bash")).toEqual([["a[1]x=b"]])
    expect(bash("a[1]", "bash")).toEqual([["a[1]"]])
    expect(bash("'a'[1]=b", "bash")).toEqual([["a[1]=b"]])
    expect(bash("foo a[1]=b", "bash")).toEqual([["foo", "a[1]=b"]])
    expect(bash("a[$(b)]=c d", "bash")).toEqual([["d"], ["b"]])
  })

  test("an arithmetic base, $#, and quotes in arithmetic", () => {
    names(bash, [
      ["(( 16#ff ))", []],
      ["(( $# ))", []],
      ["(( 'a' ))", []],
      ['(( "a" ))', []],
      ["(( $'a' ))", []],
      ["echo $(( (1) ))", [["echo", "$(( (1) ))"]]],
      ["(( a[1] ))", []],
    ])
    reasons(bash, {
      "invalid-structure": [
        "(( # ))",
        "(( a; ))",
        "(( } ))",
        "(( '(' ))",
        '(( "(" ))',
        "(( $'(' ))",
        "(( $'\\'' ))",
        "(( $'\\0' ))",
        "(( 1 ",
      ],
    })
    expect(bash("for ((a;b;c)) do d; done")).toEqual([["d"]])
    expect(bash("for ((a;b;c));\ndo d; done")).toEqual([["d"]])
    expect(bash("for ((#;;)); do d; done")).toBe("invalid-structure")
    expect(bash("for x y ((a)); do d; done")).toBe("compound-command")
    expect(bash("for ((a)x; do d; done")).toBe("invalid-structure")
  })

  test("((…)) under dash is two subshells, or refused where the readings part", () => {
    expect(bash("((a) b)", "posix")).toBe("invalid-structure")
    expect(bash("(( a ) )", "posix")).toEqual([["a"]])
    expect(bash("(( a; ))", "posix")).toBe("invalid-structure")
    expect(bash("(( 1 + 1 ))", "posix")).toEqual([["1", "+", "1"]])
    // A reading both give is listed once.
    expect(bash("(( a )); (( a ))", "posix")).toEqual([["a"]])
    expect(bash("(( $(a) )) b", "posix")).toBe("invalid-structure")
  })

  test("a word-final glob character opens a bash pattern, and only there", () => {
    expect(bash("echo ?(a)", "bash")).toEqual([["echo", "?(a)"]])
    expect(bash("echo *(a)", "bash")).toEqual([["echo", "*(a)"]])
    expect(bash("echo +(a)", "bash")).toEqual([["echo", "+(a)"]])
    expect(bash("echo !(a)", "bash")).toEqual([["echo", "!(a)"]])
    expect(bash("echo ?a(b)", "bash")).toBe("dynamic-execution")
    expect(bash("echo @(a(b))", "bash")).toEqual([["echo", "@(a(b))"]])
    expect(bash("echo @(a[1])", "bash")).toEqual([["echo", "@(a[1])"]])
    expect(bash("echo @(a\nb)", "bash")).toBe("command-substitution")
    expect(bash("echo @(a&b)", "bash")).toBe("command-substitution")
    expect(bash("echo @(a b)", "bash")).toEqual([["echo", "@(a b)"]])
  })

  test("an array's elements, comments and nested =()", () => {
    names(bash, [
      ["a=(b\tc)", []],
      ["a=(b#c)", []],
      ["a=(# c\nb)", []],
      ["a=([$(b)]=c)", [["b"]]],
      ["a=(`b`)", [["b"]]],
      ["a+=(b)", []],
      ["a=() b", [["b"]]],
      ["a=(b); c", [["c"]]],
      ["a=(b)>c", []],
      ["a=(b)|c", [["c"]]],
      ["declare a=($(b))", [["declare", "a=($(b))"], ["b"]]],
      ["local a=(=(b))", [["local", "a=(=(b))"], ["b"]]],
    ])
    expect(bash("foo a=(b)")).toBe("dynamic-execution")
    expect(bash("a==(b)")).toEqual([["b"]])
    expect(bash("a=(b\n", "bash")).toBe("command-substitution")
  })

  test("a function's head reads its name, blanks and comments before the body", () => {
    names(bash, [
      ["f.a-b() { c; }", [["c"]]],
      ["function f\n{ c; }", [["c"]]],
      ["f() # x\n{ c; }", [["c"]]],
      ["f()\n( c )", [["c"]]],
      ["f() if a; then b; fi", [["a"], ["b"]]],
      ["f() [[ a ]]", []],
      ["function\tf { c; }", [["c"]]],
    ])
    expect(bash("function { c; }")).toBe("invalid-structure")
    expect(bash("( ) { c; }")).toEqual([["c"]])
  })

  test("a redirection after a case word, a group or a list", () => {
    expect(bash("if a; then b; fi; c")).toEqual([["a"], ["b"], ["c"]])
    expect(bash("fi > x")).toBe("compound-command")
    expect(bash("a > x fi")).toEqual([["a", "fi"]])
    expect(bash("a; > x")).toEqual([["a"]])
    expect(bash("a > x;;")).toBe("invalid-structure")
    expect(bash("a | > x")).toEqual([["a"]])
    expect(bash("a && > x b")).toEqual([["a"], ["b"]])
    expect(commands("a && b c > x d")[1]).toEqual({
      resource: "b c",
      words: ["b", "c", "d"],
      rawWords: ["b", "c", "d"],
      redirectWordCount: 2,
    })
    expect(bash("foo 2\\\n> x")).toEqual([["foo"]])
    expect(commands("foo 2\\\n> x")[0].resource).toBe("foo 2\\\n> x")
  })

  test("a case's patterns, separators and bodies", () => {
    names(bash, [
      ["case x in a|b) c;; (d|e) f;; esac", [["c"], ["f"]]],
      ["case x in a) ;; esac", []],
      ["case x in a) b;& c) d;| e) f;;& esac", [["b"], ["d"], ["f"]]],
      ["case x in\n\na)\nb\n;;\n\nesac", [["b"]]],
      ["case x in a) b && c | d;; esac", [["b"], ["c"], ["d"]]],
      ["case x\nin a) b;; esac", [["b"]]],
      ["case x in $(a)) b;; esac", [["a"], ["b"]]],
      ["case x in a) if b; then c; fi;; esac", [["b"], ["c"]]],
      ["case x in a) case y in b) c;; esac;; esac", [["c"]]],
    ])
    reasons(bash, {
      "compound-command": [
        "case x in a; b) c;; esac",
        "case x in a\nb) c;; esac",
        "case x in a && b) c;; esac",
        "case x in a) b;; c",
      ],
    })
    expect(bash("case x in a) b;; esac c")).toBe("invalid-structure")
    expect(bash("case x in esac y")).toBe("invalid-structure")
  })

  test("a for's header ends at do, ;, or a newline, and nothing else", () => {
    names(bash, [
      ["for x in a\ndo b; done", [["b"]]],
      ["for x in a # c\ndo b; done", [["b"]]],
      ["for x in; do b; done", [["b"]]],
      ["for x; # c\n do b; done", [["b"]]],
      ["for x\n\ndo b\ndone", [["b"]]],
      ["for x in a; { b; }", [["b"]]],
      ["for x (a)\ndo b; done", [["b"]]],
      ["for x (a) # c\ndo b; done", [["b"]]],
      ["for x (a) { b; }", [["b"]]],
      ["for x (a); do b; done", [["b"]]],
    ])
    reasons(bash, {
      "compound-command": [
        "for x in a & b; do c; done",
        "for x in a && b; do c; done",
        "for\ndo a; done",
        "for x y do a; done",
        "for x > y do a; done",
        "for x in a; {b; }",
      ],
    })
  })

  test("repeat ends its header at its word, and takes do or a single command", () => {
    const zsh = (input: string) => bash(input, "zsh")
    names(zsh, [
      ["repeat 3; do a; done", [["a"]]],
      ["repeat 3\ndo a; done", [["a"]]],
      ["repeat 3 # c\ndo a; done", [["a"]]],
      ["repeat 3 a; b", [["a"], ["b"]]],
      ["repeat 3; a", [["a"]]],
    ])
    expect(zsh("repeat")).toBe("compound-command")
    expect(zsh("repeat 3 > x do a; done")).toBe("compound-command")
    expect(zsh("repeat | a")).toBe("compound-command")
    expect(zsh("repeat 3 | a")).toBe("invalid-structure")
    expect(zsh("repeat 'a[$(x)]' b")).toBe("dynamic-execution")
    expect(zsh("repeat a b")).toEqual([["b"]])
  })

  test("a keyword's place: then, do, done and fi after an operator or nothing", () => {
    reasons(bash, {
      "compound-command": [
        "if a; then b; fi; then",
        "if a && then b; fi",
        "while a && do b; done",
        "for x in a; do b && done",
        "if a; then b && fi",
        "if a; then b; else c && fi",
        "if a; else b; fi",
        "if a; then b; elif c; else d; fi",
        "while a; else b; done",
        "for x; do a; else b; done",
        "case x in a) b;; esac; fi",
      ],
    })
    expect(bash("a && if b; then c; fi && d")).toEqual([["a"], ["b"], ["c"], ["d"]])
    expect(bash("if a\nthen\nb\nelse\nc\nfi")).toEqual([["a"], ["b"], ["c"]])
    expect(bash("while a\ndo\nb\ndone")).toEqual([["a"], ["b"]])
    expect(bash("_if a")).toEqual([["_if", "a"]])
    expect(bash("Zf a")).toEqual([["Zf", "a"]])
    expect(bash("if\\\n a; then b; fi")).toEqual([["a"], ["b"]])
    expect(bash("in a")).toEqual([["in", "a"]])
  })

  test("a heredoc's delimiter and body, in full", () => {
    names(bash, [
      ["cat << EOF\nEOF", [["cat"]]],
      ["cat <<\tEOF\nEOF", [["cat"]]],
      ["cat <<E\\OF\nEOF", [["cat"]]],
      ['cat <<"E\\$F"\nE$F', [["cat"]]],
      ['cat <<"E\\xF"\nE\\xF', [["cat"]]],
      ["cat <<'E\\F'\nE\\F", [["cat"]]],
      ["cat <<$'E\\tF'\nE\tF", [["cat"]]],
      ["cat <<E\\\nOF\nEOF", [["cat"]]],
      ["cat <<EOF;\nEOF", [["cat"]]],
      ["cat <<EOF|foo\nEOF", [["cat"], ["foo"]]],
      ["cat <<-EOF\n\t\tEOF", [["cat"]]],
      ["cat <<EOF\n`a`\nEOF", [["cat"], ["a"]]],
      ["cat <<EOF\n${a:-$(b)}\nEOF", [["cat"], ["b"]]],
    ])
    expect(commands("cat <<EOF\n  \nEOF  ".trimEnd())[0].resource).toBe("cat <<EOF\n  \nEOF")
    expect(commands("  cat <<EOF\nEOF")[0].resource).toBe("cat <<EOF\nEOF")
    reasons(bash, {
      heredoc: ["cat <<EOF\nEOFx", "cat <<EOF\n EOF", "cat <<$'E'\n$E", "cat <<'EOF'\nE\\\nOF"],
    })
    expect(bash("cat <<EOF\nE\\\\\nEOF")).toEqual([["cat"]])
    expect(bash("cat <<a\\\\\nb\na\\\nb")).toEqual([["cat"], ["b"]])
  })

  // Dash's two readings of `((` add a scan at each level. No input we found reaches the budget on this side: the depth
  // and the length limits bound the work first, so the budget's guards here are a net these cases cannot show.
  test("the depth stops what nests, sooner where dash's reading counts twice", () => {
    const nested = (depth: number) => `${"((".repeat(depth)}a${"))".repeat(depth)}`
    expect(bash(nested(16), "posix")).toEqual([["a"]])
    expect(bash(nested(17), "posix")).toBe("invalid-structure")
    expect(bash(nested(16), "bash")).toEqual([])
    expect(bash(nested(18), "bash")).toBe("invalid-structure")
  })
})

// Whether a word can be indexed: inside an indexable word's `[` is a list, where `;` is refused. Elsewhere `[` is a
// character, and the `;` ends the command. Fifteen rules of the scanner have this as their only visible effect.
describe("what PowerShell can index", () => {
  const indexed = (prefix: string) => ps(`foo ${prefix}[a;b]`)

  test("a variable, a string, a block's result and their members", () => {
    for (const prefix of [
      "$a",
      "$a.b",
      "$a.b.c",
      "$a::b",
      "$a.b1",
      "$a_b",
      "$a?",
      "$:a",
      '"a"',
      "'a'",
      '"a".b',
      "'a'::b",
      '"a"?.b',
      '"a"?[0]',
      "${a}",
      "${a}.b",
      "$(a).b",
      "(a).b",
      "(a)::b",
      "(a)?.b",
      "(a)[0]",
      "(a)[0].b",
      '$a."b"',
      "$a.'b'",
      '$a.b."c"',
      "$a.${b}",
      "$a.$b",
      '"a"?.',
      "$a.b?.c",
    ])
      expect({ prefix, got: indexed(prefix) }).toEqual({ prefix, got: "invalid-structure" })
  })

  test("a bare word, or a variable a character or a space has ended", () => {
    const words = (prefix: string, tail = "[a") => [["foo", `${prefix}${tail}`], ["b]"]]
    for (const prefix of [
      "a",
      "a.b",
      "a::b",
      "-a",
      "$",
      "$-",
      "$a-",
      "$a+",
      "$a,b",
      "$a..b",
      "$a.b..c",
      "${a}x",
      "${a}..b",
      "$a.b-",
      "$a.b:c",
    ])
      expect({ prefix, got: indexed(prefix) }).toEqual({ prefix, got: words(prefix) })
    expect(ps("foo $a [b;c]")).toEqual([["foo", "$a", "[b"], ["c]"]])
    expect(ps("foo a`qb[c;d]")).toEqual([["foo", "aqb[c"], ["d]"]])
    expect(ps("foo x'a'[c;d]")).toEqual([["foo", "xa[c"], ["d]"]])
    expect(ps('foo $a."b"x[c;d]')).toEqual([["foo", "$a.b", "x[c"], ["d]"]])
    // A string ends its word, and past a started `${a}` only `.` is a member.
    for (const rest of ["..b", "x", ".-", ":b", "?b"])
      expect(ps(`foo "a"${rest}[c;d]`)).toEqual([["foo", "a", `${rest}[c`], ["d]"]])
    for (const prefix of ["${a}::b", "${a}?.b"]) expect(indexed(prefix)).toEqual(words(prefix))
  })

  test("a member operator at a comment or a line's end continues the word", () => {
    names(ps, [
      ["foo $a.b.# x\n[c]", [["foo", "$a.b.", "[c]"]]],
      ["foo $a.<# x #>\nb", [["foo", "$a.", "b"]]],
      ["foo $a.<# x #>b", [["foo", "$a.", "b"]]],
      ["foo $a::<# x #>\nb", [["foo", "$a::", "b"]]],
      ["foo a. # x\nb", [["foo", "a."], ["b"]]],
      ["foo $a. # x\nb", [["foo", "$a."], ["b"]]],
      ["foo $a<# x #>\nb", [["foo", "$a<#", "x"], ["b"]]],
    ])
  })

  test("inside a type's brackets a # is a character, and an indexable's list has no separators", () => {
    names(ps, [
      ["[a#b]$c", []],
      ["[a.b#c+d]$e = f", [["f"]]],
      ["[a#b#c]", []],
    ])
    expect(ps("[-#]")).toBe("invalid-structure")
    for (const separator of [";", "|", "||", "&&", "&"]) expect(ps(`$a[b${separator}c]`)).toBe("invalid-structure")
    expect(ps("$a[b\nc]")).toEqual([])
    expect(ps("$a[b]")).toEqual([])
    expect(ps("$a[(b)]")).toEqual([["b"]])
    expect(ps("[a]::b")).toEqual([])
    expect(ps("[a]::b((c))")).toEqual([["c"]])
    expect(ps("$a[b](c)")).toEqual([["c"]])
  })
})

describe("the PowerShell edges of a word", () => {
  test("an expression's first word ends at a redirection, and an assignment's clears it", () => {
    names(ps, [
      ["$a>b", []],
      ["$a *>b", []],
      ["$a*>b", []],
      ["$a*b", []],
      ["1>b", []],
      ["$a = b > c", [["b"]]],
      ["$a = $b = c", [["c"]]],
      ["$a.b = c", [["c"]]],
      ["$a[0] = c", [["c"]]],
      ["[a]$b = c", [["c"]]],
      ["$a=b", [["b"]]],
      ["$a+=b", [["b"]]],
      ["foreach ($a in b) { c }", [["b"], ["c"]]],
      ["foreach ($a in$b) { c }", [["c"]]],
      ["(a in b)", [["a", "in", "b"]]],
      ["($a in b)", [["b"]]],
      ["($a inx b)", []],
    ])
  })

  test("a keyword's case and following character decide if it is one", () => {
    names(ps, [
      ["if(a){b}", [["a"], ["b"]]],
      ["While(a){b}", [["a"], ["b"]]],
      ["foreach($a in b){c}", [["b"], ["c"]]],
      ["foreach ($a in b) {c}", [["b"], ["c"]]],
      ["foreach\n($a in b) {c}", [["b"], ["c"]]],
      ["param\n($a)", []],
      ["[a()]param($b)", []],
      ["[a()]class B { }", []],
      ["[a()]enum B { }", []],
      ["[a()]foo", []],
      ["[a]if", []],
      ["iffy", [["iffy"]]],
      ["if-x", [["if-x"]]],
      ["Return a", [["a"]]],
      ["throwx a", [["throwx", "a"]]],
      ["exit;a", [["a"]]],
      ["do { a } while (b); c", [["a"], ["b"], ["c"]]],
      ["do { a }\nwhile (b)", [["a"], ["b"]]],
      ["do { a } b", [["a"], ["b"]]],
      ["while (a) { b } c", [["a"], ["b"], ["c"]]],
      ["try { a } b", [["a"], ["b"]]],
      ["try { a } catch { b } catch { c }", [["a"], ["b"], ["c"]]],
      ["if (a) { b } c", [["a"], ["b"], ["c"]]],
      ["if (a) { b }; else { c }", [["a"], ["b"], ["else", "{ c }"], ["c"]]],
      ["switch -x (a) { }", [["a"]]],
      ["switch (a) { $b { c } }", [["a"], ["c"]]],
      ["switch (a) { 1 { c } default { d } }", [["a"], ["c"], ["d"]]],
      ["function f { param($x) a }", [["a"]]],
      ["class C { [int]$x = (a) ; b() { c } }", [["a"], ["c"]]],
      ["enum E { A = (a) }", [["a"]]],
      ["using module a", []],
      ["break;a", [["a"]]],
      // The line after them is still in their clause, so it is not read. An unconditional jump never reaches it.
      ["continue\na", []],
      ["break\na", []],
      [":l", [[":l"]]],
      [":l foo", [[":l", "foo"]]],
      [":l do { a } while (b)", [["a"], ["b"]]],
      [":1 while (a) { }", [[":1", "while", "(a)", "{ }"], ["a"]]],
    ])
    reasons(ps, { "invalid-structure": ["if (a) b", "return|a"] })
    expect(ps("using")).toEqual([])
  })

  test("a blocked clause must be filled, and refuses a redirection", () => {
    reasons(ps, {
      "invalid-redirect": ["if > a", "try > a", "$x > > y", "(a > > b)", "foo >> > x"],
      "invalid-structure": ["if (a) b;", "do;", "try;", "if\n;", "function f;"],
    })
    expect(ps("using a > b")).toEqual([])
    expect(ps("foo\n> x")).toBe("invalid-redirect")
  })

  test("a redirection's form, its end, and a number that is only a word", () => {
    names(ps, [
      ["foo 2>> x", [["foo"]]],
      ["foo 3> x", [["foo"]]],
      ["foo 6> x", [["foo"]]],
      ["foo 3>&1", [["foo"]]],
      ["foo 6>&1", [["foo"]]],
      ["foo 2>&1 x", [["foo", "x"]]],
      ["foo 12", [["foo", "12"]]],
      ["foo 1x", [["foo", "1x"]]],
      ["foo *x", [["foo", "*x"]]],
      ["foo a>b", [["foo", "a>b"]]],
    ])
    expect(psCommands("foo >> out")[0].resource).toBe("foo >> out")
    expect(psCommands("foo 2>&1")[0].resource).toBe("foo 2>&1")
    expect(psCommands("foo 2>&1 ")[0].resource).toBe("foo 2>&1")
    expect(psCommands("foo  ;")[0].resource).toBe("foo")
    reasons(ps, {
      "invalid-redirect": [
        "foo 0> x",
        "foo 12> x",
        "foo 7>&1",
        "foo 2>&",
        "foo 2>&10",
        "foo >>> x",
        "2>&1 foo",
        "foo *>>&1",
      ],
    })
    expect(ps("1>&2")).toBe("invalid-redirect")
    expect(ps("foo\n2>&1")).toBe("invalid-redirect")
  })

  test("an at sign's forms, and a string's, in a word", () => {
    names(ps, [
      ["foo @a", [["foo", "@a"]]],
      ["foo @_", [["foo", "@_"]]],
      ["foo @1", [["foo", "@1"]]],
      ["foo @?", [["foo", "@?"]]],
      ["foo a@", [["foo", "a@"]]],
      ["foo a@(b)", [["foo", "a@", "(b)"], ["b"]]],
      ["foo a,@(b)", [["foo", "a,", "@(b)"], ["b"]]],
      ["foo a,'b'", [["foo", "a,b"]]],
      ["foo a,@'\nb\n'@", [["foo", "a,", "b"]]],
      ["foo a,${b}", [["foo", "a,${b}"]]],
      ["foo a{b}", [["foo", "a", "{b}"], ["b"]]],
      ["foo a(b)", [["foo", "a", "(b)"], ["b"]]],
      ["foo $a(b)", [["foo", "$a", "(b)"], ["b"]]],
      ['foo "a"b', [["foo", "a", "b"]]],
      ['foo "a""b" c', [["foo", 'a"b', "c"]]],
      ['foo a"b"', [["foo", "ab"]]],
      ['foo a"b""c"', [["foo", 'ab"c']]],
      ["foo --%a", [["foo", "--%a"]]],
    ])
    reasons(ps, { "invalid-structure": ["foo @ a", "foo @;", "foo @-"] })
    expect(ps("foo @'x\n'@")).toBe("unterminated-quote")
    expect(ps("@'\n$(a)\n'@ b")).toEqual([])
  })

  test("a here-string's line ends, escapes and nested quotes", () => {
    names(ps, [
      ["foo @'  \nb\n'@", [["foo", "b"]]],
      ["foo @'\n'x\n'@", [["foo", "'x"]]],
      ["foo @'\nb\r'@", [["foo", "b"]]],
      ["foo @'\na\n\n'@", [["foo", "a\n"]]],
      [
        'foo @"\n$(a "b")\n"@',
        [
          ["foo", '$(a "b")'],
          ["a", "b"],
        ],
      ],
      ['foo @"\n`"@\n"@', [["foo", '`"@']]],
      ['foo @"\n${a}"@\n"@', [["foo", '${a}"@']]],
      ['foo @"\n$(a)"@\n"@', [["foo", '$(a)"@'], ["a"]]],
    ])
    expect(psCommands("foo @'\nb\n'@ c")[0].rawWords).toEqual(["foo", "@'\nb\n'@", "c"])
    reasons(ps, { "invalid-structure": ['foo @"\n$(\n"@', 'foo @"\n$(;|)\n"@'] })
  })

  test("a string's $( may hold quotes of its own, and a backtick or a doubled quote before one", () => {
    names(ps, [
      [
        'foo "$(a "b")"',
        [
          ["foo", '$(a "b")'],
          ["a", "b"],
        ],
      ],
      [
        'foo "$(a `"b`")"',
        [
          ["foo", '$(a `"b`")'],
          ["a", "b"],
        ],
      ],
      [
        'foo "$(a ""b"")"',
        [
          ["foo", '$(a ""b"")'],
          ["a", "b"],
        ],
      ],
      ['foo "$(a (b))"', [["foo", "$(a (b))"], ["a", "(b)"], ["b"]]],
      ['foo "${a}$(b)"', [["foo", "${a}$(b)"], ["b"]]],
      ['foo "${a`}}"', [["foo", "${a`}}"]]],
      ['foo "a$b"', [["foo", "a$b"]]],
      ['foo "$"', [["foo", "$"]]],
    ])
    reasons(ps, {
      "invalid-structure": ['foo "${a', 'foo "$(', 'foo "$(a', 'foo "${a`', "foo ${a`"],
    })
  })

  test("backticks at a token's edge are trivia; inside a word they are text", () => {
    names(ps, [
      ["foo a`\nb", [["foo", "a\nb"]]],
      ["foo a `\nb", [["foo", "a", "b"]]],
      ["foo `\n`\nb", [["foo", "b"]]],
      ["foo `\r\nb", [["foo", "b"]]],
      ["foo `\rb", [["foo", "b"]]],
      ["foo a, `\nb", [["foo", "a,", "b"]]],
      ["foo a,`\nb", [["foo", "a,", "b"]]],
      ["$a`\nb", []],
      ["$a `\nb", []],
      ["foo `u{1F600}", [["foo", "\u{1F600}"]]],
      ["foo `u{10FFFF}", [["foo", "\u{10FFFF}"]]],
      ["foo `ua", [["foo", "ua"]]],
    ])
  })

  test("--% in a place it does not stop", () => {
    names(ps, [
      ["foo --%; b", [["foo", "--%", "; b"]]],
      ["foo --%x; b", [["foo", "--%x"], ["b"]]],
      ["foo > --% ; b", [["foo"], ["b"]]],
      ["foo --%\tb; c", [["foo", "--%", "b; c"]]],
      ["foo --% ", [["foo", "--%"]]],
      ["foo --%\r\nb", [["foo", "--%"], ["b"]]],
      ["foo --% a\rb", [["foo", "--%", "a"], ["b"]]],
      ["using --% a; b", [["b"]]],
      ["$a --% b", []],
    ])
  })

  test("the call operator's places, and a dot that is no operator", () => {
    names(ps, [
      ["& foo; & bar", [["foo"], ["bar"]]],
      ["&'foo' a", [["foo", "a"]]],
      ['. "foo"', [["foo"]]],
      [". $a", [["$a"]]],
      [".(a)", [["(a)"], ["a"]]],
      [". {a}", [["{a}"], ["a"]]],
      ["./foo", [["./foo"]]],
      ["..", [[".."]]],
      ["& (a)", [["(a)"], ["a"]]],
      ["$a = & foo", [["foo"]]],
    ])
    expect(psCommands("a | & b c")[1]).toEqual({
      resource: "& b c",
      words: ["b", "c"],
      rawWords: ["b", "c"],
      wordEnds: [3, 5],
    })
    reasons(ps, { "invalid-structure": ["& . a", ". & a", "& ;", ". ;"] })
  })

  test("the budget and the depth stop what nests", () => {
    const strings = (depth: number) => `${'"$('.repeat(depth)}a${')"'.repeat(depth)}`
    expect(ps(strings(31))).toEqual([["a"]])
    expect(ps(strings(32))).toBe("invalid-structure")
    // Each string's `$(` scans to the input's end for its quotes, which is what the budget is spent on.
    expect(ps('"$(a)" '.repeat(100))).toEqual(Array.from({ length: 100 }, () => ["a"]))
    expect(ps('"$(a)" '.repeat(9000))).toBe("invalid-structure")
    expect(ps(`foo @"\n${"$(a)\n".repeat(9000)}"@`)).toBe("invalid-structure")
    expect(ps(`foo ${"$(a) ".repeat(10000)}`)).not.toBe("invalid-structure")
  })
})

// Inputs `bench/subsume/pinned.py` kept: each tells apart a fault the derived cases above do not. Random, then shrunk,
// so they read oddly, and many are not valid scripts: what they pin is the scanner's reading, checked against its
// source, and only the keys the faults change (null: the key is absent). A failure here is a change to look at, not
// necessarily a defect.
describe("pinned inputs", () => {
  const summarize = (dialect: string, script: string): Record<string, unknown> => {
    const result = dialect === "pwsh" ? ShellScan.scanPowerShell(script) : ShellScan.scan(script, dialect as Dialect)
    if (result.kind === "opaque") return { reason: result.reason }
    const summary: Record<string, unknown> = { commands: result.commands.length }
    result.commands.forEach((command, index) => {
      for (const [key, value] of Object.entries(command)) summary[`${index}.${key}`] = JSON.stringify(value)
    })
    return summary
  }
  const PINNED: [string, string, Record<string, unknown>][] = [
    [
      "posix",
      "for (functions='$(a)' '\\x41'); do git; done|&\nin$x[$(a)]",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        "2.rawWords": null,
        "2.resource": null,
        "2.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "bash",
      "if ?(a); then =(a) fi; fi >| 'a[`x`]'",
      {
        "0.rawWords": '["?(a)"]',
        "0.resource": '"?(a)"',
        "0.words": '["?(a)"]',
        "1.rawWords": '["=(a)","fi"]',
        "1.resource": '"=(a) fi"',
        "1.words": '["=(a)","fi"]',
        "2.rawWords": '["a"]',
        "2.resource": '"a"',
        "2.words": '["a"]',
        commands: 3,
        reason: null,
      },
    ],
    [
      "bash",
      "for (); do ${x['$(a)']} '`x`'; done; case a${x:='$(a)'} in\nesac",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "bash",
      '$"a"',
      { "0.rawWords": '["$\\"a\\""]', "0.resource": '"$\\"a\\""', "0.words": '["a"]', commands: 1, reason: null },
    ],
    [
      "bash",
      "getopts '\\101' y[a",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "pwsh",
      "(foreach [int]$x) { @{a 1} } { } { } & class { } & try { } { }",
      {
        "1.rawWords": '["try","{ }","{ }"]',
        "1.resource": '"& try { } { }"',
        "1.wordEnds": "[5,9,13]",
        "1.words": '["try","{ }","{ }"]',
        commands: 2,
      },
    ],
    [
      "pwsh",
      "foo --% $x",
      { "0.rawWords": '["foo","--%","$x"]', "0.resource": '"foo --% $x"', "0.wordEnds": "[3,7,10]" },
    ],
    [
      "bash",
      "for x do [[ ( ) $[x] ]]; done&& until -o; do A='$(a)' -ne${(q)x}; done",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    ["pwsh", "2>", { commands: null, reason: "invalid-structure" }],
    ["posix", "-ge${\\\n||", { reason: "dynamic-execution" }],
    [
      "pwsh",
      "a, \r $x[0]",
      {
        "0.rawWords": '["a,","$x[0]"]',
        "0.resource": '"a, \\r $x[0]"',
        "0.wordEnds": "[2,10]",
        "0.words": '["a,","$x[0]"]',
      },
    ],
    ["posix", "for (READNULLCMD[a 'a[`x`]'", { reason: "invalid-structure" }],
    ["bash", "case -v in\nesac\n( ${x:'$(a)'}", { error: null, reason: "dynamic-execution" }],
    [
      "posix",
      "vared -ne dis_functions[1]=$(a)",
      {
        "0.rawWords": '["vared","-ne","dis_functions[1]=$(a)"]',
        "0.resource": '"vared -ne dis_functions[1]=$(a)"',
        "0.words": '["vared","-ne","dis_functions[1]=$(a)"]',
        "1.rawWords": '["a"]',
        "1.resource": '"a"',
        "1.words": '["a"]',
        commands: 2,
        reason: null,
      },
    ],
    ["pwsh", "1 && x", { "0.resource": '"x"', "0.wordEnds": "[1]" }],
    [
      "pwsh",
      "& --`% @{a=b}",
      {
        "0.rawWords": '["--`%","@{a=b}"]',
        "0.resource": '"& --`% @{a=b}"',
        "0.wordEnds": "[6,13]",
        "1.rawWords": '["b"]',
        "1.resource": '"b"',
        "1.statementHead": "true",
        "1.wordEnds": "[1]",
        "1.words": '["b"]',
        commands: 2,
      },
    ],
    [
      "pwsh",
      "break l #\ngit",
      {
        "0.rawWords": '["git"]',
        "0.resource": '"git"',
        "0.statementHead": "true",
        "0.wordEnds": "[3]",
        "0.words": '["git"]',
        commands: 1,
      },
    ],
    [
      "zsh",
      "function f { { a[$b]=c continue '('; }; }",
      {
        "0.rawWords": '["continue","\'(\'"]',
        "0.resource": "\"a[$b]=c continue '('\"",
        "0.words": '["continue","("]',
        commands: 1,
        reason: null,
      },
    ],
    ["zsh", "[[ do${x@P}", { reason: "dynamic-execution" }],
    [
      "zsh",
      "unset '$(x)'",
      {
        "0.declaration": null,
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    ["pwsh", '@"\n"@ { &&\n>', { reason: "invalid-redirect" }],
    ["bash", "(( $'\\101' ))", { commands: null, reason: "dynamic-execution" }],
    [
      "posix",
      "shift '\\x41'",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "pwsh",
      "`$a $x.y.\n$x[0]",
      {
        "0.rawWords": '["`$a","$x.y."]',
        "0.resource": '"`$a $x.y."',
        "0.wordEnds": "[3,9]",
        "0.words": '["$a","$x.y."]',
      },
    ],
    ["pwsh", "a[0] \r else 'a b'", { "1.statementHead": "true", "1.wordEnds": "[4,10]" }],
    [
      "pwsh",
      "Get-Thing --`% 2>&1",
      {
        "0.rawWords": '["Get-Thing","--`%","2>&1"]',
        "0.resource": '"Get-Thing --`% 2>&1"',
        "0.statementHead": "true",
        "0.wordEnds": "[9,14,19]",
        "0.words": '["Get-Thing","--%","2>&1"]',
        commands: 1,
        reason: null,
      },
    ],
    [
      "pwsh",
      "@'\n'@\n* && using \"${x}\"\nif",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.statementHead": null,
        "0.wordEnds": null,
        "0.words": null,
        commands: null,
        reason: "invalid-structure",
      },
    ],
    [
      "bash",
      "if $x; then ( foo$(( )) ); fi|& $~x",
      {
        "0.rawWords": '["$x"]',
        "0.resource": '"$x"',
        "0.words": '["$x"]',
        "1.rawWords": '["foo$(( ))"]',
        "1.resource": '"foo$(( ))"',
        "1.words": '["foo$(( ))"]',
        "2.rawWords": '["$~x"]',
        "2.resource": '"$~x"',
        "2.words": '["$~x"]',
        "3.rawWords": null,
        "3.resource": null,
        "3.words": null,
        commands: 3,
        reason: null,
      },
    ],
    ["zsh", "getln 'a[$(x)]'| (( ))|& ( ) (a|b) nullglob", { reason: "dynamic-execution" }],
    ["pwsh", "`u{41}", { "0.wordEnds": "[6]" }],
    ["bash", "[[ ]]\nx", { "0.rawWords": '["x"]', "0.resource": '"x"', "0.words": '["x"]', commands: 1, reason: null }],
    ["bash", "(($~x))&", { commands: 0, reason: null }],
    ["pwsh", "if \r\n{ }", { commands: 0, reason: null }],
    ["posix", "(( $[x] ))", { reason: "command-substitution" }],
    [
      "posix",
      "unset $[1]",
      {
        "0.declaration": null,
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        commands: null,
        reason: "command-substitution",
      },
    ],
    [
      "zsh",
      "stat aliases",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    ["bash", "3 (($(a);;));", { reason: "compound-command" }],
    ["bash", "case do in\nesac", { commands: 0, reason: null }],
    ["posix", "[[ keyword$[x]", { reason: "invalid-structure" }],
    ["posix", "for (-E $[x]);", { reason: "command-substitution" }],
    ["pwsh", '@"\n$(a)\n"@ foo)', { reason: "invalid-structure" }],
    [
      "zsh",
      "bye `a`\nA='$(a)'",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    ["bash", "A='$(a)' <<< '$'", { commands: 0, reason: null }],
    [
      "bash",
      '((-le"$x[$(a)]"))',
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "invalid-structure" },
    ],
    [
      "bash",
      "zformat 'a[$(x)]'",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "posix",
      "A='$(a)' break a",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    ["pwsh", "try { } { } { } #", { commands: 0, reason: null }],
    [
      "posix",
      "private saliases[a",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "pwsh",
      "a#b $x::y\n({ }) { }",
      {
        "0.rawWords": '["a#b","$x::y"]',
        "0.resource": '"a#b $x::y"',
        "0.wordEnds": "[3,9]",
        "0.words": '["a#b","$x::y"]',
      },
    ],
    [
      "zsh",
      "exit ${|a; } 'a[`x`]'",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "pwsh",
      '"$(a)"\n(1 "a$(b)c" { }',
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.statementHead": null,
        "0.wordEnds": null,
        "0.words": null,
        commands: null,
        reason: "invalid-structure",
      },
    ],
    [
      "bash",
      "A='$(a)' ${functions[a]}",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    ["posix", '<<-EOF\nEOF\nelse <<"EOF"', { reason: "compound-command" }],
    ["bash", "case '\\101' in\na) &>> do;;", { reason: "compound-command" }],
    [
      "pwsh",
      'a[0] --`% #> \r\n<# #> @"\n"@',
      { "0.rawWords": '["a[0]","--`%","#>"]', "0.resource": '"a[0] --`% #>"', "0.wordEnds": "[4,9,12]" },
    ],
    ["zsh", "for (globsubst =~${!x[1]});", { reason: "invalid-structure" }],
    [
      "bash",
      "vared READNULLCMD[1]='$(a)'",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "bash",
      "{ A='$(a)' ${(s:,:)x} -gt; }",
      {
        "0.rawWords": '["${(s:,:)x}","-gt"]',
        "0.resource": "\"A='$(a)' ${(s:,:)x} -gt\"",
        "0.words": '["${(s:,:)x}","-gt"]',
        commands: 1,
        reason: null,
      },
    ],
    ["posix", "for x do ((-gt${NULLCMD}));", { reason: "invalid-structure" }],
    [
      "zsh",
      "for (then '$(x)'); do\nEOF\ndone",
      { "0.rawWords": '["EOF"]', "0.resource": '"EOF"', "0.words": '["EOF"]', commands: 1, reason: null },
    ],
    [
      "zsh",
      "function f { zstyle aliases; }",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "bash",
      "( A='$(a)' zparseopts ==$(a) )",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    ["pwsh", '[int] <# #> \r\nelse <# #> @"\n"@', { "0.statementHead": "true" }],
    [
      "zsh",
      "repeat -lt do A='$(a)' foo; done",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    ["posix", "for ((i=0;i<1;i++)); do set -m;", { reason: "compound-command" }],
    [
      "pwsh",
      "(parallel { @'\n'@ }) #\nnamespace \r",
      {
        "0.rawWords": '["namespace"]',
        "0.resource": '"namespace"',
        "0.statementHead": "true",
        "0.wordEnds": "[9]",
        "0.words": '["namespace"]',
        commands: 1,
        reason: null,
      },
    ],
    ["zsh", "A=(a b) '$(x)'; for x in 'a[$(x)]';", { reason: "compound-command" }],
    [
      "posix",
      "for x do ${x:-a} in ${x[$(a)]}; done;",
      {
        "0.rawWords": '["${x:-a}","in","${x[$(a)]}"]',
        "0.resource": '"${x:-a} in ${x[$(a)]}"',
        "0.words": '["${x:-a}","in","${x[$(a)]}"]',
        "1.rawWords": '["a"]',
        "1.resource": '"a"',
        "1.words": '["a"]',
        commands: 2,
        reason: null,
      },
    ],
    [
      "bash",
      "&> esac&& A='$(a)' readarray $$'a'&& -p",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "zsh",
      "zregexparse 'a[`x`]'; function f { a; };",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    ["zsh", "for (${x:1} saliases=('$(a)' $$'\\a'; done", { reason: "compound-command" }],
    ["bash", "A=(a b) -E&& ${(e)x} 2> -t${functions[a]}", { "1.resource": '"${(e)x}"' }],
    ["bash", "case saliases=($(a)\na) globsubst;;\n<<-EOF", { reason: "compound-command" }],
    [
      "bash",
      "vared\nselect \\ ; do ${functions[a]}; done",
      {
        "0.rawWords": '["vared"]',
        "0.resource": '"vared"',
        "0.words": '["vared"]',
        "1.rawWords": '["${functions[a]}"]',
        "1.resource": '"${functions[a]}"',
        "1.words": '["${functions[a]}"]',
        commands: 2,
      },
    ],
    [
      "zsh",
      "-E${x:='$(a)'}\n{ read <<EOF\n$(a)\nEOF\n}|| a",
      {
        "0.rawWords": "[\"-E${x:='$(a)'}\"]",
        "0.resource": "\"-E${x:='$(a)'}\"",
        "0.words": "[\"-E${x:='$(a)'}\"]",
        "1.rawWords": '["read"]',
        "1.resource": '"read <<EOF\\n$(a)\\nEOF"',
        "1.words": '["read"]',
        "2.rawWords": '["a"]',
        "2.resource": '"a"',
        "2.words": '["a"]',
        "3.rawWords": '["a"]',
        "3.resource": '"a"',
        "3.words": '["a"]',
        commands: 4,
        reason: null,
      },
    ],
    [
      "zsh",
      "if until set; do $x; done; then ((-p)); fi",
      {
        "0.rawWords": '["set"]',
        "0.resource": '"set"',
        "0.words": '["set"]',
        "1.rawWords": '["$x"]',
        "1.resource": '"$x"',
        "1.words": '["$x"]',
        commands: 2,
        reason: null,
      },
    ],
    [
      "bash",
      "for (($(a);;)); do compgen NULLCMD='$(a)'; done",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "posix",
      "until 'a b' -F; do logout '\\101' \"${x:-$'a'}\"; done",
      {
        "0.rawWords": null,
        "0.resource": null,
        "0.words": null,
        "1.rawWords": null,
        "1.resource": null,
        "1.words": null,
        commands: null,
        reason: "dynamic-execution",
      },
    ],
    [
      "posix",
      "case '$' in\na) function f { continue '\\x41'; };;\nesac",
      { "0.rawWords": null, "0.resource": null, "0.words": null, commands: null, reason: "dynamic-execution" },
    ],
    [
      "bash",
      "for x do $'\\101'; done|| let '\\101' > ${NULLCMD}; while exec; do !=; done",
      {
        "0.rawWords": "[\"$'\\\\101'\"]",
        "0.resource": "\"$'\\\\101'\"",
        "0.words": '["A"]',
        "1.rawWords": '["let","\'\\\\101\'"]',
        "1.resource": "\"let '\\\\101'\"",
        "1.words": '["let","\\\\101"]',
        "2.rawWords": '["exec"]',
        "2.resource": '"exec"',
        "2.words": '["exec"]',
        "3.rawWords": '["!="]',
        "3.resource": '"!="',
        "3.words": '["!="]',
        commands: 4,
        reason: null,
      },
    ],
    [
      "posix",
      "if !=; then { return; }; elif ]]; then case != in (a) $((1));; esac; else ${functions[a]}",
      { reason: "dynamic-execution" },
    ],
  ]

  test("each reads as it was checked to", () => {
    for (const [dialect, script, pins] of PINNED) {
      const summary = summarize(dialect, script)
      const got: Record<string, unknown> = Object.fromEntries(
        Object.keys(pins).map((key) => [key, summary[key] ?? null]),
      )
      expect({ dialect, script, got }).toEqual({ dialect, script, got: pins })
    }
  })
})
