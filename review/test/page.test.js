// Tests for the review page's browser-free logic (src/page.js): links,
// titles, counts and hash routing. The page's rendering (src/main.jsx) is
// checked by eye (DEC-019).

import { test } from "node:test";
import assert from "node:assert/strict";
import { docHref, imageSource, linkAttributes, many, opensView, parseHash, tabOrder, viewHash, viewTitle,
  vscodeLink } from "../src/page.js";

const TABS = {
  a: { name: "Architecture", views: { "arch:repo": {} }, root: "arch:repo" },
  v: { name: "Code map", views: { "": {}, "app/cli.py": {} }, root: "" },
  d: { name: "Docs", root: "README.md" },
  r: { name: "Agents", root: "" },
};
const PLACES = { tabs: TABS, docPaths: new Set(["README.md", "docs/a b.md"]), roleNames: new Set(["lead"]) };

test("a VS Code link opens the repo path, encoded, at its line when there is one", () => {
  assert.equal(vscodeLink("/home/me/repo", "src/a b.py", 12), "vscode://file//home/me/repo/src/a%20b.py:12");
  assert.equal(vscodeLink("/r", "x.py"), "vscode://file//r/x.py");
});

test("a view's title is its own, else its id, else the repo; a box opens only a view the page holds", () => {
  const views = { app: { title: "The app" } };
  assert.deepEqual([viewTitle("app", views), viewTitle("gone", views), viewTitle("", views)], ["The app", "gone", "(repo)"]);
  assert.deepEqual([opensView({ view: "app" }, views), opensView({ view: "gone" }, views), opensView({}, views), opensView(null, views)],
    [true, false, false, false]);
  assert.deepEqual([many(1, "module"), many(0, "module"), many(2, "test")], ["1 module", "0 modules", "2 tests"]);
});

test("the tabs are architecture, code map, docs, agents, each only when it has a root", () => {
  assert.deepEqual(tabOrder(TABS), ["a", "v", "d", "r"]);
  assert.deepEqual(tabOrder({ ...TABS, a: { views: {}, root: null }, d: { root: null } }), ["v", "r"]);
});

test("a hash names a tab and a view the page holds; anything else falls back to the first tab's root", () => {
  assert.deepEqual(parseHash("#v=app%2Fcli.py", PLACES), { tab: "v", id: "app/cli.py" });
  assert.deepEqual(parseHash("#v=nowhere", PLACES), { tab: "v", id: "" });
  assert.deepEqual(parseHash("#a=arch%3Arepo", PLACES), { tab: "a", id: "arch:repo" });
  assert.deepEqual(parseHash("", PLACES), { tab: "a", id: "arch:repo" });
  assert.deepEqual(parseHash("#x=1", PLACES), { tab: "a", id: "arch:repo" });
  const noArch = { ...PLACES, tabs: { ...TABS, a: { views: {}, root: null } } };
  assert.deepEqual(parseHash("#a=arch%3Arepo", noArch), { tab: "v", id: "" });
});

test("a docs hash names a document and an anchor, and a roles hash a role, each falling back when unknown", () => {
  assert.deepEqual(parseHash("#d=docs%2Fa%20b.md#Some%20heading", PLACES), { tab: "d", id: "docs/a b.md", anchor: "Some heading" });
  assert.deepEqual(parseHash("#d=missing.md", PLACES), { tab: "d", id: "README.md", anchor: null });
  assert.deepEqual(parseHash("#r=lead", PLACES), { tab: "r", id: "lead" });
  assert.deepEqual(parseHash("#r=nobody", PLACES), { tab: "r", id: "" });
});

test("hashes are written as they are read", () => {
  assert.equal(viewHash("app/cli.py"), "v=app%2Fcli.py");
  assert.equal(viewHash("arch:repo", "a"), "a=arch%3Arepo");
  assert.equal(docHref("docs/a b.md"), "#d=docs%2Fa%20b.md");
  assert.equal(docHref("docs/a b.md", "Some heading"), "#d=docs%2Fa%20b.md#Some%20heading");
  assert.deepEqual(parseHash("#" + viewHash("app/cli.py"), PLACES), { tab: "v", id: "app/cli.py" });
});

test("a document's links open documents and anchors in the Docs tab, repo files in VS Code, outside links in a new tab", () => {
  assert.deepEqual(linkAttributes({ kind: "doc", path: "docs/b.md", anchor: "x" }, "README.md", "/r"), { href: "#d=docs%2Fb.md#x" });
  assert.deepEqual(linkAttributes({ kind: "anchor", anchor: "y" }, "README.md", "/r"), { href: "#d=README.md#y" });
  assert.deepEqual(linkAttributes({ kind: "file", path: "src/a.py", line: 3 }, "README.md", "/r"),
    { href: "vscode://file//r/src/a.py:3", title: "Open in VS Code" });
  assert.deepEqual(linkAttributes({ kind: "external" }, "README.md", "/r"), { target: "_blank", rel: "noopener noreferrer" });
  assert.deepEqual(linkAttributes({ kind: "other" }, "README.md", "/r"), {});
  assert.equal(imageSource({ kind: "file", path: "img/a b.png" }, "/r"), "file:///r/img/a%20b.png");
  assert.equal(imageSource({ kind: "external" }, "/r"), null);
});
