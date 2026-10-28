// Tests for the view-to-graph conversion (src/graph.js, DEC-019, DEC-020),
// with a real ELK layout. The drawing itself is checked by eye.

import { test } from "node:test";
import assert from "node:assert/strict";
import ELK from "elkjs/lib/elk.bundled.js";
import { archSize, arrowHead, boxSize, counts, curvePath, direct, drawable, elkGraph, halfway, neighbours, placeBelow,
  roundedPath, toFlow, trimEnd } from "../src/graph.js";

const VIEW = {
  id: "app", kind: "folder", boxes: [
    { id: "app/cli.py", label: "cli.py", kind: "module", level: 1, detail: "1 module", view: "app/cli.py" },
    { id: "app/util.py", label: "util.py", kind: "module", level: 0, detail: "1 module, 3 tests" },
    { id: "app/db.py", label: "db.py", kind: "module", level: 0, detail: "1 module" },
  ],
  edges: [
    { from: "app/cli.py", to: "app/util.py", imports: 1, calls: 4 },
    { from: "app/cli.py", to: "app/db.py", calls: 1, cycle: true },
    { from: "app/cli.py", to: "elsewhere", calls: 2 },
    { from: "app/db.py", to: "app/db.py", calls: 1 },
  ],
};
const VIEWS = { "app/cli.py": { id: "app/cli.py" } };

test("only edges with both ends in the view, and no loops, are drawn", () => {
  assert.deepEqual(drawable(VIEW).map((e) => e.to), ["app/util.py", "app/db.py"]);
});

test("boxes are sized from their text, within bounds", () => {
  assert.equal(boxSize({ label: "x", detail: "" }).width, 150);
  assert.equal(boxSize({ label: "x".repeat(200), detail: "" }).width, 300);
  const g = elkGraph(VIEW);
  assert.equal(g.children.length, 3);
  assert.equal(g.edges.length, 2);
});

test("ELK puts callers above what they use, and routes every edge", async () => {
  const laid = await new ELK().layout(elkGraph(VIEW));
  const { nodes, edges } = toFlow(VIEW, laid, VIEWS);
  const y = Object.fromEntries(nodes.map((n) => [n.id, n.position.y]));
  assert.ok(y["app/cli.py"] < y["app/util.py"] && y["app/cli.py"] < y["app/db.py"]);
  assert.equal(edges.length, 2);
  for (const e of edges) {
    assert.equal((e.data.points.length - 1) % 3, 0, "spline points come in cubic triples");
    assert.ok(e.data.label && Number.isFinite(e.data.label.x), "a count label on the curve");
  }
  assert.equal(edges.find((e) => e.target === "app/util.py").data.label.text, "5"); // imports and calls together
  assert.equal(nodes.find((n) => n.id === "app/cli.py").data.opens, true);
  assert.equal(nodes.find((n) => n.id === "app/db.py").data.opens, false);
});

test("focus covers a box and its neighbours", () => {
  assert.deepEqual([...neighbours(VIEW, "app/util.py")].sort(), ["app/cli.py", "app/util.py"]);
});

test("paths round their corners and stop short of the arrow head", () => {
  const pts = [{ x: 0, y: 0 }, { x: 0, y: 50 }, { x: 40, y: 50 }];
  assert.match(roundedPath(pts), /^M0,0 L0,42 Q0,50 8,50 L40,50$/);
  assert.deepEqual(trimEnd(pts, 6).at(-1), { x: 34, y: 50 });
  assert.match(arrowHead(pts, 8), /^M40,50 L32,/);
});

test("splines are drawn as cubic Béziers, with the count halfway along", () => {
  const straight = [{ x: 0, y: 0 }, { x: 0, y: 10 }, { x: 0, y: 20 }, { x: 0, y: 30 }];
  assert.equal(curvePath(straight), "M0,0 C0,10 0,20 0,30");
  const mid = halfway(straight);
  assert.ok(Math.abs(mid.x) < 1e-9 && Math.abs(mid.y - 15) < 1e-9);
  assert.deepEqual(halfway([{ x: 0, y: 0 }, { x: 10, y: 0 }]), { x: 5, y: 0 });
});

// An architecture view (DEC-020) as hobbes.architecture writes it: a part
// with its entry points above, a cycle closed by a link against the layers,
// and an outside system the part reaches.
const ARCH_VIEW = {
  id: "arch:", kind: "system", boxes: [
    { id: "door:app", kind: "door", label: "app", level: 3 },
    { id: "app", kind: "folder", label: "app/", level: 2, summary: "The app.", view: "arch:app" },
    { id: "core", kind: "folder", label: "core/", level: 1 },
    { id: "store", kind: "folder", label: "store/", level: 0, summary: "Rows on disk." },
    { id: "outside:storage", kind: "outside", label: "Storage", level: -1 },
  ],
  edges: [
    { from: "door:app", to: "app", starts: 1 },
    { from: "app", to: "core", calls: 4 },
    { from: "core", to: "store", calls: 6 },
    { from: "store", to: "core", calls: 1, cycle: true, against: true },
    { from: "app", to: "outside:storage", touches: 1, names: ["sqlite3"] },
  ],
};

test("architecture cards: taller with a summary, small doors and outside systems", () => {
  assert.equal(archSize({ kind: "folder", summary: "x" }).height > archSize({ kind: "folder" }).height, true);
  assert.equal(archSize({ kind: "door", label: "app" }).height, archSize({ kind: "outside", label: "Files" }).height);
  const g = elkGraph(ARCH_VIEW);
  assert.ok(!g.children.some((c) => c.id === "outside:storage"), "outside systems are placed after the layout");
  assert.ok(!g.edges.some((e) => e.id === "app->outside:storage"), "outside links stay out of the layout");
  assert.equal(g.layoutOptions["elk.layered.cycleBreaking.strategy"], "MODEL_ORDER");
});

test("ELK keeps the layers hobbes set, and outside systems go below", async () => {
  const laid = await new ELK().layout(elkGraph(ARCH_VIEW));
  const { nodes, edges } = toFlow(ARCH_VIEW, laid, { "arch:app": {} });
  const y = Object.fromEntries(nodes.map((n) => [n.id, n.position.y]));
  assert.ok(y["door:app"] < y.app && y.app < y.core && y.core < y.store, "entry, then users above what they use");
  assert.ok(y["outside:storage"] > y.store, "outside systems sit under everything");
  const by = Object.fromEntries(edges.map((e) => [e.id, e.data]));
  assert.equal(by["core->store"].label.text, "6");
  assert.equal(by["door:app->app"].label, null, "entry and outside links carry no count");
  assert.equal(by["app->outside:storage"].points.length, 4, "outside links get a direct curve");
  assert.equal(nodes.find((n) => n.id === "app").data.arch, true);
  assert.equal(counts(ARCH_VIEW.edges[4]), "sqlite3");
  assert.equal(counts(ARCH_VIEW.edges[0]), "1 entry point");
});

test("rows below and direct curves", () => {
  const laid = { children: [{ x: 0, y: 0, width: 200, height: 50 }, { x: 300, y: 100, width: 100, height: 50 }] };
  const row = placeBelow([{ id: "a", kind: "outside", label: "Files" }, { id: "b", kind: "outside", label: "Network" }], laid);
  assert.ok(row.every((r) => r.y > 150) && row[0].x < row[1].x);
  const mid = (row[0].x + row[1].x + row[1].width) / 2;
  assert.ok(Math.abs(mid - 200) < 1, "the row is centred under the graph");
  const up = direct({ x: 0, y: 200, width: 100, height: 50 }, { x: 0, y: 0, width: 100, height: 50 });
  assert.deepEqual([up[0].y, up[3].y], [200, 50], "a box below links from its top to the other's bottom");
});

// The Docs tab's pure parts (src/docs.js, DEC-021).
import { byFolder, linkTarget, render, resolve, slug } from "../src/docs.js";

test("heading anchors follow GitHub's, unique within a document", () => {
  assert.equal(slug("What `hobbes` is (v2)"), "what-hobbes-is-v2");
  assert.equal(slug("Acknowledgements — what Hobbes is built on"), "acknowledgements--what-hobbes-is-built-on");
  const html = render("# Hello, World!\n\n## Hello, World!\n");
  assert.match(html, /<h1 id="h-hello-world">/);
  assert.match(html, /<h2 id="h-hello-world-1">/);
});

test("links go to docs, anchors, repo files or outside", () => {
  const docs = new Set(["README.md", "docs/a.md"]);
  assert.deepEqual(linkTarget("a.md#Top", "docs/x.md", docs), { kind: "doc", path: "docs/a.md", anchor: "Top" });
  assert.deepEqual(linkTarget("../README.md", "docs/x.md", docs), { kind: "doc", path: "README.md", anchor: null });
  assert.deepEqual(linkTarget("#intro", "docs/x.md", docs), { kind: "anchor", anchor: "intro" });
  assert.deepEqual(linkTarget("../src/a.py#L12", "docs/x.md", docs), { kind: "file", path: "src/a.py", line: 12 });
  assert.equal(linkTarget("https://x.org/a.md", "docs/x.md", docs).kind, "external");
  assert.equal(linkTarget("mailto:a@b", "x.md", docs).kind, "external");
  assert.equal(linkTarget("../../out.md", "docs/x.md", docs).kind, "none", "a link out of the repo goes nowhere");
  assert.equal(resolve("docs/x.md", "/README.md"), "README.md");
  assert.equal(resolve("a/b/c.md", "./d/../e.md"), "a/b/e.md");
});

test("docs group by folder in the given order", () => {
  const files = [{ path: "README.md" }, { path: "docs/a.md" }, { path: "docs/b.md" }, { path: "go/README.md" }];
  assert.deepEqual(byFolder(files).map(([f, ds]) => [f, ds.length]), [["", 1], ["docs", 2], ["go", 1]]);
});

test("pipeline steps keep their order top to bottom; dispatch boxes are small", async () => {
  const view = {
    id: "arch:run:x", kind: "pipeline", boxes: [
      { id: "door", kind: "door", label: "app", level: 4 },
      { id: "c", kind: "folder", label: "c/", order: 3, level: 1 },
      { id: "a", kind: "module", label: "a.py", order: 1, level: 3 },
      { id: "b", kind: "folder", label: "b/", order: 2, level: 2 },
      { id: "d", kind: "dispatch", label: "main() dispatches to 3", level: 0 },
    ],
    edges: [{ from: "door", to: "a", starts: 1 }, { from: "a", to: "c", calls: 2 }, { from: "c", to: "b", calls: 1 },
      { from: "b", to: "a", calls: 1, against: true }, { from: "a", to: "d", starts: 3 }],
  };
  assert.equal(archSize({ kind: "dispatch", label: "main() dispatches to 3" }).height, archSize({ kind: "door", label: "x" }).height);
  const { nodes } = toFlow(view, await new ELK().layout(elkGraph(view)), {});
  const y = Object.fromEntries(nodes.map((n) => [n.id, n.position.y]));
  assert.ok(y.door < y.a && y.a <= y.b && y.b <= y.c, "steps run down in their order, even where a later step is called first");
});
