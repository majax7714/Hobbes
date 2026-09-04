"""Grounder v0 — Calvin's slot with the residual set to zero (`docs/calvin-potential.md` §2.3; step 3 of §8).

Deterministic and model-free. In: a template (`hobbes.derive.holes`
v0), the orchestrator's fills, the ledger at the parent SHA and the
repo read only through ``git`` at that SHA. Out: a diff that applies at
the SHA, a **NULL list**, a **read-trace**, and the counts the charter's
invariants are measured by (`docs/calvin-charter.md` §4).

**Placement (I3).** Every fill lands in the span its hole names, or in
the span the fill itself names (a ``FREEFORM`` entry, a ``NEW_SYMBOL``
after a symbol / in a region / at end of file — recorded which). A span
``{start, end}`` with ``end == start - 1`` is an insertion point before
``start``; a path absent at the SHA is created. Two fills claiming the
same lines are refused, not merged. The pruning rules run first
(`template.prune`): a fill for a hole a rule closed is ignored and
reported. An open hole with no fill and no pattern is reported as
``unfilled`` — silence on a site is a defect (I4), not an answer.

**Grounding (I1, I2).** The post-image of every edited file is parsed
by the language's lane-A provider (tree-sitter for Python and Go; the
``tsextract`` helper for TS/JS on a scratch tree of the edited files)
and every **call site** inside an edited range is resolved against the
graph at the parent SHA plus the **gensyms** — symbols the post-image
declares that the graph lacks, and terms the fills declared ``new``.
**Exact match or NULL**: no basename fallback, no fuzzy step. What is
*not* a NULL is what lane A itself does not resolve to a symbol and says
so: a builtin (the tail view's pinned lists, C-32), a local binding in
scope (ADR-046), a method on a local or expression receiver (C-63/C-80),
a name reached through an import that is not a repo module (external,
unverifiable at this SHA), a receiver that is a package-level value.
Each NULL carries the term, the fill, the line, the nearest graph names
(recorded, not used) and its §4.3 class: ``new`` when a fill declared
it, ``near-miss`` when the exact name exists in another module or a
graph name is within edit distance 3, else ``invented``. Rust and Java
fills are placed but not grounded in v0 (no unit needs them; C-91), and
a non-code file is ``not-code``. Type references, decorators and
composite literals are not call sites and are not grounded (C-91).

**HSR (§4.6)** is NULL over (in-graph + NULL), the cell's definition
with the grounder's classes; on the gold diffs it must read 0 and any
NULL is a grounder defect. ``fills_from_diff`` turns a diff into fills
against a template — the charter's "handed a raw draft diff" case and
step 3's exit instrument: every change block attributed to the open
hole whose span holds it, else a ``FREEFORM`` entry; a block inside a
hole a pruning rule closed is counted (``in_closed``), because that is
the rule being wrong.
"""
from __future__ import annotations

import collections
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath

from hobbes.derive import holes as H
from hobbes.derive.template import Ledger, prune
from hobbes.extract.tail import GO_BUILTINS, PY_BUILTINS, language_of

GROUNDER_VERSION = 0
EXPR = "<expr>"
#: The reference classes; ``NULL`` is the only failure (I2). Everything else is what lane A resolves or abstains on by rule.
CLASSES = ("in-graph", "gensym", "builtin", "local", "expr", "external", "unknown-receiver", "not-code", "unsupported", "NULL")
NULL_CLASSES = ("new", "near-miss", "invented")
PLACED_TYPES = ("SIGNATURE", "BODY", "MODULE_REGION", "CALLER_UPDATE", "TEST_EXPECTATION", "COCHANGE_TOUCH", "NEW_SYMBOL", "FREEFORM")
_NEAR = 3
_CHANGE_PRIORITY = ("BODY", "CALLER_UPDATE", "TEST_EXPECTATION", "MODULE_REGION")


# ------------------------------------------------------------------- trace

class Trace:
    """The read-trace (charter §4.2.3): every ledger or repo lookup, in order, with what it returned."""

    def __init__(self):
        self.rows: list[dict] = []

    def look(self, op: str, key, result):
        self.rows.append({"op": op, "key": key, "result": result})
        return result


@lru_cache(maxsize=4096)
def _show(repo_root: str, sha: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=repo_root, capture_output=True, text=True, errors="surrogateescape")
    return r.stdout if r.returncode == 0 else None


def file_at(repo_root: Path, sha: str, path: str, trace: Trace | None = None) -> list[str] | None:
    """The file's lines at ``sha`` (no terminators), or None when absent; traced."""
    text = _show(str(repo_root), sha, path)
    lines = None if text is None else text.split("\n")[:-1] if text.endswith("\n") else (text.split("\n") if text else [])
    if trace is not None:
        trace.look("file", f"{path}@{sha[:12]}", "absent" if lines is None else f"{len(lines)} lines")
    return lines


# --------------------------------------------------------------- placement

@dataclass
class Edit:
    hole: str
    type: str
    path: str
    start: int  #: first pre-image line replaced (1-based); an insertion has end == start - 1
    end: int
    lines: list[str]
    placement: str
    created: bool = False


def _lines(code: str) -> list[str]:
    """Code as lines; the empty string is *no* lines (a pure deletion), not one empty line."""
    if code == "":
        return []
    return code.split("\n")[:-1] if code.endswith("\n") else code.split("\n")


def edits_from_fills(template: dict, doc: dict, L: Ledger, repo_root: Path, trace: Trace) -> tuple[list[Edit], dict]:
    """Every fill as an :class:`Edit`, and the report of what could not become one."""
    fills = dict(doc.get("fills") or {})
    patterns = doc.get("patterns") or {}
    sha = template["key"]["parent_sha"]
    rep = {"unfilled": [], "ignored_closed": [], "unknown_hole": [], "refused": [], "notes": [], "closed_by_prune": prune(template, fills), "declared_new": []}
    by_id = {h["id"]: h for h in template["holes"]}
    for hid in sorted(set(fills) - set(by_id)):
        rep["unknown_hole"].append(hid)
    body_of: dict[str, str] = {}  # symbol id → BODY hole id with a code fill
    for h in template["holes"]:
        if h["type"] == "BODY" and isinstance(fills.get(h["id"]), dict) and h.get("provenance", {}).get("symbol"):
            body_of[h["provenance"]["symbol"]] = h["id"]
    for h in template["holes"]:
        if h["type"] == "UNRESOLVED" and isinstance(fills.get(h["id"]), dict):
            rep["declared_new"] += sorted(t for t, c in fills[h["id"]].get("classes", {}).items() if c == "new")
    edits: list[Edit] = []
    for h in template["holes"]:
        hid, typ = h["id"], h["type"]
        if typ not in PLACED_TYPES:
            continue
        if h.get("closed") is not None:
            if hid in fills:
                rep["ignored_closed"].append({"hole": hid, "reason": h["closed"]["reason"]})
            continue
        if "fill" in h:
            continue  # answered in an earlier round
        if hid not in fills:
            if typ in patterns:
                continue
            rep["unfilled"].append(hid)
            continue
        fill = fills[hid]
        errs = H.validate_fill(h, fill)
        if errs:
            rep["refused"].append({"hole": hid, "errors": errs})
            continue
        span = h.get("span")
        if typ == "SIGNATURE":
            if fill == "unchanged":
                continue
            sym = h.get("provenance", {}).get("symbol")
            if sym in body_of:
                rep["notes"].append(f"{hid}: signature carried by {body_of[sym]}'s body")
                continue
            edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["signature"]), "span"))
        elif typ in ("BODY", "MODULE_REGION"):
            if fill != "unchanged":
                edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["code"]), "span"))
        elif typ == "CALLER_UPDATE":
            if fill["decision"] == "yes":
                edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["body"]), "span"))
        elif typ == "TEST_EXPECTATION":
            if fill != "unchanged":
                if fill.get("code"):
                    edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["code"]), "span"))
                else:
                    rep["notes"].append(f"{hid}: an expectation without code places nothing — routed back as a question")
        elif typ == "COCHANGE_TOUCH":
            if fill["decision"] == "yes":
                path = h["provenance"]["partner"]
                old = file_at(repo_root, sha, path, trace)
                edits.append(Edit(hid, typ, path, 1, len(old) if old else 0, _lines(fill["body"]), "whole-file", created=old is None))
        elif typ == "NEW_SYMBOL":
            if "covered_by" in fill:
                for c in fill["covered_by"]:
                    if c not in fills or fills[c] == "unchanged":
                        rep["notes"].append(f"{hid}: covered_by {c}, which carries no code")
                m = re.search(r"`([^`]+)`", h.get("provenance", {}).get("anchor", ""))
                if m:
                    rep["declared_new"].append(m.group(1))
                continue
            rep["declared_new"].append(fill["name"])
            path = fill["file"]
            old = file_at(repo_root, sha, path, trace)
            if fill.get("after_symbol"):
                sid = fill["after_symbol"]
                sp = trace.look("symbol", sid, L.span(sid) if sid in L.symbols else None)
                if sp is None:
                    rep["refused"].append({"hole": hid, "errors": [f"after_symbol {sid!r} is not in the ledger"]})
                    continue
                edits.append(Edit(hid, typ, sp["path"], sp["end"] + 1, sp["end"], [""] + _lines(fill["body"]), f"after {sid}"))
            elif fill.get("region") and fill["region"] != "eof":
                r = by_id.get(fill["region"])
                if not r or not r.get("span"):
                    rep["refused"].append({"hole": hid, "errors": [f"region {fill['region']!r} is not a hole with a span"]})
                    continue
                edits.append(Edit(hid, typ, r["span"]["path"], r["span"]["end"] + 1, r["span"]["end"], _lines(fill["body"]), f"end of region {r['id']}"))
            else:
                n = len(old) if old else 0
                edits.append(Edit(hid, typ, path, n + 1, n, ([""] if old else []) + _lines(fill["body"]), "end of file", created=old is None))
        elif typ == "FREEFORM":
            if fill == "none":
                continue
            for i, f in enumerate(fill if isinstance(fill, list) else [fill]):
                sp = f["span"]
                old = file_at(repo_root, sha, sp["path"], trace)
                edits.append(Edit(f"{hid}[{i}]", typ, sp["path"], sp["start"], sp["end"], _lines(f["code"]), "freeform span", created=old is None))
    return edits, rep


def apply_edits(edits: list[Edit], repo_root: Path, sha: str, trace: Trace) -> tuple[dict[str, list[str]], dict[str, list[str] | None], list[dict], dict[str, list[tuple[int, int]]]]:
    """Post-image lines per path, the pre-image, the refused overlaps, and the edited post-image ranges per path."""
    by_path: dict[str, list[Edit]] = collections.defaultdict(list)
    for e in edits:
        by_path[e.path].append(e)
    post: dict[str, list[str]] = {}
    pre: dict[str, list[str] | None] = {}
    refused: list[dict] = []
    ranges: dict[str, list[tuple[int, int]]] = {}
    for path in sorted(by_path):
        old = file_at(repo_root, sha, path, trace)
        pre[path] = old
        base = old or []
        es = sorted(by_path[path], key=lambda e: (e.start, e.end, e.hole))
        ok: list[Edit] = []
        for e in es:
            if e.end < e.start - 1 or e.start < 1 or e.end > len(base):
                refused.append({"hole": e.hole, "path": path, "reason": f"span {e.start}-{e.end} is outside the file ({len(base)} lines)"})
                continue
            if ok and (e.start <= ok[-1].end or (e.start == ok[-1].start and e.end < e.start)):
                refused.append({"hole": e.hole, "path": path, "reason": f"overlaps {ok[-1].hole} at {path}:{e.start}"})
                continue
            ok.append(e)
        out: list[str] = []
        cur = 1
        rs: list[tuple[int, int]] = []
        for e in ok:
            out += base[cur - 1: e.start - 1]
            rs.append((len(out) + 1, len(out) + len(e.lines)))
            out += e.lines
            cur = e.end + 1
        out += base[cur - 1:]
        post[path] = out
        ranges[path] = rs
    return post, pre, refused, ranges


def unified(path: str, old: list[str] | None, new: list[str]) -> str:
    """One file's diff in the form ``git apply`` takes."""
    head = [f"diff --git a/{path} b/{path}"]
    if old is None:
        head.append("new file mode 100644")
    body = list(difflib.unified_diff(old or [], new, fromfile="/dev/null" if old is None else f"a/{path}", tofile=f"b/{path}", lineterm=""))
    return "\n".join(head + body) + "\n" if body else ""


# --------------------------------------------------------------- references

@dataclass
class Ref:
    name: str
    receiver: str | None  #: None bare; ``<expr>``; else the receiver text (an alias, a local, a package name)
    line: int
    scope: str | None = None
    parts: list[str] = field(default_factory=list)  #: the full dotted chain for Python


@dataclass
class Parsed:
    """What one post-image file yields for grounding, in one shape across languages."""
    lang: str
    symbols: list[dict]  #: {name, qualname, kind, line, end_line}
    refs: list[Ref]
    imports: list[dict]  #: {"bound": name, "module": dotted-or-path, "kind": "module"|"name"|"external", "name"?: imported name}
    locals: list[tuple[str, int, int]]


def _parse_python(text: str) -> Parsed:
    from hobbes.extract import pysource
    p = pysource.parse_source(text.encode())
    imports = []
    for imp in p.imports:
        if isinstance(imp, pysource.PlainImport):
            imports.append({"bound": imp.alias or imp.module.split(".")[0], "module": imp.module if imp.alias else imp.module.split(".")[0], "kind": "module", "full": imp.module})
        else:
            for name, bound in imp.names:
                imports.append({"bound": bound, "module": imp.module, "level": imp.level, "kind": "name", "name": name})
    refs = []
    for c in p.calls:
        parts = c.callee.split(".")
        refs.append(Ref(parts[-1], None if len(parts) == 1 else (EXPR if parts[0] == EXPR else ".".join(parts[:-1])), c.line, c.scope, parts))
    return Parsed("python", [{"name": s.name, "qualname": s.qualname, "kind": s.kind, "line": s.line, "end_line": s.end_line} for s in p.symbols],
                  refs, imports, [(b.name, b.start, b.end) for b in p.local_bindings])


def _parse_go(path: str, text: str) -> Parsed:
    from hobbes.extract import gosource
    g = gosource._parse_file(path, text.encode())
    imports = [{"bound": i["alias"], "module": i["path"], "kind": "module"} for i in g.imports]
    refs = [Ref(c["name"], c["receiver"], c["line"], c.get("scope")) for c in g.calls]
    return Parsed("go", g.symbols, refs, imports, [tuple(b[:3]) for b in g.local_bindings])


#: The callable globals of the JS runtime the helper runs under, pinned the way the tail view pins Python's and Go's
#: (C-32): Node v24.18.0, ``Object.getOwnPropertyNames(globalThis)`` filtered to functions — the ECMAScript
#: constructors and functions plus the WHATWG/Node globals (timers, fetch, URL, TextEncoder…) — minus the
#: ``-e``/REPL conveniences (``assert``, ``events``, ``stream``, ``node:test``) that are not globals in a module.
#: The tail view has no TS/JS builtin list because the checker resolves them there; the grounder reads a
#: post-image the checker has not seen, so it needs one.
JS_BUILTINS = frozenset({
    "AbortController", "AbortSignal", "AggregateError", "Array", "ArrayBuffer", "AsyncDisposableStack", "BigInt",
    "BigInt64Array", "BigUint64Array", "Blob", "Boolean", "BroadcastChannel", "Buffer", "ByteLengthQueuingStrategy",
    "CloseEvent", "CompressionStream", "CountQueuingStrategy", "Crypto", "CryptoKey", "CustomEvent", "DOMException",
    "DataView", "Date", "DecompressionStream", "DisposableStack", "Error", "EvalError", "Event", "EventTarget", "File",
    "FinalizationRegistry", "Float16Array", "Float32Array", "Float64Array", "FormData", "Function", "Headers",
    "Int16Array", "Int32Array", "Int8Array", "Iterator", "Map", "MessageChannel", "MessageEvent", "MessagePort",
    "Navigator", "Number", "Object", "Performance", "PerformanceEntry", "PerformanceMark", "PerformanceMeasure",
    "PerformanceObserver", "PerformanceObserverEntryList", "PerformanceResourceTiming", "Promise", "Proxy",
    "RangeError", "ReadableByteStreamController", "ReadableStream", "ReadableStreamBYOBReader",
    "ReadableStreamBYOBRequest", "ReadableStreamDefaultController", "ReadableStreamDefaultReader", "ReferenceError",
    "RegExp", "Request", "Response", "Set", "SharedArrayBuffer", "String", "SubtleCrypto", "SuppressedError", "Symbol",
    "SyntaxError", "TextDecoder", "TextDecoderStream", "TextEncoder", "TextEncoderStream", "TransformStream",
    "TransformStreamDefaultController", "TypeError", "URIError", "URL", "URLPattern", "URLSearchParams", "Uint16Array",
    "Uint32Array", "Uint8Array", "Uint8ClampedArray", "WeakMap", "WeakRef", "WeakSet", "WebSocket", "WritableStream",
    "WritableStreamDefaultController", "WritableStreamDefaultWriter", "atob", "btoa", "clearImmediate",
    "clearInterval", "clearTimeout", "decodeURI", "decodeURIComponent", "encodeURI", "encodeURIComponent", "escape",
    "eval", "fetch", "isFinite", "isNaN", "parseFloat", "parseInt", "queueMicrotask", "require", "setImmediate",
    "setInterval", "setTimeout", "structuredClone", "unescape",
})
_TS_IMPORT = re.compile(r"""(?:from|import|require\()\s*['"](\.[^'"]+)['"]""")
_TS_EXTS = ("", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", "/index.ts", "/index.js", "/index.mjs")


def _materialize_imports(path: str, text: str, scratch: Path, repo_root: Path, sha: str) -> None:
    """Copy the files a post-image's relative imports name from the parent SHA into the scratch tree, so the helper can resolve them (it drops an import it cannot resolve)."""
    for m in _TS_IMPORT.finditer(text):
        base = str(PurePosixPath(os.path.normpath(str(PurePosixPath(path).parent / m.group(1)))))
        for ext in _TS_EXTS:
            cand = base + ext
            target = scratch / cand
            if target.exists():
                break
            src = _show(str(repo_root), sha, cand)
            if src is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(src, errors="surrogateescape")
                break


_TS_DECL = re.compile(r"\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)")
_TS_DESTRUCT = re.compile(r"\b(?:const|let|var)\s*\{([^}]*)\}\s*=")
_TS_PARAMS = re.compile(r"(?:function\s*[\w$]*\s*|\b)\(([^()]*)\)\s*(?:=>|\{)")


def _parse_ts(path: str, text: str, scratch: Path, repo_root: Path, sha: str) -> Parsed:
    from hobbes.extract import tssource
    target = scratch / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, errors="surrogateescape")
    _materialize_imports(path, text, scratch, repo_root, sha)
    facts = tssource.run_helper(scratch)
    f = next((x for x in facts.get("files", []) if x["path"] == path), None) or {"symbols": [], "calls": [], "imports": []}
    lines = text.split("\n")
    refs = []
    for c in f["calls"]:
        line = lines[c["line"] - 1] if 0 < c["line"] <= len(lines) else ""
        before = line[: c["col"]]
        m = re.search(r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\.\s*$", before)
        receiver = m.group(1) if m else (EXPR if before.rstrip().endswith(".") else None)
        refs.append(Ref(c["name"], receiver, c["line"], c.get("scope")))
    imports = []
    for i in f["imports"]:
        for n in i.get("names", []):
            imports.append({"bound": n, "module": i["specifier"], "kind": "name" if not i.get("external") else "external", "name": n})
    # the helper carries no local bindings; a text read of declarations, destructurings and parameter lists stands in (C-91)
    locs: list[tuple[str, int, int]] = []
    for m in _TS_DECL.finditer(text):
        locs.append((m.group(1), 1, len(lines)))
    for m in _TS_DESTRUCT.finditer(text):
        for n in re.findall(r"[A-Za-z_$][\w$]*", m.group(1)):
            locs.append((n, 1, len(lines)))
    for m in _TS_PARAMS.finditer(text):
        for n in re.findall(r"[A-Za-z_$][\w$]*", m.group(1)):
            locs.append((n, 1, len(lines)))
    return Parsed("ts/js", [{"name": s["name"], "qualname": s.get("qualname", s["name"]), "kind": s["kind"], "line": s["line"], "end_line": s.get("end_line", s["line"])} for s in f["symbols"]],
                  refs, imports, locs)


def parse_post(path: str, text: str, scratch: Path, repo_root: Path, sha: str) -> Parsed | None:
    """The post-image parsed by its language's lane-A provider; None for a language v0 does not ground."""
    lang = language_of(path)
    if lang == "python":
        return _parse_python(text)
    if lang == "go":
        return _parse_go(path, text)
    if lang == "ts/js":
        return _parse_ts(path, text, scratch, repo_root, sha)
    return None


# --------------------------------------------------------------- resolution

class _Resolver:
    """Exact-match resolution against the ledger plus the gensyms, every lookup traced."""

    def __init__(self, L: Ledger, repo_root: Path, sha: str, trace: Trace, post_parsed: dict[str, Parsed], declared: set[str], post_text: dict[str, str] | None = None):
        self.L, self.repo_root, self.sha, self.trace = L, repo_root, sha, trace
        self.declared = declared
        self.post_text = post_text or {}
        self.pkg: dict[str, dict[str, str]] = collections.defaultdict(dict)  # Go: package dir → name → symbol id
        for sid, s in L.symbols.items():
            p = L.mod_path.get(s["module"])
            if p and p.endswith(".go"):
                self.pkg[str(PurePosixPath(p).parent)][s["name"]] = sid
        self.mod_syms: dict[str, dict[str, str]] = collections.defaultdict(dict)  # module → qualname → id
        for sid, s in L.symbols.items():
            self.mod_syms[s["module"]][s.get("qualname", s["name"])] = sid
        self.gensyms: dict[str, set[str]] = collections.defaultdict(set)  # file → names the post-image declares that the graph lacks
        self.gensym_quals: dict[str, set[str]] = collections.defaultdict(set)
        for path, P in post_parsed.items():
            mod = L.path_mod.get(path)
            known = self.mod_syms.get(mod, {}) if mod else {}
            for s in P.symbols:
                if s["qualname"] not in known:
                    self.gensyms[path].add(s["name"])
                    self.gensym_quals[path].add(s["qualname"])
        self.go_mods = self._go_modules()
        self.all_gensyms = set().union(*self.gensyms.values()) if self.gensyms else set()

    def _module_text(self, mod: str) -> str | None:
        """A repo module's source: the post-image when the diff edits it, else the parent's."""
        path = self.L.mod_path.get(mod)
        if path is None:
            return None
        if path in self.post_text:
            return self.post_text[path]
        return _show(str(self.repo_root), self.sha, path)

    def py_reexport(self, mod: str, name: str, depth: int = 0) -> str | None:
        """``from X import name`` where X's own source from-imports *name* from a repo module that declares it: the symbol id one hop away (a package ``__init__`` re-export). Exact; at most three hops."""
        if depth > 2:
            return None
        text = self._module_text(mod)
        if text is None:
            return None
        from hobbes.extract import pysource
        for imp in pysource.parse_source(text.encode()).imports:
            if isinstance(imp, pysource.FromImport):
                for imported, bound in imp.names:
                    if bound != name:
                        continue
                    tm = self.py_module(mod, imp.module, imp.level)
                    if tm is None:
                        return None
                    sid = self.trace.look("symbol", f"{tm}.{imported}", self.mod_syms.get(tm, {}).get(imported))
                    if sid:
                        return self.trace.look("re-export", f"{mod}.{name}", sid)
                    return self.py_reexport(tm, imported, depth + 1)
        return None

    def py_module_value(self, mod: str, name: str) -> bool:
        """Whether *name* is bound at module level in *mod*'s source (a constant, a table, a compiled regex) — a value lane A does not model as a symbol, so a member on it is unverifiable, not a NULL."""
        text = self._module_text(mod)
        if text is None:
            return False
        return self.trace.look("module-value", f"{mod}.{name}", bool(re.search(rf"^{re.escape(name)}\s*(?::[^=\n]*)?=", text, re.M)))

    def _go_modules(self) -> dict[str, str]:
        """module path → directory, from every go.mod at the SHA (the join's own source of package identity)."""
        r = subprocess.run(["git", "ls-tree", "-r", "--name-only", self.sha], cwd=self.repo_root, capture_output=True, text=True)
        out = {}
        for p in r.stdout.split("\n"):
            if p == "go.mod" or p.endswith("/go.mod"):
                text = _show(str(self.repo_root), self.sha, p) or ""
                m = re.search(r"^module\s+(\S+)", text, re.M)
                if m:
                    out[m.group(1)] = str(PurePosixPath(p).parent) if "/" in p else ""
        return out

    def go_package_dir(self, import_path: str) -> str | None:
        for mod in sorted(self.go_mods, key=len, reverse=True):
            if import_path == mod or import_path.startswith(mod + "/"):
                d = self.go_mods[mod]
                rest = import_path[len(mod):].lstrip("/")
                return "/".join(x for x in (d, rest) if x)
        return None

    def py_module(self, this_mod: str | None, module: str, level: int) -> str | None:
        """A Python import target as a graph module id, or None when it is not one (external or unknown). A relative import is resolved as the graph builder resolves it: from the package itself when the importer is a package ``__init__``, else from the importer's parent."""
        if level and this_mod:
            parts = this_mod.split(".")
            if not (self.L.mod_path.get(this_mod) or "").endswith("__init__.py"):
                parts = parts[:-1]
            cut = len(parts) - (level - 1)
            if cut < 0:
                return self.trace.look("module", f"{'.' * level}{module}", None)
            module = ".".join(parts[:cut] + ([module] if module else []))
        return self.trace.look("module", module, module if module in self.L.mod_path else None)

    def _near(self, name: str) -> list[str]:
        return self.L.nearest(name)

    def null(self, term: str, path: str) -> tuple[str, list[str], str]:
        near = self._near(term)
        if term in self.declared:
            cls = "new"
        elif term in self.L.by_name:
            cls = "near-miss"  # the exact name exists, in another module: a placement or import miss, not an invention
        elif any(_edit_distance(term.lower(), n.lower()) <= _NEAR for n in near):
            cls = "near-miss"
        else:
            cls = "invented"
        return "NULL", near, cls

    def in_scope_local(self, P: Parsed, name: str, line: int) -> bool:
        return any(n == name and a <= line <= b for n, a, b in P.locals)

    def resolve(self, path: str, P: Parsed, r: Ref) -> tuple[str, str | None]:
        """(class, target) for one reference."""
        if r.receiver == EXPR:
            return "expr", None
        if P.lang == "go":
            return self._go(path, P, r)
        if P.lang == "python":
            return self._py(path, P, r)
        return self._ts(path, P, r)

    def _go(self, path: str, P: Parsed, r: Ref) -> tuple[str, str | None]:
        T = self.trace
        d = str(PurePosixPath(path).parent)
        if r.receiver is None:
            if r.name in GO_BUILTINS:
                return "builtin", None
            if self.in_scope_local(P, r.name, r.line):
                return "local", None
            sid = T.look("package", f"{d}:{r.name}", self.pkg.get(d, {}).get(r.name))
            if sid:
                return "in-graph", sid
            if any(r.name in self.gensyms[p] for p in self.gensyms if str(PurePosixPath(p).parent) == d):
                return "gensym", r.name
            return "NULL", None
        imp = next((i for i in P.imports if i["bound"] == r.receiver), None)
        if imp is not None:
            pd = T.look("import", imp["module"], self.go_package_dir(imp["module"]))
            if pd is None:
                return "external", imp["module"]
            sid = T.look("package", f"{pd}:{r.name}", self.pkg.get(pd, {}).get(r.name))
            if sid:
                return "in-graph", sid
            if any(r.name in self.gensyms[p] for p in self.gensyms if str(PurePosixPath(p).parent) == pd):
                return "gensym", r.name
            return "NULL", None
        if self.in_scope_local(P, r.receiver, r.line):
            return "local", r.receiver
        return "unknown-receiver", r.receiver

    def _py(self, path: str, P: Parsed, r: Ref) -> tuple[str, str | None]:
        L, T = self.L, self.trace
        mod = L.path_mod.get(path)
        parts = r.parts
        head = parts[0]
        quals = dict(self.mod_syms.get(mod, {})) if mod else {}
        gens = self.gensym_quals.get(path, set())

        def local_symbol(qual: str):
            sid = T.look("symbol", f"{mod}.{qual}" if mod else qual, quals.get(qual))
            if sid:
                return "in-graph", sid
            if qual in gens:
                return "gensym", qual
            return None

        if head in ("self", "cls") and len(parts) == 2 and r.scope:
            sp = r.scope.split(".")
            for depth in range(len(sp), 0, -1):
                prefix = ".".join(sp[:depth])
                hit = local_symbol(f"{prefix}.{parts[1]}")
                if hit:
                    return hit
            return "unknown-receiver", head  # a method the class does not declare here: inherited or a defect; v0 abstains (C-91)
        if len(parts) == 1:
            if head in PY_BUILTINS:
                return "builtin", None
            if self.in_scope_local(P, head, r.line):
                return "local", None
            hit = local_symbol(head)
            if hit:
                return hit
            imp = next((i for i in P.imports if i["bound"] == head), None)
            if imp is not None:
                if imp["kind"] == "name":
                    tm = self.py_module(mod, imp["module"], imp.get("level", 0))
                    if tm is None:
                        return "external", imp["module"]
                    sid = T.look("symbol", f"{tm}.{imp['name']}", self.mod_syms.get(tm, {}).get(imp["name"]))
                    if sid:
                        return "in-graph", sid
                    if f"{tm}.{imp['name']}" in L.mod_path:
                        return "in-graph", f"{tm}.{imp['name']}"
                    if any(imp["name"] in self.gensym_quals[p] for p in self.gensym_quals if L.path_mod.get(p) == tm):
                        return "gensym", imp["name"]
                    re_ = self.py_reexport(tm, imp["name"])
                    if re_:
                        return "in-graph", re_
                    return "NULL", None
                return "unknown-receiver", head
            return "NULL", None
        if self.in_scope_local(P, head, r.line):
            return "local", head
        imp = next((i for i in P.imports if i["bound"] == head), None)
        if imp is not None and imp["kind"] == "module":
            full = imp.get("full", imp["module"])
            chain = full.split(".") + parts[1:]
            for i in range(len(chain) - 1, 0, -1):
                tm = ".".join(chain[:i])
                if tm in L.mod_path:
                    qual = ".".join(chain[i:])
                    sid = T.look("symbol", f"{tm}.{qual}", self.mod_syms.get(tm, {}).get(qual))
                    if sid:
                        return "in-graph", sid
                    if any(qual in self.gensym_quals[p] for p in self.gensym_quals if L.path_mod.get(p) == tm):
                        return "gensym", qual
                    return self._py_member(tm, chain[i:])
            return "external", full
        if imp is not None and imp["kind"] == "name":
            tm = self.py_module(mod, imp["module"], imp.get("level", 0))
            if tm is None:
                return "external", imp["module"]
            sub = f"{tm}.{imp['name']}"
            if sub in L.mod_path:  # from pkg import submodule; submodule.func()
                qual = ".".join(parts[1:])
                sid = T.look("symbol", f"{sub}.{qual}", self.mod_syms.get(sub, {}).get(qual))
                if sid:
                    return "in-graph", sid
                if any(qual in self.gensym_quals[p] for p in self.gensym_quals if L.path_mod.get(p) == sub):
                    return "gensym", qual
                return self._py_member(sub, parts[1:])
            if self.mod_syms.get(tm, {}).get(imp["name"]) and len(parts) == 2:  # Class.method on an imported class
                sid = T.look("symbol", f"{tm}.{imp['name']}.{parts[1]}", self.mod_syms.get(tm, {}).get(f"{imp['name']}.{parts[1]}"))
                if sid:
                    return "in-graph", sid
                return "unknown-receiver", head  # a member the class does not declare: inherited, an attribute, or wrong — v0 abstains (C-91)
            return "unknown-receiver", head
        if head in quals or head in gens:  # Class.method on a class of this file
            if len(parts) == 2:
                hit = local_symbol(f"{head}.{parts[1]}")
                if hit:
                    return hit
            return "unknown-receiver", head
        return "unknown-receiver", head

    def _py_member(self, mod: str, rest: list[str]) -> tuple[str, str | None]:
        """``module.rest...()`` where the graph has no symbol for it: a re-exported symbol (in-graph), a member on a module-level value (abstain), else NULL."""
        if len(rest) == 1:
            re_ = self.py_reexport(mod, rest[0])
            if re_:
                return "in-graph", re_
        if self.py_module_value(mod, rest[0]):
            return "unknown-receiver", f"{mod}.{rest[0]}"
        if len(rest) > 1 and self.py_reexport(mod, rest[0]):
            return "unknown-receiver", f"{mod}.{rest[0]}"  # a member of a re-exported class: not a call site lane A resolves (C-91)
        return "NULL", None

    def _ts(self, path: str, P: Parsed, r: Ref) -> tuple[str, str | None]:
        L, T = self.L, self.trace
        mod = L.path_mod.get(path)
        names = {s["name"]: s for s in P.symbols}
        if r.receiver is None:
            if r.name in JS_BUILTINS:
                return "builtin", None
            if self.in_scope_local(P, r.name, r.line) and r.name not in names:
                return "local", None
            imp = next((i for i in P.imports if i["bound"] == r.name), None)
            if imp is not None:
                if imp["kind"] == "external":
                    return "external", imp["module"]
                tm = self.ts_module(path, imp["module"])
                if tm is None:
                    return "external", imp["module"]
                sid = T.look("symbol", f"{tm}.{r.name}", self.mod_syms.get(tm, {}).get(r.name))
                if sid:
                    return "in-graph", sid
                if any(r.name in self.gensyms[p] for p in self.gensyms if L.path_mod.get(p) == tm):
                    return "gensym", r.name
                return "NULL", None
            sid = T.look("symbol", f"{mod}.{r.name}", self.mod_syms.get(mod, {}).get(r.name) if mod else None)
            if sid:
                return "in-graph", sid
            if r.name in self.gensyms.get(path, set()):
                return "gensym", r.name
            return "NULL", None
        head = r.receiver.split(".")[0]
        imp = next((i for i in P.imports if i["bound"] == head), None)
        if imp is not None:
            if imp["kind"] == "external" or self.ts_module(path, imp["module"]) is None:
                return "external", imp["module"]
            return "unknown-receiver", head  # a member of a repo module's export: not a call site lane A resolves (C-91)
        if self.in_scope_local(P, head, r.line):
            return "local", head
        return "unknown-receiver", head

    def ts_module(self, path: str, specifier: str) -> str | None:
        if not specifier.startswith("."):
            return self.trace.look("import", specifier, None)
        target = str(PurePosixPath(os.path.normpath(str(PurePosixPath(path).parent / specifier))))
        stem = re.sub(r"\.(m?[jt]sx?)$", "", target)
        for cand in (stem, stem + "/index"):
            if cand in self.L.mod_path:
                return self.trace.look("import", specifier, cand)
        return self.trace.look("import", specifier, None)


def _edit_distance(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > _NEAR:
        return _NEAR + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ------------------------------------------------------------------ ground

def ground(template: dict, doc: dict, L: Ledger, repo_root: Path) -> dict:
    """The grounder: fills → diff + NULL list + read-trace + the invariant counts. Deterministic in its inputs (I5)."""
    trace = Trace()
    sha = template["key"]["parent_sha"]
    edits, rep = edits_from_fills(template, doc, L, repo_root, trace)
    post, pre, overlaps, ranges = apply_edits(edits, repo_root, sha, trace)
    rep["refused"] += overlaps
    partition = set(template.get("constraints", {}).get("write_partition", []))
    diff = "".join(unified(p, pre[p], post[p]) for p in sorted(post))
    refs: list[dict] = []
    nulls: list[dict] = []
    by_class = collections.Counter()
    parsed: dict[str, Parsed] = {}
    with tempfile.TemporaryDirectory(prefix="hobbes-ground-") as tmp:
        scratch = Path(tmp)
        for path in sorted(post):
            text = "\n".join(post[path]) + ("\n" if post[path] else "")
            lang = language_of(path)
            if lang is None:
                continue
            P = parse_post(path, text, scratch, repo_root, sha)
            if P is None:
                continue
            parsed[path] = P
            trace.look("parse", path, f"{P.lang}: {len(P.symbols)} symbols, {len(P.refs)} call sites")
    R = _Resolver(L, repo_root, sha, trace, parsed, set(rep["declared_new"]), {p: "\n".join(post[p]) + ("\n" if post[p] else "") for p in post})
    hole_at: dict[str, list[tuple[int, int, str]]] = collections.defaultdict(list)  # which hole owns each post-image range, in apply_edits' order
    for path in post:
        es = sorted([e for e in edits if e.path == path and not any(x.get("hole") == e.hole for x in overlaps)], key=lambda e: (e.start, e.end, e.hole))
        for e, (a, b) in zip(es, ranges[path]):
            hole_at[path].append((a, b, e.hole))
    for path in sorted(post):
        lang = language_of(path)
        if lang is None:
            by_class["not-code"] += 1
            refs.append({"hole": ",".join(h for _, _, h in hole_at[path]), "path": path, "line": 0, "term": "", "class": "not-code", "target": None})
            continue
        P = parsed.get(path)
        if P is None:
            by_class["unsupported"] += 1
            refs.append({"hole": ",".join(h for _, _, h in hole_at[path]), "path": path, "line": 0, "term": "", "class": "unsupported", "target": lang})
            continue
        for r in P.refs:
            owner = next((h for a, b, h in hole_at[path] if a <= r.line <= b), None)
            if owner is None:
                continue
            cls, target = R.resolve(path, P, r)
            row = {"hole": owner, "path": path, "line": r.line, "term": r.name if r.receiver is None else f"{r.receiver}.{r.name}", "class": cls, "target": target}
            by_class[cls] += 1
            if cls == "NULL":
                _, near, ncls = R.null(r.name, path)
                row.update({"null_class": ncls, "nearest": near, "declared": r.name in R.declared})
                nulls.append(row)
            refs.append(row)
    judged = by_class["in-graph"] + by_class["NULL"]
    out = {
        "grounder_version": GROUNDER_VERSION,
        "key": {**template["key"], "grounder_version": GROUNDER_VERSION},
        "diff": diff,
        "post": {p: "\n".join(post[p]) + ("\n" if post[p] else "") for p in sorted(post)},
        "files": [{"path": p, "created": pre[p] is None, "lines_before": len(pre[p] or []), "lines_after": len(post[p]), "in_partition": p in partition} for p in sorted(post)],
        "edits": [{"hole": e.hole, "type": e.type, "path": e.path, "span": {"start": e.start, "end": e.end}, "placement": e.placement, "lines_out": max(e.end - e.start + 1, 0), "lines_in": len(e.lines), "in_partition": e.path in partition}
                  for e in sorted(edits, key=lambda e: (e.path, e.start, e.end, e.hole))],
        "outside_partition": sum(1 for e in edits if e.path not in partition),
        "references": {"total": sum(by_class.values()), **{c: by_class[c] for c in CLASSES}},
        "refs": refs,
        "null": nulls,
        "null_by_class": {c: sum(1 for n in nulls if n["null_class"] == c) for c in NULL_CLASSES},
        "gensyms": sorted(R.all_gensyms | R.declared),
        "hsr": round(by_class["NULL"] / judged, 4) if judged else None,
        **{k: rep[k] for k in ("unfilled", "ignored_closed", "unknown_hole", "refused", "notes", "closed_by_prune", "declared_new")},
        "trace": trace.rows,
    }
    out["output_hash"] = hashlib.sha256(json.dumps({k: v for k, v in out.items() if k != "trace"}, sort_keys=True).encode()).hexdigest()[:16]
    return out


# ------------------------------------------------------- a diff as fills

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def blocks_of(diff: str) -> tuple[list[tuple[int, int, list[str]]], bool]:
    """A file's diff as change blocks ``(old_start, old_end, new_lines)`` — ``old_end == old_start - 1`` is an insertion before ``old_start`` — and whether the file is new."""
    new_file = "new file mode" in diff
    blocks: list[tuple[int, int, list[str]]] = []
    lines = diff.split("\n")
    i = 0
    while i < len(lines):
        m = _HUNK.match(lines[i])
        if not m:
            i += 1
            continue
        o = int(m.group(1)) if m.group(2) != "0" else int(m.group(1)) + 1
        i += 1
        dels: list[int] = []
        adds: list[str] = []
        at = None

        def flush():
            nonlocal dels, adds, at
            if dels or adds:
                if dels:
                    blocks.append((dels[0], dels[-1], adds))
                else:
                    blocks.append((at, at - 1, adds))
            dels, adds, at = [], [], None

        while i < len(lines) and not _HUNK.match(lines[i]) and not lines[i].startswith("diff --git"):
            l = lines[i]
            if l.startswith("-"):
                if adds:
                    flush()
                dels.append(o)
                o += 1
            elif l.startswith("+"):
                if at is None and not dels:
                    at = o
                adds.append(l[1:])
            elif l.startswith(" ") or l == "":
                if l == "" and i == len(lines) - 1:
                    break
                flush()
                o += 1
            elif l.startswith("\\"):
                pass
            i += 1
        flush()
    return blocks, new_file


def fills_from_diff(template: dict, gold: list[tuple[str, str]], repo_root: Path) -> tuple[dict, dict]:
    """A diff expressed as fills against the template (charter §4.1: a draft diff with no hole for it is FREEFORM); returns the fills document and the attribution counts."""
    counts = collections.Counter()
    fills: dict = {}
    freeform: list[dict] = []
    span_holes = [h for h in template["holes"] if h.get("span") and h["type"] in _CHANGE_PRIORITY]
    sig_holes = [h for h in template["holes"] if h["type"] == "SIGNATURE"]
    per_path: dict[str, list[tuple[int, int, list[str]]]] = {}
    for path, diff in gold:
        blocks, new = blocks_of(diff)
        if new:
            freeform.append({"code": "\n".join(l for _, _, ls in blocks for l in ls) + "\n", "span": {"path": path, "start": 1, "end": 0}})
            counts["new_file"] += 1
            continue
        per_path[path] = blocks

    def holds(h, a, b):
        s = h["span"]
        if b >= a:
            return s["start"] <= a and b <= s["end"]
        return s["start"] <= a <= s["end"] + 1 and (a != s["end"] + 1 or not any(o is not h and o["span"]["path"] == s["path"] and o["span"]["start"] == a for o in span_holes))

    # signatures first: a symbol whose first line is in a block has a new signature; then prune, then attribute to open holes
    for h in sig_holes:
        s = h["span"]
        hit = next((bl for bl in per_path.get(s["path"], []) if bl[1] >= bl[0] and bl[0] <= s["start"] <= bl[1]), None)
        fills[h["id"]] = {"signature": hit[2][0] if hit and hit[2] else ""} if hit and hit[2] else "unchanged"
    closed = prune(template, fills)
    counts["closed_by_prune"] = len(closed)
    open_holes = [h for h in span_holes if h.get("closed") is None]
    owned: dict[str, list[tuple[int, int, list[str]]]] = collections.defaultdict(list)
    for path, blocks in per_path.items():
        for a, b, new_lines in blocks:
            owner = None
            for typ in _CHANGE_PRIORITY:
                owner = next((h for h in open_holes if h["type"] == typ and h["span"]["path"] == path and holds(h, a, b)), None)
                if owner:
                    break
            if owner is None:
                shut = next((h for h in span_holes if h.get("closed") is not None and h["span"]["path"] == path and holds(h, a, b)), None)
                if shut is not None:
                    counts["in_closed"] += 1
                    counts.setdefault("in_closed_at", [])
                    counts["in_closed_at"].append(f"{shut['id']} ({shut['closed']['reason']}) {path}:{a}-{b}")
                freeform.append({"code": "\n".join(new_lines) + ("\n" if new_lines else ""), "span": {"path": path, "start": a, "end": b}})
                counts["freeform"] += 1
            else:
                owned[owner["id"]].append((a, b, new_lines))
                counts["in_hole"] += 1
    sha = template["key"]["parent_sha"]
    for h in open_holes:
        hid, typ, s = h["id"], h["type"], h["span"]
        if hid not in owned:
            fills[hid] = "unchanged" if typ in ("BODY", "MODULE_REGION", "TEST_EXPECTATION") else {"decision": "no", "reason": "the diff does not touch it"}
            continue
        old = file_at(repo_root, sha, s["path"]) or []
        seg = old[s["start"] - 1: s["end"]]
        for a, b, new_lines in sorted(owned[hid], key=lambda x: (x[0], x[1]), reverse=True):
            i = a - s["start"]
            seg[i: i + max(b - a + 1, 0)] = new_lines
        code = "\n".join(seg) + "\n"
        fills[hid] = {"code": code} if typ in ("BODY", "MODULE_REGION") else {"decision": "yes", "reason": "the diff touches it", "body": code} if typ == "CALLER_UPDATE" else {"expectation": "the diff's", "code": code}
        counts[f"filled_{typ}"] += 1
    for h in template["holes"]:
        if h["type"] == "COCHANGE_TOUCH" and h.get("closed") is None:
            fills[h["id"]] = {"decision": "no", "reason": "the diff does not touch it"}
        elif h["type"] == "FREEFORM":
            fills[h["id"]] = freeform if freeform else "none"
    return {"fills": fills, "patterns": {}}, dict(counts)


