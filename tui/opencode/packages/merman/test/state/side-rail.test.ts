import { expect, test } from "bun:test"
import { drawSideRailCase } from "./side-rail-case"

// Drawn in a child process limited to 1 s (it takes 50 ms): were the endless rail loop back, it would hang this run and take
// the host's memory, so it is never drawn in this process.
const drawInChild = (mode: "TB" | "width") =>
  Bun.spawnSync([process.execPath, `${import.meta.dir}/side-rail-case.ts`, mode], { timeout: 1000 })

test("a fork fix: the diagram whose side rail once looped forever is drawn and ends, top to bottom or by the width fallback", () => {
  // Its rail started and ended on one row; ends on one row now go straight across, so no rail is drawn, and the
  // rail loop keeps its bound for any other caller.
  for (const mode of ["TB", "width"] as const) {
    const child = drawInChild(mode)
    expect([child.exitedDueToTimeout, child.exitCode]).toEqual([false, 0])
    expect(child.stdout.toString().trimEnd().split("\n").slice(0, 4)).toEqual([
      "__start>B vertical 4",
      "B>P0x vertical-elbow 7",
      "P0x>P1x horizontal-forward 14",
      "B>P1x vertical-elbow 27",
    ])
  }
  expect(typeof drawSideRailCase).toBe("function")
})

test("top to bottom, a transition between composites whose ends share a row goes straight across into the target's near side", () => {
  // Once a fork defect: a side rail ran right past P1x to the rail column and back along the same row, over P1x
  // (its label lost), its head against P1x's far wall.
  const child = drawInChild("TB")
  expect(child.stdout.toString().trimEnd().split("\n").slice(4)).toEqual([
    "    ●",
    "    │",
    "    │",
    "    │",
    "    ▼",
    "  ╭───╮",
    "  │ B │",
    "  ╰─┬─╯",
    "    │",
    "   a│ retry",
    "   b╰┬───────────────────╮",
    "╭─ P0 ────╮         ╭─ A long composite title ╮",
    "│    ▼    │         │    ▼                    │",
    "│ ╭─────╮ │ retry   │ ╭─────╮                 │",
    "│ │ P0x ├────────────▶│ P1x │                 │",
    "│ ╰─────╯ │         │ ╰─────╯                 │",
    "│         │         │                         │",
    "╰─────────╯         ╰─────────────────────────╯",
  ])
})
