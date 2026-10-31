// pinned.py's harness for merman's state layout, laid out as the drawing does (from the visible model): random state diagrams (every direction, nested composites with
// markers, choices, self loops, labels, notes), each summarized by the tests' own `layout-summary.ts`, so a
// pinned case asserts the same entries. Copied into the package root as `.pinned/`, so `../src` is the planted copy.
import { packageRoot, runHarness } from "./cli"
import { generate } from "./state-gen"

const { createStateDiagramLayout } = await import(`${packageRoot}/src/state/layout.ts`)
const { parseMermaidStateDiagram } = await import(`${packageRoot}/src/state/parser.ts`)
const { prepareVisibleStateDiagram } = await import(`${packageRoot}/src/state/visible-model.ts`)
const { summary } = await import(`${packageRoot}/test/state/layout-summary.ts`)

export function summarize(input: string): Record<string, unknown> {
  try {
    const gap = Number(input.match(/^%%gap (\d+)$/m)?.[1] ?? 5)
    return summary(
      createStateDiagramLayout(prepareVisibleStateDiagram(parseMermaidStateDiagram(input)), { minStateGap: gap }),
    )
  } catch (error) {
    return { error: String(error) }
  }
}

if (import.meta.main) await runHarness(generate, summarize)
