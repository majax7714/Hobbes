import { createStateDiagramDrawing } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { renderStateGridText } from "../../src/state/render-grid"

/**
 * The smallest diagram found whose side rail starts and ends on one row (P0x to P1x, across two composites):
 * drawn top to bottom, the rail loop never ended and took all memory (22 GB on the host that found it). Run as
 * a child process by `side-rail.test.ts`, so a return of that loop fails on a time limit instead of hanging.
 */
export const SIDE_RAIL_SOURCE = [
  "stateDiagram-v2",
  "state P0 {",
  "[*] --> P0x",
  "}",
  'state "A long composite title" as P1 {',
  "[*] --> P1x",
  "}",
  "[*] --> B",
  "P0x --> P1 : retry",
  "B --> P1 : a<br>b",
  "B --> P0 : retry",
].join("\n")

export function drawSideRailCase(options: { direction?: "TB"; layoutMaxWidth?: number }): string {
  const drawing = createStateDiagramDrawing(parseMermaidStateDiagram(SIDE_RAIL_SOURCE), options)
  const routes = drawing.transitionPlans.map(
    (plan) => `${plan.route.transition.from}>${plan.route.transition.to} ${plan.route.kind} ${plan.path.length}`,
  )
  return [...routes, renderStateGridText(drawing.grid)].join("\n")
}

if (import.meta.main) {
  const options = process.argv[2] === "width" ? { layoutMaxWidth: 53 } : { direction: "TB" as const }
  console.log(drawSideRailCase(options))
}
