import { expect, test } from "bun:test"
import { parseDiagramTextLines, splitDiagramLines } from "../../src/core/text-lines"

test("a line is split at every <br> spelling, each piece trimmed, italic runs read from <i> and <em>", () => {
  expect(parseDiagramTextLines("  a <i>b</i> c <br> d<BR/>e<br />f")).toEqual([
    { text: "a b c", runs: [{ text: "a ", italic: false }, { text: "b", italic: true }, { text: " c", italic: false }] },
    { text: "d", runs: [{ text: "d", italic: false }] },
    { text: "e", runs: [{ text: "e", italic: false }] },
    { text: "f", runs: [{ text: "f", italic: false }] },
  ])
  expect(parseDiagramTextLines("<EM>loud</em> <i >x")).toEqual([
    { text: "loud x", runs: [{ text: "loud", italic: true }, { text: " ", italic: false }, { text: "x", italic: true }] },
  ])
})

test("an empty label is one line with no runs, and splitting keeps only each line's text", () => {
  expect(parseDiagramTextLines("")).toEqual([{ text: "", runs: [] }])
  expect(splitDiagramLines("one<br>two <i>three</i>")).toEqual(["one", "two three"])
})
