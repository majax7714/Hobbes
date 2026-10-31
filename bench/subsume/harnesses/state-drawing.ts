// pinned.py's harness for merman's state routing and drawing: the shared random state diagrams, drawn with random
// options, each summarized as its routes (kind, corners, label) and its drawn rows. Copied into the package root
// as `.pinned/`, so `../src` is the planted copy.
import { packageRoot, runHarness } from "./cli"
import { generate } from "./state-gen"

const { createStateDiagramDrawing } = await import(`${packageRoot}/src/state/drawing.ts`)
const { parseMermaidStateDiagram } = await import(`${packageRoot}/src/state/parser.ts`)
const { renderStateGridText } = await import(`${packageRoot}/src/state/render-grid.ts`)

function corners(path: readonly (readonly [number, number])[]): string {
  const kept = path.filter((point, index) => {
    const before = path[index - 1]
    const after = path[index + 1]
    if (!before || !after) return true
    return (before[0] === point[0]) !== (point[0] === after[0])
  })
  return kept.map(([x, y]) => `${x},${y}`).join(" ")
}

export function summarize(input: string): Record<string, unknown> {
  try {
    const gap = Number(input.match(/^%%gap (\d+)$/m)?.[1] ?? 5)
    const style = input.match(/^%%style (\w+) (\w+) (\d*)$/m)
    const drawing = createStateDiagramDrawing(parseMermaidStateDiagram(input), {
      minStateGap: gap,
      ...(style
        ? {
            borderStyle: style[1] as "single",
            arrowHeadStyle: style[2] as "line",
          }
        : {}),
      ...(style?.[3] ? { layoutMaxWidth: Number(style[3]) } : {}),
    })
    const out: Record<string, unknown> = {}
    drawing.transitionPlans.forEach((plan, index) => {
      out[`route:${index}`] =
        `${plan.route.transition.from}>${plan.route.transition.to} ${plan.route.kind} ${corners(plan.path)}` +
        (plan.label ? ` @${plan.label.x},${plan.label.y}` : "")
    })
    renderStateGridText(drawing.grid)
      .split("\n")
      .forEach((row, index) => {
        out[`row:${index}`] = row
      })
    return out
  } catch (error) {
    return { error: String(error) }
  }
}

// The shared diagrams, three in ten drawn with another border, the line head, or a width to fold at.
export function generateStyled(rand: () => number): string {
  const source = generate(rand)
  if (rand() >= 0.3) return source
  const border = ["rounded", "single", "double", "heavy"][Math.floor(rand() * 4)]
  const head = rand() < 0.5 ? "filled" : "line"
  const width = rand() < 0.5 ? String(20 + Math.floor(rand() * 60)) : ""
  return `%%style ${border} ${head} ${width}\n${source}`
}

if (import.meta.main) await runHarness(generateStyled, summarize)
