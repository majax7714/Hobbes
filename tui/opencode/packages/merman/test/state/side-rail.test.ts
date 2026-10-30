import { expect, test } from "bun:test"
import { drawSideRailCase } from "./side-rail-case"

// Drawn in a child process limited to 1 s (it takes 50 ms): were the endless rail loop back, it would hang this run and take
// the host's memory, so it is never drawn in this process.
const drawInChild = (mode: "TB" | "width") =>
  Bun.spawnSync([process.execPath, `${import.meta.dir}/side-rail-case.ts`, mode], { timeout: 1000 })

test("a fork fix: a side rail that starts and ends on one row is drawn and ends, top to bottom or by the width fallback", () => {
  for (const mode of ["TB", "width"] as const) {
    const child = drawInChild(mode)
    expect([child.exitedDueToTimeout, child.exitCode]).toEqual([false, 0])
    expect(child.stdout.toString().trimEnd().split("\n").slice(0, 4)).toEqual([
      "__start>B vertical 4",
      "B>P0x vertical-elbow 7",
      "P0x>P1x side-parallel 65",
      "B>P1x vertical-elbow 27",
    ])
  }
  expect(typeof drawSideRailCase).toBe("function")
})

test("a fork defect, pinned: that rail doubles back along its own row, over the target, into its far side", () => {
  // P0x's rail runs right past P1x to the rail column and back left along the same row, over P1x, its head
  // against P1x's far wall (currently-open.md). A fix changes this.
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
    "│ ╭─────╮ │         │ ╭─────╮                 │",
    "│ │ P0x ├────────────────────◀────────────────────┤ retry",
    "│ ╰─────╯ │         │ ╰─────╯                 │",
    "│         │         │                         │",
    "╰─────────╯         ╰─────────────────────────╯",
  ])
})
