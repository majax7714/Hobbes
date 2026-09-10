// shapes.mjs on a built repo: one call per callee shape the bucket reads,
// and the command line producing the same record. Zero dev dependencies
// beyond tsextract's ts-morph: `node --test shapes.test.mjs` here, which
// `shape_test.go` runs.
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { calleeShapes } from "./shapes.mjs";

const LIB = `export function foo(a: number): number;
export function foo(a: string): string;
export function foo(a: any): any { return a; }
export const bar = (x: number) => x;
export class Box {
  run() { return 1; }
  go() { return this.run(); }
  static make() { return new Box(); }
}
export interface Api { load(): void }
`;

const APP = `import { foo, bar, Box, Api } from "./lib";
foo(1);
bar(2);
const b = Box.make();
b.run();
new Box().go();
function inner(cb: () => void) { cb(); }
const api: Api = { load() {} };
api.load();
(() => 1)();
const t = { m: [foo] }; t.m[0](3);
foo(1).toFixed();
`;

function makeRepo() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "shapes-"));
  fs.mkdirSync(path.join(root, "src"));
  fs.writeFileSync(path.join(root, "tsconfig.json"), JSON.stringify({
    compilerOptions: { target: "es2020", module: "commonjs", strict: true },
    include: ["src"],
  }));
  fs.writeFileSync(path.join(root, "src/lib.ts"), LIB);
  fs.writeFileSync(path.join(root, "src/app.ts"), APP);
  return root;
}

const root = makeRepo();
const records = calleeShapes(root);
const app = records.filter((r) => r.path === "src/app.ts");
const at = (line, name) => {
  const found = app.find((r) => r.line === line && r.name === name);
  assert.ok(found, `no record at src/app.ts:${line} ${name} in ${JSON.stringify(app.map((r) => [r.line, r.name]))}`);
  return found;
};

test("an identifier callee carries its declarations through the import alias, and the resolved overload", () => {
  const r = at(2, "foo");
  assert.equal(r.shape, "identifier");
  assert.equal(r.recv, null);
  assert.deepEqual(r.decls.map((d) => [d.kind, d.file, d.line, d.ext]),
    [["function-decl", "src/lib.ts", 1, false], ["function-decl", "src/lib.ts", 2, false], ["function-decl", "src/lib.ts", 3, false]]);
  // tsc's oracle names the signature the call resolves to: the number overload
  assert.deepEqual(r.sigDecl, { kind: "function-decl", file: "src/lib.ts", line: 1 });
  assert.deepEqual([r.line, r.col, r.cline, r.ccol, r.js], [2, 0, 2, 0, false]);
});

test("a variable's kind spells keyword, nesting and initializer", () => {
  assert.equal(at(3, "bar").decls[0].kind, "var:const:top:fn-literal");
});

test("a member callee names the terminal and reads the receiver", () => {
  const make = at(4, "make");
  assert.equal(make.shape, "member");
  assert.equal(make.recv, "ident:class");
  assert.equal(make.decls[0].kind, "method");
  assert.deepEqual([make.line, make.col, make.cline, make.ccol], [4, 14, 4, 10]);
  assert.equal(at(5, "run").recv, "ident:var:const:top:call-result");
  assert.equal(at(6, "go").recv, "new");
  assert.equal(at(12, "toFixed").recv, "call-result");
  assert.equal(at(12, "toFixed").decls[0].ext, true);
});

test("a new expression is a site of its own, shaped by the class it names", () => {
  const box = at(6, "Box");
  assert.equal(box.shape, "new");
  assert.equal(box.recv, null);
  assert.equal(box.decls[0].kind, "class");
  assert.deepEqual([box.line, box.col, box.cline, box.ccol], [6, 4, 6, 4]);
  // Box declares no constructor: the construct signature tsc resolves is
  // synthesised and has no declaration — the record says so (null); the
  // oracle names the class at that site instead (its `target` rule)
  assert.equal(box.sigDecl, null);
  // the `new` inside lib's static make(), and the member call on the result still reads `new`
  assert.equal(records.filter((r) => r.shape === "new").length, 2);
  assert.equal(at(6, "go").recv, "new");
});

test("a call on this, a parameter, and an interface member", () => {
  const lib = records.find((r) => r.path === "src/lib.ts" && r.name === "run");
  assert.equal(lib.recv, "this");
  assert.equal(at(7, "cb").decls[0].kind, "param");
  const load = at(9, "load");
  assert.equal(load.recv, "ident:var:const:top:ObjectLiteralExpression");
  assert.equal(load.decls[0].kind, "method-signature");
});

test("the shapes with no terminal name: an IIFE in parentheses and a computed callee", () => {
  const paren = app.find((r) => r.line === 10);
  assert.equal(paren.shape, "paren");
  assert.equal(paren.name, "(() => 1)");
  assert.deepEqual(paren.decls, []);
  const computed = app.find((r) => r.line === 11 && r.shape === "computed");
  assert.equal(computed.name, "t.m[0]");
  assert.equal(computed.col, computed.ccol);
});

test("the command line emits the same record", () => {
  const script = fileURLToPath(new URL("./shapes.mjs", import.meta.url));
  const out = JSON.parse(execFileSync(process.execPath, [script, root], { encoding: "utf8" }));
  assert.deepEqual(out, records);
});
