#!/usr/bin/env node
// Hobbes TS/JS facts extractor (ADR-021).
//
// Walks a repo's TS/JS files through ts-morph (the TypeScript compiler
// API) and prints one deterministic facts JSON document on stdout for
// the Python pipeline to join into graph/tests/interfaces artifacts.
// Resolution happens here, where the compiler is: imports and calls
// carry repo-relative resolved targets, or are marked external, or are
// omitted (false edges are worse than missing edges, ADR-007/021).
//
// Usage: node extract.mjs --repo <repo-root>

import fs from "node:fs";
import path from "node:path";
import { builtinModules } from "node:module";
import { pathToFileURL } from "node:url";
import v8 from "node:v8";
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";

// ts-morph (and the TypeScript compiler under it) is loaded where a checker
// runs: in the zone workers, and in any thread that imports this module as
// a library. The CLI's main thread only hands zones out and assembles the
// facts, so it never loads it: the compiler's own heap is not paid twice
// (ADR-184's amendment, 2026-11-02).
let Node;
let Project;
let ts;
async function loadTsMorph() {
  if (ts) return;
  ({ Node, Project, ts } = await import("ts-morph"));
  fastLineNumbers((await import("@ts-morph/common")).default);
}

/** ts-morph answers every line number (`getStartLineNumber`,
 * `getEndLineNumber`, `getLineAndColumnAtPos`) by counting the newlines
 * from the start of the file to the position, one character at a time:
 * quadratic in a file's length over its nodes, and the largest single cost
 * of the walk outside the checker. This gives `StringUtils.getLineNumberAtPos`
 * the same answer — the number of `\n` before *pos*, plus one, after the
 * same range check — from a binary search over the text's newline offsets,
 * kept for the last few texts asked about. Nothing else changes. */
function fastLineNumbers(common) {
  const { StringUtils, errors } = common;
  const recent = [];
  const newlines = (str) => {
    for (const [text, offsets] of recent) if (text === str) return offsets;
    const found = [];
    for (let i = str.indexOf("\n"); i !== -1; i = str.indexOf("\n", i + 1)) found.push(i);
    const offsets = Int32Array.from(found);
    recent.unshift([str, offsets]);
    if (recent.length > 4) recent.pop();
    return offsets;
  };
  StringUtils.getLineNumberAtPos = (str, pos) => {
    errors.throwIfOutOfRange(pos, [0, str.length], "pos");
    const offsets = newlines(str);
    // The count of newline offsets below pos.
    let lo = 0;
    let hi = offsets.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (offsets[mid] < pos) lo = mid + 1;
      else hi = mid;
    }
    return lo + 1;
  };
}
const IS_CLI_MAIN = isMainThread && Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (!IS_CLI_MAIN) await loadTsMorph();

// v2 (V2.M3, ADR-029/031): `calls` carries every call site rather than
// only resolved ones, positioned on the terminal identifier with a
// 0-based `col` and its bare `name`, so the evidence IR can join it
// against SCIP occurrences; `callee`/`callee_path` are null when the
// checker could not resolve it, and are now the join's fallback rather
// than an edge. Test cases carry `end_line`, so reach can be per case.
// v3 (C-5 surfacing): every file carries `routes_declined` — route
// registrations seen and declined because their path is computed, so the
// http-ts pack can report the absence instead of leaving it silent.
export const HELPER_VERSION = 10;
// v4, since 2026-09-05 (C-63 surfaced): a call whose callee is itself an
// expression — an element access, a call's result, a parenthesised
// value — is a `calls` record named `<expr>` alone, with callee and
// origin null: counted, never resolvable. No field changed.
export const EXPR_CALLEE_NAME = "<expr>";
// v5, since 2026-09-09 (ADR-104, C-97): every `calls` record carries
// `ambiguous` — null, or `"union-member"` when the callee is a member of
// a union-typed receiver whose members do not share one declaration of
// that member (`n: A | B; n.render()` with both overriding). The checker
// resolves such a call to the *first* member's declaration, and so does
// scip-typescript; neither is the static answer, so the helper abstains
// (callee, callee_path and origin null) and the join vetoes lane B's
// pick at that site. The oracle lane found the shape on ajv (3 rows) and
// hono (7 rows) drawn at semantic certainty.
export const UNION_MEMBER = "union-member";
// v6, since 2026-09-20 (ADR-142): a top-level `constructions` map — per
// file, the 1-based line and 0-based column of every `new` expression's
// callee terminal identifier. Recorded beside `calls` and deliberately
// not in it (`extractConstructions`): lane A can say a construction was
// written, never what was constructed, so the join reads the token and
// lane B names the constructor. No `calls` record changed.
// v7, since 2026-10-01 (ADR-158, C-176): a `calls` record's `scope` is
// the innermost enclosing **graph symbol** (`enclosingScope`). A named
// class's constructor, accessor, `static {}` block, field initializer
// and member decorators now name the class, where they named nothing
// (the module); a nested function, nested arrow const or a method of a
// class declared inside a function names the top-level symbol around it,
// where it named itself and the caller dangled. No field changed.
// v8 (C-177): a tagged template is a `calls` record, its tag in callee
// position (`` tag`x` `` as `tag(..)`, `` a.b`x` `` at `b`). No field
// changed.
// v9 (ADR-179, C-176): a direct member of an object literal bound at top
// level is a `method` symbol carrying `scope_only: true` — a caller, never
// a target — and `scope` names it for the calls written inside it.
// v10 (ADR-180, C-9): a field of a top-level named class holding an arrow
// function or function expression is a `method` symbol at its name's line,
// and `scope` names it for the calls written inside the function.

const EXTENSIONS = new Set([".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"]);

// Mirror of the Python discover.SKIPPED_DIR_NAMES; dot-dirs are skipped
// wholesale there too.
const SKIPPED_DIRS = new Set([
  "node_modules",
  "__pycache__",
  "venv",
  "dist",
  "build",
  "site-packages",
]);

const BUILTINS = new Set(builtinModules);

const EXPRESS_VERBS = new Set([
  "get", "post", "put", "delete", "patch", "options", "head", "all",
]);
const NEST_VERBS = new Map([
  ["Get", "GET"], ["Post", "POST"], ["Put", "PUT"], ["Delete", "DELETE"],
  ["Patch", "PATCH"], ["Options", "OPTIONS"], ["Head", "HEAD"], ["All", "ALL"],
]);

// --- discovery -------------------------------------------------------------

/** Walk the repo's directories the way the Python discovery walks do
 * (`discover.iter_python_files`, `tssource.has_ts_files`), calling
 * *onFile(full, name)* for every entry that is not a directory. Dot
 * names and SKIPPED_DIRS are pruned. Symlinks follow one rule on both
 * sides (C-73): a directory link whose target lies **inside the repo**
 * is a second copy of a tree the walk reaches at its real path, so it
 * is not descended — the ingest records the link; a link to a directory
 * **outside** the repo is the only copy Hobbes will see and is walked;
 * a file link is followed; a dangling link is nothing. The helper used
 * to skip every symlink, which left a repo whose only copy sat behind
 * a link lane-A-less there while the Python walk found it. One guard
 * the Python side does not need: a link to a directory that *contains*
 * the repo would loop the walk and is skipped. */
function walkRepo(repoRoot, onFile) {
  let realRoot;
  try {
    realRoot = fs.realpathSync(repoRoot);
  } catch {
    return;
  }
  const stack = [repoRoot];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const full = path.join(dir, entry.name);
      let isDirectory = entry.isDirectory();
      if (entry.isSymbolicLink()) {
        try {
          isDirectory = fs.statSync(full).isDirectory();
        } catch {
          continue; // dangling: nothing is there to walk
        }
      }
      if (!isDirectory) {
        onFile(full, entry.name);
        continue;
      }
      if (SKIPPED_DIRS.has(entry.name)) continue;
      if (entry.isSymbolicLink()) {
        let real;
        try {
          real = fs.realpathSync(full);
        } catch {
          continue;
        }
        const inside = real === realRoot || real.startsWith(realRoot + path.sep);
        const contains = realRoot.startsWith(real + path.sep);
        if (inside || contains) continue; // C-73: one tree, walked at its target
      }
      stack.push(full);
    }
  }
}

/** Every `jsconfig.json` the walk reaches, repo-relative and sorted —
 * found so the ingest can say it did not read them (C-166). */
export function discoverJsconfigs(repoRoot) {
  const found = [];
  walkRepo(repoRoot, (full, name) => {
    if (name === "jsconfig.json") found.push(path.relative(repoRoot, full).split(path.sep).join("/"));
  });
  return found.sort();
}

export function discoverFiles(repoRoot) {
  const found = [];
  walkRepo(repoRoot, (full, name) => {
    if (EXTENSIONS.has(path.extname(name))) {
      found.push(path.relative(repoRoot, full).split(path.sep).join("/"));
    }
  });
  return found.sort();
}

// --- helpers ---------------------------------------------------------------

function relPath(repoRoot, sourceFile) {
  return path.relative(repoRoot, sourceFile.getFilePath()).split(path.sep).join("/");
}

/** External package name for a specifier, or null for unresolved relative
 * paths and path aliases. Node builtins are kept, not dropped (ADR-038
 * lifted C-3's stdlib-noise rule): `node:child_process` is exactly the
 * import a reviewer wants flagged. They normalise to a `node:`-prefixed
 * name — `fs`, `node:fs` and `fs/promises` all become `node:fs` — so a
 * builtin never shares a node with an npm package that reuses its name,
 * and both import spellings land on one node. */
export function externalName(specifier) {
  if (specifier.startsWith(".") || specifier.startsWith("/")) return null;
  const bare = specifier.startsWith("node:") ? specifier.slice(5) : specifier;
  const segments = bare.split("/");
  // "@/x" and "~/x" are unresolved path aliases, not packages.
  if (segments[0] === "@" || segments[0] === "~") return null;
  const name = bare.startsWith("@") ? segments.slice(0, 2).join("/") : segments[0];
  if (BUILTINS.has(name) || specifier.startsWith("node:")) return `node:${name}`;
  return name;
}

/** Manual relative resolution for require()/import() specifiers, which
 * bypass the checker's import graph. Repo-relative result or null. */
export function resolveRelative(fromFile, specifier, fileSet) {
  if (!specifier.startsWith(".")) return null;
  const base = path.posix.normalize(
    path.posix.join(path.posix.dirname(fromFile), specifier)
  );
  return resolveAsFile(base, fileSet);
}

/** A specifier whose extension marks a non-code asset (css, images,
 * fonts…): a real import of a file the graph deliberately does not
 * model, which is not a resolution failure and must not be reported as
 * one. Code extensions and extensionless specifiers are never assets. */
export function isAssetSpecifier(specifier) {
  const ext = path.posix.extname(specifier);
  return ext !== "" && !EXTENSIONS.has(ext) && ext !== ".json";
}

/** A repo path with the extension/index candidates tried, or null. */
function resolveAsFile(base, fileSet) {
  const candidates = [base];
  for (const ext of EXTENSIONS) candidates.push(base + ext);
  for (const ext of EXTENSIONS) candidates.push(`${base}/index${ext}`);
  return candidates.find((c) => fileSet.has(c)) ?? null;
}

/** Workspace packages: `{name -> {dir, main}}` from every package.json in
 * the repo (C-12). A monorepo imports its own packages by *name*
 * (`import "@app/ui"`), each zone is a separate program, and the checker
 * resolves the name into node_modules or nowhere — so the edge between
 * two of the repo's own packages was silently absent. The names are the
 * repo's to declare, read the same way every other manifest fact is. */
export function discoverWorkspacePackages(repoRoot) {
  const packages = new Map();
  walkRepo(repoRoot, (full, name) => {
    if (name !== "package.json") return;
    try {
      const data = JSON.parse(fs.readFileSync(full, "utf8"));
      if (data && typeof data.name === "string" && data.name) {
        const rel = path.relative(repoRoot, path.dirname(full)).split(path.sep).join("/");
        packages.set(data.name, {
          dir: rel === "" ? "." : rel,
          main: typeof data.main === "string" ? data.main : null,
        });
      }
    } catch {
      // a broken manifest is not the extractor's problem
    }
  });
  return packages;
}

/** Resolve a bare specifier against the repo's own package names (C-12).
 * `@app/ui` -> the package's entry file; `@app/ui/button` -> the file
 * under its directory. Repo-relative result or null — never a guess: a
 * name that matches no discovered file resolves to nothing. */
export function resolveWorkspace(specifier, packages, fileSet) {
  if (specifier.startsWith(".") || specifier.startsWith("/")) return null;
  for (const [name, pkg] of packages) {
    if (specifier !== name && !specifier.startsWith(name + "/")) continue;
    const prefix = pkg.dir === "." ? "" : pkg.dir + "/";
    if (specifier === name) {
      const candidates = [];
      if (pkg.main) {
        candidates.push(path.posix.normalize(prefix + pkg.main));
      }
      candidates.push(`${prefix}index`, `${prefix}src/index`);
      for (const base of candidates) {
        const hit = fileSet.has(base) ? base : resolveAsFile(base, fileSet);
        if (hit) return hit;
      }
      return null;
    }
    const sub = specifier.slice(name.length + 1);
    return resolveAsFile(path.posix.normalize(prefix + sub), fileSet);
  }
  return null;
}

function firstStringArg(call) {
  const arg = call.getArguments()[0];
  return arg && (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg))
    ? arg.getLiteralValue()
    : null;
}

/** The qualname a repo declaration contributes symbols under, or null
 * for declarations we don't model. Only top-level declarations (and
 * methods of top-level classes) qualify — parity with the symbol list,
 * so a call edge never points at a symbol the graph doesn't have. */
function declQualname(decl) {
  if (Node.isMethodDeclaration(decl)) {
    const cls = decl.getParent();
    if (!Node.isClassDeclaration(cls) || !Node.isSourceFile(cls.getParent())) {
      return null;
    }
    const clsName = cls.getName();
    return clsName ? `${clsName}.${decl.getName()}` : null;
  }
  if (Node.isFunctionDeclaration(decl) || Node.isClassDeclaration(decl)) {
    return Node.isSourceFile(decl.getParent()) ? decl.getName() ?? null : null;
  }
  if (Node.isVariableDeclaration(decl)) {
    const statement = decl.getFirstAncestorByKind(ts.SyntaxKind.VariableStatement);
    if (!statement || !Node.isSourceFile(statement.getParent())) return null;
    const init = decl.getInitializer();
    const modeled =
      init &&
      (Node.isArrowFunction(init) ||
        Node.isFunctionExpression(init) ||
        (Node.isCallExpression(init) &&
          init.getExpression().getText() !== "require"));
    if (!modeled) return null;
    const name = decl.getNameNode();
    return Node.isIdentifier(name) ? name.getText() : null;
  }
  return null;
}

/** The qualname of the innermost **graph symbol** enclosing a node, or
 * null where that is the module (C-176, ADR-158). The vocabulary is
 * `extractSymbols`': a top-level named function declaration, a top-level
 * variable bound to an arrow or function expression, a top-level named
 * class and that class's methods. So a scope always names a symbol the
 * graph has: a nested function, a nested `const f = () => …` and a
 * method of a class declared inside a function file their calls under
 * the top-level symbol around them, never under an id with no node (until
 * 0.2.82-beta they named themselves, and the caller dangled). A member of
 * an object literal bound at top level is its own scope (ADR-179,
 * `literalMembers`); a namespace's body, any other literal's method, an
 * unnamed class and a function assigned to a property stay the module's:
 * below the floor.
 *
 * Inside a named class, code that runs as part of the class rather than
 * as one method is the **class's**: a constructor, an accessor, a
 * `static {}` block, a field initializer, and a member's decorators and
 * computed name, which run when the class is defined. Python files a
 * class attribute's value and a method decorator's call under the class
 * too. A method's body and parameters are the method's. The class's own
 * decorators and heritage clauses run in the module's scope, so they stay
 * the module's, as a Python class decorator does. */
function enclosingScope(node) {
  const ancestors = node.getAncestors(); // the parent first, the source file last
  // ADR-179: a member of a literal bound at top level is a symbol, and
  // nothing inside it is one, so the first such ancestor is the innermost.
  const members = literalMembers(node.getSourceFile());
  for (const a of ancestors) {
    const qualname = members.get(a);
    if (qualname) return qualname;
  }
  const top = ancestors.length >= 2 ? ancestors[ancestors.length - 2] : null;
  const childOf = (parent) => ancestors.find((a) => a.getParent() === parent);
  if (!top) return null;
  if (Node.isFunctionDeclaration(top)) return top.getName() ?? null;
  if (Node.isVariableStatement(top)) {
    const decl = ancestors.findLast((a) => Node.isVariableDeclaration(a));
    const init = decl && decl.getInitializer();
    const bound =
      init &&
      (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) &&
      Node.isIdentifier(decl.getNameNode()) &&
      ancestors.includes(init);
    return bound ? decl.getName() : null;
  }
  if (!Node.isClassDeclaration(top) || !top.getName()) return null;
  const member = childOf(top);
  if (!member || Node.isDecorator(member) || Node.isHeritageClause(member)) return null;
  if (Node.isMethodDeclaration(member)) {
    const inMember = ancestors.slice(0, ancestors.indexOf(member));
    const atDefinition =
      inMember.some((a) => Node.isDecorator(a)) || childOf(member) === member.getNameNode();
    if (!atDefinition) return `${top.getName()}.${member.getName()}`;
  }
  // ADR-180: a function-literal field's body runs when the field is called,
  // not when the class is built, so it is the field's, as a method's is.
  if (Node.isPropertyDeclaration(member) && ancestors.includes(member.getInitializer())) {
    const field = functionFields(top).get(member);
    if (field) return field;
  }
  return top.getName();
}

// --- the one walk ------------------------------------------------------------

/** Every stage reads a file's nodes of a few kinds, in the order a
 * pre-order walk meets them. The file is walked once, over the compiler's
 * own nodes, and each stage is handed its kinds' nodes in that order, wrapped
 * only when a stage asks for them: a stage sees exactly the nodes, in exactly
 * the order, that its own `forEachDescendant` walk handed it, and asks the
 * checker the same questions in the same order. Walking each file once
 * rather than once per stage, and wrapping a node only when a stage reads
 * it, was the larger part of the helper's time outside the checker
 * (ADR-184's amendment, 2026-11-02). */
const WALK_GROUPS = {
  calls: new Set(),
  callExpressions: new Set(),
  news: new Set(),
  envAccess: new Set(),
  objectLiterals: new Set(),
};
let walked = { sourceFile: null, groups: null };

function kindGroups() {
  if (!WALK_GROUPS.calls.size) {
    const K = ts.SyntaxKind;
    for (const k of [K.CallExpression, K.TaggedTemplateExpression, K.JsxSelfClosingElement, K.JsxOpeningElement]) {
      WALK_GROUPS.calls.add(k);
    }
    WALK_GROUPS.callExpressions.add(K.CallExpression);
    WALK_GROUPS.news.add(K.NewExpression);
    WALK_GROUPS.envAccess.add(K.PropertyAccessExpression).add(K.ElementAccessExpression);
    WALK_GROUPS.objectLiterals.add(K.ObjectLiteralExpression);
  }
  return WALK_GROUPS;
}

/** *sourceFile*'s descendants in *group* (a key of WALK_GROUPS), in
 * pre-order, as ts-morph nodes — what `forEachDescendant` would have visited
 * and kept. The walk is shared by every stage of the file it was made for. */
function descendants(sourceFile, group) {
  if (walked.sourceFile !== sourceFile) {
    const groups = kindGroups();
    const found = Object.fromEntries(Object.keys(groups).map((g) => [g, []]));
    const entries = Object.entries(groups);
    const visit = (node) => {
      const kind = node.kind;
      for (const [g, kinds] of entries) if (kinds.has(kind)) found[g].push(node);
      ts.forEachChild(node, visit);
    };
    ts.forEachChild(sourceFile.compilerNode, visit);
    walked = { sourceFile, groups: found };
  }
  return walked.groups[group].map((node) => sourceFile._getNodeFromCompilerNode(node));
}

// --- per-file extraction ---------------------------------------------------

function extractImports(sourceFile, repoRoot, fileSet, filePath, project, packages, unresolved) {
  const imports = [];
  const push = (specifier, resolvedFile, names, line) => {
    if (resolvedFile) {
      const target = relPath(repoRoot, resolvedFile);
      if (fileSet.has(target)) {
        imports.push({ external: null, line, names, resolved: target, specifier });
        return;
      }
    }
    // The checker resolves within its own zone (one Project per
    // tsconfig), so a cross-zone import lands here — and used to vanish
    // (C-12). Two deterministic fallbacks before giving up: a relative
    // path is unambiguous regardless of zones, and a bare specifier
    // matching one of the repo's own package names is the monorepo's own
    // declaration of the target.
    const crossZone =
      resolveRelative(filePath, specifier, fileSet) ??
      resolveWorkspace(specifier, packages, fileSet);
    if (crossZone && crossZone !== filePath) {
      imports.push({ external: null, line, names, resolved: crossZone, specifier });
      return;
    }
    const external = externalName(specifier);
    if (external) {
      imports.push({ external, line, names, resolved: null, specifier });
      return;
    }
    // Resolved nowhere and names no package: an alias into a zone this
    // walk cannot read, or a path that is not there. The edge is absent
    // rather than guessed, and the absence is recorded (C-12's floor) —
    // except for asset imports (`./index.css`, `./logo.svg`): those name
    // files the graph deliberately does not model, and reporting them as
    // failures every ingest would bury the real records under noise.
    if (!isAssetSpecifier(specifier)) unresolved.push({ line, specifier });
  };

  for (const imp of sourceFile.getImportDeclarations()) {
    const names = imp.getNamedImports().map((n) => n.getName());
    const def = imp.getDefaultImport();
    if (def) names.unshift(def.getText());
    const ns = imp.getNamespaceImport();
    if (ns) names.unshift(`* as ${ns.getText()}`);
    push(
      imp.getModuleSpecifierValue(),
      imp.getModuleSpecifierSourceFile(),
      names.sort(),
      imp.getStartLineNumber()
    );
  }
  for (const exp of sourceFile.getExportDeclarations()) {
    const specifier = exp.getModuleSpecifierValue();
    if (!specifier) continue; // `export { x }` — not a dependency
    const names = exp.getNamedExports().map((n) => n.getName());
    push(
      specifier,
      exp.getModuleSpecifierSourceFile(),
      names.length ? names.sort() : ["*"],
      exp.getStartLineNumber()
    );
  }
  // require() and dynamic import() bypass the import graph; resolve
  // them through the compiler's own resolver (so a zone's path aliases
  // apply), falling back to plain relative resolution.
  const resolveSpecifier = (specifier) => {
    const result = ts.resolveModuleName(
      specifier,
      sourceFile.getFilePath(),
      project.getCompilerOptions(),
      project.getModuleResolutionHost()
    );
    const resolvedFile = result.resolvedModule?.resolvedFileName;
    if (resolvedFile) {
      const target = path.relative(repoRoot, resolvedFile).split(path.sep).join("/");
      if (fileSet.has(target)) return target;
    }
    return (
      resolveRelative(filePath, specifier, fileSet) ??
      resolveWorkspace(specifier, packages, fileSet)
    );
  };
  for (const node of descendants(sourceFile, "callExpressions")) {
    const expr = node.getExpression();
    const isRequire = Node.isIdentifier(expr) && expr.getText() === "require";
    const isDynamic = expr.getKind() === ts.SyntaxKind.ImportKeyword;
    if (!isRequire && !isDynamic) continue;
    const specifier = firstStringArg(node);
    if (!specifier) continue;
    const resolved = resolveSpecifier(specifier);
    const line = node.getStartLineNumber();
    if (resolved) {
      imports.push({ external: null, line, names: [], resolved, specifier });
    } else {
      const external = externalName(specifier);
      if (external) {
        imports.push({ external, line, names: [], resolved: null, specifier });
      } else if (!isAssetSpecifier(specifier)) {
        unresolved.push({ line, specifier });
      }
    }
  }
  return imports.sort(
    (a, b) => a.line - b.line || a.specifier.localeCompare(b.specifier)
  );
}

// An overloaded function or method is one declaration to the semantic
// lane, placed at its *first* signature — while ts-morph hands out the
// implementation. Emitting the implementation's line left the two lanes
// naming different lines for the same symbol (date-fns, 2026-09-03: 54
// lane disagreements on three functions, and the join could find no
// lane A symbol at SCIP's line, so those calls fell below the floor).
// The symbol starts where the semantic lane says it does and ends where
// the implementation ends (C-89).
function declarationStart(node) {
  const overloads = typeof node.getOverloads === "function" ? node.getOverloads() : [];
  return overloads.length ? overloads[0].getStartLineNumber() : node.getStartLineNumber();
}

function baseSymbols(sourceFile) {
  const symbols = [];
  const add = (name, qualname, kind, node) =>
    symbols.push({
      end_line: node.getEndLineNumber(),
      kind,
      line: declarationStart(node),
      name,
      qualname,
    });
  for (const fn of sourceFile.getFunctions()) {
    if (fn.getName()) add(fn.getName(), fn.getName(), "function", fn);
  }
  for (const cls of sourceFile.getClasses()) {
    if (!cls.getName()) continue;
    add(cls.getName(), cls.getName(), "class", cls);
    for (const method of cls.getMethods()) {
      add(method.getName(), `${cls.getName()}.${method.getName()}`, "method", method);
    }
    for (const [field, qualname] of functionFields(cls)) {
      // At the name's line, where scip-typescript defines it and the tsc key
      // places the target — not at a decorator above it.
      symbols.push({
        end_line: field.getEndLineNumber(),
        kind: "method",
        line: field.getNameNode().getStartLineNumber(),
        name: field.getName(),
        qualname,
      });
    }
  }
  for (const decl of sourceFile.getVariableDeclarations()) {
    const init = decl.getInitializer();
    if (!init || !Node.isIdentifier(decl.getNameNode())) continue;
    if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
      add(decl.getName(), decl.getName(), "function", decl);
    } else if (
      Node.isCallExpression(init) &&
      init.getExpression().getText() !== "require"
    ) {
      // Call-initialized consts are the JS idiom for callable values —
      // zustand stores, axios instances, styled components. Modeling
      // them keeps call edges pointing at symbols that exist.
      // (require() consts are module handles, not symbols.)
      add(decl.getName(), decl.getName(), "const", decl);
    }
  }
  return symbols;
}

/** A top-level named class's fields that hold an arrow function or a
 * function expression, mapped to their qualnames (ADR-180, C-9): called like
 * methods, keyed by the tsc oracle as call targets, and defined by
 * scip-typescript at the name. Fails toward drawing less: a qualname the
 * class writes twice (a `static` and an instance field of one name) or one
 * a method of the class already has mints nothing. A computed name mints
 * nothing. `declQualname` does not name these, so only lane B's reference
 * draws to them. */
function functionFields(cls) {
  const cached = functionFieldCache.get(cls);
  if (cached) return cached;
  const fields = new Map();
  const cname = cls.getName();
  if (cname && Node.isSourceFile(cls.getParent())) {
    const methods = new Set(cls.getMethods().map((m) => m.getName()));
    const found = cls.getProperties().filter((p) => {
      const init = p.getInitializer();
      const name = p.getNameNode();
      return (
        init &&
        (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) &&
        (Node.isIdentifier(name) || Node.isPrivateIdentifier(name))
      );
    });
    const count = new Map();
    for (const p of found) count.set(p.getName(), (count.get(p.getName()) ?? 0) + 1);
    for (const p of found) {
      if (count.get(p.getName()) === 1 && !methods.has(p.getName())) fields.set(p, `${cname}.${p.getName()}`);
    }
  }
  functionFieldCache.set(cls, fields);
  return fields;
}

const functionFieldCache = new WeakMap();

/** The binding a top-level object literal is written under, as the prefix
 * of its members' qualnames, or null (ADR-179): `X` for a top-level
 * `const`/`let`/`var X = {…}`; `module.exports`, `exports.y` or
 * `module.exports.y` for a top-level statement assigning it; `default` for
 * `export default {…}`. `as`, `satisfies` and parentheses are looked
 * through. Anything else — a literal returned, passed, nested in another
 * literal, or assigned below top level — has no binding here. */
function literalBinding(literal) {
  let p = literal.getParent();
  while (p && (Node.isAsExpression(p) || Node.isSatisfiesExpression(p) || Node.isParenthesizedExpression(p))) {
    p = p.getParent();
  }
  if (!p) return null;
  if (Node.isVariableDeclaration(p)) {
    const statement = p.getFirstAncestorByKind(ts.SyntaxKind.VariableStatement);
    const name = p.getNameNode();
    return statement && Node.isSourceFile(statement.getParent()) && Node.isIdentifier(name)
      ? name.getText()
      : null;
  }
  if (Node.isExportAssignment(p)) return p.isExportEquals() ? null : "default";
  if (
    Node.isBinaryExpression(p) &&
    p.getOperatorToken().getKind() === ts.SyntaxKind.EqualsToken &&
    Node.isExpressionStatement(p.getParent()) &&
    Node.isSourceFile(p.getParent().getParent())
  ) {
    const left = p.getLeft().getText();
    if (left === "module.exports" || /^(module\.)?exports\.[A-Za-z_$][\w$]*$/.test(left)) return left;
  }
  return null;
}

/** A literal member's written name, or null for a computed one. */
function memberName(member) {
  const name = member.getNameNode();
  if (Node.isIdentifier(name) || Node.isPrivateIdentifier(name)) return name.getText();
  if (Node.isStringLiteral(name) || Node.isNoSubstitutionTemplateLiteral(name)) return name.getLiteralValue();
  return null;
}

const literalMemberCache = new WeakMap();

/** The members of object literals bound at top level that are graph
 * symbols, mapped to their qualnames (ADR-179, C-176). A member counts
 * when its value runs as a function: a method, a `get`/`set` accessor, or
 * a property whose value is an arrow function or function expression;
 * only a literal's **direct** members. Fails toward drawing less: a
 * qualname written twice in the file (a getter and its setter, two
 * `module.exports = {…}`) or equal to a symbol the file already has mints
 * nothing, and those calls stay the module's. Each is **scope only**: a
 * caller, never a target (`declQualname` does not name it, and the join's
 * `starting_at` skips it). Shared by `extractSymbols` and `enclosingScope`
 * so a scope always names a symbol the graph has. */
function literalMembers(sourceFile) {
  const cached = literalMemberCache.get(sourceFile);
  if (cached) return cached;
  const taken = new Set(baseSymbols(sourceFile).map((s) => s.qualname));
  const found = [];
  for (const node of descendants(sourceFile, "objectLiterals")) {
    const prefix = literalBinding(node);
    if (!prefix) continue;
    for (const member of node.getProperties()) {
      const runs =
        Node.isMethodDeclaration(member) ||
        Node.isGetAccessorDeclaration(member) ||
        Node.isSetAccessorDeclaration(member) ||
        (Node.isPropertyAssignment(member) &&
          (Node.isArrowFunction(member.getInitializer()) ||
            Node.isFunctionExpression(member.getInitializer())));
      const name = runs ? memberName(member) : null;
      if (name !== null) found.push([member, `${prefix}.${name}`]);
    }
  }
  const count = new Map();
  for (const [, q] of found) count.set(q, (count.get(q) ?? 0) + 1);
  const members = new Map(found.filter(([, q]) => count.get(q) === 1 && !taken.has(q)));
  literalMemberCache.set(sourceFile, members);
  return members;
}

function extractSymbols(sourceFile) {
  const symbols = baseSymbols(sourceFile);
  for (const [member, qualname] of literalMembers(sourceFile)) {
    symbols.push({
      end_line: member.getEndLineNumber(),
      kind: "method",
      line: member.getStartLineNumber(),
      name: memberName(member),
      qualname,
      scope_only: true,
    });
  }
  return symbols.sort((a, b) => a.line - b.line || a.qualname.localeCompare(b.qualname));
}

/** Follow a CommonJS re-export to the module that actually exports the
 * value (ADR-141, C-167). `getAliasedSymbol()` stops at a re-exporting
 * file's `export=` symbol, because TypeScript does not treat a `require`
 * call on the right of `module.exports = …` as an alias — so a call
 * through `require('..')` into a root `index.js` that is one line of
 * re-export had no callee at all. Given the alias-resolved symbol, this
 * returns the symbol to resolve declarations from.
 *
 * It acts only on the written shape: an `export=` symbol whose single
 * declaration is a binary expression whose right side (through any
 * further `=`, for `exports = module.exports = require(…)`) is
 * `require("<literal>")`. The specifier's own symbol is the *compiler's*
 * module resolution — never a type — and the walk continues from that
 * module's `export=`, at most eight hops so a cycle (`a.js` ↔ `b.js`)
 * terminates. Anything else — a module that does not resolve, a template
 * literal or computed specifier, a conditional — stops the walk and
 * returns the symbol we have, which resolves no more than before.
 *
 * No `.ts` file is affected: there `export =` is an ExportAssignment,
 * not a binary expression, so the first gate declines it. */
function pierceRequireReexport(symbol) {
  for (let hop = 0; hop < 8 && symbol && symbol.getName() === "export="; hop++) {
    const decls = symbol.getDeclarations();
    if (decls.length !== 1 || !Node.isBinaryExpression(decls[0])) return symbol;
    let rhs = decls[0].getRight();
    while (
      Node.isBinaryExpression(rhs) &&
      rhs.getOperatorToken().getKind() === ts.SyntaxKind.EqualsToken
    ) {
      rhs = rhs.getRight();
    }
    if (!Node.isCallExpression(rhs) || rhs.getExpression().getText() !== "require") {
      return symbol;
    }
    const arg = rhs.getArguments()[0];
    if (!arg || !Node.isStringLiteral(arg)) return symbol;
    const next = arg.getSymbol()?.getExport("export=");
    if (!next) return symbol;
    symbol = next.getAliasedSymbol() ?? next;
  }
  return symbol;
}

/** Resolve an identifier/property expression to a repo symbol via the
 * checker, piercing import aliases. {path, qualname} or null. */
function resolveExpressionTarget(expr, repoRoot, fileSet) {
  if (!Node.isIdentifier(expr) && !Node.isPropertyAccessExpression(expr)) {
    return null;
  }
  let symbol = expr.getSymbol();
  if (!symbol) return null;
  const aliased = symbol.getAliasedSymbol();
  if (aliased) symbol = aliased;
  symbol = pierceRequireReexport(symbol);
  for (const decl of symbol.getDeclarations()) {
    const declFile = decl.getSourceFile();
    const target = relPath(repoRoot, declFile);
    if (!fileSet.has(target)) continue;
    const qualname = declQualname(decl);
    if (qualname) return { path: target, qualname };
  }
  return null;
}

/** The static→union-member shape (ADR-104, C-97): a property access whose
 * receiver type is a union of two or more non-nullish members that do not
 * all resolve the accessed member to one declaration. Returns the
 * ambiguity's name or null. `T | undefined` is not the shape (one
 * member); a union whose members inherit one base method is not either
 * (one declaration) — those resolve as before. Declarations are keyed by
 * file and start position, so two overloads of one method in one class
 * still count as one declaration set per member... and two members'
 * distinct overrides count as two. */
function unionAmbiguity(expr) {
  if (!Node.isPropertyAccessExpression(expr)) return null;
  let type;
  try {
    type = expr.getExpression().getType();
  } catch {
    return null;
  }
  if (!type || !type.isUnion()) return null;
  const parts = type.getUnionTypes().filter((t) => !t.isNull() && !t.isUndefined());
  if (parts.length < 2) return null;
  const name = expr.getName();
  const declarationKeys = new Set();
  for (const part of parts) {
    const member = part.getProperty(name);
    if (!member) continue;
    for (const decl of member.getDeclarations()) {
      declarationKeys.add(`${decl.getSourceFile().getFilePath()}:${decl.getStart()}`);
    }
  }
  return declarationKeys.size > 1 ? UNION_MEMBER : null;
}

/** Where an *unresolved* callee's declarations live — the tail view's
 * checker-grade origin (ADR-045, helper v4). Runs only when
 * resolveExpressionTarget returned null, and states which of its two
 * gates failed: every declaration outside the repo's file set is
 * `external` (a dependency or ambient lib); a declaration inside the
 * repo that declQualname does not model is `local` (same file) or
 * `nested` (another file) — a binding below the graph's vocabulary,
 * seen and deliberately not modelled (C-9), which is knowledge the
 * pipeline was previously discarding. Null when the checker has no
 * symbol or no declarations at all. */
function calleeOrigin(expr, repoRoot, fileSet, sourceFile) {
  if (!Node.isIdentifier(expr) && !Node.isPropertyAccessExpression(expr)) {
    return null;
  }
  let symbol = expr.getSymbol();
  if (!symbol) return null;
  const aliased = symbol.getAliasedSymbol();
  if (aliased) symbol = aliased;
  symbol = pierceRequireReexport(symbol);
  const decls = symbol.getDeclarations();
  if (!decls.length) return null;
  const here = relPath(repoRoot, sourceFile);
  let sawInRepo = null;
  for (const decl of decls) {
    const target = relPath(repoRoot, decl.getSourceFile());
    if (fileSet.has(target)) {
      sawInRepo = target === here ? "local" : sawInRepo ?? "nested";
      if (sawInRepo === "local") break;
    }
  }
  return sawInRepo ?? "external";
}

/** A callee that is a keyword — `import(..)`, `super(..)` — rather
 * than a value: never a call site of this lane. */
function isKeywordCallee(expr) {
  const kind = expr.getKind();
  return kind === ts.SyntaxKind.ImportKeyword || kind === ts.SyntaxKind.SuperKeyword;
}

/** The identifier that names the callee — what a reader would point at,
 * and what SCIP puts its occurrence on. `f()` -> `f`; `a.b.c()` -> `c`. */
function terminalIdentifier(expr) {
  if (Node.isIdentifier(expr)) return expr;
  if (Node.isPropertyAccessExpression(expr)) return expr.getNameNode();
  return null;
}

/**
 * Every call site, resolved or not (ADR-029's evidence IR; V2.M3).
 *
 * Before V2.M3 this emitted a record only when the checker resolved the
 * callee, which made lane A's TS call sites invisible in two ways that
 * both mattered: the join had nothing to match SCIP's resolutions
 * *against* (SCIP cannot tell a call from a reference, so tree-sitter's
 * — here ts-morph's — "this is a call" is the half it cannot supply),
 * and resolution coverage had no denominator, so a TS repo would have
 * reported 100% accounted no matter how much it missed.
 *
 * The gate mirrors `pysource`'s: a callee that is a plain identifier or
 * an attribute chain carries its terminal identifier's name; a callee
 * that is itself an expression — `table[k](s)`, `f()()`, `(a || b)()`
 * — is a site named `<expr>` alone (C-63, surfaced 2026-09-05). Nothing
 * can resolve the second kind, and until then it was not counted at all,
 * so a repo of dispatch tables read as fully accounted; now the
 * denominator holds it and the tail view names it `expr-callee`.
 *
 * Position is the **terminal identifier's**, not the call expression's,
 * because that is where the semantic provider puts its occurrence. They
 * differ on a wrapped chain (`obj\n  .method()`), and a line mismatch
 * there is a silently unjoined call rather than an error.
 *
 * **JSX instantiations are call sites** (C-24 lifted, 2026-08-15):
 * `<BetCard />` executes BetCard when the element renders, so a test
 * that only renders a component genuinely reaches it — leaving these as
 * bare references made every such test's reach empty. Honesty about the
 * edges of that claim: only component-like tags count (a capitalised
 * identifier, or any dotted tag — `<div>` is a string at runtime, not
 * code this repo owns); the framework mediates *when* the component
 * body runs, exactly as any call site behind a branch mediates whether
 * its callee runs; and only the opening tag is a site — a closing tag
 * repeats the name, it does not instantiate again.
 */
function extractCalls(sourceFile, repoRoot, fileSet) {
  const calls = [];
  const push = (terminal, resolveFrom, scopeNode) => {
    // v5: a member of a union receiver with more than one declaration in
    // play is an abstention, not a resolution — the checker's pick would
    // be the first member's (ADR-104, C-97).
    const ambiguous = unionAmbiguity(resolveFrom);
    const target = ambiguous ? null : resolveExpressionTarget(resolveFrom, repoRoot, fileSet);
    const { line, column } = sourceFile.getLineAndColumnAtPos(terminal.getStart());
    calls.push({
      // Lane A's own resolution, kept as the join's fallback rather than
      // as an edge (ADR-031). Null when the checker could not resolve it.
      callee: target ? target.qualname : null,
      callee_path: target ? target.path : null,
      // 1-based line, 0-based column — SCIP's convention, so the join
      // compares like with like.
      line,
      col: column - 1,
      name: terminal.getText(),
      // v4: where an unresolved callee's declarations live (ADR-045) —
      // `local` | `nested` | `external` | null; null too when the
      // checker resolved it, because then callee/callee_path answer.
      origin: target || ambiguous
        ? null
        : calleeOrigin(resolveFrom, repoRoot, fileSet, sourceFile),
      scope: enclosingScope(scopeNode),
      ambiguous,
    });
  };
  // C-63: the callee has no terminal identifier for SCIP to put an
  // occurrence on. Positioned where the callee expression starts, so a
  // reader can point at it; callee and origin null — the join skips a
  // name nothing carries, and the tail classes it `expr-callee`.
  const pushExpressionCallee = (callee, scopeNode) => {
    const { line, column } = sourceFile.getLineAndColumnAtPos(callee.getStart());
    calls.push({
      callee: null,
      callee_path: null,
      line,
      col: column - 1,
      name: EXPR_CALLEE_NAME,
      origin: null,
      scope: enclosingScope(scopeNode),
      ambiguous: null,
    });
  };
  for (const node of descendants(sourceFile, "calls")) {
    if (Node.isCallExpression(node)) {
      const callee = node.getExpression();
      const terminal = terminalIdentifier(callee);
      if (terminal) push(terminal, callee, node);
      // `import(..)` is an import (extractImports reads it) and
      // `super(..)` a keyword, not a value in callee position: neither
      // is a site, as before.
      else if (!isKeywordCallee(callee)) pushExpressionCallee(callee, node);
      continue;
    }
    // C-177: `` tag`text` `` calls `tag` with the template's strings and
    // values, so it is a site exactly as `tag(..)` is, its tag in callee
    // position; until v8 the index's occurrence there was a `uses` alone.
    if (Node.isTaggedTemplateExpression(node)) {
      const tag = node.getTag();
      const terminal = terminalIdentifier(tag);
      if (terminal) push(terminal, tag, node);
      else pushExpressionCallee(tag, node);
      continue;
    }
    if (Node.isJsxSelfClosingElement(node) || Node.isJsxOpeningElement(node)) {
      const tag = node.getTagNameNode();
      const component =
        (Node.isIdentifier(tag) && /^[A-Z]/.test(tag.getText())) ||
        Node.isPropertyAccessExpression(tag);
      if (!component) continue;
      const terminal = terminalIdentifier(tag);
      if (terminal) push(terminal, tag, node);
    }
  }
  return calls.sort(
    (a, b) => a.line - b.line || a.col - b.col || a.name.localeCompare(b.name)
  );
}

/**
 * Every construction token in the file (ADR-142): the 1-based line and
 * 0-based column of each `new` expression's callee terminal identifier,
 * sorted.
 *
 * The same `terminalIdentifier` `extractCalls` uses, positioned the same
 * way, because the whole question the join asks of these is whether lane
 * B put a resolution at *exactly* this token.
 *
 * **Not a call site**, and that is ADR-132's reason a language later: at
 * a `new X()` lane A cannot tell what was constructed, only that a
 * construction was written. The checker's answer there is the class,
 * while the constructor that runs may be a base's — 55 of 58 such rows
 * read contradicted when the shape was measured — so a construction
 * reaches no `calls` record, no callee fallback, no veto, no
 * resolution-coverage denominator and no tail class. What lane A states
 * here is one fact: a construction was written at this token.
 *
 * A callee with no terminal identifier records nothing: `new this(…)`
 * and `new (pick())()` name no symbol either lane could agree on (C-1),
 * and there is no token for the index to meet.
 */
function extractConstructions(sourceFile) {
  const tokens = [];
  for (const node of descendants(sourceFile, "news")) {
    const terminal = terminalIdentifier(node.getExpression());
    if (!terminal) continue;
    const { line, column } = sourceFile.getLineAndColumnAtPos(terminal.getStart());
    tokens.push([line, column - 1]);
  }
  return tokens.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

function extractEnvReads(sourceFile) {
  const reads = [];
  for (const node of descendants(sourceFile, "envAccess")) {
    let base = null;
    let name = null;
    if (Node.isPropertyAccessExpression(node)) {
      base = node.getExpression().getText();
      name = node.getName();
    } else if (Node.isElementAccessExpression(node)) {
      base = node.getExpression().getText();
      const arg = node.getArgumentExpression();
      name = arg && Node.isStringLiteral(arg) ? arg.getLiteralValue() : null;
    }
    if (name && (base === "process.env" || base === "import.meta.env")) {
      reads.push({ line: node.getStartLineNumber(), var: name });
    }
  }
  return reads.sort((a, b) => a.line - b.line || a.var.localeCompare(b.var));
}

function expressReceiverOk(receiver) {
  const text = receiver.getText();
  if (text === "app" || text === "router" || text === "server") return true;
  const symbol = Node.isIdentifier(receiver) ? receiver.getSymbol() : null;
  if (!symbol) return false;
  return symbol.getDeclarations().some((decl) => {
    if (!Node.isVariableDeclaration(decl)) return false;
    const init = decl.getInitializer();
    return init ? /\bexpress\(|\.Router\(|^Router\(/.test(init.getText()) : false;
  });
}

function extractRoutes(sourceFile, repoRoot, fileSet) {
  const routes = [];
  const declined = [];
  // Express: app.get("/path", handler) — receiver must look like an
  // express app/router and the path literal must start with "/", so
  // map.get("key") never counts.
  for (const node of descendants(sourceFile, "callExpressions")) {
    const expr = node.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) continue;
    const verb = expr.getName();
    if (!EXPRESS_VERBS.has(verb)) continue;
    if (!expressReceiverOk(expr.getExpression())) continue;
    const args = node.getArguments();
    const routePath = firstStringArg(node);
    if (!routePath) {
      // A registration-shaped call (real express receiver, a handler
      // argument) whose path is computed. The route stays absent — a
      // guessed path is a false interface — but the sighting is reported
      // so the absence is legible (C-5). One string argument alone is not
      // registration-shaped: `app.get('view engine')` reads a setting.
      if (args.length >= 2) {
        declined.push({ framework: "express", line: node.getStartLineNumber() });
      }
      continue;
    }
    if (!routePath.startsWith("/")) continue;
    const handlerArg = args[args.length - 1];
    let handler = "<inline>";
    let handlerPath = null;
    if (Node.isIdentifier(handlerArg)) {
      const target = resolveExpressionTarget(handlerArg, repoRoot, fileSet);
      handler = target ? target.qualname : handlerArg.getText();
      handlerPath = target ? target.path : null;
    }
    routes.push({
      framework: "express",
      handler,
      handler_path: handlerPath,
      line: node.getStartLineNumber(),
      method: verb.toUpperCase(),
      path: routePath,
    });
  }
  // Nest: @Controller("prefix") classes with @Get("sub")-family methods.
  // A decorator argument that exists but is not a string literal is a
  // computed path: the route is declined, never emitted with the computed
  // segment silently dropped — that would report a path the app does not
  // serve, which is worse than C-5's absence.
  for (const cls of sourceFile.getClasses()) {
    const controller = cls.getDecorator("Controller");
    if (!controller || !cls.getName()) continue;
    const prefixArg = controller.getArguments()[0];
    const prefixComputed = Boolean(prefixArg) && !Node.isStringLiteral(prefixArg);
    const prefix =
      prefixArg && Node.isStringLiteral(prefixArg) ? prefixArg.getLiteralValue() : "";
    for (const method of cls.getMethods()) {
      for (const [decoratorName, httpMethod] of NEST_VERBS) {
        const decorator = method.getDecorator(decoratorName);
        if (!decorator) continue;
        const subArg = decorator.getArguments()[0];
        if (prefixComputed || (subArg && !Node.isStringLiteral(subArg))) {
          declined.push({ framework: "nest", line: method.getStartLineNumber() });
          continue;
        }
        const sub = subArg ? subArg.getLiteralValue() : "";
        const parts = [prefix, sub].filter(Boolean).map((p) => p.replace(/^\/|\/$/g, ""));
        routes.push({
          framework: "nest",
          handler: `${cls.getName()}.${method.getName()}`,
          handler_path: relPath(repoRoot, sourceFile),
          line: method.getStartLineNumber(),
          method: httpMethod,
          path: "/" + parts.join("/"),
        });
      }
    }
  }
  return {
    routes: routes.sort((a, b) => a.line - b.line || a.path.localeCompare(b.path)),
    declined: declined.sort((a, b) => a.line - b.line),
  };
}

// --- tests -----------------------------------------------------------------

export function isTestFile(filePath) {
  const base = path.posix.basename(filePath);
  return (
    /\.(test|spec)\.[cm]?[jt]sx?$/.test(base) ||
    filePath.split("/").includes("__tests__")
  );
}

function testFramework(sourceFile, filePath, imports) {
  const specifiers = new Set(imports.map((i) => i.specifier));
  if (specifiers.has("node:test")) return "node:test";
  for (const spec of specifiers) {
    if (spec === "vitest" || spec.startsWith("vitest/")) return "vitest";
    if (spec === "@jest/globals") return "jest";
  }
  if (!isTestFile(filePath)) return null;
  // Test-named file using bare describe/it/test globals (jest- or
  // vitest-with-globals style): inventoried, framework honest-unknown.
  let usesGlobals = false;
  for (const node of descendants(sourceFile, "callExpressions")) {
    if (
      Node.isIdentifier(node.getExpression()) &&
      ["describe", "it", "test"].includes(node.getExpression().getText())
    ) {
      usesGlobals = true;
    }
  }
  return usesGlobals ? "unknown" : null;
}

function testCallName(call) {
  const expr = call.getExpression();
  if (Node.isIdentifier(expr)) return expr.getText();
  // it.skip(...) / test.only(...) / describe.skip(...)
  if (
    Node.isPropertyAccessExpression(expr) &&
    Node.isIdentifier(expr.getExpression()) &&
    ["skip", "only", "todo", "concurrent", "sequential"].includes(expr.getName())
  ) {
    return expr.getExpression().getText();
  }
  return null;
}

/** A test or describe call's title: the string literal it is given, or else, its argument being computed
 * (a template with `${…}`, a name, a call), that argument's source text, marked computed (ADR-188, C-199);
 * null when the call has no argument. */
function caseTitle(call) {
  const arg = call.getArguments()[0];
  if (!arg) return null;
  const literal = firstStringArg(call);
  return literal !== null ? { text: literal, computed: false } : { text: arg.getText(), computed: true };
}

function describeChain(node) {
  const titles = [];
  let current = node.getParent();
  while (current) {
    if (Node.isCallExpression(current) && testCallName(current) === "describe") {
      const title = caseTitle(current);
      if (title && title.text) titles.unshift(title);
    }
    current = current.getParent();
  }
  return titles;
}

function extractTests(sourceFile, filePath, imports) {
  const framework = testFramework(sourceFile, filePath, imports);
  if (!framework) return { framework: null, cases: [] };
  const cases = [];
  for (const node of descendants(sourceFile, "callExpressions")) {
    const callName = testCallName(node);
    if (callName !== "it" && callName !== "test") continue;
    const title = caseTitle(node);
    if (title === null) continue;
    const chain = [...describeChain(node), title];
    cases.push({
      line: node.getStartLineNumber(),
      // The case's extent, so reach can be attributed per case rather than
      // per file (C-11). A JS test body is an anonymous closure with no
      // symbol to hang an edge on, so range containment is the only way to
      // ask "which calls belong to this `it()`".
      end_line: node.getEndLineNumber(),
      qualname: chain.map((t) => t.text).join(" > "),
      ...(chain.some((t) => t.computed) ? { computed_title: true } : {}),
    });
  }
  return {
    framework,
    cases: cases.sort((a, b) => a.line - b.line || a.qualname.localeCompare(b.qualname)),
  };
}

// --- repo extraction -------------------------------------------------------

/** Repo-relative path of the nearest tsconfig.json at or above *file*'s
 * directory (never above the repo root), or "" when there is none. */
export function nearestTsconfig(root, file) {
  let dir = path.posix.dirname(file);
  while (true) {
    const candidate = dir === "." ? "tsconfig.json" : `${dir}/tsconfig.json`;
    if (fs.existsSync(path.join(root, candidate))) return candidate;
    if (dir === ".") return "";
    dir = path.posix.dirname(dir);
  }
}

/** Repo-relative posix form of an absolute path under *root*. */
function relPosix(root, abs) {
  return path.relative(root, abs).split(path.sep).join("/");
}

/** The raw JSON of a tsconfig (comments tolerated, `extends` NOT
 * applied), or `{}` when it cannot be read. Cheap: no disk walk. */
function tsconfigRaw(root, config, cache) {
  const key = `raw:${config}`;
  if (!cache.has(key)) {
    const read = ts.readConfigFile(path.join(root, config), ts.sys.readFile);
    cache.set(key, read.config && typeof read.config === "object" ? read.config : {});
  }
  return cache.get(key);
}

/** A *solution-style* tsconfig: project `references` and no inputs of
 * its own — `files` or `include` written empty, neither non-empty. It
 * describes no files, so its compiler options are nobody's — loading it
 * as a zone's options ran the checker at its ES5 defaults (C-98). A
 * config with `references` and *neither* key is not one: the compiler's
 * default include is then the whole directory (C-99). The rule is lane
 * B's `is_solution_tsconfig` (C-90), read from the same two keys. */
export function isSolutionTsconfig(raw) {
  const nonEmpty = (v) => Array.isArray(v) && v.length > 0;
  if (!Array.isArray(raw.references) || nonEmpty(raw.include) || nonEmpty(raw.files)) return false;
  return "files" in raw || "include" in raw;
}

/** The compiler's own reading of a tsconfig — its inputs after
 * `extends` / `include` / `exclude` / `files`, and its project
 * references resolved to config files — both repo-relative; references
 * outside the repo are dropped. Parsed once per config per extraction:
 * the include globs walk the disk, so this is asked only of the
 * projects a solution config names, never of an ordinary zone. */
function tsconfigInputs(root, config, cache) {
  const key = `parsed:${config}`;
  if (!cache.has(key)) {
    const host = { ...ts.sys, onUnRecoverableConfigFileDiagnostic: () => {} };
    const parsed = ts.getParsedCommandLineOfConfigFile(path.join(root, config), {}, host);
    const references = [];
    for (const ref of parsed?.projectReferences ?? []) {
      const rel = relPosix(root, ts.resolveProjectReferencePath(ref));
      if (!rel.startsWith("..") && !path.isAbsolute(rel)) references.push(rel);
    }
    cache.set(key, {
      files: new Set((parsed?.fileNames ?? []).map((f) => relPosix(root, f))),
      references,
    });
  }
  return cache.get(key);
}

/** The tsconfig whose project *file* belongs to — its zone.
 *
 * The nearest `tsconfig.json` at or above the file, as before; but when
 * that one is a solution config (C-98), the zone is the first project
 * it references — in the order written, solutions followed
 * transitively inside the repo — whose inputs, by the compiler's own
 * reading, include the file. A file no referenced project claims gets
 * "" and runs under the default options, exactly as a file under no
 * tsconfig does (and as lane B's generated config treats it, C-90);
 * `extractRepo` reports those per solution config. A project that
 * includes a file twice (two references both claiming it) is one
 * program per reference to `tsc -b`; here the first named wins, and
 * `tsconfigs` in the facts names the zones actually used. */
export function zoneTsconfig(root, file, cache = new Map()) {
  const nearest = nearestTsconfig(root, file);
  if (!nearest || !isSolutionTsconfig(tsconfigRaw(root, nearest, cache))) return nearest;
  const seen = new Set();
  const claimant = (config) => {
    if (seen.has(config)) return "";
    seen.add(config);
    if (!isSolutionTsconfig(tsconfigRaw(root, config, cache))) {
      return tsconfigInputs(root, config, cache).files.has(file) ? config : "";
    }
    for (const ref of tsconfigInputs(root, config, cache).references) {
      const found = claimant(ref);
      if (found) return found;
    }
    return "";
  };
  return claimant(nearest);
}

/** What `extractRepo` decides before any zone runs: the files, the zones
 * they group into (sorted, as the serial loop ran them), and the
 * repo-level records (unclaimed files, ignored jsconfigs), which come
 * before every zone's in the facts. */
function planRepo(repoRoot) {
  const root = path.resolve(repoRoot);
  const files = discoverFiles(root);
  const fileSet = new Set(files);
  const packages = discoverWorkspacePackages(root);

  // Files group by the tsconfig whose project they belong to ("zones"),
  // one ts-morph Project per zone, so per-package compiler options —
  // path aliases above all — resolve the way that package's own build
  // does. Files under no tsconfig share a default allowJs project, and
  // so do files under a solution-style root that no referenced project
  // includes (C-98) — those are reported, per solution config, below.
  // Cross-zone imports don't resolve (separate programs); accepted, rare.
  const zones = new Map();
  const unclaimed = new Map();
  const configCache = new Map();
  for (const file of files) {
    const zone = zoneTsconfig(root, file, configCache);
    if (!zones.has(zone)) zones.set(zone, []);
    zones.get(zone).push(file);
    if (!zone) {
      const nearest = nearestTsconfig(root, file);
      if (nearest) {
        if (!unclaimed.has(nearest)) unclaimed.set(nearest, []);
        unclaimed.get(nearest).push(file);
      }
    }
  }

  const errors = [];
  for (const [solution, its] of [...unclaimed.entries()].sort()) {
    // Visible, not silent (P1): the files a solution config's projects
    // leave unclaimed ran under the default options, not the repo's.
    const sample = its.slice(0, 4).join(", ");
    errors.push({
      message:
        `${its.length} file(s) no project referenced from ${solution} includes (${sample}` +
        `${its.length > 4 ? ", …" : ""}) — extracted under the default compiler options`,
      path: solution,
      stage: "tsconfig-unclaimed",
    });
  }
  // C-166: zones key on tsconfig.json alone, in both lanes, so a
  // jsconfig.json's options (paths, baseUrl, jsx, lib, target) are never
  // read. Said once per jsconfig that governs a discovered file and has
  // no tsconfig.json beside it (where one does, TypeScript reads that
  // instead, and so do we).
  for (const jsconfig of discoverJsconfigs(root)) {
    const dir = path.posix.dirname(jsconfig);
    if (fs.existsSync(path.join(root, dir, "tsconfig.json"))) continue;
    const under = files.filter((f) => dir === "." || f.startsWith(dir + "/"));
    if (!under.length) continue;
    const nearest = nearestTsconfig(root, dir === "." ? "x" : `${dir}/x`);
    errors.push({
      message:
        `not read: its ${under.length} file(s) are extracted under ` +
        `${nearest ? nearest : "the default compiler options"}, not its compilerOptions (C-166)`,
      path: jsconfig,
      stage: "jsconfig-ignored",
    });
  }
  return { root, fileSet, packages, zones: [...zones.entries()].sort(), errors };
}

/** One zone's facts: its files' records in file order, its records, and
 * ADR-142's construction tokens as `[file, tokens]` pairs. A zone reads
 * nothing another zone writes (one ts-morph Project each), so zones can
 * run apart and their results merge into the same bytes (ADR-184). */
export function extractZone(root, zone, zoneFiles, fileSet, packages) {
  const out = [];
  const errors = [];
  // ADR-142's tokens, kept out of the per-file records because they are
  // not facts about a call: one entry per file that writes a `new`, and
  // none at all for a file that does not.
  const constructions = [];
  // Zone configs get safety overrides: extraction must handle files
  // the package's own build ignores (a stray service worker), and
  // checking dependency .d.ts is pure risk with no facts to gain.
  const project = zone
    ? new Project({
        tsConfigFilePath: path.join(root, zone),
        skipAddingFilesFromTsConfig: true,
        compilerOptions: { allowJs: true, checkJs: false, noEmit: true, skipLibCheck: true },
      })
    : new Project({
        compilerOptions: {
          allowJs: true,
          checkJs: false,
          module: ts.ModuleKind.ESNext,
          moduleResolution: ts.ModuleResolutionKind.Bundler,
          skipLibCheck: true,
          target: ts.ScriptTarget.ES2022,
          jsx: ts.JsxEmit.Preserve,
        },
      });
  for (const file of zoneFiles) project.addSourceFileAtPath(path.join(root, file));
  for (const file of zoneFiles) {
    // Every ts-morph wrapper this file's stages create (its own nodes, and
    // the declarations the checker hands back from other files) is let go
    // once its record is built: the records are plain data, and the
    // wrappers of every file otherwise stayed on the heap until the zone
    // ended. The checker's own state is untouched, so the facts are the
    // same bytes.
    project.forgetNodesCreatedInBlock(() => extractFile(file));
  }
  // The last file's walk names this zone's program; let it go with the zone.
  walked = { sourceFile: null, groups: null };
  return { files: out, errors, constructions };

  function extractFile(file) {
    const sourceFile = project.getSourceFile(path.join(root, file));
    // A checker internal crash on one stage of one file must not
    // zero the repo: the stage degrades to empty and the facts say
    // so — degradation is visible, never silent (P1).
    const attempt = (stage, fallback, run) => {
      try {
        return run();
      } catch (error) {
        errors.push({ message: String(error.message).slice(0, 200), path: file, stage });
        return fallback;
      }
    };
    const unresolved = [];
    const imports = attempt("imports", [], () =>
      extractImports(sourceFile, root, fileSet, file, project, packages, unresolved)
    );
    if (unresolved.length) {
      // C-12's surfacing floor: the edges that still cannot be drawn
      // stop being silent. One record per file, specifiers named.
      const sample = unresolved.slice(0, 4).map((u) => u.specifier).join(", ");
      errors.push({
        message:
          `${unresolved.length} import(s) resolved nowhere (${sample}) — ` +
          "edges absent rather than guessed",
        path: file,
        stage: "imports-unresolved",
      });
    }
    const tests = attempt("tests", { framework: null, cases: [] }, () =>
      extractTests(sourceFile, file, imports)
    );
    const routeFacts = attempt("routes", { routes: [], declined: [] }, () =>
      extractRoutes(sourceFile, root, fileSet)
    );
    const tokens = attempt("constructions", [], () =>
      extractConstructions(sourceFile)
    );
    if (tokens.length) constructions.push([file, tokens]);
    out.push({
      calls: attempt("calls", [], () => extractCalls(sourceFile, root, fileSet)),
      env_reads: attempt("env_reads", [], () => extractEnvReads(sourceFile)),
      imports,
      path: file,
      routes: routeFacts.routes,
      routes_declined: routeFacts.declined,
      symbols: attempt("symbols", [], () => extractSymbols(sourceFile)),
      test_framework: tests.framework,
      tests: tests.cases,
    });
  }
}

/** The repo's facts from its plan and every zone's result, in zone order:
 * the merge the serial loop made, so the output is the same bytes however
 * the zones ran. Each result's files are `[path, json]` pairs, a file's
 * record already serialized where it was built (`serializeZone`), so the
 * merge holds strings, never the records' object graphs; the document is
 * spliced from them exactly as `JSON.stringify` would write it. */
function finishRepoJson(plan, results) {
  const files = [];
  const errors = [...plan.errors];
  const constructions = new Map();
  for (const result of results) {
    files.push(...result.files);
    errors.push(...result.errors);
    for (const [file, tokens] of result.constructions) constructions.set(file, tokens);
  }
  files.sort((a, b) => a[0].localeCompare(b[0]));
  errors.sort((a, b) => a.path.localeCompare(b.path) || a.stage.localeCompare(b.stage));
  return (
    '{"constructions":' +
    JSON.stringify(Object.fromEntries([...constructions].sort((a, b) => a[0].localeCompare(b[0])))) +
    ',"errors":' + JSON.stringify(errors) +
    ',"files":[' + files.map(([, json]) => json).join(",") + "]" +
    ',"helper_version":' + JSON.stringify(HELPER_VERSION) +
    ',"tsconfigs":' + JSON.stringify(plan.zones.map(([zone]) => zone).filter(Boolean).sort()) +
    "}"
  );
}

/** A zone's result with each file's record serialized, for `finishRepoJson`. */
function serializeZone(result) {
  return {
    files: result.files.map((record) => [record.path, JSON.stringify(record)]),
    errors: result.errors,
    constructions: result.constructions,
  };
}

/** What `planRepo` decided, as plain data a worker can post. */
function planMessage(plan) {
  return { root: plan.root, fileSet: plan.fileSet, packages: plan.packages, zones: plan.zones, errors: plan.errors };
}

/** The repo's facts, every zone in this thread, one after another. */
export function extractRepo(repoRoot) {
  const plan = planRepo(repoRoot);
  return JSON.parse(finishRepoJson(
    plan,
    plan.zones.map(([zone, zoneFiles]) =>
      serializeZone(extractZone(plan.root, zone, zoneFiles, plan.fileSet, plan.packages))),
  ));
}

/** A zone that outran its cap (ADR-184, C-196): its files stay listed —
 * discovery found them — with no facts, and one record says why. */
export function zoneTimedOut(zone, zoneFiles, seconds, jobs = 1) {
  const sample = zoneFiles.slice(0, 4).join(", ");
  // Zones that run at once share the box, so a zone near its cap can finish
  // one at a time and not beside others: the knob that says so is named.
  const beside = jobs > 1
    ? `; ${jobs} zones ran at once (HOBBES_TS_JOBS=1 runs them one at a time)`
    : "";
  return {
    files: zoneFiles.map((file) => ({
      calls: [], env_reads: [], imports: [], path: file, routes: [], routes_declined: [],
      symbols: [], test_framework: null, tests: [],
    })),
    errors: [{
      message:
        `the zone ${zone || "under the default compiler options"} did not finish within its ${seconds} s cap ` +
        `(C-196; HOBBES_TIMEOUT_SCALE raises every cap${beside}): its ${zoneFiles.length} file(s) (${sample}` +
        `${zoneFiles.length > 4 ? ", …" : ""}) are listed with no facts — no import, call, symbol, route ` +
        "or test is drawn from them",
      path: zone || ".",
      stage: "zone-timeout",
    }],
    constructions: [],
  };
}

/** The repo's facts with its zones on worker threads, at most *jobs* at a
 * time, the largest first, each under its own cap (ADR-184 lever 2). The
 * merge is `extractRepo`'s, in zone order, so a run whose every zone
 * finishes is the same bytes as the serial one. A zone past its cap is
 * stopped and recorded (`zoneTimedOut`); a zone whose worker fails
 * otherwise fails the run, as it would in the serial loop. */
/** A worker whose heap has grown past this after a zone is retired and the
 * lane's next zone goes to a fresh one. V8 keeps a heap it has grown, so a
 * worker that ran a large zone would otherwise hold that zone's garbage
 * beside the next zone's program; a fresh worker costs one load of the
 * compiler. Small zones share a worker, which is where the reuse pays. */
const RECYCLE_HEAP_BYTES = 300 * 1024 * 1024;

/** The longest delay setTimeout keeps: a 32-bit signed count of ms. */
const MAX_TIMER_MS = 2 ** 31 - 1;

export async function extractRepoParallel(repoRoot, options = {}) {
  return JSON.parse(await extractRepoParallelJson(repoRoot, options));
}

/** `extractRepoParallel`'s facts as the JSON document the CLI prints.
 *
 * The workers live for the whole run, each taking the next zone as it
 * finishes the last, so the compiler is loaded once per worker rather than
 * once per zone (ADR-184's amendment, 2026-11-02). The first worker plans
 * the repo too, so this thread never loads it. A zone's cap runs from when
 * the zone is handed over; a zone past it stops its worker, is recorded
 * (`zoneTimedOut`), and a fresh worker takes that lane's next zone. */
export async function extractRepoParallelJson(repoRoot, { jobs = 1, zoneTimeoutSeconds = 300 } = {}) {
  const spawn = (init) => {
    const worker = new Worker(new URL(import.meta.url), { workerData: { hobbesWorker: true, ...init } });
    // Messages and failures arrive here in order; `next` hands the next one
    // to whoever is waiting.
    const inbox = [];
    let waiting = null;
    const deliver = (item) => {
      if (waiting) {
        const w = waiting;
        waiting = null;
        w(item);
      } else inbox.push(item);
    };
    worker.on("message", (message) => deliver({ message }));
    worker.on("error", (error) => deliver({ error }));
    worker.on("exit", (code) => deliver({ exit: code }));
    const next = () => (inbox.length ? Promise.resolve(inbox.shift()) : new Promise((r) => { waiting = r; }));
    return { worker, next };
  };
  const fail = (item, what) => {
    if (item.error) throw item.error;
    throw new Error(`the zone worker for ${what} exited ${item.exit} with no facts`);
  };

  const first = spawn({ repoRoot: path.resolve(repoRoot) });
  const planned = await first.next();
  if (!planned.message) fail(planned, "the repo's plan");
  const plan = planned.message.plan;
  const results = new Array(plan.zones.length);
  const width = Math.max(1, Math.min(jobs, plan.zones.length));
  const order = plan.zones
    .map((_, i) => i)
    .sort((a, b) => plan.zones[b][1].length - plan.zones[a][1].length || a - b);
  const fresh = () => spawn({ plan });
  const ms = zoneTimeoutSeconds * 1000;
  // A zone on *handle*'s worker: its result, or its timeout record (and
  // the worker stopped, so the lane needs a fresh one).
  const runZone = async (handle, i) => {
    const [zone, zoneFiles] = plan.zones[i];
    handle.worker.postMessage({ zone: i });
    let timer;
    // Past setTimeout's own limit (about 24.8 days) Node fires at once,
    // which would stop every zone: there the zone has no cap of its own,
    // and the whole run's backstop holds.
    const capped = ms <= MAX_TIMER_MS
      ? new Promise((resolve) => { timer = setTimeout(() => resolve({ timedOut: true }), ms); })
      : new Promise(() => {});
    const item = await Promise.race([handle.next(), capped]);
    clearTimeout(timer);
    if (item.timedOut) {
      await handle.worker.terminate();
      return { result: serializeZone(zoneTimedOut(zone, zoneFiles, zoneTimeoutSeconds, width)), alive: false };
    }
    if (!item.message) fail(item, zone || "the default options");
    if (item.message.heap > RECYCLE_HEAP_BYTES) {
      await handle.worker.terminate();
      return { result: item.message.result, alive: false };
    }
    return { result: item.message.result, alive: true };
  };
  let nextZone = 0;
  let failed = false;
  const handles = [];
  const lane = async (handle) => {
    // A failed zone fails the run, so no lane starts another after it.
    while (nextZone < order.length && !failed) {
      const i = order[nextZone++];
      if (!handle) handle = fresh();
      handles.push(handle);
      try {
        const { result, alive } = await runZone(handle, i);
        results[i] = result;
        if (!alive) handle = null;
      } catch (error) {
        failed = true;
        throw error;
      }
    }
    if (handle) await handle.worker.terminate();
  };
  try {
    await Promise.all(Array.from({ length: width }, (_, k) => lane(k === 0 ? first : null)));
  } finally {
    await Promise.all([first, ...handles].map((h) => h.worker.terminate()));
  }
  return finishRepoJson(plan, results);
}

/** The tsconfig project each TS/JS file of the repo belongs to, by the
 * rule `extractRepo` groups them (`zoneTsconfig`): "" for a file under
 * no config or one no referenced project of a solution config claims.
 * Served as `--zones` to lane B (`scipsource.ts_zone_map`), so a
 * solution-style zone is indexed by exactly the projects lane A types
 * it by — one rule, one implementation, in both lanes (C-98). Reads
 * configs only; executes nothing of the repo's. */
export function zoneMap(repoRoot) {
  const root = path.resolve(repoRoot);
  const cache = new Map();
  const zones = {};
  for (const file of discoverFiles(root)) zones[file] = zoneTsconfig(root, file, cache);
  return { zones };
}

// --- CLI -------------------------------------------------------------------

async function main(argv) {
  let repo = process.cwd();
  let mode = "facts";
  let jobs = 1;
  let zoneTimeoutSeconds = 300;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--repo" && argv[i + 1]) {
      repo = argv[++i];
    } else if (argv[i] === "--zones") {
      mode = "zones";
    } else if (argv[i] === "--jobs" && argv[i + 1]) {
      jobs = Math.max(1, Number.parseInt(argv[++i], 10) || 1);
    } else if (argv[i] === "--zone-timeout" && argv[i + 1]) {
      const seconds = Number(argv[++i]);
      zoneTimeoutSeconds = seconds > 0 ? seconds : 300;
    } else {
      process.stderr.write(`tsextract: unknown argument ${argv[i]}\n`);
      return 2;
    }
  }
  if (mode === "zones") {
    await loadTsMorph();
    process.stdout.write(JSON.stringify(zoneMap(repo)) + "\n");
  } else {
    process.stdout.write(await extractRepoParallelJson(repo, { jobs, zoneTimeoutSeconds }) + "\n");
  }
  return 0;
}

// process.exitCode, never process.exit(): exiting eagerly truncates
// stdout at the 64KB pipe buffer on large repos. A zone worker loads this
// file too, with the same argv, so only the main thread runs the CLI.
if (IS_CLI_MAIN) {
  main(process.argv.slice(2)).then(
    (code) => { process.exitCode = code; },
    (error) => { process.stderr.write(`tsextract: ${error?.stack ?? error}\n`); process.exitCode = 1; },
  );
}

// A zone worker (ADR-184): it plans the repo if it was not handed a plan
// (the first worker, which posts the plan back), then extracts each zone the
// main thread names, posting back its facts with each file's record
// serialized (`serializeZone`), until it is stopped.
if (!isMainThread && workerData && workerData.hobbesWorker) {
  let plan = workerData.plan;
  if (!plan) {
    plan = planMessage(planRepo(workerData.repoRoot));
    parentPort.postMessage({ plan });
  }
  parentPort.on("message", ({ zone: i }) => {
    const [zone, zoneFiles] = plan.zones[i];
    const result = serializeZone(extractZone(plan.root, zone, zoneFiles, plan.fileSet, plan.packages));
    // The heap this zone left behind: the main thread retires a worker
    // whose heap has grown past RECYCLE_HEAP_BYTES, so a large zone's
    // garbage is never carried into the next zone's peak.
    parentPort.postMessage({ result, heap: v8.getHeapStatistics().total_heap_size });
  });
}
