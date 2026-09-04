"""`hobbes template` — the Calvin M0 template generator (`docs/calvin-potential.md` §2.1; step 2 of §8).

Deterministic and model-free: the task text, the ledger at the parent
SHA (graph + testmap), the repo (read only through ``git`` at that SHA)
and the co-change window in; a template in the hole language v0
(`hobbes.derive.holes`) out — same inputs, same bytes, keyed
``(parent_sha, task_hash, template_version)`` and hashed.

**Anchor pass (H-a).** The task's tokens are matched against the ledger
in a fixed order, each anchor recording the matcher that fired:
backticked identifiers (exact node id, symbol id, unique symbol name or
module basename); file paths (exact, then a unique ``/``-boundary
suffix); test ids (``path::name`` in the testmap); stack-trace lines
(``path:line`` inside a known span); quoted strings and backticked
non-identifiers as **literals** (``git grep -F`` at the SHA, the hit
lines mapped to the spans that hold them — the step-1 reading: for a
task like "add a flag to `oracle go-rta`" the literal is the only
thread into the code); and bare identifiers naming **exactly one**
node. A bare-identifier anchor is the weakest evidence and opens an
``ANCHOR_CONFIRM``. Every code-shaped token (C-36's rule) that no
matcher bound is emitted in the ``UNRESOLVED`` block with its nearest
graph names — recorded, never used — for the orchestrator to classify;
a backticked term that only the literal matcher caught stays there too,
because as a *name* it is unbound.

**Structure pass (H-s).** The anchored symbols plus their in-repo
callees are the **interior** (``SIGNATURE`` + ``BODY`` per symbol);
(plus the types an anchored symbol ``uses`` that are declared in an
interior file — the struct a flag lands in), their callers get ``CALLER_UPDATE`` (closed with reason ``partition``
when the caller's file is outside the write partition), the tests the
testmap says reach them ``TEST_EXPECTATION``, the interior files'
module-level code ``MODULE_REGION`` holes (``head`` before the first
symbol, each ``gap`` between symbols, ``tail`` to end of file — the
``imports`` kind of the design needs line facts the graph does not
carry, so the head holds them, v0), and files co-committed with an
interior file at least twice in the window ``COCHANGE_TOUCH``. The
write partition is the interior's files plus the guarding tests' files.
Regions are emitted for interior files only: a test file's module-level
code is not where a task lands, and a region outside the partition
could not be written anyway. Zero anchors (at build time, or after
round 1 refused every confirmation) → one ``ANCHOR`` hole, carrying
**candidates from Hobbes** (step 6's first protocol change, from the
step-4 reading that an orchestrator asked outright echoes the task's
prose): the planner's lexical seeds over the task with the word that
seeded each (C-36 — the same input arm O's manifest is built from),
the nearest graph names per unresolved term with their node ids, and
the ledger's file listing by directory. The orchestrator chooses among
them or names something else that exists; binding stays exact.

``apply_round1`` rebuilds the template from the orchestrator's answers
to the round-1 holes (``refers`` terms become anchors, ``new`` terms
open ``NEW_SYMBOL`` holes, a rejected ``ANCHOR_CONFIRM`` drops its
anchor); ``prune`` applies the structural rules after fills (a function
``SIGNATURE = unchanged`` closes that symbol's ``CALLER_UPDATE``s —
functions only, a type's callers change when its fields do; a
``MODULE_REGION = unchanged`` is dropped). ``score_coverage`` and
``score_anchors`` are §4.1 and §4.2 against a gold diff, computed with
no orchestrator in the loop.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
from pathlib import Path

from hobbes.derive.cochange import CoChange
from hobbes.derive.holes import FILL_SHAPES, TEMPLATE_VERSION
from hobbes.derive.impact import _TOKEN, _code_shaped

_BACKTICK = re.compile(r"`([^`\n]+)`")
_QUOTED = re.compile(r'"([^"\n]{4,})"')
_TEST_ID = re.compile(r"[\w./-]+::[\w-]+(?: > [^;,.\n]+?)?(?=[;,.\s]|$)")
_STACK = re.compile(r"([\w./-]+\.\w+):(\d+)")
_PATHISH = re.compile(r"[\w.-]+(?:/[\w.-]+)+")
_GREP_LINE = re.compile(r"^[0-9a-f]{7,40}:(.+?):(\d+):")
NEAREST = 4
PARTNER_MIN = 2
#: A literal that lands in more symbols than this is too common to anchor (`calls`, `uses`, `grade` name edge types and
#: subcommands across the repo); the note records the count and the term goes to the unresolved block. A declared guess.
LITERAL_MAX_NODES = 12
FUNCTION_KINDS = ("function", "method")


def task_hash(task: str) -> str:
    """The change-spec's keying (ADR-026): the id follows the text."""
    return hashlib.sha256(task.encode()).hexdigest()[:12]


# ------------------------------------------------------------------ ledger

class Ledger:
    """The graph and testmap at one SHA, indexed for the two passes."""

    def __init__(self, graph: dict, tests: dict):
        self.graph = graph
        self.sha = graph["sha"]
        self.symbols = {s["id"]: s for s in graph["symbols"]}
        self.mod_path = {n["id"]: n["path"] for n in graph["nodes"] if n.get("path")}
        self.path_mod = {v: k for k, v in self.mod_path.items()}
        self.by_module: dict[str, list[dict]] = {}
        for s in sorted(graph["symbols"], key=lambda s: (s["module"], s["line"], s["id"])):
            self.by_module.setdefault(s["module"], []).append(s)
        self.by_name: dict[str, list[str]] = {}
        for s in graph["symbols"]:
            self.by_name.setdefault(s["name"], []).append(s["id"])
        for m, p in self.mod_path.items():
            self.by_name.setdefault(Path(p).stem, []).append(m)
            self.by_name.setdefault(m.rsplit("/", 1)[-1], []).append(m)
        self.calls_out: dict[str, list[dict]] = {}
        self.calls_in: dict[str, list[dict]] = {}
        for e in graph["symbol_edges"]:
            if e["type"] == "calls" and e["from"] in self.symbols and e["to"] in self.symbols:
                self.calls_out.setdefault(e["from"], []).append(e)
                self.calls_in.setdefault(e["to"], []).append(e)
        self.tests = sorted(tests.get("tests", []), key=lambda t: t["id"])
        self.test_ids = {t["id"] for t in self.tests}
        self.names = sorted(self.by_name)
        #: module → the repo modules it imports (the graph's `imports` module edges; `ext:` targets dropped) — what a test
        #: reaches without calling anything the testmap maps (step 6's `PROFILES` miss: a module-level value read by name).
        self.imports_of: dict[str, set[str]] = {}
        for e in graph.get("module_edges", []):
            if e.get("type") == "imports" and e["to"] in self.mod_path:
                self.imports_of.setdefault(e["from"], set()).add(e["to"])

    def importers_of(self, module: str) -> set[str]:
        return {m for m, imps in self.imports_of.items() if module in imps}

    def span(self, sid: str) -> dict:
        s = self.symbols[sid]
        return {"path": self.mod_path[s["module"]], "start": s["line"], "end": s["end_line"]}

    def path_of(self, sid: str) -> str:
        return self.mod_path[self.symbols[sid]["module"]]

    def symbol_at(self, path: str, line: int) -> str | None:
        """The innermost symbol whose span holds ``path:line``, else None."""
        m = self.path_mod.get(path)
        best = None
        for s in self.by_module.get(m, []):
            if s["line"] <= line <= s["end_line"] and (best is None or s["end_line"] - s["line"] < best["end_line"] - best["line"]):
                best = s
        return best["id"] if best else None

    def nearest(self, term: str) -> list[str]:
        t = term.strip(".").lower()
        scored = sorted(((-difflib.SequenceMatcher(None, t, n.lower()).ratio(), n) for n in self.names if abs(len(n) - len(t)) <= 4))
        return [n for _, n in scored[:NEAREST]]


# ------------------------------------------------------------- anchor pass

def _git_grep(repo_root: Path, sha: str, literal: str) -> list[tuple[str, int]]:
    r = subprocess.run(["git", "grep", "-n", "-F", "-e", literal, sha, "--"], cwd=repo_root, capture_output=True, text=True)
    hits = []
    for line in r.stdout.splitlines():
        m = _GREP_LINE.match(line)
        if m:  # a "Binary file … matches" line has no line number and is not a hit in the ledger's sense
            hits.append((m.group(1), int(m.group(2))))
    return sorted(set(hits))


def _resolve_name(L: Ledger, term: str) -> list[str]:
    """Exact node id, symbol id, or a name exactly one node carries."""
    if term in L.mod_path or term in L.symbols:
        return [term]
    ids = L.by_name.get(term, [])
    return ids if len(ids) == 1 else []


def _resolve_path(L: Ledger, term: str) -> list[str]:
    """A file path (exact, then a unique ``/``-boundary suffix), or a directory holding modules (exact, then a unique
    suffix) → the modules directly in it — `hobbes-proxy` names `go/cmd/hobbes-proxy/`."""
    term = term.strip("./") if not term.startswith("./") else term[2:]
    if term in L.path_mod:
        return [L.path_mod[term]]
    ends = [m for p, m in L.path_mod.items() if p.endswith("/" + term)]
    if len(ends) == 1:
        return ends
    dirs = sorted({str(Path(p).parent) for p in L.path_mod})
    hit = [d for d in dirs if d == term or d.endswith("/" + term)]
    if len(hit) == 1:
        return sorted(m for p, m in L.path_mod.items() if str(Path(p).parent) == hit[0])
    return []


def _literal_anchors(L: Ledger, repo_root: Path, literal: str) -> tuple[list[str], str]:
    """Symbols whose span holds a hit of *literal* at the SHA. A hit outside every span (a file's doc comment, a
    Markdown file) anchors nothing — it is named in the note, never expanded into a module's every symbol."""
    nodes = []
    hits = _git_grep(repo_root, L.sha, literal)
    outside = 0
    for path, ln in hits:
        sym = L.symbol_at(path, ln) if path in L.path_mod else None
        if sym:
            nodes.append(sym)
        else:
            outside += 1
    where = ", ".join(f"{p}:{n}" for p, n in hits[:6]) + (" …" if len(hits) > 6 else "")
    if outside:
        where += f" ({outside} hit{'s' if outside > 1 else ''} outside any symbol span, not anchored)"
    nodes = sorted(set(nodes))
    if len(nodes) > LITERAL_MAX_NODES:
        return [], f"{len(nodes)} symbols hold the literal — too common to anchor (cap {LITERAL_MAX_NODES})"
    return nodes, where


def anchor_pass(L: Ledger, task: str, repo_root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """``(anchors, unresolved, dropped)`` — the matchers in the design's order; every anchor names its matcher;
    *dropped* are the literals over the cap, recorded with their count and anchoring nothing."""
    anchors: list[dict] = []
    dropped: list[dict] = []  # literals over the cap: recorded, anchoring nothing
    bound: set[str] = set()

    def add(term, matcher, nodes, note=None):
        if nodes:
            a = {"term": term, "matcher": matcher, "nodes": sorted(nodes)}
            if note:
                a["note"] = note
            anchors.append(a)
            bound.add(term)
        return bool(nodes)

    # 1. backticked identifiers; a backticked non-identifier is searched as a literal (5)
    backticked: list[str] = []
    for term in _BACKTICK.findall(task):
        term = term.strip()
        backticked.append(term)
        if " " not in term:
            nodes = _resolve_name(L, term)
            if nodes and add(term, "backtick", nodes, None if term in L.mod_path or term in L.symbols else "matched by a name exactly one node carries — confirm"):
                continue
            if add(term, "path", _resolve_path(L, term)):
                continue
        nodes, where = _literal_anchors(L, repo_root, term)
        add(term, "literal", nodes, f"backtick → no node id or basename matches; the literal is at {where}" if nodes else None)
        if not nodes and where:
            dropped.append({"term": term, "matcher": "literal", "nodes": [], "note": where})
        for sub in term.split():
            if sub not in bound and _code_shaped(sub) and not _resolve_name(L, sub):
                nodes, where = _literal_anchors(L, repo_root, sub)
                add(sub, "literal", nodes, f"not an identifier in the graph (see unresolved) but a literal at {where}" if nodes else None)
    # 2. file paths; 3. test ids; 4. stack-trace lines
    for term in _TEST_ID.findall(task):
        term = term.strip()
        hits = [t for t in L.tests if t["id"] == term or t["id"].endswith(term)]
        add(term, "test-id", [t["symbol"] for t in hits if t.get("symbol") in L.symbols])
    for path, ln in _STACK.findall(task):
        if path in L.path_mod:
            add(f"{path}:{ln}", "stack-trace", [L.symbol_at(path, int(ln)) or L.path_mod[path]])
    for term in _PATHISH.findall(task):
        if term not in bound and not any(term in a["term"] for a in anchors):
            add(term, "path", _resolve_path(L, term))
    # 5. quoted strings as literals
    for lit in _QUOTED.findall(task):
        if lit not in bound:
            nodes, where = _literal_anchors(L, repo_root, lit)
            add(lit, "literal", nodes, f"quoted; found at {where}" if nodes else None)
            if not nodes and where:
                dropped.append({"term": lit, "matcher": "literal", "nodes": [], "note": where})
    # 2 again for bare code-shaped tokens that are paths or directories (`hobbes-proxy`, `run-cell.sh`); 6. bare identifiers naming exactly one node
    for tok in sorted(set(_TOKEN.findall(task))):
        tok = tok.rstrip(".,;:")
        if tok in bound or any(tok in a["term"] for a in anchors if a["matcher"] != "bare-identifier"):
            continue
        if _code_shaped(tok) and add(tok, "path", _resolve_path(L, tok)):
            continue
        add(tok, "bare-identifier", _resolve_name(L, tok))
    # the unresolved block: code-shaped tokens no matcher bound as a name
    named = {a["term"] for a in anchors if a["matcher"] != "literal"}
    unresolved = []
    candidates = sorted(set(t.rstrip(".,;:") for t in _TOKEN.findall(task)) | set(backticked))
    for tok in candidates:
        if tok in named or tok in L.mod_path or " " in tok:
            continue
        if not _code_shaped(tok) and tok not in backticked:  # a backticked word is code by the task's own declaration
            continue
        if _resolve_name(L, tok) or _resolve_path(L, tok):
            continue
        unresolved.append({"term": tok, "nearest": L.nearest(tok)})
    return anchors, unresolved, dropped


# ---------------------------------------------------------- structure pass

def _hole(hid, typ, span, prov, cons, **kw):
    h = {"id": hid, "type": typ, "span": span, "constraints": cons, "provenance": prov, "fill_schema": FILL_SHAPES[typ]}
    h.update(kw)
    return h


def _file_length(repo_root: Path, sha: str, path: str) -> int:
    r = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=repo_root, capture_output=True, text=True, check=True)
    return len(r.stdout.splitlines())


def structure_pass(L: Ledger, anchors: list[dict], repo_root: Path, cochange: CoChange | None, new_terms: list[str] = ()) -> tuple[list[dict], dict]:
    """Holes from the anchors, in a stable order; returns ``(holes, constraints)``."""
    test_syms = {t["symbol"] for t in L.tests if t.get("symbol")}
    seeds: set[str] = set()
    literal_tests: set[str] = set()
    for a in anchors:
        if a["matcher"] == "bare-identifier":
            continue  # a round-1 question (ANCHOR_CONFIRM); it joins the structure only once confirmed
        for n in a["nodes"]:
            if n in test_syms:
                literal_tests.add(n)  # a literal inside a test is a reaching test, not interior
            elif n in L.symbols:
                seeds.add(n)
            # a module node seeds nothing (step 6): its symbols are asked as ANCHOR_CONFIRMs in round 1 (`build_template`),
            # and only a confirmed one joins the interior — a whole module as bodies cost 1,068 holes and $5 on one key
    interior = set(seeds)
    for sid in sorted(seeds):
        for e in L.calls_out.get(sid, []):
            interior.add(e["to"])
    files = sorted({L.path_of(i) for i in interior})
    for e in L.graph["symbol_edges"]:  # a type an *anchored* symbol uses, declared in an interior file, is interior too (the struct a flag lands in)
        if e["type"] == "uses" and e["from"] in seeds and e["to"] in L.symbols and L.path_of(e["to"]) in files:
            interior.add(e["to"])
    interior_s = sorted(interior, key=lambda i: (L.path_of(i), L.symbols[i]["line"], i))
    reaching = [t for t in L.tests if set(t.get("reaches", [])) & interior or t.get("symbol") in literal_tests]
    # step 6: a test whose module *imports* an interior file's module guards it too, whether or not the testmap maps a call
    # (`test_containment` reads `PROFILES`, a module-level value: no call site, no reach — and the gold changed those tests)
    interior_modules = {L.path_mod[f] for f in files if f in L.path_mod}
    importing = {t["id"]: sorted(L.imports_of.get(L.path_mod.get(t["file"], ""), set()) & interior_modules) for t in L.tests}
    reaching_ids = {t["id"] for t in reaching}
    importers = [t for t in L.tests if t["id"] not in reaching_ids and importing[t["id"]]]
    guard_files = sorted({t["file"] for t in reaching} | {t["file"] for t in importers})
    partition = sorted(set(files) | set(guard_files))
    cons = {"write_partition": partition}
    holes: list[dict] = []
    n = 0

    def nxt(prefix):
        nonlocal n
        n += 1
        return f"{prefix}{n}"

    anchored_by = {}
    for a in anchors:
        for node in a["nodes"]:
            anchored_by.setdefault(node, a["term"])
    for sid in interior_s:
        s = L.symbols[sid]
        why = anchored_by.get(sid) or next((f"callee of {e['from']} @ {L.path_of(e['from'])}:{e['evidence'][0]['line']} ({e['tier']})" for c in sorted(seeds) for e in L.calls_out.get(c, []) if e["to"] == sid), None) \
            or next((f"used by {e['from']} @ {L.path_of(e['from'])}:{e['evidence'][0]['line']} ({e['tier']})" for e in L.graph["symbol_edges"] if e["type"] == "uses" and e["to"] == sid and e["from"] in interior), "")
        sp = L.span(sid)
        holes.append(_hole(nxt("h"), "SIGNATURE", {"path": sp["path"], "start": sp["start"], "end": sp["start"]}, {"anchor": why, "symbol": sid, "kind": s.get("kind")}, {**cons, "type": s.get("kind")}))
        holes.append(_hole(nxt("h"), "BODY", sp, {"anchor": why, "symbol": sid, "kind": s.get("kind")}, cons))
    uses_in: dict[str, list[dict]] = {}
    for e in L.graph["symbol_edges"]:
        if e["type"] == "uses" and e["to"] in interior and e["from"] in L.symbols and L.symbols[e["to"]].get("kind") not in FUNCTION_KINDS:
            uses_in.setdefault(e["to"], []).append(e)
    seen_callers: set[tuple[str, str]] = set()
    for sid in interior_s:
        incoming = L.calls_in.get(sid, []) + uses_in.get(sid, [])  # a type's users are its callers: they change when its fields do
        for e in sorted(incoming, key=lambda e: (L.path_of(e["from"]), e["from"], e["type"])):
            if e["from"] in interior or (e["from"], sid) in seen_callers:
                continue
            seen_callers.add((e["from"], sid))
            cp = L.path_of(e["from"])
            h = _hole(nxt("h"), "CALLER_UPDATE", L.span(e["from"]), {"callee": sid, "edge": f"{e['from']} {e['type']} {sid} @ {cp}:{e['evidence'][0]['line']}", "tier": e["tier"]}, cons)
            if cp not in partition:
                h["closed"] = {"reason": f"partition: {cp} is outside the write partition"}
            holes.append(h)
    for t in reaching:
        sym = t.get("symbol")
        span = L.span(sym) if sym in L.symbols else {"path": t["file"], "start": t["line"], "end": t["line"]}
        holes.append(_hole(nxt("t"), "TEST_EXPECTATION", span, {"test": t["id"], "reaches": sorted(set(t["reaches"]) & interior)[:4], "tier": "testmap"}, cons))
    for t in importers:
        sym = t.get("symbol")
        span = L.span(sym) if sym in L.symbols else {"path": t["file"], "start": t["line"], "end": t["line"]}
        holes.append(_hole(nxt("t"), "TEST_EXPECTATION", span, {"test": t["id"], "imports": importing[t["id"]][:4], "tier": "import"}, cons))
    for path in files:
        syms = L.by_module[L.path_mod[path]]
        length = _file_length(repo_root, L.sha, path)
        regions = []
        if syms[0]["line"] > 1:
            regions.append((1, syms[0]["line"] - 1, "head", ["(file start)", syms[0]["name"]]))
        for a, b in zip(syms, syms[1:]):
            if b["line"] > a["end_line"] + 1:
                regions.append((a["end_line"] + 1, b["line"] - 1, "gap", [a["name"], b["name"]]))
        if syms[-1]["end_line"] < length:
            regions.append((syms[-1]["end_line"] + 1, length, "tail", [syms[-1]["name"], "(end of file)"]))
        for a, b, kind, between in regions:
            holes.append(_hole(nxt("m"), "MODULE_REGION", {"path": path, "start": a, "end": b}, {"kind": kind, "between": between, "anchor": "interior file"}, cons))
    if cochange is not None:
        partners: dict[str, list[str]] = {}
        for f in files:
            for p, k in cochange.partners(f, PARTNER_MIN):
                if p not in partition:
                    partners.setdefault(p, []).append(f"{Path(f).name} ×{k}")
        for p in sorted(partners):
            holes.append(_hole(nxt("x"), "COCHANGE_TOUCH", None, {"cochange": f"co-committed with {', '.join(partners[p])} in the window", "partner": p},
                               {**cons, "note": "outside the write partition unless you say why it must move"}, ask=f"is `{p}` touched by this change; why"))
    for term in new_terms:
        holes.append(_hole(nxt("n"), "NEW_SYMBOL", None, {"anchor": f"UNRESOLVED: `{term}` declared new"}, cons,
                           ask=f"where does the new thing `{term}` go — a new top-level symbol (name, file, position, body), or covered by another hole's fill?"))
    holes.append(_hole(nxt("f"), "FREEFORM", None, {"anchor": "none"}, cons, ask="anything the template did not anticipate"))
    return holes, cons


# ---------------------------------------------------------------- template

#: The file listing in an ``ANCHOR`` hole's candidates stops here; past it, directories only (a repo this big is not this experiment's).
CANDIDATE_FILES_MAX = 1500


def anchor_candidates(L: Ledger, task: str, unresolved: list[dict], refused: set[str] = frozenset()) -> dict:
    """What Hobbes can offer an anchorless task to choose among — never a guess, always what the ledger holds:
    ``lexical`` (the planner's seed resolver over the task, C-36: node, path, the word that seeded it, and whether round 1
    already refused that word), ``nearest`` (each unresolved term's nearest graph names with their node ids), and ``files``
    (every module path in the ledger, grouped by top-level directory; directories alone past ``CANDIDATE_FILES_MAX``)."""
    from hobbes.derive.impact import filter_seeds, resolve_seeds
    seeds, _ = resolve_seeds(L.graph, task, [], lexical=True)
    kept, _ = filter_seeds(L.graph, task, seeds, [])
    lexical = []
    for node, term in sorted(kept.items()):
        row = {"node": node, "path": L.mod_path.get(node) or (L.path_of(node) if node in L.symbols else None), "term": term}
        if term in refused or term.lower() in {r.lower() for r in refused}:
            row["refused"] = True
        lexical.append(row)
    nearest = []
    for u in unresolved:
        names = [{"name": n, "nodes": sorted(L.by_name.get(n, []))[:3]} for n in u["nearest"]]
        nearest.append({"term": u["term"], "names": names})
    paths = sorted(L.mod_path.values())
    by_dir: dict[str, list[str]] = {}
    for p in paths:
        by_dir.setdefault(p.split("/", 1)[0] if "/" in p else ".", []).append(p)
    files = {"n": len(paths), "by_dir": by_dir if len(paths) <= CANDIDATE_FILES_MAX else {}}
    if len(paths) > CANDIDATE_FILES_MAX:
        dirs: dict[str, int] = {}
        for p in paths:
            d = "/".join(p.split("/")[:2]) if p.count("/") >= 2 else (p.rsplit("/", 1)[0] if "/" in p else ".")
            dirs[d] = dirs.get(d, 0) + 1
        files["dirs"] = dirs
    return {"lexical": lexical, "nearest": nearest, "files": files}


def build_template(task: str, L: Ledger, repo_root: Path, cochange: CoChange | None = None, *,
                   extra_anchors: list[dict] = (), drop_terms: set[str] = frozenset(), new_terms: list[str] = ()) -> dict:
    """The template for *task* at the ledger's SHA; deterministic in its inputs."""
    anchors, unresolved, dropped = anchor_pass(L, task, repo_root)
    anchors = [a for a in anchors if a["term"] not in drop_terms] + [a for a in extra_anchors if a["term"] not in drop_terms or a.get("note", "").startswith("confirmed")]
    round1: list[dict] = []
    if unresolved:
        round1.append(_hole("u1", "UNRESOLVED", None, {"anchor": "the task's code-shaped tokens no matcher bound"}, {}, ask="classify each unresolved term",
                            terms=[dict(u) for u in unresolved]))
    confirmable = [a for a in anchors if a["matcher"] == "bare-identifier" or (a["matcher"] == "backtick" and a.get("note", "").startswith("matched by a name"))]
    i = 0
    for a in confirmable:
        nodes = [n for n in a["nodes"] if n not in L.mod_path]  # a module node is asked symbol by symbol below, never as a whole
        if not nodes:
            continue
        i += 1
        round1.append(_hole(f"c{i}", "ANCHOR_CONFIRM", None, {"anchor": a["term"], "matcher": a["matcher"]}, {},
                            ask=f"is `{', '.join(nodes)}` (matched by the {'bare word' if a['matcher'] == 'bare-identifier' else 'backticked name'} '{a['term']}') a site this task concerns?"))
    # step 6: an anchor that names a *module* (a bare word, a backticked file, an ANCHOR answer) opens one ANCHOR_CONFIRM per
    # symbol of the module, each with its span — confirmations, not bodies; an unanswered confirmation is a refusal (`run_t`)
    for a in anchors:
        for mod in [n for n in a["nodes"] if n in L.mod_path]:
            for sym in L.by_module.get(mod, []):
                i += 1
                sp = L.span(sym["id"])
                round1.append(_hole(f"c{i}", "ANCHOR_CONFIRM", sp, {"anchor": a["term"], "matcher": a["matcher"], "module": mod, "symbol": sym["id"], "kind": sym.get("kind")}, {},
                                    ask=f"is `{sym['id']}` (a {sym.get('kind') or 'symbol'} in `{sp['path']}`, the module the task names as '{a['term']}') a site this task concerns? answer only if yes; unanswered is no"))
    if anchors:
        holes, cons = structure_pass(L, anchors, repo_root, cochange, new_terms)
    else:
        # No anchor at all — at build time, or after round 1 refused every bare-word match (the step-4 reading: a FREEFORM-only
        # template shows the orchestrator no code, and "none" is its only honest answer): ask which symbols or files the task concerns.
        cons = {"write_partition": []}
        holes = [_hole("a1", "ANCHOR", None, {"anchor": "nothing in the task names repo structure" if not drop_terms else "round 1 confirmed no anchor"}, {},
                       ask="which symbols or files does this task concern? (exact symbol ids, names or paths from the repo — the candidates below, or others that exist)",
                       candidates=anchor_candidates(L, task, unresolved, drop_terms))]
        holes.append(_hole("f1", "FREEFORM", None, {"anchor": "none"}, cons, ask="anything the template did not anticipate"))
    t = {
        "template_version": TEMPLATE_VERSION,
        "key": {"parent_sha": L.sha, "task_hash": task_hash(task), "template_version": TEMPLATE_VERSION},
        "task": task,
        "ledger": {"sha": L.sha, "built_by": L.graph.get("built_by", {}).get("sha"), "schema_version": L.graph.get("schema_version"),
                   "containment": "all_contained" if L.graph.get("containment", {}).get("all_contained") else "not all contained"},
        "anchors": anchors,
        "anchors_dropped": dropped,
        "unresolved": unresolved,
        "holes": round1 + holes,
        "constraints": cons,
        "pruning_rules": ["a function SIGNATURE = unchanged closes that symbol's CALLER_UPDATEs (functions only)",
                          "a caller outside the write partition is closed with reason partition",
                          "MODULE_REGION = unchanged is dropped from the diff",
                          "pattern fills accepted for CALLER_UPDATE, MODULE_REGION, TEST_EXPECTATION, COCHANGE_TOUCH"],
    }
    t["template_hash"] = hashlib.sha256(canonical(t).encode()).hexdigest()[:16]
    return t


def canonical(t: dict) -> str:
    return json.dumps({k: v for k, v in t.items() if k != "template_hash"}, sort_keys=True, separators=(",", ":"))


def apply_round1(task: str, L: Ledger, repo_root: Path, cochange: CoChange | None, template: dict, fills: dict) -> dict:
    """Rebuild from the round-1 answers: ``refers`` → anchors, ``new`` → NEW_SYMBOL holes, a refused ANCHOR_CONFIRM → its anchor dropped."""
    extra, drop, new = [], set(), []
    for h in template["holes"]:
        f = fills.get(h["id"])
        if f is None:
            continue
        if h["type"] == "UNRESOLVED":
            for term, cls in sorted(f["classes"].items()):
                if cls == "new":
                    new.append(term)
                elif cls == "refers":
                    node = f["refers_to"][term]
                    if node in L.symbols or node in L.mod_path:
                        extra.append({"term": term, "matcher": "backtick", "nodes": [node], "note": "the orchestrator's refers answer"})
        elif h["type"] == "ANCHOR_CONFIRM":
            term = h["provenance"]["anchor"]
            drop.add(term)
            if f.get("confirm") is True:
                if h["provenance"].get("symbol"):  # one symbol of a named module: it alone joins, as its own anchor
                    extra.append({"term": h["provenance"]["symbol"], "matcher": "backtick", "nodes": [f["alternative"]] if f.get("alternative") else [h["provenance"]["symbol"]],
                                  "note": f"confirmed by the orchestrator (a symbol of `{h['provenance']['module']}`, named by '{term}')"})
                else:
                    a = next(a for a in template["anchors"] if a["term"] == term)
                    extra.append({"term": term, "matcher": "backtick", "nodes": [f["alternative"]] if f.get("alternative") else [n for n in a["nodes"] if n not in L.mod_path], "note": "confirmed by the orchestrator"})
        elif h["type"] == "ANCHOR":  # names the orchestrator gives for an anchorless task: bound exactly as a backticked term would be, or not at all
            for name in f.get("names") or []:
                nodes = _resolve_name(L, name) or _resolve_path(L, name)
                if nodes:
                    extra.append({"term": name, "matcher": "backtick", "nodes": nodes, "note": "the orchestrator's ANCHOR answer"})
    return build_template(task, L, repo_root, cochange, extra_anchors=extra, drop_terms=drop, new_terms=new)


def prune(template: dict, fills: dict) -> list[str]:
    """Close holes the fills make structural: a function SIGNATURE unchanged closes its CALLER_UPDATEs; a region unchanged is dropped. Returns the closed ids."""
    closed = []
    unchanged_fns = {h["provenance"]["symbol"] for h in template["holes"]
                     if h["type"] == "SIGNATURE" and fills.get(h["id"]) == "unchanged" and h["provenance"].get("kind") in FUNCTION_KINDS}
    for h in template["holes"]:
        if h.get("closed") is not None:
            continue
        if h["type"] == "CALLER_UPDATE" and h["provenance"].get("callee") in unchanged_fns:
            h["closed"] = {"reason": f"signature of {h['provenance']['callee']} unchanged"}
            closed.append(h["id"])
        elif h["type"] == "MODULE_REGION" and fills.get(h["id"]) == "unchanged":
            h["closed"] = {"reason": "unchanged"}
            closed.append(h["id"])
    return closed


# ------------------------------------------------------------------ scoring

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)  # the pre-image side: the parent SHA is exactly the pre-image
SYMBOL_TYPES = ("SIGNATURE", "BODY", "CALLER_UPDATE", "TEST_EXPECTATION")


def score_coverage(template: dict, gold: list[tuple[str, str]]) -> dict:
    """§4.1: every gold hunk in one of four buckets — ``symbol``, ``region``, ``new_file``, ``outside``."""
    spans = [(h["span"], h["type"]) for h in template["holes"] if h.get("span")]
    out = {"symbol": 0, "region": 0, "new_file": 0, "outside": 0, "hunks": 0}
    for path, diff in gold:
        new = "new file mode" in diff
        for m in _HUNK.finditer(diff):
            st = int(m.group(1)); n = int(m.group(2) or 1); en = st + max(n, 1) - 1
            out["hunks"] += 1
            if new:
                out["new_file"] += 1
                continue
            hit = [typ for sp, typ in spans if sp["path"] == path and sp["start"] <= en and st <= sp["end"]]
            if any(t in SYMBOL_TYPES for t in hit):
                out["symbol"] += 1
            elif "MODULE_REGION" in hit:
                out["region"] += 1
            else:
                out["outside"] += 1
    return out


def score_anchors(template: dict, L: Ledger, gold: list[tuple[str, str]]) -> dict:
    """§4.2 at file grain and symbol grain, per matcher: anchors vs. the files and symbols the gold diff touches at the parent."""
    gold_files = {p for p, _ in gold}
    gold_syms: set[str] = set()
    for path, diff in gold:
        for m in _HUNK.finditer(diff):
            st = int(m.group(1)); n = int(m.group(2) or 1)
            for ln in range(st, st + max(n, 1)):
                s = L.symbol_at(path, ln)
                if s:
                    gold_syms.add(s)
    per: dict[str, dict] = {}
    afiles, asyms = set(), set()
    for a in template["anchors"]:
        row = per.setdefault(a["matcher"], {"anchors": 0, "file_hits": 0, "symbol_hits": 0})
        for node in a["nodes"]:
            row["anchors"] += 1
            f = L.path_of(node) if node in L.symbols else L.mod_path.get(node)
            afiles.add(f)
            row["file_hits"] += f in gold_files
            if node in L.symbols:
                asyms.add(node)
                row["symbol_hits"] += node in gold_syms
    return {"per_matcher": per, "files": {"tp": len(afiles & gold_files), "anchored": len(afiles), "gold": len(gold_files)},
            "symbols": {"tp": len(asyms & gold_syms), "anchored": len(asyms), "gold": len(gold_syms)},
            "unresolved": len(template["unresolved"]), "zero_anchor": not template["anchors"]}
