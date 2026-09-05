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

import { Node, Project, ts } from "ts-morph";

// v2 (V2.M3, ADR-029/031): `calls` carries every call site rather than
// only resolved ones, positioned on the terminal identifier with a
// 0-based `col` and its bare `name`, so the evidence IR can join it
// against SCIP occurrences; `callee`/`callee_path` are null when the
// checker could not resolve it, and are now the join's fallback rather
// than an edge. Test cases carry `end_line`, so reach can be per case.
// v3 (C-5 surfacing): every file carries `routes_declined` — route
// registrations seen and declined because their path is computed, so the
// http-ts pack can report the absence instead of leaving it silent.
export const HELPER_VERSION = 4;
// v4, since 2026-09-05 (C-63 surfaced): a call whose callee is itself an
// expression — an element access, a call's result, a parenthesised
// value — is a `calls` record named `<expr>` alone, with callee and
// origin null: counted, never resolvable. No field changed.
export const EXPR_CALLEE_NAME = "<expr>";

const EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);

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

/** Enclosing top-level-symbol qualname for a node, or null at module level. */
function enclosingScope(node) {
  let current = node.getParent();
  while (current) {
    if (Node.isMethodDeclaration(current)) {
      const cls = current.getFirstAncestorByKind(ts.SyntaxKind.ClassDeclaration);
      const clsName = cls && cls.getName();
      if (clsName) return `${clsName}.${current.getName()}`;
    }
    if (Node.isFunctionDeclaration(current) && current.getName()) {
      return current.getName();
    }
    if (
      (Node.isArrowFunction(current) || Node.isFunctionExpression(current)) &&
      Node.isVariableDeclaration(current.getParent()) &&
      Node.isIdentifier(current.getParent().getNameNode())
    ) {
      return current.getParent().getNameNode().getText();
    }
    current = current.getParent();
  }
  return null;
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
  sourceFile.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    const expr = node.getExpression();
    const isRequire = Node.isIdentifier(expr) && expr.getText() === "require";
    const isDynamic = expr.getKind() === ts.SyntaxKind.ImportKeyword;
    if (!isRequire && !isDynamic) return;
    const specifier = firstStringArg(node);
    if (!specifier) return;
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
  });
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

function extractSymbols(sourceFile) {
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
  return symbols.sort((a, b) => a.line - b.line || a.qualname.localeCompare(b.qualname));
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
  for (const decl of symbol.getDeclarations()) {
    const declFile = decl.getSourceFile();
    const target = relPath(repoRoot, declFile);
    if (!fileSet.has(target)) continue;
    const qualname = declQualname(decl);
    if (qualname) return { path: target, qualname };
  }
  return null;
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
    const target = resolveExpressionTarget(resolveFrom, repoRoot, fileSet);
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
      origin: target
        ? null
        : calleeOrigin(resolveFrom, repoRoot, fileSet, sourceFile),
      scope: enclosingScope(scopeNode),
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
    });
  };
  sourceFile.forEachDescendant((node) => {
    if (Node.isCallExpression(node)) {
      const callee = node.getExpression();
      const terminal = terminalIdentifier(callee);
      if (terminal) push(terminal, callee, node);
      // `import(..)` is an import (extractImports reads it) and
      // `super(..)` a keyword, not a value in callee position: neither
      // is a site, as before.
      else if (!isKeywordCallee(callee)) pushExpressionCallee(callee, node);
      return;
    }
    if (Node.isJsxSelfClosingElement(node) || Node.isJsxOpeningElement(node)) {
      const tag = node.getTagNameNode();
      const component =
        (Node.isIdentifier(tag) && /^[A-Z]/.test(tag.getText())) ||
        Node.isPropertyAccessExpression(tag);
      if (!component) return;
      const terminal = terminalIdentifier(tag);
      if (terminal) push(terminal, tag, node);
    }
  });
  return calls.sort(
    (a, b) => a.line - b.line || a.col - b.col || a.name.localeCompare(b.name)
  );
}

function extractEnvReads(sourceFile) {
  const reads = [];
  sourceFile.forEachDescendant((node) => {
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
  });
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
  sourceFile.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    const expr = node.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) return;
    const verb = expr.getName();
    if (!EXPRESS_VERBS.has(verb)) return;
    if (!expressReceiverOk(expr.getExpression())) return;
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
      return;
    }
    if (!routePath.startsWith("/")) return;
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
  });
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
  sourceFile.forEachDescendant((node) => {
    if (
      Node.isCallExpression(node) &&
      Node.isIdentifier(node.getExpression()) &&
      ["describe", "it", "test"].includes(node.getExpression().getText())
    ) {
      usesGlobals = true;
    }
  });
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

function describeChain(node) {
  const titles = [];
  let current = node.getParent();
  while (current) {
    if (Node.isCallExpression(current) && testCallName(current) === "describe") {
      const title = firstStringArg(current);
      if (title) titles.unshift(title);
    }
    current = current.getParent();
  }
  return titles;
}

function extractTests(sourceFile, filePath, imports) {
  const framework = testFramework(sourceFile, filePath, imports);
  if (!framework) return { framework: null, cases: [] };
  const cases = [];
  sourceFile.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    const callName = testCallName(node);
    if (callName !== "it" && callName !== "test") return;
    const title = firstStringArg(node);
    if (title === null) return;
    cases.push({
      line: node.getStartLineNumber(),
      // The case's extent, so reach can be attributed per case rather than
      // per file (C-11). A JS test body is an anonymous closure with no
      // symbol to hang an edge on, so range containment is the only way to
      // ask "which calls belong to this `it()`".
      end_line: node.getEndLineNumber(),
      qualname: [...describeChain(node), title].join(" > "),
    });
  });
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

export function extractRepo(repoRoot) {
  const root = path.resolve(repoRoot);
  const files = discoverFiles(root);
  const fileSet = new Set(files);
  const packages = discoverWorkspacePackages(root);

  // Files group by their nearest tsconfig.json ("zones"), one ts-morph
  // Project per zone, so per-package compiler options — path aliases
  // above all — resolve the way that package's own build does. Files
  // under no tsconfig share a default allowJs project. Cross-zone
  // imports don't resolve (separate programs); accepted, rare.
  const zones = new Map();
  for (const file of files) {
    const zone = nearestTsconfig(root, file);
    if (!zones.has(zone)) zones.set(zone, []);
    zones.get(zone).push(file);
  }

  const out = [];
  const errors = [];
  for (const [zone, zoneFiles] of [...zones.entries()].sort()) {
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
  out.sort((a, b) => a.path.localeCompare(b.path));
  errors.sort((a, b) => a.path.localeCompare(b.path) || a.stage.localeCompare(b.stage));
  return {
    errors,
    files: out,
    helper_version: HELPER_VERSION,
    tsconfigs: [...zones.keys()].filter(Boolean).sort(),
  };
}

// --- CLI -------------------------------------------------------------------

function main(argv) {
  let repo = process.cwd();
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--repo" && argv[i + 1]) {
      repo = argv[++i];
    } else {
      process.stderr.write(`tsextract: unknown argument ${argv[i]}\n`);
      return 2;
    }
  }
  process.stdout.write(JSON.stringify(extractRepo(repo)) + "\n");
  return 0;
}

// process.exitCode, never process.exit(): exiting eagerly truncates
// stdout at the 64KB pipe buffer on large repos.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}
