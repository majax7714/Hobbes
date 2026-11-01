// pinned.py's harness for merman's state search: random small grids, each with blocked cells, starts, a goal
// and a budget, summarized as the path found and the budget left. An input's first line names the grid, the goal and
// the budget (pinned.py never deletes it); each later line is one start or one blocked cell.
import { packageRoot, runHarness } from "./cli"

const { findStateManhattanPath } = await import(`${packageRoot}/src/state/search.ts`)

export function generate(rand: () => number): string {
  const n = (max: number) => Math.floor(rand() * max)
  const size = 2 + n(5)
  const budget = [3, 8, 30, 250_000][n(4)]
  const lines = [`grid ${size} goal ${n(size)} ${n(size)} budget ${budget}`]
  for (let k = 1 + n(3); k > 0; k--) lines.push(`start ${n(size)} ${n(size)}`)
  for (let k = n(size * size); k > 0; k--) lines.push(`block ${n(size)} ${n(size)}`)
  return lines.join("\n")
}

export function summarize(input: string): Record<string, unknown> {
  try {
    const [head, ...rest] = input.split("\n")
    const [, size, , gx, gy, , budget] = head!.split(" ").map((word) => Number(word))
    const starts = rest.filter((line) => line.startsWith("start")).map((line) => line.split(" ").map(Number))
    const blocked = new Set(
      rest.filter((line) => line.startsWith("block")).map((line) => line.slice(6).replace(" ", ":")),
    )
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

if (import.meta.main) await runHarness(generate, summarize)
