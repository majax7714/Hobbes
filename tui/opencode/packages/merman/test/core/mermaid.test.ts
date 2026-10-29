import { expect, test } from "bun:test"
import {
  decodeMermaidText,
  firstMeaningfulMermaidLine,
  meaningfulNumberedMermaidLines,
  numberedMermaidLines,
  stripMermaidQuotes,
} from "../../src/core/mermaid"

const SOURCE = "graph TD\r\n  A --> B  \n\n  %% a comment\nB"

test("every line is numbered from 1 and trimmed, CRLF or LF alike; the meaningful ones drop blanks and %% comments and keep their numbers", () => {
  expect([...numberedMermaidLines(SOURCE)]).toEqual([
    { lineNumber: 1, text: "graph TD" },
    { lineNumber: 2, text: "A --> B" },
    { lineNumber: 3, text: "" },
    { lineNumber: 4, text: "%% a comment" },
    { lineNumber: 5, text: "B" },
  ])
  expect([...meaningfulNumberedMermaidLines(SOURCE)]).toEqual([
    { lineNumber: 1, text: "graph TD" },
    { lineNumber: 2, text: "A --> B" },
    { lineNumber: 5, text: "B" },
  ])
})

test("the first meaningful line skips leading blanks and comments; none at all is undefined", () => {
  expect(firstMeaningfulMermaidLine("\n   %% intro\r\n  sequenceDiagram  \nA->>B: hi")).toBe("sequenceDiagram")
  expect(firstMeaningfulMermaidLine("  \n%% only\n%%")).toBeUndefined()
})

test("matching quotes of either kind are stripped and the inside decoded strictly; a quote at one end only is kept", () => {
  expect(stripMermaidQuotes('  "a &amp; b"  ')).toBe("a & b")
  expect(stripMermaidQuotes("'x &lt; y'")).toBe("x < y")
  for (const kept of [`"half'`, `'half"`, `half"`, `half'`, `"half`, `'half`]) expect(stripMermaidQuotes(kept)).toBe(kept)
  expect(stripMermaidQuotes("  bare &gt; text ")).toBe("bare > text")
  expect(stripMermaidQuotes('"')).toBe("")
  expect(decodeMermaidText("a &amp b")).toBe("a &amp b")
  expect(decodeMermaidText("&#65;&#x42;&quot;")).toBe('AB"')
})
