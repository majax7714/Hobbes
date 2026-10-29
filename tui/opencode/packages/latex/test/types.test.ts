import { expect, test } from "bun:test"
import { LatexParseError } from "../src/types"

// The rest of the module is type declarations; only the error class runs.
test("a parse error names itself and carries its offset in the message and as a field", () => {
  const error = new LatexParseError("Expected \"}\"", 7)
  expect(error).toBeInstanceOf(Error)
  expect(error.name).toBe("LatexParseError")
  expect(error.message).toBe('Expected "}" at offset 7')
  expect(error.position).toBe(7)
})
