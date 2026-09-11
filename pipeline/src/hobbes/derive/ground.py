"""Grounder v0 — Calvin's slot with the residual set to zero (`docs/calvin/calvin-potential.md` §2.3; step 3 of §8).

Deterministic and model-free. In: a template (`hobbes.derive.holes`
v0), the orchestrator's fills, the ledger at the parent SHA and the
repo read only through ``git`` at that SHA. Out: a diff that applies at
the SHA, a **NULL list**, a **read-trace**, and the counts the charter's
invariants are measured by (`docs/calvin/calvin-charter.md` §4).

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

**Go (`docs/calvin/calvin-m0-go.md` §2.4).** The builtin list is Go's
universe scope, pinned (``GO_PREDECLARED``), and a bare name binds a
local, then the package, then the universe — never a method. **Rule 1:**
a method call on a receiver whose type the syntax states — a receiver
or parameter, ``var x T``, ``x := T{…}`` / ``&T{…}`` / ``new(T)``, a
package-level ``var`` of those shapes — resolves on that type: the
graph's method (``in-graph``), one the post-image declares (``gensym``),
one promoted through an embedded repo type, else NULL; a struct field
is ``field``, a type outside the repo (or a member promoted from one)
``external``, a predeclared type ``builtin``; a type parameter, a
function-local type, a binding the syntax does not type and a type the
graph does not hold abstain. **Rule 2:** a method an interface type of
the graph declares resolves to the interface method (``interface``,
judged beside ``in-graph``); the implementers an RTA key names for it
are recorded on the row, never bound. A NULL row names its **scope**
(M0-Go WP-7a): where a declaration of the name would have to sit for
the call to bind — the package directory of a bare or package-qualified
Go name, the directory and type of a member on a typed receiver; None
where the grounder cannot say (every other language, an untyped
receiver). Adapter protocol v0.4's declaration hole reads it.

**The world (`docs/calvin/calvin-m0-go.md` §2.5, M0-Go WP-9, WP-8's D-g).**
A declaration extends the world; it does not escape it. On a Go
post-image, every import spec inside an edited range is judged
(``go_import_world``): a package of the standard library (``GO_STDLIB``,
pinned from go1.26.5), a package of the file's own module (its go.mod
at the SHA; the directory must hold Go files at the SHA or in the
diff), or a package under a module the parent's go.mod requires — else
a NULL of class ``import-outside``, one per spec, at its line. And a
qualifier the file does not import is judged, not left to abstain: a
call ``q.f()`` or a selector ``q.x`` / qualified type ``q.T`` in an
edited range whose ``q`` no import of the file may bind, no identifier
of the file writes, and no Go file of its package declares at top level
is a NULL of class ``unimported`` (`_Resolver.go_unimported`; every
doubt abstains). A non-call selector becomes a reference row only when
it is a NULL; every judgment is tallied under ``world``.

**Density (Track B).** Every reference the parent graph judges carries
``dense | sparse | absent`` beside its class (``density_table``,
``DENSITY_RULE``): a real symbol by its in-degree against the parent's
k, a gensym or a NULL ``absent``. Density is never a reason to NULL.

**HSR (§4.6)** is NULL over (in-graph + interface + NULL), the cell's definition
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
from hobbes.extract.tail import PY_BUILTINS, language_of

GROUNDER_VERSION = 3  #: 1: Go's rules 1 and 2, the universe list, the density field (M0-Go §2.4); 2: the world check on Go fills (M0-Go WP-9);
#: 3: signatures in the world — a call's arity and a qualified reference's declared existence, each its own NULL class (M0-Go round 2 WP-14b, §2.5);
#: also v3: a post-image carrying the render's gutter is its own class, `malformed`, rather than a silent zero (round 2 D-m)
EXPR = "<expr>"
#: The reference classes; ``NULL`` is the only failure (I2). Everything else is what lane A resolves or abstains on by rule.
#: ``malformed`` (round 2 D-m) is a file whose post-image carries the render's line-number gutter — a garbled body a live
#: protocol run's validator guard refuses before it ever reaches here (WP-7a's `carries_gutter`), seen only in a replay of
#: a pre-guard record; parsing it finds essentially nothing, and this class says why rather than reading as an empty file.
CLASSES = ("in-graph", "interface", "gensym", "builtin", "local", "field", "expr", "external", "unknown-receiver", "not-code", "unsupported", "malformed", "NULL")
#: The classes a density is read for: a reference the parent graph judges.
DENSITY_CLASSES = ("in-graph", "interface", "gensym", "NULL")
#: Track B's rule, stated on every record (M0-Go §2.4, "k so the top third of real symbols are dense").
DENSITY_RULE = ("in-degree = distinct symbols with a calls or uses edge into the symbol, any tier, self-edges dropped; "
                "population = every symbol of the parent graph; k = the smallest k >= 1 with at most ceil(N/3) symbols at in-degree >= k, "
                "so ties at k are never split and the dense share is at most a third; dense iff in-degree >= k, else sparse; "
                "absent = not a symbol of the parent graph (a gensym, a NULL); an interface method reads its interface type's in-degree")
#: Go's universe scope, pinned from go1.26.5's ``go/types.Universe`` (the image's toolchain): the builtin functions, the
#: predeclared types (a conversion is spelled like a call, and ``err.Error()`` is a method of one), the constants and ``nil``.
#: The tail view's ``GO_BUILTINS`` is its callable subset less ``any`` and ``comparable``.
GO_PREDECLARED = frozenset({
    "append", "cap", "clear", "close", "complex", "copy", "delete", "imag", "len", "make", "max", "min", "new", "panic",
    "print", "println", "real", "recover",
    "any", "bool", "byte", "comparable", "complex128", "complex64", "error", "float32", "float64", "int", "int16", "int32",
    "int64", "int8", "rune", "string", "uint", "uint16", "uint32", "uint64", "uint8", "uintptr",
    "false", "iota", "nil", "true",
})
#: The Go standard library a fill may import, pinned from go1.26.5 (the image's toolchain, as ``GO_PREDECLARED`` is): ``go list std``
#: less every path with an ``internal`` element and every ``vendor/…`` path — neither is importable from a module — 176 packages.
GO_STDLIB = frozenset("""
archive/tar archive/zip bufio bytes cmp compress/bzip2 compress/flate compress/gzip compress/lzw compress/zlib container/heap
container/list container/ring context crypto crypto/aes crypto/cipher crypto/des crypto/dsa crypto/ecdh crypto/ecdsa crypto/ed25519
crypto/elliptic crypto/fips140 crypto/hkdf crypto/hmac crypto/hpke crypto/md5 crypto/mlkem crypto/mlkem/mlkemtest crypto/pbkdf2
crypto/rand crypto/rc4 crypto/rsa crypto/sha1 crypto/sha256 crypto/sha3 crypto/sha512 crypto/subtle crypto/tls crypto/x509
crypto/x509/pkix database/sql database/sql/driver debug/buildinfo debug/dwarf debug/elf debug/gosym debug/macho debug/pe
debug/plan9obj embed encoding encoding/ascii85 encoding/asn1 encoding/base32 encoding/base64 encoding/binary encoding/csv
encoding/gob encoding/hex encoding/json encoding/pem encoding/xml errors expvar flag fmt go/ast go/build go/build/constraint
go/constant go/doc go/doc/comment go/format go/importer go/parser go/printer go/scanner go/token go/types go/version hash
hash/adler32 hash/crc32 hash/crc64 hash/fnv hash/maphash html html/template image image/color image/color/palette image/draw
image/gif image/jpeg image/png index/suffixarray io io/fs io/ioutil iter log log/slog log/syslog maps math math/big math/bits
math/cmplx math/rand math/rand/v2 mime mime/multipart mime/quotedprintable net net/http net/http/cgi net/http/cookiejar
net/http/fcgi net/http/httptest net/http/httptrace net/http/httputil net/http/pprof net/mail net/netip net/rpc net/rpc/jsonrpc
net/smtp net/textproto net/url os os/exec os/signal os/user path path/filepath plugin reflect regexp regexp/syntax runtime
runtime/cgo runtime/coverage runtime/debug runtime/metrics runtime/pprof runtime/race runtime/trace slices sort strconv strings
structs sync sync/atomic syscall testing testing/cryptotest testing/fstest testing/iotest testing/quick testing/slogtest
testing/synctest text/scanner text/tabwriter text/template text/template/parse time time/tzdata unicode unicode/utf16
unicode/utf8 unique unsafe weak
""".split())
#: cgo's pseudo-package: no package ``go list std`` names, importable by a cgo file.
GO_PSEUDO_IMPORTS = frozenset({"C"})
#: The NULL classes the world check raises (M0-Go WP-9): an import path outside the world, a qualifier nothing binds.
WORLD_NULL_CLASSES = ("import-outside", "unimported")
#: Signatures in the world (M0-Go round 2 WP-14b, §2.5): a call's own argument count against its callee's declared parameter
#: count, and a qualified reference against its package's declared top-level names — each judged only where the grounder
#: fully owns the package (this module's own, never std or a dependency) and never on a doubt (variadics, generics, …).
SIGNATURE_NULL_CLASSES = ("arity", "undeclared-type")
NULL_CLASSES = ("new", "near-miss", "invented") + WORLD_NULL_CLASSES + SIGNATURE_NULL_CLASSES
#: The world check's rule, stated on every record (M0-Go WP-9, D-g; §2.5).
WORLD_RULE = ("Go only, inside edited ranges. An import path is std (GO_STDLIB, go1.26.5's `go list std` less internal and vendor paths; "
              "cgo's C), module (under the module path of the go.mod governing the file at the SHA, naming a directory with Go files at the "
              "SHA or in the diff), or required (under a module path a require line of that go.mod names, // indirect included; the "
              "package is not checked to exist inside the module) — else a NULL `import-outside`, one per spec; unverifiable when no go.mod "
              "governs the file. A qualifier q of a call q.f(), a selector q.x or a qualified type q.T is a NULL `unimported` when no import "
              "of the file may bind q (an explicit alias exactly; an unaliased path by the names its path conventionally spells, "
              "`_go_import_names`, plus the package clause of a module package), the file has no dot import, q is not predeclared, no "
              "identifier of the file other than a selector's operand is q, and no Go file of the package declares q at top level (the "
              "syntax, build tags not read); else it abstains. A non-call selector is a reference row only when it is a NULL.")
#: Signatures in the world's rule, stated on every record (M0-Go round 2 WP-14b, §2.5).
SIGNATURE_RULE = ("Go only. A qualifier q bound (not `unimported`) to exactly one import of *this module's own* package — never std, a "
                   "required (external) module, or an ambiguous or unresolved bind, each a doubt the rule abstains on — makes q.name a NULL "
                   "`undeclared-type` when that package (its files at the SHA, plus the diff) declares no `name` at top level; a package the "
                   "diff does not touch is read whole, so a promoted or generic member is not this rule's concern. A call bound `in-graph` to "
                   "a repo Go function or method is a NULL `arity` when its own syntactic argument count differs from the callee's own "
                   "declaration, read exactly (grouped parameter names each count once); either side abstains on a variadic parameter, the "
                   "callee's own type parameters, a call whose sole argument is itself a call expression (Go's multi-value spread, "
                   "`f(g())`, which the grammar alone cannot rule out), or the callee's own file being one this diff edits (its signature "
                   "may be exactly what is changing — read only against a declaration this diff leaves alone).")
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
                if fill.get("body"):
                    edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["body"]), "span"))
                else:
                    rep["notes"].append(f"{hid}: a 'yes' without a body places nothing — routed back with the span")
        elif typ == "TEST_EXPECTATION":
            if fill != "unchanged":
                if fill.get("code"):
                    edits.append(Edit(hid, typ, span["path"], span["start"], span["end"], _lines(fill["code"]), "span"))
                else:
                    rep["notes"].append(f"{hid}: an expectation without code places nothing — routed back as a question")
        elif typ == "COCHANGE_TOUCH":
            if fill["decision"] == "yes" and not fill.get("body"):
                rep["notes"].append(f"{hid}: a 'yes' without a body places nothing — routed back with the file")
            elif fill["decision"] == "yes":
                path = h["provenance"]["partner"]
                old = file_at(repo_root, sha, path, trace)
                edits.append(Edit(hid, typ, path, 1, len(old) if old else 0, _lines(fill["body"]), "whole-file", created=old is None))
        elif typ == "NEW_SYMBOL":
            if "covered_by" in fill:
                for c in fill["covered_by"]:
                    if c not in fills or fills[c] in ("unchanged", "none") or (isinstance(fills[c], dict) and fills[c].get("decision") == "no"):
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
    argc: int | None = None  #: Go: the call's own argument count, or None on a doubt (round 2 WP-14b, §2.5)
    variadic_call: bool = False  #: Go: the call spreads its last argument with ``...``


@dataclass
class Parsed:
    """What one post-image file yields for grounding, in one shape across languages."""
    lang: str
    symbols: list[dict]  #: {name, qualname, kind, line, end_line}
    refs: list[Ref]
    imports: list[dict]  #: {"bound": name, "module": dotted-or-path, "kind": "module"|"name"|"external", "name"?: imported name}
    locals: list[tuple[str, int, int]]
    go_binds: list[tuple] = field(default_factory=list)  #: Go: (name, typeref | None, declared at, start, end) — rule 1's reading
    go_tparams: list[tuple[str, int, int]] = field(default_factory=list)  #: Go: type parameters in scope over a function's extent
    go_ltypes: list[tuple[str, int, int]] = field(default_factory=list)  #: Go: types declared inside a function
    go_root: object = None  #: Go: the post-image's tree-sitter root — the world check's reading (imports, selectors, identifiers)


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
        if parts == [EXPR]:
            continue  # a callee that is itself an expression names nothing to bind (C-63's Python shape)
        refs.append(Ref(parts[-1], None if len(parts) == 1 else (EXPR if parts[0] == EXPR else ".".join(parts[:-1])), c.line, c.scope, parts))
    return Parsed("python", [{"name": s.name, "qualname": s.qualname, "kind": s.kind, "line": s.line, "end_line": s.end_line} for s in p.symbols],
                  refs, imports, [(b.name, b.start, b.end) for b in p.local_bindings])


def _parse_go(path: str, text: str) -> Parsed:
    from hobbes.extract import gosource
    source = text.encode("utf-8", "surrogateescape")
    g = gosource._parse_file(path, source)
    imports = [{"bound": i["alias"], "module": i["path"], "kind": "module"} for i in g.imports]
    refs = [Ref(c["name"], c["receiver"], c["line"], c.get("scope"), argc=c.get("argc"), variadic_call=bool(c.get("variadic_call"))) for c in g.calls]
    root = gosource._PARSER.parse(source).root_node
    binds, tparams, ltypes = _go_scopes(root)
    return Parsed("go", g.symbols, refs, imports, [tuple(b[:3]) for b in g.local_bindings], binds, tparams, ltypes, root)


def _gtext(node) -> str:
    return (node.text or b"").decode("utf-8", "surrogateescape")


def _go_typeref(node) -> tuple[str | None, str] | None:
    """A Go type expression as ``(package alias or None, type name)`` when it names one named type — through ``*``,
    parentheses and type arguments — else None (a slice, map, func, channel or literal struct type names none)."""
    while node is not None and node.type in ("pointer_type", "parenthesized_type"):
        node = node.named_children[0] if node.named_children else None
    if node is not None and node.type == "generic_type":
        node = node.child_by_field_name("type")
    if node is None:
        return None
    if node.type == "type_identifier":
        return (None, _gtext(node))
    if node.type == "qualified_type":
        pkg, name = node.child_by_field_name("package"), node.child_by_field_name("name")
        if pkg is not None and name is not None:
            return (_gtext(pkg), _gtext(name))
    return None


def _go_value_typeref(node) -> tuple[str | None, str] | None:
    """The type a Go value expression states by its syntax — ``T{…}``, ``&T{…}``, ``new(T)`` — else None: a call's result
    type is not read (that is the checker's, not the grammar's), nor ``new(v)`` on a value (go1.26's ``new(expr)``)."""
    if node is None:
        return None
    if node.type == "unary_expression":
        op = node.child_by_field_name("operator")
        if op is None or _gtext(op) != "&":
            return None
        node = node.child_by_field_name("operand")
        if node is None:
            return None
    if node.type == "composite_literal":
        return _go_typeref(node.child_by_field_name("type"))
    if node.type == "call_expression":
        fn, args = node.child_by_field_name("function"), node.child_by_field_name("arguments")
        if fn is not None and fn.type == "identifier" and _gtext(fn) == "new" and args is not None and args.named_child_count == 1 \
                and args.named_children[0].type != "identifier":
            return _go_typeref(args.named_children[0])
    return None


def _go_list(node) -> list:
    if node is None:
        return []
    return list(node.named_children) if node.type == "expression_list" else [node]


def _go_scopes(root) -> tuple[list, list, list]:
    """Rule 1's reading of one Go file. Every binding below package level as ``(name, typeref | None, declared at, start,
    end)`` — the forms `gosource._local_bindings` records (parameters with the receiver and named results, ``:=``, ``var``,
    ``range``), with the type when the syntax states one and the line that declares it; the type parameters in scope (a
    function's own and a generic receiver's) and the function-local type names, each ``(name, start, end)`` over the
    innermost function's extent."""
    binds: list[tuple] = []
    tparams: list[tuple] = []
    ltypes: list[tuple] = []

    def params(plist, own):
        for decl in plist.named_children:
            if decl.type in ("parameter_declaration", "variadic_parameter_declaration"):
                t = _go_typeref(decl.child_by_field_name("type")) if decl.type == "parameter_declaration" else None
                for nm in decl.children_by_field_name("name"):
                    binds.append((_gtext(nm), t, own[0], *own))

    def walk(node, extent):
        kind = node.type
        if kind in ("function_declaration", "method_declaration", "func_literal"):
            own = (node.start_point.row + 1, node.end_point.row + 1)
            recv = node.child_by_field_name("receiver")
            if recv is not None:
                params(recv, own)
                stack = [recv]
                while stack:
                    n = stack.pop()
                    if n.type == "type_arguments":
                        tparams.extend((_gtext(t), *own) for t in _walk_nodes(n) if t.type == "type_identifier")
                    else:
                        stack.extend(n.children)
            tpl = node.child_by_field_name("type_parameters")
            if tpl is not None:
                for decl in tpl.named_children:
                    tparams.extend((_gtext(nm), *own) for nm in decl.children_by_field_name("name"))
            for f in ("parameters", "result"):
                pl = node.child_by_field_name(f)
                if pl is not None and pl.type == "parameter_list":
                    params(pl, own)
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    walk(child, own)
            return
        if extent is not None:
            line = node.start_point.row + 1
            if kind == "short_var_declaration":
                ls, rs = _go_list(node.child_by_field_name("left")), _go_list(node.child_by_field_name("right"))
                for i, ident in enumerate(ls):
                    if ident.type == "identifier":
                        binds.append((_gtext(ident), _go_value_typeref(rs[i]) if len(rs) == len(ls) else None, line, *extent))
            elif kind == "var_spec":
                names = node.children_by_field_name("name")
                typ = node.child_by_field_name("type")
                vs = _go_list(node.child_by_field_name("value"))
                for i, nm in enumerate(names):
                    t = _go_typeref(typ) if typ is not None else (_go_value_typeref(vs[i]) if len(vs) == len(names) else None)
                    binds.append((_gtext(nm), t, line, *extent))
            elif kind == "range_clause":
                binds.extend((_gtext(i), None, line, *extent) for i in _go_list(node.child_by_field_name("left")) if i.type == "identifier")
            elif kind in ("type_spec", "type_alias"):
                nm = node.child_by_field_name("name")
                if nm is not None:
                    ltypes.append((_gtext(nm), *extent))
        for child in node.children:
            walk(child, extent)

    walk(root, None)
    return binds, tparams, ltypes


def _walk_nodes(node):
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _iter_nodes(node):
    """Every node under *node*, preorder, without recursion (a whole post-image may be deep)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


_GO_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _go_import_specs(root) -> list[dict]:
    """Every import spec of a Go file: ``{"alias": the name written before the path (``_`` and ``.`` as written) or None, "path", "line"}``."""
    out = []
    for decl in root.children:
        if decl.type != "import_declaration":
            continue
        for n in _iter_nodes(decl):
            if n.type != "import_spec":
                continue
            nm, p = n.child_by_field_name("name"), n.child_by_field_name("path")
            if p is None:
                continue
            out.append({"alias": _gtext(nm) if nm is not None else None, "path": _gtext(p).strip('"`'), "line": n.start_point.row + 1})
    return out


def _go_plain_identifiers(root) -> set[str]:
    """Every identifier a Go file writes other than as a selector's operand — a binding or a use: a name so written is declared somewhere
    the syntax does not have to say, so the world check never calls it unimported."""
    out = set()
    for n in _iter_nodes(root):
        if n.type != "identifier":
            continue
        p = n.parent
        if p is not None and p.type == "selector_expression":
            op = p.child_by_field_name("operand")
            if op is not None and op.start_byte == n.start_byte and op.end_byte == n.end_byte:
                continue
        out.add(_gtext(n))
    return out


def _go_toplevel_names(root) -> set[str]:
    """The package-level names one Go file declares: functions (not methods), types, vars and consts, grouped or not."""
    out = set()
    for node in root.children:
        if node.type == "function_declaration":
            nm = node.child_by_field_name("name")
            if nm is not None:
                out.add(_gtext(nm))
        elif node.type in ("type_declaration", "var_declaration", "const_declaration"):
            for n in _iter_nodes(node):
                if n.type in ("type_spec", "type_alias", "var_spec", "const_spec"):
                    out.update(_gtext(x) for x in n.children_by_field_name("name"))
    return out


def _go_import_names(ipath: str) -> set[str]:
    """The package names an unaliased import of *ipath* may bind when its package clause is not read: the last element (the one before
    a ``/vN`` major-version suffix), less a gopkg.in ``.vN``, with a ``go-`` / ``-go`` / ``go`` / ``.go`` affix dropped, and ``-`` / ``.``
    dropped or spelled ``_`` — the spellings a path conventionally carries its package's name in. Deliberately wide: a name kept abstains."""
    parts = ipath.split("/")
    last = parts[-1]
    base = parts[-2] if len(parts) > 1 and re.fullmatch(r"v\d+", last) else last
    base = re.sub(r"\.v\d+$", "", base)
    out = {last, base}
    for b in list(out):
        for x in (b, b.removeprefix("go-"), b.removesuffix("-go"), b.removeprefix("go"), b.removesuffix(".go")):
            out |= {x, x.replace("-", "").replace(".", ""), x.replace("-", "_").replace(".", "_")}
    return {x for x in out if x}


def _go_find_decl_at(root, line: int, kind: str):
    """The top-level ``function_declaration`` (*kind* ``"function"``) or ``method_declaration`` (*kind* ``"method"``) whose
    own start is *line* — the same line `gosource._symbols` records — else None (WP-14b, §2.5's arity read)."""
    want = "function_declaration" if kind == "function" else "method_declaration"
    for node in root.children:
        if node.type == want and node.start_point.row + 1 == line:
            return node
    return None


def _go_own_param_list(decl):
    """A function or method declaration's **own** parameter list — the ``parameter_list`` child immediately after its name
    (``identifier`` for a function, ``field_identifier`` for a method; a method's receiver is a ``parameter_list`` *before*
    the name, `gosource._receiver_type` reads the same shape). A parenthesized multi-value result (``(Config, error)``)
    parses as *another* ``parameter_list`` **after** this one — the naive "last one" reading of it is wrong, and was
    WP-14b's first bug, caught by the gold re-ground (`vc.Translate() (Config, error)`, a 0-arity method the naive
    reading counted as 2)."""
    seen_name = False
    for child in decl.children:
        if child.type in ("identifier", "field_identifier"):
            seen_name = True
            continue
        if seen_name and child.type == "parameter_list":
            return child
    return None


def _go_param_arity(decl) -> int | None:
    """The declared parameter count of a Go function or method declaration, exactly — a grouped name (``a, b string``) counts
    once each, an unnamed parameter (an interface method's signature) counts one — else None on a doubt: the declaration binds
    type parameters (generics), or any parameter is variadic (the call side, not this side, is where the syntax admits it may
    take zero or more)."""
    if any(c.type == "type_parameter_list" for c in decl.children):
        return None
    params = _go_own_param_list(decl)
    if params is None:
        return None
    total = 0
    for child in params.named_children:
        if child.type == "variadic_parameter_declaration":
            return None
        if child.type != "parameter_declaration":
            continue
        names = sum(1 for gc in child.children if gc.type == "identifier")
        total += names if names else 1
    return total


def _go_read_type(spec, path: str, imports: list[dict]) -> dict:
    """One top-level Go ``type_spec`` / ``type_alias`` as rule 1 reads it: ``kind`` (struct / interface / alias / other),
    the field names, the methods an interface declares, the embedded types (typerefs, None for one the reading cannot
    name) and, for ``other``, whether the underlying type is a named one (whose members a defined type may carry)."""
    d = str(PurePosixPath(path).parent)
    out = {"path": path, "dir": d, "imports": imports, "kind": "other", "fields": set(), "methods": set(), "embeds": [], "named_underlying": False}
    typ = spec.child_by_field_name("type")
    if spec.type == "type_alias":
        out["kind"] = "alias"
        out["embeds"] = [_go_typeref(typ)]
        return out
    if typ is None:
        return out
    if typ.type == "struct_type":
        out["kind"] = "struct"
        for fl in typ.named_children:
            for fd in fl.named_children:
                if fd.type != "field_declaration":
                    continue
                names = fd.children_by_field_name("name")
                if names:
                    out["fields"].update(_gtext(n) for n in names)
                else:
                    out["embeds"].append(_go_typeref(fd.child_by_field_name("type")))
    elif typ.type == "interface_type":
        out["kind"] = "interface"
        for el in typ.named_children:
            if el.type == "method_elem":
                nm = el.child_by_field_name("name")
                if nm is not None:
                    out["methods"].add(_gtext(nm))
            elif el.type == "type_elem":
                out["embeds"].extend(_go_typeref(c) for c in el.named_children)
    else:  # a defined type: its declared methods only, unless the underlying names a type whose members it may carry
        ref = _go_typeref(typ)
        out["named_underlying"] = ref is not None and not (ref[0] is None and ref[1] in GO_PREDECLARED and ref[1] != "error")
    return out


def density_table(graph: dict) -> dict:
    """Track B's density over one parent graph (``DENSITY_RULE``): every symbol's in-degree, the population, ``k`` and how
    many symbols are dense. Deterministic in the graph."""
    into: dict[str, set[str]] = collections.defaultdict(set)
    for e in graph.get("symbol_edges", []):
        if e.get("type") in ("calls", "uses") and e["from"] != e["to"]:
            into[e["to"]].add(e["from"])
    degree = {s["id"]: len(into.get(s["id"], ())) for s in graph.get("symbols", [])}
    ranked = sorted(degree.values(), reverse=True)
    cap = -(-len(ranked) // 3)
    k = max(1, ranked[cap] + 1) if cap < len(ranked) else 1
    return {"rule": DENSITY_RULE, "k": k, "population": len(ranked), "cap": cap, "dense_in_population": sum(1 for v in ranked if v >= k), "degree": degree}


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
_TS_EXTS = ("", ".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs", ".jsx", "/index.ts", "/index.js", "/index.mjs")


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
        if c["name"] == EXPR:
            continue  # the helper's marker for a callee that is an expression: nothing to bind (C-63)
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
        self.pkg: dict[str, dict[str, str]] = collections.defaultdict(dict)  # Go: package dir → name → id of what a bare name binds (never a method)
        self.go_methods: dict[tuple[str, str], dict[str, str]] = collections.defaultdict(dict)  # Go: (dir, receiver type) → method name → id
        for sid, s in L.symbols.items():
            p = L.mod_path.get(s["module"])
            if p and p.endswith(".go"):
                d = str(PurePosixPath(p).parent)
                if s.get("kind") == "method":
                    self.go_methods[(d, s.get("qualname", s["name"]).split(".")[0])][s["name"]] = sid
                else:
                    self.pkg[d][s["name"]] = sid
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
        self.tree_files = subprocess.run(["git", "ls-tree", "-r", "--name-only", self.sha], cwd=self.repo_root, capture_output=True, text=True).stdout.split("\n")
        self.go_mods = self._go_modules()
        self.go_dirs = {H.dir_of(p) for p in self.tree_files if p.endswith(".go")} | {H.dir_of(p) for p, P in post_parsed.items() if P.lang == "go"}
        self._requires: dict[str, frozenset] = {}
        self._toplevel: dict[str, set[str]] = {}
        self._file_names: dict[str, dict] = {}
        self.all_gensyms = set().union(*self.gensyms.values()) if self.gensyms else set()
        self.post_parsed = post_parsed
        self.go_gensym_bare: dict[str, set[str]] = collections.defaultdict(set)  # Go: dir → package-level names the post-image adds
        self.go_gensym_methods: dict[tuple[str, str], set[str]] = collections.defaultdict(set)  # Go: (dir, receiver type) → methods it adds
        for path, P in post_parsed.items():
            if P.lang != "go":
                continue
            d = str(PurePosixPath(path).parent)
            for s in P.symbols:
                if s["qualname"] in self.gensym_quals[path]:
                    if s["kind"] == "method":
                        self.go_gensym_methods[(d, s["qualname"].split(".")[0])].add(s["name"])
                    else:
                        self.go_gensym_bare[d].add(s["name"])
        self._go_files: dict[tuple[str, bool], tuple | None] = {}
        self._go_decls: dict[tuple[str, str, bool], dict | None] = {}
        self.iface: dict[str, tuple[str, str]] = {}  # rule 2: interface-method target → (interface type id, the RTA key's name for it)
        self._go_arities: dict[str, int | None] = {}  # WP-14b: in-graph Go symbol id → its own declared parameter count, or None
        self._arity_reasons: dict[tuple, str] = {}  # WP-14b: (path, line, name, receiver) → the arity NULL's reason text

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
        out = {}
        for p in self.tree_files:
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
        """Resolution, then signatures in the world (WP-14b, §2.5): a call bound `in-graph` is re-read as a NULL `arity` when
        it states an argument count its own callee's declaration does not accept, else unchanged."""
        cls, target = self._go_resolve(path, P, r)
        if cls == "in-graph":
            override = self._go_arity_null(path, r, target)
            if override is not None:
                return override
        return cls, target

    def _go_resolve(self, path: str, P: Parsed, r: Ref) -> tuple[str, str | None]:
        T = self.trace
        d = str(PurePosixPath(path).parent)
        if r.receiver is None:  # Go's scoping: a local, then the package block, then the universe
            if self.in_scope_local(P, r.name, r.line):
                return "local", None
            sid = T.look("package", f"{d}:{r.name}", self.pkg.get(d, {}).get(r.name))
            if sid:
                return "in-graph", sid
            if r.name in self.go_gensym_bare.get(d, ()):
                return "gensym", r.name
            if r.name in GO_PREDECLARED:
                return "builtin", None
            return "NULL", None
        local = self.go_binding(P, r.receiver, r.line)
        imp = next((i for i in P.imports if i["bound"] == r.receiver), None)
        if imp is not None and local is None:  # a binding declared before the call shadows the package name
            pd = T.look("import", imp["module"], self.go_package_dir(imp["module"]))
            if pd is None:
                return "external", imp["module"]
            sid = T.look("package", f"{pd}:{r.name}", self.pkg.get(pd, {}).get(r.name))
            if sid:
                return "in-graph", sid
            if r.name in self.go_gensym_bare.get(pd, ()):
                return "gensym", r.name
            return "NULL", None
        if local is not None and local[0] is not None:  # rule 1: a receiver whose type the syntax states
            return self.go_call_on(self.go_resolve_type(local[0], d, P.imports, P, r.line), r, "local")
        if local is not None or self.in_scope_local(P, r.receiver, r.line):
            return "local", r.receiver
        decl = self.go_var_type(d, r.receiver)
        if decl is not None:  # rule 1 on a package-level var whose declaration states its type
            ref, vpath, imports = decl
            return self.go_call_on(self.go_resolve_type(ref, str(PurePosixPath(vpath).parent), imports), r, "unknown-receiver")
        if self.go_unimported(path, P, r.receiver):  # the world check (WP-9, D-g): a qualifier nothing binds is judged, not abstained on
            return "NULL", "unimported"
        return "unknown-receiver", r.receiver

    def null_scope(self, path: str, P: Parsed, r: Ref) -> dict | None:
        """Where a declaration of a NULL name would have to sit for this call to bind (M0-Go WP-7a): Go only — ``{"dir"}`` for a bare
        name (its file's package) or a package-qualified one (the imported package's directory), ``{"dir", "type"}`` for a member on
        a receiver whose type the syntax states (rule 1); None when the grounder cannot say. The same readings `_go` resolves by."""
        if P.lang != "go":
            return None
        d = str(PurePosixPath(path).parent)
        if r.receiver is None:
            return {"dir": d}
        local = self.go_binding(P, r.receiver, r.line)
        imp = next((i for i in P.imports if i["bound"] == r.receiver), None)
        if imp is not None and local is None:
            pd = self.go_package_dir(imp["module"])
            return None if pd is None else {"dir": pd}
        t = None
        if local is not None and local[0] is not None:
            t = self.go_resolve_type(local[0], d, P.imports, P, r.line)
        elif local is None and not self.in_scope_local(P, r.receiver, r.line) and (decl := self.go_var_type(d, r.receiver)) is not None:
            t = self.go_resolve_type(decl[0], str(PurePosixPath(decl[1]).parent), decl[2])
        return {"dir": t[1], "type": t[2]} if t is not None and t[0] == "repo" else None

    # ---- Go: rules 1 and 2 (M0-Go §2.4)

    def go_binding(self, P: Parsed, name: str, line: int) -> tuple | None:
        """The innermost binding of *name* declared at or before *line* in a function enclosing it: ``(typeref,)``, the
        typeref None when the syntax does not state one or that function binds the name with more than one; else None."""
        cands = [b for b in P.go_binds if b[0] == name and b[3] <= line <= b[4] and b[2] <= line]
        if not cands:
            return None
        inner = min(b[4] - b[3] for b in cands)
        types = {b[1] for b in cands if b[4] - b[3] == inner}
        return (types.pop() if len(types) == 1 else None,)

    def go_resolve_type(self, ref, d: str, imports: list[dict], P: Parsed | None = None, line: int = 0) -> tuple | None:
        """A typeref read in a file of package dir *d*: ``("repo", dir, name)``, ``("external", import path)`` or
        ``("builtin", name)``; None for a type parameter or a function-local type in scope, or an alias no import binds."""
        if ref is None:
            return None
        alias, name = ref
        if alias is None:
            if P is not None and any(n == name and a <= line <= b for n, a, b in P.go_tparams + P.go_ltypes):
                return None
            if name in GO_PREDECLARED and name not in self.pkg.get(d, {}) and name not in self.go_gensym_bare.get(d, ()):
                return ("builtin", name)
            return ("repo", d, name)
        imp = next((i for i in imports if i["bound"] == alias), None)
        if imp is None:
            return None
        pd = self.trace.look("import", imp["module"], self.go_package_dir(imp["module"]))
        return ("external", imp["module"]) if pd is None else ("repo", pd, name)

    def go_call_on(self, t: tuple | None, r: Ref, unread: str) -> tuple[str, str | None]:
        """Member ``r.name`` called on a receiver of resolved type *t*; *unread* is the abstention when the type cannot be named."""
        if t is None:
            return unread, r.receiver
        if t[0] in ("builtin", "external"):
            return t[0], t[1]
        return self.go_member(t[1], t[2], r.name)

    def go_member(self, d: str, T: str, name: str, depth: int = 0) -> tuple[str, str | None]:
        """Member *name* of repo type *T* in package dir *d*, exactly: the graph's method, a method the post-image adds,
        an interface's method (rule 2), a field, one promoted through an embedded repo type (depth ≤ 3) — else NULL. A member
        that may be promoted from a type outside the repo abstains as that type's class; a type neither the graph nor the
        post-image declares, or a defined type over a named one, abstains ``unknown-receiver``."""
        sid = self.trace.look("method", f"{d}:{T}.{name}", self.go_methods.get((d, T), {}).get(name))
        if sid:
            return "in-graph", sid
        if name in self.go_gensym_methods.get((d, T), ()):
            return "gensym", f"{T}.{name}"
        decl = self.go_type_decl(d, T)
        if decl is None:
            return "unknown-receiver", T
        if decl["kind"] == "interface" and name in decl["methods"]:
            tsid = self.pkg.get(d, {}).get(T)
            parent = self.go_type_decl(d, T, parent=True)
            if tsid is None or self.L.symbols[tsid].get("kind") != "type" or parent is None or name not in parent["methods"]:
                return "gensym", f"{T}.{name}"  # an interface method the diff declares: new, not a parent symbol
            target = f"{tsid}.{name}"
            self.iface[target] = (tsid, f"{self.go_import_path(d)}.{T}.{name}")
            return "interface", target
        if name in decl["fields"]:
            return "field", f"{T}.{name}"
        outside = None
        for ref in decl["embeds"]:
            t = self.go_resolve_type(ref, decl["dir"], decl["imports"])
            if t is None or t[0] != "repo":
                outside = outside or (t if t is not None else ("unknown-receiver", T))
                continue
            if depth < 3:
                hit = self.go_member(t[1], t[2], name, depth + 1)
                if hit[0] != "NULL":
                    return hit
        if outside is not None:
            return outside[0], outside[1]
        if decl["kind"] == "other" and decl["named_underlying"]:
            return "unknown-receiver", T
        return "NULL", None

    def go_file(self, path: str, parent: bool = False) -> tuple | None:
        """A Go file's tree and imports — the post-image when the diff edits it (unless *parent*), else the parent's."""
        key = (path, parent)
        if key not in self._go_files:
            from hobbes.extract import gosource
            text = None if parent else self.post_text.get(path)
            if text is None:
                text = _show(str(self.repo_root), self.sha, path)
            if text is None:
                self._go_files[key] = None
            else:
                root = gosource._PARSER.parse(text.encode("utf-8", "surrogateescape")).root_node
                imports = [{"bound": i["alias"], "module": i["path"]} for n in root.children if n.type == "import_declaration" for i in gosource._imports(n)]
                self._go_files[key] = (root, imports)
        return self._go_files[key]

    def _go_decl_paths(self, d: str, name: str, kind: str, parent: bool) -> list[str]:
        paths = [] if parent else [p for p in sorted(self.post_parsed) if self.post_parsed[p].lang == "go" and str(PurePosixPath(p).parent) == d
                                   and any(s["name"] == name and s["kind"] == kind for s in self.post_parsed[p].symbols)]
        sid = self.pkg.get(d, {}).get(name)
        if not paths and sid and self.L.symbols[sid].get("kind") == kind:
            paths = [self.L.mod_path[self.L.symbols[sid]["module"]]]
        return paths

    def go_type_decl(self, d: str, T: str, parent: bool = False) -> dict | None:
        """Repo type *T* of package dir *d* as `_go_read_type` reads it — from the post-image that declares it, else the
        file the graph places it in (only the latter when *parent*); None when neither has it. Traced."""
        key = (d, T, parent)
        if key not in self._go_decls:
            decl = None
            for path in self._go_decl_paths(d, T, "type", parent):
                f = self.go_file(path, parent)
                if f is None:
                    continue
                root, imports = f
                for node in root.children:
                    if node.type != "type_declaration":
                        continue
                    for spec in node.named_children:
                        nm = spec.child_by_field_name("name") if spec.type in ("type_spec", "type_alias") else None
                        if nm is not None and _gtext(nm) == T:
                            decl = _go_read_type(spec, path, imports)
                            break
                    if decl:
                        break
                if decl:
                    break
            self.trace.look("type-decl", f"{d}:{T}{'@parent' if parent else ''}", None if decl is None else f"{decl['kind']} in {decl['path']}")
            self._go_decls[key] = decl
        return self._go_decls[key]

    def go_var_type(self, d: str, name: str) -> tuple | None:
        """A package-level ``var`` of package dir *d*: ``(typeref, path, imports)`` when its declaration states a type
        (``var x T``, ``= T{…}``, ``= &T{…}``, ``= new(T)``), else None. Traced."""
        for path in self._go_decl_paths(d, name, "var", False):
            f = self.go_file(path)
            if f is None:
                continue
            root, imports = f
            for node in root.children:
                if node.type != "var_declaration":
                    continue
                specs = [c for c in node.named_children if c.type == "var_spec"]
                specs += [s for c in node.named_children if c.type == "var_spec_list" for s in c.named_children if s.type == "var_spec"]
                for spec in specs:
                    names = [_gtext(n) for n in spec.children_by_field_name("name")]
                    if name not in names:
                        continue
                    typ, vs = spec.child_by_field_name("type"), _go_list(spec.child_by_field_name("value"))
                    i = names.index(name)
                    ref = _go_typeref(typ) if typ is not None else (_go_value_typeref(vs[i]) if len(vs) == len(names) else None)
                    self.trace.look("var-type", f"{d}:{name}", None if ref is None else ".".join(x for x in ref if x))
                    return None if ref is None else (ref, path, imports)
        return None

    def go_import_path(self, d: str) -> str:
        """The import path of package dir *d* (the inverse of `go_package_dir`) — the name an RTA key gives its members."""
        d = "" if d == "." else d
        for mod, mdir in sorted(self.go_mods.items(), key=lambda x: len(x[1]), reverse=True):
            if mdir == "" or d == mdir or d.startswith(mdir + "/"):
                rest = d[len(mdir):].lstrip("/") if mdir else d
                return mod + ("/" + rest if rest else "")
        return d

    # ---- Go: signatures in the world (M0-Go round 2 WP-14b, §2.5)

    def go_arity(self, sid: str) -> int | None:
        """The declared parameter count of in-graph Go symbol *sid*'s own function or method declaration — read from its
        source at the SHA (`go_file`, ``parent=True``: *sid* is in the parent graph by construction), exactly, or None on
        any doubt (`_go_param_arity`; not a function or method; its declaration cannot be found or read; **its own file is
        edited by this diff** — the parent's signature is not the world a call in the post-image is bound by when the
        signature itself may be the thing changing, gold's own `DirectoryTargets`/`detectRule` being exactly this shape,
        caught by the gold re-ground). Cached — the same callee is asked once per grounding."""
        if sid not in self._go_arities:
            self._go_arities[sid] = self._compute_go_arity(sid)
        return self._go_arities[sid]

    def _compute_go_arity(self, sid: str) -> int | None:
        sym = self.L.symbols.get(sid)
        if sym is None or sym.get("kind") not in ("function", "method"):
            return None
        path = self.L.mod_path.get(sym["module"])
        if path is None or not path.endswith(".go"):
            return None
        if path in self.post_text:  # this diff may itself be changing the callee's own signature: abstain
            return None
        f = self.go_file(path, parent=True)
        if f is None:
            return None
        root, _imports = f
        line = sym.get("line")
        if line is None:
            return None
        decl = _go_find_decl_at(root, line, sym["kind"])
        if decl is None:
            return None
        arity = _go_param_arity(decl)
        self.trace.look("arity", sid, arity)
        return arity

    def _go_arity_null(self, path: str, r: Ref, sid: str) -> tuple[str, str | None] | None:
        """Call *r*, bound `in-graph` to Go symbol *sid*, as a NULL `arity` when its own syntactic argument count differs
        from *sid*'s declared parameter count — None (no override) on any doubt: the call's own shape (`r.argc`, a possible
        multi-value spread; `r.variadic_call`, a slice spread) or the callee's (`go_arity`, variadic or generic) abstains."""
        if r.argc is None or r.variadic_call:
            return None
        want = self.go_arity(sid)
        if want is None or want == r.argc:
            return None
        self._arity_reasons[(path, r.line, r.name, r.receiver)] = (
            f"`{r.name}` declares {want} parameter{'s' if want != 1 else ''}, called here with {r.argc}"
        )
        return "NULL", "arity"

    def arity_reason(self, path: str, r: Ref) -> str:
        return self._arity_reasons.get(
            (path, r.line, r.name, r.receiver),
            f"`{r.name}` is called with {r.argc} argument(s), which its own declaration does not accept",
        )

    # ---- Go: the world (M0-Go WP-9, D-g; §2.5)

    def go_module_of(self, d: str) -> tuple[str, str] | None:
        """The module governing package dir *d*: ``(module path, its go.mod's directory)`` — the go.mod nearest above *d* at the SHA."""
        d = "" if d == "." else d
        best = None
        for mod, mdir in self.go_mods.items():
            if (mdir == "" or d == mdir or d.startswith(mdir + "/")) and (best is None or len(mdir) > len(best[1])):
                best = (mod, mdir)
        return best

    def go_requires(self, mdir: str) -> frozenset:
        """The module paths the go.mod in *mdir* requires at the SHA: every ``require`` line, single or in a block, ``// indirect``
        included (the build resolves an import from any module its go.mod lists)."""
        if mdir not in self._requires:
            text = _show(str(self.repo_root), self.sha, f"{mdir}/go.mod" if mdir else "go.mod") or ""
            mods, block = set(), False
            for line in text.split("\n"):
                s = line.split("//", 1)[0].strip()
                if block:
                    if s.startswith(")"):
                        block = False
                    elif s:
                        mods.add(s.split()[0].strip('"'))
                elif re.match(r"require\b", s):
                    rest = s[len("require"):].strip()
                    if rest.startswith("("):
                        block = True
                    elif rest:
                        mods.add(rest.split()[0].strip('"'))
            self._requires[mdir] = frozenset(mods)
            self.trace.look("go.mod", f"{mdir or '.'}/go.mod", f"{len(mods)} required modules")
        return self._requires[mdir]

    def go_import_world(self, file_path: str, ipath: str) -> tuple[str, str | None]:
        """Where one import path of a Go file sits in the world: ``("std" | "module" | "required", None)``, ``("import-outside", why)``, or
        ``("unverifiable", why)`` when no go.mod governs the file (`WORLD_RULE`)."""
        if ipath in GO_STDLIB or ipath in GO_PSEUDO_IMPORTS:
            return "std", None
        m = self.go_module_of(H.dir_of(file_path))
        if m is None:
            return "unverifiable", "no go.mod governs the file"
        mod, mdir = m
        if ipath == mod or ipath.startswith(mod + "/"):
            d = "/".join(x for x in (mdir, ipath[len(mod):].lstrip("/")) if x)
            if d in self.go_dirs:
                return "module", None
            return "import-outside", f"a path of the module `{mod}` naming no Go package at this commit or in the diff (`{d or '.'}/`)"
        if any(ipath == r or ipath.startswith(r + "/") for r in self.go_requires(mdir)):
            return "required", None
        return "import-outside", f"not the Go standard library (go1.26.5), not a package of the module `{mod}`, and under no module its go.mod requires"

    def go_package_clause(self, d: str) -> str | None:
        """The package clause of package dir *d*: its first non-test Go file in the post-image, else at the SHA."""
        cands = sorted(p for p, P in self.post_parsed.items() if P.lang == "go" and H.dir_of(p) == d and not p.endswith("_test.go"))
        cands += sorted(p for p in self.tree_files if p.endswith(".go") and not p.endswith("_test.go") and H.dir_of(p) == d)
        for p in cands:
            f = self.go_file(p)
            if f is not None:
                from hobbes.extract import gosource
                return gosource._package_name(f[0]) or None
        return None

    def go_file_names(self, path: str, P: Parsed) -> dict:
        """What names a Go post-image may qualify with: ``bound`` (what its imports may bind — `_go_import_names`, an explicit alias
        exactly, a module package's clause too), ``dot`` (a dot import: anything may be bound) and ``plain`` (`_go_plain_identifiers`)."""
        if path not in self._file_names:
            bound, dot = set(), False
            for s in _go_import_specs(P.go_root):
                if s["alias"] == ".":
                    dot = True
                elif s["alias"] == "_":
                    continue
                elif s["alias"]:
                    bound.add(s["alias"])
                else:
                    bound |= _go_import_names(s["path"])
                    m = self.go_module_of(H.dir_of(path))
                    if m is not None and (s["path"] == m[0] or s["path"].startswith(m[0] + "/")):
                        clause = self.go_package_clause("/".join(x for x in (m[1], s["path"][len(m[0]):].lstrip("/")) if x))
                        if clause:
                            bound.add(clause)
            self._file_names[path] = {"bound": bound, "dot": dot, "plain": _go_plain_identifiers(P.go_root)}
        return self._file_names[path]

    def go_dir_toplevel(self, d: str) -> set[str]:
        """Every package-level name a Go file of package dir *d* declares, by the syntax: the parent's files (the post-image where the diff
        edits one) and the post-image's new files there. Build tags are not read — a union, so a doubt abstains."""
        d = "" if d == "." else d
        if d not in self._toplevel:
            paths = {p for p in self.tree_files if p.endswith(".go") and H.dir_of(p) == d}
            paths |= {p for p, P in self.post_parsed.items() if P.lang == "go" and H.dir_of(p) == d}
            names: set[str] = set()
            for p in sorted(paths):
                f = self.go_file(p)
                if f is not None:
                    names |= _go_toplevel_names(f[0])
            self._toplevel[d] = names
            self.trace.look("package-names", f"{d or '.'}/", f"{len(names)} names in {len(paths)} files")
        return self._toplevel[d]

    def go_qualifier_package_dir(self, path: str, P: Parsed, q: str) -> str | None:
        """The in-repo package directory qualifier *q* names in Go post-image *path*, when *q* binds to exactly one import
        of **this module's own** package (`go_import_world`'s ``"module"``) — else None: std, a required (external) module,
        an alias no import binds, or two imports binding *q* to different packages. `undeclared-type`'s world is exactly
        what `go_dir_toplevel` reads whole, so every doubt here abstains rather than guess at a package this grounder does
        not fully own (SIGNATURE_RULE)."""
        if P.lang != "go" or P.go_root is None or not q:
            return None
        m = self.go_module_of(H.dir_of(path))
        hit: str | None = None
        for s in _go_import_specs(P.go_root):
            if s["alias"] in (".", "_"):
                continue
            ipath = s["path"]
            if s["alias"]:
                matched = s["alias"] == q
            else:
                matched = q in _go_import_names(ipath)
                if not matched and m is not None and (ipath == m[0] or ipath.startswith(m[0] + "/")):
                    d = "/".join(x for x in (m[1], ipath[len(m[0]):].lstrip("/")) if x)
                    matched = self.go_package_clause(d) == q
            if not matched:
                continue
            kind, _why = self.go_import_world(path, ipath)
            if kind != "module" or m is None:
                return None  # bound, but not a package this rule fully owns: abstain outright
            d = "/".join(x for x in (m[1], ipath[len(m[0]):].lstrip("/")) if x)
            if hit is not None and hit != d:
                return None  # two imports bind q to different packages: ambiguous, abstain
            hit = d
        return hit

    def go_unimported(self, path: str, P: Parsed, q: str | None) -> bool:
        """Whether qualifier *q* in Go post-image *path* names nothing the file can see (`WORLD_RULE`): no import may bind it, no dot
        import, not predeclared, never written as a plain identifier, declared at top level by no Go file of the package."""
        if P.lang != "go" or P.go_root is None or not q or not _GO_IDENT.fullmatch(q) or q == "_" or q in GO_PREDECLARED:
            return False
        info = self.go_file_names(path, P)
        if info["dot"] or q in info["bound"] or q in info["plain"]:
            return False
        d = str(PurePosixPath(path).parent)
        if q in self.pkg.get(d, {}) or q in self.go_gensym_bare.get(d, ()) or q in self.go_dir_toplevel(d):
            return False
        return self.trace.look("unimported", f"{path}:{q}", True)

    def go_world(self, path: str, P: Parsed, owned: list[tuple[int, int, str]]) -> tuple[list[dict], collections.Counter]:
        """The world check on one Go post-image (`WORLD_RULE`, `SIGNATURE_RULE`): every import spec and every non-call selector or
        qualified type inside an edited range — a bound qualifier of this module's own package is also read against
        `go_dir_toplevel` (WP-14b, §2.5). Returns the NULL rows (``kind`` import / selector / type, with the owning hole and the reason)
        and the tally of every judgment."""
        rows: list[dict] = []
        tally: collections.Counter = collections.Counter()
        if P.lang != "go" or P.go_root is None:
            return rows, tally

        def owner(line):
            return next((h for a, b, h in owned if a <= line <= b), None)

        for s in _go_import_specs(P.go_root):
            h = owner(s["line"])
            if h is None:
                continue
            kind, why = self.go_import_world(path, s["path"])
            tally[f"import:{kind}"] += 1
            self.trace.look("import-world", s["path"], kind)
            if kind == "import-outside":
                rows.append({"hole": h, "line": s["line"], "term": s["path"], "kind": "import", "null_class": "import-outside", "reason": why})
        seen = set()
        for n in _iter_nodes(P.go_root):
            if n.type == "selector_expression":
                op, fld = n.child_by_field_name("operand"), n.child_by_field_name("field")
                if op is None or fld is None or op.type != "identifier":
                    continue
                par = n.parent
                fn = par.child_by_field_name("function") if par is not None and par.type == "call_expression" else None
                if fn is not None and fn.start_byte == n.start_byte and fn.end_byte == n.end_byte:
                    continue  # a call site: judged with the calls (`_go`)
                q, name = _gtext(op), _gtext(fld)
            elif n.type == "qualified_type":
                pk, nm = n.child_by_field_name("package"), n.child_by_field_name("name")
                if pk is None or nm is None:
                    continue
                q, name = _gtext(pk), _gtext(nm)
            else:
                continue
            line = n.start_point.row + 1
            h = owner(line)
            if h is None or (line, q, name) in seen:
                continue
            seen.add((line, q, name))
            if self.go_unimported(path, P, q):
                tally["qualifier:unimported"] += 1
                rows.append({"hole": h, "line": line, "term": f"{q}.{name}", "kind": "selector", "null_class": "unimported", "reason": self.unimported_reason(path, q)})
                continue
            # WP-14b, §2.5: bound to a package this grounder fully owns (its own module) — is *name* really there?
            pd = self.go_qualifier_package_dir(path, P, q)
            if pd is not None and name not in self.go_dir_toplevel(pd):
                tally["qualifier:undeclared-type"] += 1
                rows.append({"hole": h, "line": line, "term": f"{q}.{name}", "kind": "type" if n.type == "qualified_type" else "selector",
                             "null_class": "undeclared-type", "reason": self.undeclared_type_reason(q, pd, name)})
            else:
                tally["qualifier:bound-or-abstained"] += 1
        return rows, tally

    @staticmethod
    def unimported_reason(path: str, q: str) -> str:
        return f"`{q}` is imported by no import of `{path}`, and neither the file nor its package declares it"

    @staticmethod
    def undeclared_type_reason(q: str, pd: str, name: str) -> str:
        return f"`{q}` is package `{pd or '.'}/` of this module, which declares no `{name}` at top level"

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

def ground(template: dict, doc: dict, L: Ledger, repo_root: Path, *, rta: dict | None = None) -> dict:
    """The grounder: fills → diff + NULL list + read-trace + the invariant counts. Deterministic in its inputs (I5).

    *rta* — ``{"source": str, "sites": {interface method name: [implementer names]}}``, an RTA key's invoke sites — puts
    the implementers it names on each rule-2 row; they are recorded, never bound."""
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
    D = density_table(L.graph)
    dens = collections.Counter()
    world = collections.Counter()

    def density(cls: str, target: str | None) -> tuple[str | None, int | None]:
        if cls not in DENSITY_CLASSES:
            return None, None
        if cls in ("gensym", "NULL"):
            return "absent", None
        deg = D["degree"].get(R.iface[target][0] if cls == "interface" else target)
        return (None, None) if deg is None else ("dense" if deg >= D["k"] else "sparse", deg)

    hole_at: dict[str, list[tuple[int, int, str]]] = collections.defaultdict(list)  # which hole owns each post-image range, in apply_edits' order
    for path in post:
        es = sorted([e for e in edits if e.path == path and not any(x.get("hole") == e.hole for x in overlaps)], key=lambda e: (e.start, e.end, e.hole))
        for e, (a, b) in zip(es, ranges[path]):
            hole_at[path].append((a, b, e.hole))
    for path in sorted(post):
        lang = language_of(path)
        if lang is None:
            by_class["not-code"] += 1
            refs.append({"hole": ",".join(h for _, _, h in hole_at[path]), "path": path, "line": 0, "term": "", "class": "not-code", "target": None, "density": None, "refs_in": None})
            continue
        P = parsed.get(path)
        if P is None:
            by_class["unsupported"] += 1
            refs.append({"hole": ",".join(h for _, _, h in hole_at[path]), "path": path, "line": 0, "term": "", "class": "unsupported", "target": lang, "density": None, "refs_in": None})
            continue
        text = "\n".join(post[path]) + ("\n" if post[path] else "")
        if text and H.carries_gutter(text):  # round 2 D-m: say so, not a silent zero (a pre-guard replay only; the validator refuses this live)
            by_class["malformed"] += 1
            refs.append({"hole": ",".join(h for _, _, h in hole_at[path]), "path": path, "line": 0, "term": "", "class": "malformed", "target": None,
                         "density": None, "refs_in": None, "reason": H.GUTTER_ERROR})
            continue
        for r in P.refs:
            owner = next((h for a, b, h in hole_at[path] if a <= r.line <= b), None)
            if owner is None:
                continue
            cls, target = R.resolve(path, P, r)
            row = {"hole": owner, "path": path, "line": r.line, "term": r.name if r.receiver is None else f"{r.receiver}.{r.name}", "class": cls, "target": target}
            row["density"], row["refs_in"] = density(cls, target)
            if row["density"]:
                dens[row["density"]] += 1
            if cls == "interface":
                row["rta_key"] = R.iface[target][1]
                row["implementers"] = None if rta is None else sorted(rta.get("sites", {}).get(row["rta_key"], []))
            by_class[cls] += 1
            if cls == "NULL" and target in WORLD_NULL_CLASSES:  # the world check on a call's qualifier (WP-9)
                row["target"] = None
                row.update({"null_class": target, "nearest": [], "declared": False, "scope": None, "kind": "call", "reason": R.unimported_reason(path, r.receiver)})
                nulls.append(row)
            elif cls == "NULL" and target == "arity":  # signatures in the world (WP-14b, §2.5)
                row["target"] = None
                row.update({"null_class": "arity", "nearest": [], "declared": False, "scope": None, "kind": "call", "reason": R.arity_reason(path, r)})
                nulls.append(row)
            elif cls == "NULL":
                _, near, ncls = R.null(r.name, path)
                row.update({"null_class": ncls, "nearest": near, "declared": r.name in R.declared, "scope": R.null_scope(path, P, r)})
                nulls.append(row)
            refs.append(row)
        wrows, tally = R.go_world(path, P, hole_at[path])
        world.update(tally)
        for w in wrows:
            row = {"hole": w["hole"], "path": path, "line": w["line"], "term": w["term"], "class": "NULL", "target": None, "density": "absent", "refs_in": None,
                   "null_class": w["null_class"], "nearest": [], "declared": False, "scope": None, "kind": w["kind"], "reason": w["reason"]}
            dens["absent"] += 1
            by_class["NULL"] += 1
            nulls.append(row)
            refs.append(row)
    judged = by_class["in-graph"] + by_class["interface"] + by_class["NULL"]
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
        "density": {**{k: D[k] for k in ("rule", "k", "population", "cap", "dense_in_population")}, "counts": {c: dens[c] for c in ("dense", "sparse", "absent")}},
        "rta": None if rta is None else rta.get("source"),
        "world": {"rule": WORLD_RULE, "signature_rule": SIGNATURE_RULE, "stdlib": f"go1.26.5, {len(GO_STDLIB)} packages", "counts": dict(sorted(world.items()))},
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


