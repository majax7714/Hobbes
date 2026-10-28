// A level view (DEC-014) as a graph to lay out and draw (DEC-019).
//
// `elkGraph` turns a view's boxes and edges into ELK's input: one node per
// box, sized from its text, and one edge per link. ELK's layered layout
// puts callers above what they use and routes edges as splines. `toFlow`
// turns ELK's result into React Flow nodes and edges, keeping each edge's
// curve and the point halfway along it, where its link count goes. Counts
// are not ELK labels: those add layers and make a view a third taller.
// Architecture views (DEC-020) get taller cards with summaries, and ELK
// breaks cycles where hobbes.architecture set links against the layers.
// No DOM here, so node can test it.

export const ORDERED = new Set(["flow", "entries"]); // views drawn as numbered lists
export const GROUPS = new Set(["prefix", "more", "group", "entries", "files"]); // boxes standing for several things
export const ARCH = new Set(["system", "components", "pipeline"]); // architecture graph view kinds (DEC-020)

const CHAR = 7.6, SMALL = 6.2, PAD = 30, MIN_W = 150, MAX_W = 300, BOX_H = 66;
export const SPARSE = 12; // views with at most this many edges show every count

export const LAYOUT = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.edgeRouting": "SPLINES",
  "elk.spacing.nodeNode": "32",
  "elk.layered.spacing.nodeNodeBetweenLayers": "56",
  "elk.spacing.edgeNode": "18",
  "elk.spacing.edgeEdge": "12",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
  "elk.spacing.componentComponent": "40",
  "elk.aspectRatio": "3", // unlinked boxes pack into wide rows, not a tall column
  "elk.padding": "[top=24,left=24,bottom=24,right=24]",
};

export const LAYOUT_ARCH = {
  ...LAYOUT,
  "elk.layered.cycleBreaking.strategy": "MODEL_ORDER", // boxes come sorted by level: links against it break cycles
  "elk.spacing.nodeNode": "40",
  "elk.layered.spacing.nodeNodeBetweenLayers": "64",
};

export const total = (e) => (e.imports || 0) + (e.calls || 0) + (e.uses || 0);
export const counts = (c) => {
  const parts = ["imports", "calls", "uses"].filter((k) => c[k]).map((k) => `${c[k]} ${k}`);
  if (c.starts) parts.push(`${c.starts} entry point${c.starts === 1 ? "" : "s"}`);
  if (c.names) parts.push(c.names.join(", "));
  return parts.join(", ");
};
/** Links drawn as dependencies (with counts), not entry or outside links. */
export const isDependency = (e) => total(e) > 0;
/** Links to outside systems stay out of the layout (they would tie every part
 * into one wide layer); the page draws them only on focus. Outside systems
 * go in a row below the rest (``placeBelow``). */
export const laidOutLink = (e) => !e.touches;
const laidOutBox = (b) => b.kind !== "outside";
const BELOW_GAP = 72, ROW_GAP = 24;

/** Positions for *boxes* in a row centred under the laid-out graph *laid*. */
export function placeBelow(boxes, laid) {
  const kids = laid.children || [];
  const bottom = kids.reduce((m, c) => Math.max(m, c.y + c.height), 0);
  const left = kids.reduce((m, c) => Math.min(m, c.x), Infinity);
  const right = kids.reduce((m, c) => Math.max(m, c.x + c.width), -Infinity);
  const sizes = boxes.map(archSize);
  const width = sizes.reduce((w, s) => w + s.width, 0) + ROW_GAP * Math.max(0, boxes.length - 1);
  let x = kids.length ? (left + right) / 2 - width / 2 : 24;
  const y = kids.length ? bottom + BELOW_GAP : 24;
  return boxes.map((b, i) => {
    const at = { id: b.id, x, y, ...sizes[i] };
    x += sizes[i].width + ROW_GAP;
    return at;
  });
}
export const strokeWidth = (e) => 1.2 + Math.min(3, Math.log2(1 + total(e)) / 2);

const ARCH_W = 264, ARCH_H = 108, ARCH_SHORT = 80, SMALL_H = 54;

/** An architecture card's size: wide cards, taller with a summary; entry
 * points and outside systems are small. */
export function archSize(box) {
  if (box.kind === "door" || box.kind === "outside" || box.kind === "dispatch") {
    const width = Math.max((box.label || "").length * CHAR, 90) + PAD + 24;
    return { width: Math.round(Math.min(MAX_W, Math.max(130, width))), height: SMALL_H };
  }
  return { width: ARCH_W, height: box.summary ? ARCH_H : ARCH_SHORT };
}

export function boxSize(box) {
  const label = (box.label || "").length + (box.root ? 2 : 0);
  const width = Math.max(label * CHAR, (box.detail || "").length * SMALL) + PAD;
  return { width: Math.round(Math.min(MAX_W, Math.max(MIN_W, width))), height: BOX_H };
}

/** The edges ELK and React Flow can draw: both ends in the view, no loops. */
export function drawable(view) {
  const ids = new Set(view.boxes.map((b) => b.id));
  return view.edges.filter((e) => ids.has(e.from) && ids.has(e.to) && e.from !== e.to);
}

export const edgeId = (e) => `${e.from}->${e.to}`;

export function elkGraph(view) {
  const ordered = [...view.boxes].sort((a, b) => b.level - a.level || a.label.localeCompare(b.label));
  const arch = ARCH.has(view.kind);
  return {
    id: "root",
    layoutOptions: arch ? LAYOUT_ARCH : LAYOUT,
    children: ordered.filter(laidOutBox).map((b) => ({ id: b.id, ...(arch ? archSize(b) : boxSize(b)) })),
    edges: drawable(view).filter(laidOutLink).map((e) => ({ id: edgeId(e), sources: [e.from], targets: [e.to] })),
  };
}

/** React Flow nodes and edges from ELK's laid-out graph. */
export function toFlow(view, laid, views) {
  const at = new Map(laid.children.map((c) => [c.id, c]));
  for (const c of placeBelow(view.boxes.filter((b) => !laidOutBox(b)), laid)) at.set(c.id, c);
  const routed = new Map((laid.edges || []).map((e) => [e.id, e]));
  const nodes = view.boxes.map((b) => {
    const c = at.get(b.id);
    return {
      id: b.id, type: "box", position: { x: c.x, y: c.y }, width: c.width, height: c.height,
      data: { box: b, opens: b.view != null && b.view in views, arch: ARCH.has(view.kind) },
    };
  });
  const edges = drawable(view).map((e) => {
    const r = routed.get(edgeId(e));
    const section = r && r.sections && r.sections[0];
    const points = section ? [section.startPoint, ...(section.bendPoints || []), section.endPoint]
      : laidOutLink(e) ? null : direct(at.get(e.from), at.get(e.to));
    return {
      id: edgeId(e), source: e.from, target: e.to, type: "routed",
      data: { link: e, points, arch: ARCH.has(view.kind),
        label: points && isDependency(e) ? { ...halfway(points), text: String(total(e)) } : null },
    };
  });
  return { nodes, edges };
}

/** A curve from the bottom of box *a* to the top of box *b* (or the other
 * way when *b* is above), for links ELK did not route. */
export function direct(a, b) {
  const down = b.y >= a.y + a.height;
  const p0 = { x: a.x + a.width / 2, y: down ? a.y + a.height : a.y };
  const p3 = { x: b.x + b.width / 2, y: down ? b.y : b.y + b.height };
  const bend = Math.max(30, Math.abs(p3.y - p0.y) / 2) * (down ? 1 : -1);
  return [p0, { x: p0.x, y: p0.y + bend }, { x: p3.x, y: p3.y - bend }, p3];
}

/** The box ids next to *id* in the view (with *id*), for focus. */
export function neighbours(view, id) {
  const near = new Set([id]);
  for (const e of view.edges) {
    if (e.from === id) near.add(e.to);
    if (e.to === id) near.add(e.from);
  }
  return near;
}

/** ELK's spline points as an SVG path: cubic Béziers from the start, three
 * points each; any other count is drawn as a polyline with rounded corners. */
export function curvePath(points) {
  if (!isCubic(points)) return roundedPath(points);
  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length; i += 3) {
    const [a, b, c] = points.slice(i, i + 3);
    d += ` C${a.x},${a.y} ${b.x},${b.y} ${c.x},${c.y}`;
  }
  return d;
}

/** The point halfway along the curve (or polyline) through *points*. */
export function halfway(points) {
  const line = isCubic(points) ? sampled(points) : points;
  const lengths = [0];
  for (let i = 1; i < line.length; i++) lengths.push(lengths[i - 1] + dist(line[i - 1], line[i]));
  const half = lengths[lengths.length - 1] / 2;
  const i = Math.max(1, lengths.findIndex((l) => l >= half));
  const span = lengths[i] - lengths[i - 1] || 1;
  return toward(line[i - 1], line[i], ((half - lengths[i - 1]) / span) * dist(line[i - 1], line[i]));
}

const isCubic = (points) => points.length >= 4 && (points.length - 1) % 3 === 0;

function sampled(points, steps = 12) {
  const out = [points[0]];
  for (let i = 1; i < points.length; i += 3) {
    const p0 = points[i - 1], [p1, p2, p3] = points.slice(i, i + 3);
    for (let s = 1; s <= steps; s++) {
      const t = s / steps, u = 1 - t;
      const w = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t];
      out.push({ x: w[0] * p0.x + w[1] * p1.x + w[2] * p2.x + w[3] * p3.x,
        y: w[0] * p0.y + w[1] * p1.y + w[2] * p2.y + w[3] * p3.y });
    }
  }
  return out;
}

/** An SVG path through *points* with rounded corners. */
export function roundedPath(points, radius = 8) {
  if (points.length < 2) return "";
  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const p = points[i - 1], q = points[i], n = points[i + 1];
    const r = Math.min(radius, dist(p, q) / 2, dist(q, n) / 2);
    const a = toward(q, p, r), b = toward(q, n, r);
    d += ` L${a.x},${a.y} Q${q.x},${q.y} ${b.x},${b.y}`;
  }
  const last = points[points.length - 1];
  return d + ` L${last.x},${last.y}`;
}

/** *points* with the last one pulled back *by* along the last segment, so a
 * line stops where its arrow head starts. */
export function trimEnd(points, by) {
  const tip = points[points.length - 1], from = points[points.length - 2];
  const len = dist(from, tip);
  if (len <= by) return points;
  return [...points.slice(0, -1), toward(tip, from, by)];
}

/** A small triangle at the end of *points*, pointing along the last segment. */
export function arrowHead(points, size = 7) {
  const tip = points[points.length - 1], from = points[points.length - 2];
  const len = dist(from, tip) || 1;
  const ux = (tip.x - from.x) / len, uy = (tip.y - from.y) / len;
  const bx = tip.x - ux * size, by = tip.y - uy * size;
  const w = size * 0.55;
  return `M${tip.x},${tip.y} L${bx - uy * w},${by + ux * w} L${bx + uy * w},${by - ux * w} Z`;
}

const dist = (p, q) => Math.hypot(q.x - p.x, q.y - p.y);
const toward = (from, to, r) => {
  const len = dist(from, to) || 1;
  return { x: from.x + ((to.x - from.x) * r) / len, y: from.y + ((to.y - from.y) * r) / len };
};
