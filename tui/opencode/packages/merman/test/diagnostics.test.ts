import { expect, test } from "bun:test"
import { MermaidSyntaxError } from "../src/diagnostics"

test("a syntax error says what, in which kind of diagram, at which line, quoting the source line", () => {
  const error = new MermaidSyntaxError("sequence", 4, "A -x B", "Unsupported arrow")
  expect(error).toBeInstanceOf(Error)
  expect([error.name, error._tag, error.kind, error.lineNumber, error.sourceLine]).toEqual(["MermaidSyntaxError", "MermaidSyntaxError", "sequence", 4, "A -x B"])
  expect(error.message).toBe('Unsupported arrow in sequence diagram at line 4: "A -x B"')
  expect(new MermaidSyntaxError("gantt", 1, "x").message).toBe('Unsupported syntax in gantt diagram at line 1: "x"')
})
