// The box tests the defect checks share: two boxes overlapping, and one wholly inside another.
export type Box = { id: string; left: number; top: number; width: number; height: number }

export const overlap = (a: Box, b: Box) =>
  a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height
export const inside = (a: Box, o: Box) =>
  a.left >= o.left && a.top >= o.top && a.left + a.width <= o.left + o.width && a.top + a.height <= o.top + o.height
