import type { FlowchartLayout } from "../../src/flowchart/layout"

/**
 * One line per layout: each node's left,top width×height and centre, each frame's box and title side, each
 * route's points and label point, then the canvas size and direction. Pinned layouts compare this whole.
 */
export function summary(layout: FlowchartLayout): string {
  const nodes = [...layout.bounds.values()].map(
    (b) => `${b.id} ${b.left},${b.top} ${b.width}x${b.height} c${b.centerX},${b.centerY}`,
  )
  const frames = [...layout.subgraphBounds.values()].map(
    (b) => `[${b.id} ${b.left},${b.top} ${b.width}x${b.height} c${b.centerX},${b.centerY} ${b.labelSide}]`,
  )
  const routes = layout.routes.map(
    (r) =>
      `${r.edge.from}>${r.edge.to} ${r.points.map((p) => `${p.x},${p.y}`).join(" ")}` +
      (r.labelPoint ? ` @${r.labelPoint.x},${r.labelPoint.y}` : "") +
      (r.labelAxis ? ` ${r.labelAxis}` : ""),
  )
  return [...nodes, ...frames, ...routes, `${layout.width}x${layout.height} ${layout.diagram.direction}`].join("; ")
}
