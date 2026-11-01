import type { StateDiagramLayout } from "../../src/state/layout"

/**
 * One entry per placed thing: each state's left,top width×height and centre, each composite's box, each note's
 * box and connector points. Keyed so a pinned case can assert only the entries its faults change.
 */
export function summary(layout: StateDiagramLayout): Record<string, string> {
  const box = (b: { left: number; top: number; width: number; height: number; centerX: number; centerY: number }) =>
    `${b.left},${b.top} ${b.width}x${b.height} c${b.centerX},${b.centerY}`
  const out: Record<string, string> = {}
  for (const b of layout.bounds.values()) if (!layout.compositeBounds.has(b.id)) out[b.id] = box(b)
  for (const b of layout.compositeBounds.values()) out[`[${b.id}]`] = box(b)
  for (const b of layout.noteBounds) {
    out[`{${b.id}}`] = `${box(b)} ${(b.connector?.points ?? []).map((p) => `${p.x},${p.y}`).join(" ")}`
  }
  return out
}
