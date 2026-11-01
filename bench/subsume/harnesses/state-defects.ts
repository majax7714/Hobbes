// The state harnesses' check for the fork's known kinds of wrong drawing, so pinned.py never keeps an input that
// shows one as a case "pinned as observed": laid out and drawn, no two composites may cross (overlap with neither
// inside the other), no state or composite may sit outside its own composite, and no route may pass through a
// state's box (a route's first point, its departure on its own source, aside). Returns the kinds found.
import { type Box, inside, overlap } from "./boxes"
import { packageRoot } from "./cli"

const { createStateDiagramDrawing } = await import(`${packageRoot}/src/state/drawing.ts`)
const { createStateDiagramLayout } = await import(`${packageRoot}/src/state/layout.ts`)
const { prepareVisibleStateDiagram } = await import(`${packageRoot}/src/state/visible-model.ts`)

type Layout = { bounds: Map<string, Box>; compositeBounds: Map<string, Box> }
type Diagram = { states: { id: string; parentId?: string }[]; composites: { id: string; parentId?: string }[] }


export function boxDefects(diagram: Diagram, layout: Layout): string[] {
  const found: string[] = []
  for (const item of [...diagram.states, ...diagram.composites]) {
    const box = layout.compositeBounds.get(item.id) ?? layout.bounds.get(item.id)
    const outer = item.parentId ? layout.compositeBounds.get(item.parentId) : undefined
    if (box && outer && !inside(box, outer)) found.push("outside its composite")
  }
  const composites = [...layout.compositeBounds.values()]
  composites.forEach((a, index) => {
    for (const b of composites.slice(index + 1))
      if (overlap(a, b) && !inside(a, b) && !inside(b, a)) found.push("composites cross")
  })
  return found
}

export function stateDefects(diagram: unknown, options: { minStateGap: number }): string[] {
  const visible = prepareVisibleStateDiagram(diagram)
  const found = boxDefects(visible, createStateDiagramLayout(visible, { minStateGap: options.minStateGap }))
  const drawing = createStateDiagramDrawing(diagram, options)
  found.push(...boxDefects(drawing.diagram, drawing.layout))
  found.push(...routeDefects(drawing.layout, drawing.transitionPlans))
  return [...new Set(found)].sort()
}

type Plan = { path: [number, number][]; route: { transition: { from: string } } }

export function routeDefects(layout: Layout, plans: readonly Plan[]): string[] {
  const found: string[] = []
  const states = [...layout.bounds.values()].filter((box: Box) => !layout.compositeBounds.has(box.id) && box.width > 1)
  for (const plan of plans)
    plan.path.forEach(([x, y], index) => {
      for (const box of states)
        if (overlap({ id: "", left: x, top: y, width: 1, height: 1 }, box))
          if (index > 0 || box.id !== plan.route.transition.from) found.push("route through a state")
    })
  return found
}
