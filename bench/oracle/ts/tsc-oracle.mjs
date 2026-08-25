// The TypeScript resolution oracle (design §5, ADR-089): the zone's own
// `tsc` resolves every call site; the oracle records what it resolved
// to. Loads `typescript` from the zone itself when the zone has one
// (the compiler the project pins — the same environment lane B indexed
// under), else from this directory.
//
//   node tsc-oracle.mjs --repo <repo> --zone <dir-with-tsconfig> --out <file>
//
// Emits the OracleExport shape of bench/oracle/internal/edges: kind
// "resolution", one site per CallExpression / NewExpression /
// TaggedTemplateExpression / Decorator / JSX element, targets = every
// declaration of the resolved signature's symbol (overload-set
// membership, D-O4), positions = repo-relative path + 1-based line of
// the declaration's *name* identifier. A site with no resolved
// signature, or a signature with no declaration (any, synthetic union
// apply), has no targets: oracle-silent (no-targets).
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, arr) => {
    if (a.startsWith("--")) acc.push([a.slice(2), arr[i + 1]]);
    return acc;
  }, []),
);
if (!args.repo || !args.zone) {
  console.error("usage: tsc-oracle.mjs --repo <repo> --zone <dir> [--out <file>]");
  process.exit(2);
}
const repo = path.resolve(args.repo);
const zone = path.resolve(repo, args.zone);
const zoneRel = path.relative(repo, zone).split(path.sep).join("/");

let ts, tsFrom;
try {
  const req = createRequire(path.join(zone, "package.json"));
  tsFrom = req.resolve("typescript");
  ts = req("typescript");
} catch {
  const req = createRequire(import.meta.url);
  tsFrom = req.resolve("typescript");
  ts = req("typescript");
}

const configPath = ts.findConfigFile(zone, ts.sys.fileExists, "tsconfig.json");
if (!configPath) {
  console.error(`oracle: no tsconfig.json at ${zone}`);
  process.exit(1);
}
const cfg = ts.readConfigFile(configPath, ts.sys.readFile);
if (cfg.error) {
  console.error("oracle:", ts.flattenDiagnosticMessageText(cfg.error.messageText, "\n"));
  process.exit(1);
}
const parsed = ts.parseJsonConfigFileContent(cfg.config, ts.sys, path.dirname(configPath));
const program = ts.createProgram({ rootNames: parsed.fileNames, options: { ...parsed.options, noEmit: true } });
const checker = program.getTypeChecker();

const rel = (file) => path.relative(repo, file).split(path.sep).join("/");
const inRepo = (file) => !path.relative(repo, file).startsWith("..") && !file.includes("/node_modules/");
const underZone = (r) => zoneRel === "" || zoneRel === "." || r === zoneRel || r.startsWith(zoneRel + "/");
const line1 = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
const col1 = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).character + 1;

// The declaration's name identifier, per D-O4: a function/method/class
// keeps its own name; an arrow or function expression takes the name it
// is bound to (variable, property, parameter); a constructor is its
// class. Falls back to the declaration start.
function nameNode(decl) {
  if (!decl) return null;
  if (ts.isConstructorDeclaration(decl)) return decl.parent.name ?? decl;
  if (decl.name) return decl.name;
  if ((ts.isArrowFunction(decl) || ts.isFunctionExpression(decl)) && decl.parent) {
    const p = decl.parent;
    if (p.name) return p.name;
    if (ts.isBinaryExpression(p)) return p.left;
  }
  return decl;
}

// A closure, for the miss classes: a function-like declared inside
// another function's body rather than at module or class level.
function isClosure(decl) {
  let n = decl.parent;
  while (n) {
    if (ts.isFunctionLike(n)) return true;
    if (ts.isSourceFile(n) || ts.isClassLike(n) || ts.isModuleBlock(n)) return false;
    n = n.parent;
  }
  return false;
}

// What the declaration is, for the miss classes: what a call reaches.
function isClosureScope(decl) { return isClosure(decl); }

function declKind(decl) {
  if (ts.isVariableDeclaration(decl) || ts.isBindingElement(decl)) {
    // handled below: closure vs local-binding vs variable
  } else if (isClosure(decl)) return "closure";
  if (ts.isFunctionDeclaration(decl)) return "function";
  if (ts.isMethodDeclaration(decl) || ts.isGetAccessor(decl) || ts.isSetAccessor(decl)) return "method";
  if (ts.isClassLike(decl) || ts.isConstructorDeclaration(decl)) return "class";
  if (ts.isArrowFunction(decl) || ts.isFunctionExpression(decl)) {
    const p = decl.parent;
    if (p && ts.isVariableDeclaration(p)) return "variable";
    if (p && (ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p))) return "property";
    return "anonymous-function"; // an IIFE, or a literal passed straight to a call
  }
  if (ts.isVariableDeclaration(decl) || ts.isBindingElement(decl)) {
    // A binding inside a function whose initializer is not itself a
    // function literal (`const [x, setX] = useState()`, `const fn =
    // props.onClick`) is a *local binding*: the oracle can name the
    // variable, not the function behind it.
    const init = ts.isVariableDeclaration(decl) ? decl.initializer : null;
    const isFn = init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
    if (isClosureScope(decl)) return isFn ? "closure" : "local-binding";
    return "variable";
  }
  if (ts.isParameter(decl)) return "parameter";
  if (ts.isPropertySignature(decl) || ts.isMethodSignature(decl)) return "type-member";
  if (ts.isPropertyAssignment(decl) || ts.isPropertyDeclaration(decl) || ts.isShorthandPropertyAssignment(decl)) return "property";
  if (ts.isFunctionTypeNode(decl) || ts.isCallSignatureDeclaration(decl) || ts.isConstructSignatureDeclaration(decl)) return "anonymous-signature";
  return "other";
}

function target(decl) {
  if (ts.isSourceFile(decl)) return null; // a dynamic import(): a module, not a callee declaration
  const sf = decl.getSourceFile && decl.getSourceFile();
  if (!sf) return null; // synthesized (JSX intrinsic, union apply): no declaration to grade against
  const nm = nameNode(decl);
  const file = sf.fileName;
  const external = !inRepo(file) || sf.isDeclarationFile;
  return {
    pos: { path: external ? file : rel(file), line: line1(sf, nm.getStart(sf)) },
    name: (decl.symbol && checker.getFullyQualifiedName(decl.symbol)) || (nm.getText ? nm.getText(sf) : "?"),
    external: external || undefined,
    closure: declKind(decl) === "closure" || undefined,
    kind: declKind(decl),
  };
}

// The site's line is the callee name's line — the identifier lane B's
// occurrence sits on — not the parenthesis: `a\n  .b()` sites at `b`.
function siteName(node) {
  if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
    let e = node.expression;
    while (ts.isPropertyAccessExpression(e) || ts.isElementAccessExpression(e)) e = ts.isPropertyAccessExpression(e) ? e.name : e;
    return e;
  }
  if (ts.isTaggedTemplateExpression(node)) return node.tag;
  if (ts.isDecorator(node)) return ts.isCallExpression(node.expression) ? siteName(node.expression) : node.expression;
  if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) return node.tagName;
  return node;
}

function callerName(fn, sf) {
  const nm = nameNode(fn);
  if (nm === fn || !nm.getText) return "<anonymous>";
  return nm.getText(sf);
}

function isSite(node) {
  return (
    ts.isCallExpression(node) || ts.isNewExpression(node) || ts.isTaggedTemplateExpression(node) ||
    ts.isDecorator(node) || ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)
  );
}

const files = [];
const sites = [];
let enclosing = [];
for (const sf of program.getSourceFiles()) {
  if (sf.isDeclarationFile || !inRepo(sf.fileName)) continue;
  const r = rel(sf.fileName);
  if (!underZone(r)) continue;
  files.push(r);
  const visit = (node) => {
    const fnLike = ts.isFunctionLike(node) && !ts.isTypeNode(node);
    if (fnLike) enclosing.push(node);
    if (isSite(node)) {
      const nm = siteName(node);
      const site = {
        pos: { path: r, line: line1(sf, nm.getStart(sf)) },
        col: col1(sf, nm.getStart(sf)),
        caller: enclosing.length ? callerName(enclosing[enclosing.length - 1], sf) : "<module>",
        mode: "static",
        targets: [],
      };
      let sig;
      try { sig = checker.getResolvedSignature(node); } catch { sig = undefined; }
      const decl = sig && sig.getDeclaration();
      // The callee's *binding* (D-O4): when the resolved signature is an
      // anonymous call signature — a type literal's or interface's
      // `(...): T`, the shape of every `const useX = create(...)` hook
      // and every callback parameter — the identity of the callee is
      // the variable / property / parameter it was called through, not
      // the signature's home in a .d.ts. Both product lanes resolve to
      // the binding; the oracle lists it as a target labelled `binding`.
      const anonymous = decl && !(ts.isFunctionDeclaration(decl) || ts.isMethodDeclaration(decl) || ts.isMethodSignature(decl) ||
        ts.isConstructorDeclaration(decl) || ts.isArrowFunction(decl) || ts.isFunctionExpression(decl) || ts.isClassLike(decl) ||
        ts.isGetAccessor(decl) || ts.isSetAccessor(decl));
      if (!decl || anonymous) {
        let sym;
        try { sym = checker.getSymbolAtLocation(nm); } catch { sym = undefined; }
        if (sym && sym.flags & ts.SymbolFlags.Alias) { try { sym = checker.getAliasedSymbol(sym); } catch {} }
        for (const d of (sym && sym.declarations) || []) {
          if (ts.isVariableDeclaration(d) || ts.isPropertySignature(d) || ts.isPropertyDeclaration(d) || ts.isParameter(d) || ts.isBindingElement(d) || ts.isShorthandPropertyAssignment(d) || ts.isPropertyAssignment(d)) {
            const t = target(d);
            if (t) {
              t.via = "binding";
              site.targets.push(t);
              // How the call is made, from what it was called through:
              // a type member is an interface dispatch; a parameter, a
              // local binding, or a variable without a function literal
              // behind it is a function value. tsc itself does not
              // distinguish — this is the binding's shape, stated so the
              // miss classes read the same as Go's.
              if (t.kind === "type-member") { site.mode = "dynamic"; site.interface = t; }
              else if (t.kind === "parameter" || t.kind === "local-binding" || (t.kind === "variable" && !(d.initializer && (ts.isArrowFunction(d.initializer) || ts.isFunctionExpression(d.initializer))))) site.mode = "dynamic";
            }
          }
        }
      }
      const boundAlready = site.targets.length > 0;
      if (decl && !(anonymous && boundAlready)) {
        // Overload set: every declaration of the symbol the signature
        // belongs to; a signature without a symbol (a type literal's call
        // signature) contributes its own declaration only.
        const sym = decl.symbol && decl.symbol.flags & (ts.SymbolFlags.Function | ts.SymbolFlags.Method | ts.SymbolFlags.Class | ts.SymbolFlags.Constructor)
          ? (ts.isConstructorDeclaration(decl) ? decl.parent.symbol : decl.symbol)
          : null;
        const decls = sym && sym.declarations ? sym.declarations.filter((d) => ts.isFunctionLike(d) || ts.isClassLike(d)) : [decl];
        const seen = new Set(site.targets.map((t) => t.pos.path + ":" + t.pos.line));
        for (const d of decls.length ? decls : [decl]) {
          const t = target(d);
          if (!t) continue;
          const k = t.pos.path + ":" + t.pos.line;
          if (!seen.has(k)) { seen.add(k); site.targets.push(t); }
        }
      }
      sites.push(site);
    }
    ts.forEachChild(node, visit);
    if (fnLike) enclosing.pop();
  };
  visit(sf);
}
files.sort();
sites.sort((a, b) => a.pos.path.localeCompare(b.pos.path) || a.pos.line - b.pos.line || a.col - b.col);
const out = {
  oracle: `tsc ${ts.version} (${tsFrom.includes(zone) ? "the zone's own" : "harness"})`,
  kind: "resolution",
  module: zoneRel || ".",
  roots: [],
  tags: [],
  files,
  sites,
};
const text = JSON.stringify(out, null, 2) + "\n";
if (args.out) writeFileSync(args.out, text); else process.stdout.write(text);
console.error(`tsc-oracle: ${files.length} files, ${sites.length} sites, typescript ${ts.version} from ${tsFrom}`);
