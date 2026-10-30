// pinned.py's harness for merman's state search: random small grids, each with blocked cells, starts, a goal
// and a budget, summarized as the path found and the budget left. An input is one JSON object per line pair:
// its first line is a header pinned.py never deletes, each later line one start or one blocked cell.
import { findStateManhattanPath } from "./src/state/search"

function random(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function generate(rand: () => number): string {
  const n = (max: number) => Math.floor(rand() * max)
  const size = 2 + n(5)
  const budget = [3, 8, 30, 250_000][n(4)]
  const lines = [`grid ${size} goal ${n(size)} ${n(size)} budget ${budget}`]
  for (let k = 1 + n(3); k > 0; k--) lines.push(`start ${n(size)} ${n(size)}`)
  for (let k = n(size * size); k > 0; k--) lines.push(`block ${n(size)} ${n(size)}`)
  return lines.join("\n")
}

function summarize(input: string): Record<string, unknown> {
  try {
    const [head, ...rest] = input.split("\n")
    const [, size, , gx, gy, , budget] = head!.split(" ").map((word) => Number(word))
    const starts = rest.filter((line) => line.startsWith("start")).map((line) => line.split(" ").map(Number))
    const blocked = new Set(rest.filter((line) => line.startsWith("block")).map((line) => line.slice(6).replace(" ", ":")))
    const left = { remaining: budget! }
    const path = findStateManhattanPath(
      starts.map(([, x, y]) => ({ x: x!, y: y! })),
      { x: gx!, y: gy! },
      { blocked },
      { minX: 0, minY: 0, maxX: size! - 1, maxY: size! - 1 },
      left,
    )
    return { path: JSON.stringify(path ?? null), remaining: left.remaining }
  } catch (error) {
    return { error: String(error) }
  }
}

const [command, seed, count] = process.argv.slice(2)
if (command === "gen") {
  const rand = random(Number(seed))
  console.log(JSON.stringify(Array.from({ length: Number(count) }, () => generate(rand))))
} else {
  const inputs: string[] = JSON.parse(await Bun.stdin.text())
  console.log(JSON.stringify(inputs.map(summarize)))
}
