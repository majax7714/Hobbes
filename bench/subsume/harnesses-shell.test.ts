// The shell scanner's harness loads `core`, so it is tested apart from the others, which load `merman`.
process.env.PINNED_PACKAGE ??= new URL("../../tui/opencode/packages/core", import.meta.url).pathname
const { expect, test } = await import("bun:test")
const { random } = await import("./harnesses/random")
const { generate: generateShell, summarize: summarizeShell } = await import("./harnesses/shell-scan")

test("the shell scanner's harness makes the same scripts for a seed, none an error, and names its dialect", () => {
  const rand = (seed: number) => random(seed)
  const inputs = (seed: number) => {
    const next = rand(seed)
    return Array.from({ length: 300 }, () => generateShell(next))
  }
  expect(inputs(3)).toEqual(inputs(3))
  expect(inputs(3)).not.toEqual(inputs(4))
  expect(inputs(3).every((input) => /^%%(bash|zsh|posix|pwsh)\n/.test(input))).toBe(true)
  expect(inputs(3).filter((input) => "error" in summarizeShell(input))).toEqual([])
})

test("the shell scanner's harness summarizes a refusal as its reason, a read as one key per command's field", () => {
  expect(summarizeShell("%%bash\nfoo 'a")).toEqual({ reason: "unterminated-quote" })
  expect(summarizeShell("%%posix\na[$b]=1")).toEqual({ reason: "invalid-structure" })
  expect(summarizeShell("%%bash\nfoo 'a b'")).toEqual({
    commands: 1,
    "0.resource": '"foo \'a b\'"',
    "0.words": '["foo","a b"]',
    "0.rawWords": '["foo","\'a b\'"]',
  })
  expect(summarizeShell("%%pwsh\nfoo")).toEqual({
    commands: 1,
    "0.resource": '"foo"',
    "0.words": '["foo"]',
    "0.rawWords": '["foo"]',
    "0.wordEnds": "[3]",
    "0.statementHead": "true",
  })
})
