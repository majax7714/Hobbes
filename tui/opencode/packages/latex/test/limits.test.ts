import { expect, test } from "bun:test"
import {
  assertNestingDepth,
  assertSourceLength,
  DEFAULT_MAX_NESTING_DEPTH,
  DEFAULT_MAX_SOURCE_LENGTH,
} from "../src/limits"
import { LatexParseError } from "../src/types"

function thrown(run: () => void): unknown {
  try {
    run()
  } catch (error) {
    return error
  }
  return undefined
}

test("the default limits are 100 000 characters and 256 levels", () => {
  expect(DEFAULT_MAX_SOURCE_LENGTH).toBe(100_000)
  expect(DEFAULT_MAX_NESTING_DEPTH).toBe(256)
})

test("a source at the limit passes and one character over is a parse error at the limit, labelled", () => {
  assertSourceLength("abc", 3)
  const error = thrown(() => assertSourceLength("abcd", 3)) as LatexParseError
  expect(error).toBeInstanceOf(LatexParseError)
  expect(error.message).toBe("LaTeX source exceeds the 3-character limit at offset 3")
  expect(error.position).toBe(3)
  expect(() => assertSourceLength("abcd", 3, "Expanded LaTeX source")).toThrow(
    "Expanded LaTeX source exceeds the 3-character limit",
  )
})

test("brace depth may reach the limit; one level deeper fails at that brace, and closing braces give depth back", () => {
  assertNestingDepth("{{a}}{{b}}", 2)
  assertNestingDepth("{}{}{}", 1)
  const error = thrown(() => assertNestingDepth("a{{{b}}}", 2)) as LatexParseError
  expect(error).toBeInstanceOf(LatexParseError)
  expect(error.message).toBe("LaTeX nesting exceeds the 2-level limit at offset 3")
  expect(() => assertNestingDepth("{", 0)).toThrow(LatexParseError)
  expect(() => assertNestingDepth("{a{", 1)).toThrow(LatexParseError)
  expect(() => assertNestingDepth("{{}{{", 2)).toThrow(LatexParseError)
})

test("a stray closing brace does not bank depth for later", () => {
  expect(() => assertNestingDepth("}{{", 1)).toThrow(LatexParseError)
})

test("a brace after an odd run of backslashes is escaped; after an even run it counts", () => {
  assertNestingDepth("\\{\\{\\{", 0)
  assertNestingDepth("{\\}}", 1)
  assertNestingDepth("\\\\\\{", 0)
  expect(() => assertNestingDepth("\\\\{", 0)).toThrow(LatexParseError)
  expect(() => assertNestingDepth("\\\\\\\\{", 0)).toThrow(LatexParseError)
  expect(() => assertNestingDepth("\\x{{", 1)).toThrow(LatexParseError)
})
