// pinned.py's harness for merman's state routing and drawing: the shared random state diagrams, drawn with random
// options, each summarized by the tests' own `drawing-summary.ts` (its routes and its drawn rows), or as an error
// where it shows a known wrong drawing (`state-defects.ts`). Copied into the package root as `.pinned/`, so `../src`
// is the planted copy.
import { packageRoot, runHarness } from "./cli"
import { stateDefects } from "./state-defects"
import { generate } from "./state-gen"

const { createStateDiagramDrawing } = await import(`${packageRoot}/src/state/drawing.ts`)
const { parseMermaidStateDiagram } = await import(`${packageRoot}/src/state/parser.ts`)
const { summary } = await import(`${packageRoot}/test/state/drawing-summary.ts`)

export function summarize(input: string): Record<string, unknown> {
  try {
    const gap = Number(input.match(/^%%gap (\d+)$/m)?.[1] ?? 5)
    const style = input.match(/^%%style (\w+) (\w+) (\d*)$/m)
    const diagram = parseMermaidStateDiagram(input)
    const options = {
      minStateGap: gap,
      ...(style
        ? {
            borderStyle: style[1] as "single",
            arrowHeadStyle: style[2] as "line",
          }
        : {}),
      ...(style?.[3] ? { layoutMaxWidth: Number(style[3]) } : {}),
    }
    const defects = stateDefects(diagram, options)
    if (defects.length > 0) return { error: `defect: ${defects.join(", ")}` }
    return summary(createStateDiagramDrawing(diagram, options))
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
