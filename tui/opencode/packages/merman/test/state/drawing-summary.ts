import type { StateTransitionPathPoint, StateTransitionRenderPlan } from "../../src/state/routing"
import { renderStateGridText, type StateGrid } from "../../src/state/render-grid"

/** A path's ends and turning points. */
function corners(path: readonly StateTransitionPathPoint[]): string {
  const kept = path.filter((point, index) => {
    const before = path[index - 1]
    const after = path[index + 1]
    if (!before || !after) return true
    return (before[0] === point[0]) !== (point[0] === after[0])
  })
  return kept.map(([x, y]) => `${x},${y}`).join(" ")
}

/**
 * One entry per transition as drawn (`route:i`: its ends, its route's kind, its corners and its label's top left)
 * and per drawn row (`row:n`). Keyed so a pinned case can assert only the entries its faults change.
 */
export function summary(drawing: {
  grid: StateGrid
  transitionPlans: readonly StateTransitionRenderPlan[]
}): Record<string, string> {
  const out: Record<string, string> = {}
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
}
