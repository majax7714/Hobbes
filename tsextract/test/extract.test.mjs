// Tests for the facts extractor (ADR-021). Zero dev dependencies: run
// with `npm test` (node --test). Fixtures are built in temp dirs so the
// suite exercises real discovery and real checker resolution.

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  discoverFiles,
  externalName,
  extractRepo,
  isTestFile,
  resolveRelative,
} from "../extract.mjs";

function makeRepo(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "tsextract-"));
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content);
  }
  return root;
}

function byPath(facts, rel) {
  const found = facts.files.find((f) => f.path === rel);
  assert.ok(found, `${rel} missing from facts (${facts.files.map((f) => f.path)})`);
  return found;
}

test("discoverFiles finds TS/JS extensions and prunes junk dirs", () => {
  const root = makeRepo({
    "src/a.ts": "",
    "src/b.jsx": "",
    "c.mjs": "",
    "node_modules/x/d.js": "",
    "dist/e.js": "",
    ".hidden/f.ts": "",
    "readme.md": "",
  });
  assert.deepEqual(discoverFiles(root), ["c.mjs", "src/a.ts", "src/b.jsx"]);
});

test("externalName: builtins kept under node:, packages kept, relatives null", () => {
  // ADR-038: builtins are dependencies too, one node per module however
  // the import is spelled, and never sharing a node with an npm package.
  assert.equal(externalName("node:test"), "node:test");
  assert.equal(externalName("fs/promises"), "node:fs");
  assert.equal(externalName("fs"), "node:fs");
  assert.equal(externalName("node:fs"), "node:fs");
  assert.equal(externalName("./local.js"), null);
  assert.equal(externalName("express"), "express");
  assert.equal(externalName("@nestjs/common"), "@nestjs/common");
  assert.equal(externalName("lodash/get"), "lodash");
});

test("resolveRelative tries extensions and index files", () => {
  const files = new Set(["src/a.js", "src/lib/index.ts", "src/plain.mjs"]);
  assert.equal(resolveRelative("src/main.js", "./a", files), "src/a.js");
  assert.equal(resolveRelative("src/main.js", "./a.js", files), "src/a.js");
  assert.equal(resolveRelative("src/main.js", "./lib", files), "src/lib/index.ts");
  assert.equal(resolveRelative("src/main.js", "./gone", files), null);
  assert.equal(resolveRelative("src/main.js", "express", files), null);
});

test("isTestFile conventions", () => {
  assert.ok(isTestFile("tests/flow.test.mjs"));
  assert.ok(isTestFile("src/x.spec.ts"));
  assert.ok(isTestFile("src/__tests__/y.js"));
  assert.ok(!isTestFile("src/latest.js"));
});

test("imports: named/default/namespace, re-exports, require, dynamic", () => {
  const root = makeRepo({
    "src/util.js": "export function helper() { return 1; }\nexport default helper;\n",
    "src/extra.js": "export const extra = 1;\n",
    "src/main.js": [
      'import def, { helper } from "./util.js";',
      'import * as util from "./util.js";',
      'import express from "express";',
      'import fs from "node:fs";',
      'export { extra } from "./extra.js";',
      'const lazy = () => import("./extra.js");',
      "def(); helper(); util.helper(); lazy();",
    ].join("\n"),
    "src/legacy.cjs": 'const util = require("./util.js");\nconst lodash = require("lodash");\n',
  });
  const facts = extractRepo(root);
  const main = byPath(facts, "src/main.js");
  const resolved = main.imports.filter((i) => i.resolved);
  assert.deepEqual(
    resolved.map((i) => [i.specifier, i.resolved]),
    [
      ["./util.js", "src/util.js"],
      ["./util.js", "src/util.js"],
      ["./extra.js", "src/extra.js"],
      ["./extra.js", "src/extra.js"],
    ]
  );
  assert.deepEqual(resolved[0].names, ["def", "helper"]);
  assert.deepEqual(
    main.imports.filter((i) => i.external).map((i) => i.external),
    ["express", "node:fs"]
  ); // builtins kept as externals under node: (ADR-038)
  const legacy = byPath(facts, "src/legacy.cjs");
  assert.deepEqual(
    legacy.imports.map((i) => [i.specifier, i.resolved ?? i.external]),
    [
      ["./util.js", "src/util.js"],
      ["lodash", "lodash"],
    ]
  );
});

test("symbols: functions, classes, methods, arrow consts", () => {
  const root = makeRepo({
    "src/shapes.ts": [
      "export function area(r: number) { return r * r; }",
      "export class Circle {",
      "  radius = 1;",
      "  grow(by: number) { return this.radius + by; }",
      "}",
      "export const shrink = (by: number) => by - 1;",
      "const NAME = 'x';", // plain const: not a symbol
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const symbols = byPath(facts, "src/shapes.ts").symbols;
  assert.deepEqual(
    symbols.map((s) => [s.qualname, s.kind, s.line]),
    [
      ["area", "function", 1],
      ["Circle", "class", 2],
      ["Circle.grow", "method", 4],
      ["shrink", "function", 6],
    ]
  );
});

test("an overloaded function or method starts at its first signature (C-89)", () => {
  // The semantic lane places an overloaded declaration at its first
  // signature; ts-morph hands out the implementation. date-fns
  // (2026-09-03): 54 lane disagreements and below-floor calls on three
  // functions, all this shape.
  const root = makeRepo({
    "src/over.ts": [
      "export function norm(a: string): string;",
      "export function norm(a: number): number;",
      "export function norm(a: any): any {",
      "  return a;",
      "}",
      "export class K {",
      "  m(a: string): string;",
      "  m(a: any): any { return a; }",
      "  plain() { return 1; }",
      "}",
    ].join("\n"),
  });
  const symbols = byPath(extractRepo(root), "src/over.ts").symbols;
  assert.deepEqual(
    symbols.map((s) => [s.qualname, s.line, s.end_line]),
    [
      ["norm", 1, 5],
      ["K", 6, 10],
      ["K.m", 7, 8],
      ["K.plain", 9, 9],
    ]
  );
});

test("calls resolve locally, through imports, and to methods; externals omitted", () => {
  const root = makeRepo({
    "src/util.js": "export function helper() { return 1; }\n",
    "src/main.js": [
      'import { helper } from "./util.js";',
      'import express from "express";',
      "function local() { return helper(); }",
      "function run() { local(); express(); }",
      "run();",
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const calls = byPath(facts, "src/main.js").calls;
  assert.deepEqual(
    calls.map((c) => [c.scope, c.callee_path, c.callee]),
    [
      ["local", "src/util.js", "helper"],
      ["run", "src/main.js", "local"],
      // express() resolves outside the repo. Since V2.M3 it is still a
      // call *site* — the join needs it to match SCIP against, and
      // coverage needs it in the denominator — with a null resolution.
      ["run", null, null],
      [null, "src/main.js", "run"],
    ]
  );
  // ...and it is identifiable, because the site carries the text that was
  // written even when nothing resolved it.
  assert.deepEqual(calls.map((c) => c.name), ["helper", "local", "express", "run"]);
});

test("JSX instantiations are call sites; intrinsics are not (C-24)", () => {
  const root = makeRepo({
    "src/card.tsx": "export function Card() { return <div>hi</div>; }\n",
    "src/ui.tsx": [
      "export const Ui = {",
      "  Button: function Button() { return <span>b</span>; },",
      "};",
    ].join("\n"),
    "src/app.tsx": [
      'import { Card } from "./card.js";',
      'import { Ui } from "./ui.js";',
      "export function App() {",
      "  return (",
      "    <div>",
      "      <Card />",
      "      <Card>x</Card>",
      "      <Ui.Button />",
      "    </div>",
      "  );",
      "}",
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const calls = byPath(facts, "src/app.tsx").calls;
  // <div> never appears: an intrinsic is a string at runtime, not code
  // this repo owns. <Card>x</Card> counts once — a closing tag repeats
  // the name, it does not instantiate again.
  assert.deepEqual(
    calls.map((c) => [c.name, c.callee_path, c.scope]),
    [
      ["Card", "src/card.tsx", "App"],
      ["Card", "src/card.tsx", "App"],
      // A dotted tag is a claimed site with a null fallback resolution:
      // lane A models only top-level symbols (`Ui.Button()` the call
      // resolves to nothing for the same reason), and the join's
      // semantic arm is what can still promote it.
      ["Button", null, "App"],
    ]
  );
  // Two Card sites: the self-closing element and the paired element's
  // opening tag — two instantiations in the rendered tree.
  assert.equal(calls.filter((c) => c.name === "Card").length, 2);
});

test("call sites carry the terminal identifier's name and 0-based column", () => {
  const root = makeRepo({
    "src/util.js": "export function helper() { return 1; }\nexport const obj = { helper };\n",
    "src/main.js": [
      'import { helper, obj } from "./util.js";',
      "helper(); obj.helper();",
    ].join("\n"),
  });
  const calls = byPath(extractRepo(root), "src/main.js").calls;
  // Both sites are named `helper` on one line — the case line-only
  // matching cannot resolve, which is why the IR carries a column.
  assert.deepEqual(
    calls.map((c) => [c.name, c.line, c.col]),
    [["helper", 2, 0], ["helper", 2, 14]]
  );
});

test("a wrapped call chain is positioned on the callee, not the expression", () => {
  const root = makeRepo({
    "src/main.js": ["const obj = { run() {} };", "obj", "  .run();"].join("\n"),
  });
  const calls = byPath(extractRepo(root), "src/main.js").calls;
  // The call expression starts at `obj` on line 2; SCIP puts its
  // occurrence on `run` at line 3. Reporting line 2 would leave the site
  // permanently unjoinable — a silently missing edge, not an error.
  assert.deepEqual(
    calls.map((c) => [c.name, c.line]),
    [["run", 3]]
  );
});

test("env reads: process.env and import.meta.env, both access styles", () => {
  const root = makeRepo({
    "src/config.js": [
      "const a = process.env.API_URL;",
      'const b = process.env["DB_HOST"];',
      "const c = import.meta.env.VITE_KEY;",
      "const d = other.env.NOPE;",
    ].join("\n"),
  });
  const reads = byPath(extractRepo(root), "src/config.js").env_reads;
  assert.deepEqual(
    reads.map((r) => [r.var, r.line]),
    [["API_URL", 1], ["DB_HOST", 2], ["VITE_KEY", 3]]
  );
});

test("express routes: verb + slash literal + express-ish receiver", () => {
  const root = makeRepo({
    "src/server.js": [
      'import express from "express";',
      "const app = express();",
      "function listItems(req, res) { res.send([]); }",
      'app.get("/items", listItems);',
      'app.post("/items", (req, res) => res.send({}));',
      "const map = new Map();",
      'map.get("/not-a-route");',
      'app.get("key", listItems);', // no leading slash: not a route
    ].join("\n"),
  });
  const routes = byPath(extractRepo(root), "src/server.js").routes;
  assert.deepEqual(
    routes.map((r) => [r.method, r.path, r.handler, r.handler_path]),
    [
      ["GET", "/items", "listItems", "src/server.js"],
      ["POST", "/items", "<inline>", null],
    ]
  );
});

test("computed route paths are declined and reported, never guessed (C-5)", () => {
  const root = makeRepo({
    "src/server.js": [
      'import express from "express";',
      "const app = express();",
      'const PREFIX = "/api";',
      "function handler(req, res) { res.send([]); }",
      "app.get(PREFIX, handler);", // computed: declined, recorded
      "app.get(`/items/${PREFIX}`, handler);", // template with hole: same
      'app.get("view engine");', // settings read: neither route nor declined
      'app.get("/ok", handler);', // literal: a route, not a decline
    ].join("\n"),
    "src/items.controller.ts": [
      'import { Controller, Get } from "@nestjs/common";',
      'const SUB = ":id";',
      '@Controller("items")',
      "export class ItemsController {",
      "  @Get(SUB)", // computed sub: declined — NOT reported as "/items"
      "  findOne() { return {}; }",
      '  @Get("plain")',
      "  list() { return {}; }",
      "}",
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const server = byPath(facts, "src/server.js");
  assert.deepEqual(server.routes.map((r) => r.path), ["/ok"]);
  assert.deepEqual(
    server.routes_declined.map((d) => [d.framework, d.line]),
    [["express", 5], ["express", 6]]
  );
  const controller = byPath(facts, "src/items.controller.ts");
  // The computed segment must not be silently dropped into a wrong path.
  assert.deepEqual(controller.routes.map((r) => r.path), ["/items/plain"]);
  assert.deepEqual(
    controller.routes_declined.map((d) => [d.framework, d.line]),
    [["nest", 5]]
  );
});

test("nest routes: controller prefix joins method paths", () => {
  const root = makeRepo({
    "src/items.controller.ts": [
      'import { Controller, Get, Post } from "@nestjs/common";',
      '@Controller("items")',
      "export class ItemsController {",
      '  @Get(":id")',
      "  findOne() { return {}; }",
      "  @Post()",
      "  create() { return {}; }",
      "}",
    ].join("\n"),
  });
  const routes = byPath(extractRepo(root), "src/items.controller.ts").routes;
  assert.deepEqual(
    routes.map((r) => [r.framework, r.method, r.path, r.handler]),
    [
      ["nest", "GET", "/items/:id", "ItemsController.findOne"],
      ["nest", "POST", "/items", "ItemsController.create"],
    ]
  );
});

test("tests: node:test with describe nesting", () => {
  const root = makeRepo({
    "src/flow.js": "export const ok = () => true;\n",
    "tests/flow.test.mjs": [
      'import test from "node:test";',
      'import { ok } from "../src/flow.js";',
      'test("stays ok", () => { ok(); });',
      'test.skip("skipped still inventoried", () => {});',
    ].join("\n"),
  });
  const file = byPath(extractRepo(root), "tests/flow.test.mjs");
  assert.equal(file.test_framework, "node:test");
  assert.deepEqual(
    file.tests.map((t) => [t.qualname, t.line]),
    [["stays ok", 3], ["skipped still inventoried", 4]]
  );
});

test("tests: vitest import and nested describes", () => {
  const root = makeRepo({
    "src/math.spec.ts": [
      'import { describe, it } from "vitest";',
      'describe("math", () => {',
      '  describe("add", () => {',
      '    it("adds", () => {});',
      "  });",
      '  it("subtracts", () => {});',
      "});",
    ].join("\n"),
  });
  const file = byPath(extractRepo(root), "src/math.spec.ts");
  assert.equal(file.test_framework, "vitest");
  assert.deepEqual(
    file.tests.map((t) => t.qualname),
    ["math > add > adds", "math > subtracts"]
  );
});

test("tests: bare globals in a test-named file are honest-unknown", () => {
  const root = makeRepo({
    "src/x.test.js": 'describe("x", () => { it("works", () => {}); });\n',
    "src/notatest.js": 'describe("x", () => { it("nope", () => {}); });\n',
  });
  const facts = extractRepo(root);
  assert.equal(byPath(facts, "src/x.test.js").test_framework, "unknown");
  assert.equal(byPath(facts, "src/x.test.js").tests.length, 1);
  assert.equal(byPath(facts, "src/notatest.js").test_framework, null);
});

test("output is deterministic across runs", () => {
  const files = {
    "src/util.js": "export function helper() { return 1; }\n",
    "src/main.js": 'import { helper } from "./util.js";\nhelper();\n',
  };
  const a = JSON.stringify(extractRepo(makeRepo(files)));
  const b = JSON.stringify(extractRepo(makeRepo(files)));
  assert.equal(a, b);
});

test("calls to nested declarations resolve to nothing (only top-level symbols exist)", () => {
  const root = makeRepo({
    "src/main.js": [
      "export function outer() {",
      "  const inner = () => 1;",
      "  function nested() { return 2; }",
      "  return inner() + nested();",
      "}",
      "outer();",
    ].join("\n"),
  });
  const calls = byPath(extractRepo(root), "src/main.js").calls;
  // They are call sites and are reported as such; what they must never do
  // is carry a resolution, because the symbol they'd point at does not
  // exist in the graph. A null `callee` produces no edge downstream, so
  // the M6 guarantee holds while coverage still counts the site.
  assert.deepEqual(
    calls.map((c) => [c.scope, c.callee]),
    [["outer", null], ["outer", null], [null, "outer"]]
  );
});

test("nested tsconfig zone resolves its own path aliases", () => {
  const root = makeRepo({
    "web/tsconfig.json": JSON.stringify({
      compilerOptions: {
        moduleResolution: "bundler",
        module: "esnext",
        jsx: "react-jsx",
        paths: { "@/*": ["./src/*"] },
      },
    }),
    "web/src/api/auth.ts": "export function login() { return 1; }\n",
    "web/src/app.ts": [
      'import { login } from "@/api/auth";',
      'const lazy = () => import("@/api/auth");',
      "login(); lazy();",
    ].join("\n"),
    "elsewhere/plain.js": 'import { x } from "./other.js";\n',
    "elsewhere/other.js": "export const x = 1;\n",
  });
  const facts = extractRepo(root);
  assert.deepEqual(facts.tsconfigs, ["web/tsconfig.json"]);
  const app = byPath(facts, "web/src/app.ts");
  assert.deepEqual(
    app.imports.map((i) => [i.specifier, i.resolved]),
    [
      ["@/api/auth", "web/src/api/auth.ts"],
      ["@/api/auth", "web/src/api/auth.ts"], // dynamic import, alias-resolved
    ]
  );
  // Ordered by position now, not by callee name: both sit on line 3.
  assert.deepEqual(
    app.calls.map((c) => [c.callee_path, c.callee]),
    [
      ["web/src/api/auth.ts", "login"],
      ["web/src/app.ts", "lazy"],
    ]
  );
  // The zone-less files still resolve through the default project.
  assert.equal(byPath(facts, "elsewhere/plain.js").imports[0].resolved, "elsewhere/other.js");
});

test("unresolved alias specifiers never become external packages", () => {
  const root = makeRepo({
    "src/app.ts": 'import { x } from "@/nowhere";\nimport { y } from "~/also/nowhere";\n',
  });
  assert.deepEqual(byPath(extractRepo(root), "src/app.ts").imports, []);
});

test("call-initialized consts are symbols; calls to them stay consistent", () => {
  const root = makeRepo({
    "src/store.ts": [
      "function create(fn: any) { return fn; }",
      "export const useStore = create(() => ({ n: 1 }));",
      "export const DATA = { n: 1 };", // plain data const: not a symbol
      'const fs = require("node:fs");', // module handle: not a symbol
    ].join("\n"),
    "src/page.ts": [
      'import { useStore, DATA } from "./store.js";',
      "export function Page() { return useStore(); }",
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const store = byPath(facts, "src/store.ts");
  assert.deepEqual(
    store.symbols.map((s) => [s.qualname, s.kind]),
    [["create", "function"], ["useStore", "const"]]
  );
  const calls = byPath(facts, "src/page.ts").calls;
  assert.deepEqual(
    calls.map((c) => [c.scope, c.callee_path, c.callee]),
    [["Page", "src/store.ts", "useStore"]]
  );
});

test("cross-zone relative imports resolve against the repo file set (C-12)", () => {
  // Two zones, each its own tsconfig — separate programs, so the
  // checker cannot see across. A relative path is unambiguous anyway.
  const root = makeRepo({
    "packages/a/tsconfig.json": "{}",
    "packages/a/src/main.ts": 'import { util } from "../../b/src/util";\nutil();\n',
    "packages/b/tsconfig.json": "{}",
    "packages/b/src/util.ts": "export function util() { return 1; }\n",
  });
  const facts = extractRepo(root);
  const main = byPath(facts, "packages/a/src/main.ts");
  assert.deepEqual(
    main.imports.map((i) => [i.specifier, i.resolved]),
    [["../../b/src/util", "packages/b/src/util.ts"]]
  );
});

test("workspace package names resolve to the owning zone's entry (C-12)", () => {
  const root = makeRepo({
    "packages/ui/package.json": '{"name": "@app/ui", "main": "src/index.ts"}',
    "packages/ui/tsconfig.json": "{}",
    "packages/ui/src/index.ts": "export function Button() { return 1; }\n",
    "packages/ui/src/card.ts": "export function Card() { return 2; }\n",
    "packages/app/tsconfig.json": "{}",
    "packages/app/src/main.ts": [
      'import { Button } from "@app/ui";',
      'import { Card } from "@app/ui/src/card";',
      "Button(); Card();",
    ].join("\n"),
  });
  const facts = extractRepo(root);
  const main = byPath(facts, "packages/app/src/main.ts");
  assert.deepEqual(
    main.imports.map((i) => [i.specifier, i.resolved]),
    [
      ["@app/ui", "packages/ui/src/index.ts"],
      ["@app/ui/src/card", "packages/ui/src/card.ts"],
    ]
  );
});

test("imports that resolve nowhere are surfaced, never guessed (C-12 floor)", () => {
  const root = makeRepo({
    "tsconfig.json": "{}",
    "src/main.ts": 'import { x } from "@/nowhere";\nimport { y } from "./missing";\nx(); y();\n',
  });
  const facts = extractRepo(root);
  assert.deepEqual(byPath(facts, "src/main.ts").imports, []);
  const record = facts.errors.find((e) => e.stage === "imports-unresolved");
  assert.ok(record, "the absence must be recorded");
  assert.equal(record.path, "src/main.ts");
  assert.match(record.message, /2 import\(s\) resolved nowhere/);
  assert.match(record.message, /@\/nowhere/);
});

test("a workspace name that matches no file resolves to nothing", () => {
  // resolveWorkspace never invents: the package exists but its entry
  // does not, so the import surfaces as unresolved instead of pointing
  // at a directory.
  const root = makeRepo({
    "packages/ghost/package.json": '{"name": "ghost", "main": "dist/out.js"}',
    "src/main.ts": 'import g from "ghost";\ng();\n',
  });
  const facts = extractRepo(root);
  const main = byPath(facts, "src/main.ts");
  // Falls through to externalName — "ghost" is a plausible npm package,
  // which is the honest classification when its source is not here.
  assert.deepEqual(
    main.imports.map((i) => [i.specifier, i.external]),
    [["ghost", "ghost"]]
  );
});

test("asset imports are not reported as resolution failures", () => {
  // `./index.css` is a real import of a file the graph deliberately
  // does not model — reporting it as "resolved nowhere" on every ingest
  // would bury the real C-12 records under noise.
  const root = makeRepo({
    "tsconfig.json": "{}",
    "src/main.ts": 'import "./index.css";\nimport logo from "./logo.svg";\nexport const x = logo;\n',
  });
  const facts = extractRepo(root);
  assert.equal(facts.errors.filter((e) => e.stage === "imports-unresolved").length, 0);
});

test("origins: unresolved callees say where their declarations live (v4)", () => {
  const root = makeRepo({
    "src/state.ts": [
      "export function makePair() { return [1, (v: number) => v] as const; }",
    ].join("\n"),
    "src/app.tsx": [
      "import { makePair } from './state';",
      "export function App() {",
      "  const [count, setCount] = makePair();", // local destructured binding
      "  const bump = () => setCount(1);",       // -> origin local
      "  const big = Math.max(1, 2);",           // ambient lib -> external
      "  return bump() + big + undeclared();",   // no symbol -> origin null
      "}",
    ].join("\n"),
  });
  const calls = byPath(extractRepo(root), "src/app.tsx").calls;
  const by = (name) => calls.find((c) => c.name === name);
  assert.equal(by("setCount").origin, "local");
  assert.equal(by("setCount").callee, null);
  assert.equal(by("max").origin, "external");
  assert.equal(by("undeclared").origin, null);
  // a resolved callee answers through callee/callee_path, never origin
  assert.equal(by("makePair").origin, null);
  assert.equal(by("makePair").callee, "makePair");
});

test("origins: a binding below the modelled vocabulary is `local`", () => {
  const root = makeRepo({
    "src/lib.ts": [
      "function helper() { return 1; }",
      "export const use = () => helper();", // module-level fn -> resolves
      "export function wrap() {",
      "  const inner = () => 2;",
      "  return inner();",                  // local binding -> origin local
      "}",
    ].join("\n"),
  });
  const calls = byPath(extractRepo(root), "src/lib.ts").calls;
  const inner = calls.find((c) => c.name === "inner");
  assert.equal(inner.origin, "local");
  assert.equal(inner.callee, null);
});
