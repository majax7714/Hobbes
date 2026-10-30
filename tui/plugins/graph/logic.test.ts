// Tests for the graph plugin's TUI-free logic (logic.ts). The panel itself is drawn by the TUI and checked
// live (docs/watterson/README.md). Run with the TUI's Bun: `bun test tui/plugins/graph`.
import { expect, test } from "bun:test"
import {
  FRAMES,
  lines,
  MAX_LINKS,
  modeLabel,
  moveSelection,
  pickPicture,
  rowText,
  shownLinks,
  statusLine,
  viewHeading,
  type Picture,
} from "./logic"

const made: string[] = []
const hex = (h: string) => {
  made.push(h)
  return `#${h}`
}

test("a picture is two pixels a cell: upper, lower or both half blocks, palette letters made once, runs merged", () => {
  made.length = 0
  const picture: Picture = { rows: ["TTa.a", "t.aaa", "T"], palette: { a: "ff0000" } }
  expect(lines(picture, "text", "muted", hex)).toEqual([
    [
      { text: "▀", fg: "text", bg: "muted" },
      { text: "▀", fg: "text" },
      { text: "▀", fg: "#ff0000", bg: "#ff0000" },
      { text: "▄", fg: "#ff0000" },
      { text: "▀", fg: "#ff0000", bg: "#ff0000" },
    ],
    [{ text: "▀", fg: "text" }],
  ])
  expect(made).toEqual(["ff0000"])
})

test("cells of one colour pair and one glyph join one span; a change of glyph or colour starts another", () => {
  expect(lines({ rows: ["TT..TT", "TT..tt"], palette: {} }, "T", "t", hex)).toEqual([
    [{ text: "▀▀", fg: "T", bg: "T" }, { text: "  " }, { text: "▀▀", fg: "T", bg: "t" }],
  ])
  expect(lines({ rows: ["T.", ".T"], palette: {} }, "T", "t", hex)).toEqual([[{ text: "▀", fg: "T" }, { text: "▄", fg: "T" }]])
})

const art: Picture = { rows: Array.from({ length: 10 }, () => "x".repeat(20)), palette: {} }
const letters: Picture = { rows: Array.from({ length: 4 }, () => "x".repeat(8)), palette: {} }

test("the art is drawn when the terminal is four columns wider and twelve rows taller, else the letters, else nothing", () => {
  expect(pickPicture({ art, letters }, 24, 17)).toBe(art)
  expect(pickPicture({ art, letters }, 23, 17)).toBe(letters)
  expect(pickPicture({ art, letters }, 24, 16)).toBe(letters)
  expect(pickPicture({ art: null, letters }, 12, 14)).toBe(letters)
  expect(pickPicture({ art, letters }, 11, 14)).toBeUndefined()
  expect(pickPicture({ art, letters }, 12, 13)).toBeUndefined()
  expect(pickPicture(undefined, 200, 200)).toBeUndefined()
})

test("the Hobbes item says the state, and with details what a click does or how long it has been starting", () => {
  const status = (state: "on" | "off" | "failed" | "unavailable" | "starting", since: number | null = null) => ({ state, detail: "", since })
  expect(statusLine(undefined, true, 0)).toEqual({ text: "", tone: "muted" })
  expect(statusLine(status("on"), true, 0)).toEqual({ text: "● hobbes on", tone: "success" })
  expect([statusLine(status("off"), false, 0), statusLine(status("off"), true, 0)]).toEqual([
    { text: "◌ hobbes off", tone: "muted" },
    { text: "◌ hobbes off · start", tone: "muted" },
  ])
  expect([statusLine(status("failed"), false, 0), statusLine(status("failed"), true, 0)]).toEqual([
    { text: "✕ hobbes failed", tone: "error" },
    { text: "✕ hobbes failed · retry", tone: "error" },
  ])
  expect(statusLine(status("unavailable"), true, 0)).toEqual({ text: "◌ hobbes unavailable", tone: "muted" })
  expect(statusLine(status("starting", 1_000), true, 3_999)).toEqual({ text: `${FRAMES[3]} hobbes starting · 2s`, tone: "warning" })
  expect(statusLine(status("starting", 5_000), true, 1_200).text).toBe(`${FRAMES[0]} hobbes starting · 0s`)
  expect(statusLine(status("starting"), false, 240).text).toBe(`${FRAMES[2]} hobbes starting`)
})

test("the spinner turns a frame every 120 ms through ten frames", () => {
  const frame = (now: number) => statusLine({ state: "starting", detail: "", since: null }, false, now).text[0]
  expect([frame(0), frame(119), frame(120), frame(1_199), frame(1_200)]).toEqual([FRAMES[0], FRAMES[0], FRAMES[1], FRAMES[9], FRAMES[0]])
  expect(FRAMES.length).toBe(10)
})

test("the mode item names the mode", () => {
  expect([modeLabel("mapped"), modeLabel("mapping"), modeLabel("default")]).toEqual(["◆ agent mapped", "✎ edit mapping", "◇ default"])
})

test("the selection moves by its step and stays on the list; an empty list keeps it", () => {
  expect([moveSelection(2, 1, 5), moveSelection(4, 1, 5), moveSelection(0, -1, 5), moveSelection(3, -10, 5), moveSelection(1, 10, 5)]).toEqual([3, 4, 0, 0, 4])
  expect(moveSelection(3, 1, 0)).toBe(3)
})

test("the panel's heading, row text and links read as the user sees them", () => {
  expect(viewHeading({ kind: "folder", level: 2, sha: "abc1234", dirty: false })).toBe("  folder · level 2 · abc1234")
  expect(viewHeading({ kind: "module", level: 0, sha: "abc1234", dirty: true })).toBe("  module · level 0 · abc1234 (dirty)")
  expect(rowText({ opens: "app/cli", label: "cli.py", root: false })).toEqual({ marker: "▸ ", label: "cli.py" })
  expect(rowText({ opens: null, label: "app", root: true })).toEqual({ marker: "  ", label: "app (root)" })
  const links = Array.from({ length: 11 }, (_, i) => `l${i}`)
  expect(MAX_LINKS).toBe(8)
  expect(shownLinks(links)).toEqual({ shown: links.slice(0, 8), more: 3 })
  expect(shownLinks(links.slice(0, 8))).toEqual({ shown: links.slice(0, 8), more: 0 })
  expect(shownLinks([])).toEqual({ shown: [], more: 0 })
})
