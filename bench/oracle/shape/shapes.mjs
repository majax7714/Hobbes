// The callee-shape record (bench tooling, 2026-09-10): every call site of a
// TS zone with the checker's reading of the callee expression — an
// identifier's declaration kind, a member's receiver shape, the resolved
// signature's declaration — so an oracle cell's misses can be bucketed
// by *what the call is written on* (docs/oracle/oracle-misses.md, the
// callee-shape bucket). Reads ts-morph from tsextract/node_modules.
//   node bench/oracle/shape/shapes.mjs <repo-root> > shapes.json
// `calleeShapes(root)` is the walk; `shapes.test.mjs` drives it on a
// built repo (run by `go test` in this directory).
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
const require = createRequire(new URL("../../../tsextract/", import.meta.url));
const { Project, Node, ts } = require("ts-morph");

// One declaration's kind, as the bucket reads it: a variable spelled
// `var:<kw>:<top|nested>:<initializer>`, everything else by its node.
export function declKind(d) {
  if (Node.isFunctionDeclaration(d)) return "function-decl";
  if (Node.isMethodDeclaration(d)) return "method";
  if (Node.isMethodSignature(d)) return "method-signature";
  if (Node.isPropertySignature(d)) return "property-signature";
  if (Node.isPropertyDeclaration(d)) return "property-decl";
  if (Node.isClassDeclaration(d)) return "class";
  if (Node.isParameterDeclaration(d)) return "param";
  if (Node.isImportSpecifier(d) || Node.isImportClause(d) || Node.isNamespaceImport(d)) return "import";
  if (Node.isVariableDeclaration(d)) {
    const init = d.getInitializer();
    const vs = d.getVariableStatement();
    const top = vs && Node.isSourceFile(vs.getParent());
    let ik = "none";
    if (init) {
      if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) ik = "fn-literal";
      else if (Node.isCallExpression(init)) ik = "call-result";
      else ik = init.getKindName();
    }
    const kw = vs ? vs.getDeclarationKind() : "?";
    return `var:${kw}:${top ? "top" : "nested"}:${ik}`;
  }
  if (Node.isBindingElement(d)) return "binding-element";
  if (Node.isShorthandPropertyAssignment(d) || Node.isPropertyAssignment(d)) return "object-literal-member";
  if (Node.isCallSignatureDeclaration(d)) return "call-signature";
  if (Node.isFunctionExpression(d) || Node.isArrowFunction(d)) return "fn-literal";
  return d.getKindName();
}

function declsOf(root, node) {
  const sym = node.getSymbol();
  if (!sym) return [];
  const s = sym.getAliasedSymbol?.() ?? sym;
  let decls = s.getDeclarations();
  if (!decls.length) decls = sym.getDeclarations();
  return decls.map(d => ({ kind: declKind(d), file: path.relative(root, d.getSourceFile().getFilePath()), line: d.getStartLineNumber(), ext: d.getSourceFile().getFilePath().includes("node_modules") }));
}

function receiverShape(root, r) {
  if (Node.isThisExpression(r)) return "this";
  if (Node.isSuperExpression(r)) return "super";
  if (Node.isCallExpression(r)) return "call-result";
  if (Node.isElementAccessExpression(r)) return "element";
  if (Node.isPropertyAccessExpression(r)) return "property-chain";
  if (Node.isIdentifier(r)) {
    const ds = declsOf(root, r);
    const k = ds.length ? ds[0].kind : "unresolved";
    return `ident:${k}`;
  }
  if (Node.isNewExpression(r)) return "new";
  if (Node.isParenthesizedExpression(r)) return "paren";
  return r.getKindName();
}

// Every call site of the zone under <root>/tsconfig.json: one record per
// CallExpression with the callee's shape, the terminal name's
// declarations and the resolved signature's declaration. Lines are
// 1-based, columns 0-based; `line`/`col` name the terminal identifier
// (the oracle's site), `cline`/`ccol` the callee expression's start.
export function calleeShapes(root) {
  const project = new Project({ tsConfigFilePath: path.join(root, "tsconfig.json"),
    compilerOptions: { allowJs: true, checkJs: false, noEmit: true, skipLibCheck: true } });
  const out = [];
  for (const sf of project.getSourceFiles()) {
    const fp = sf.getFilePath();
    if (fp.includes("node_modules")) continue;
    const rel = path.relative(root, fp);
    sf.forEachDescendant(node => {
      if (!Node.isCallExpression(node)) return;
      const callee = node.getExpression();
      let shape, terminal = null, recv = null;
      if (Node.isIdentifier(callee)) { shape = "identifier"; terminal = callee; }
      else if (Node.isPropertyAccessExpression(callee)) { shape = "member"; terminal = callee.getNameNode(); recv = receiverShape(root, callee.getExpression()); }
      else if (Node.isElementAccessExpression(callee)) { shape = "computed"; }
      else if (Node.isCallExpression(callee)) { shape = "call-result-callee"; }
      else if (Node.isParenthesizedExpression(callee)) { shape = "paren"; }
      else if (Node.isSuperExpression(callee) || callee.getKind() === ts.SyntaxKind.ImportKeyword) { shape = "keyword"; }
      else if (Node.isArrowFunction(callee) || Node.isFunctionExpression(callee)) { shape = "iife"; }
      else shape = callee.getKindName();
      const pos = sf.getLineAndColumnAtPos(callee.getStart());
      const tpos = terminal ? sf.getLineAndColumnAtPos(terminal.getStart()) : pos;
      const decls = terminal ? declsOf(root, terminal) : [];
      // resolved signature's declaration (what tsc's oracle names)
      let sigDecl = null;
      try {
        const sig = project.getTypeChecker().getResolvedSignature(node);
        const d = sig && sig.getDeclaration();
        if (d) sigDecl = { kind: declKind(d), file: path.relative(root, d.getSourceFile().getFilePath()), line: d.getStartLineNumber() };
      } catch (e) {}
      out.push({ path: rel, js: /\.[cm]?js$/.test(rel), line: tpos.line, col: tpos.column - 1, cline: pos.line, ccol: pos.column - 1,
        name: terminal ? terminal.getText() : callee.getText().slice(0, 40), shape, recv, decls, sigDecl });
    });
  }
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.stdout.write(JSON.stringify(calleeShapes(process.argv[2])));
}
