"""`hobbes gate` — the linker on a finished diff (`docs/calvin/calvin-m0-gate.md` §2.2, §0b).

One deterministic pass, no model, over a unified diff at its parent SHA:

1. **Grounder v3** (`hobbes.derive.ground`) on every reference in the added and changed lines. The diff is read through a
   one-hole template (`gate_template`: a single ``FREEFORM`` hole), so every change block is a FREEFORM entry at its own
   pre-image span: the gate needs no task, no anchor and no template of the unit, and it declares nothing — a finished diff
   declares a name by writing its declaration, which grounds as a gensym (`NEW_RULE`).
2. **The complement split** against the unit's blind-spot map (§0b's schema, `validate_map`): a NULL keeps its class when its
   site lies in a captured region, and a name-absence NULL in a blind spot becomes ``unknown`` with the map's reason
   (`LOOKUP_RULE`).
3. **The partition check** at file grain: every file the diff touches against the unit's write partition, a ``partition`` row
   per file outside it, at any HSR (`PARTITION_RULE`).
4. **The verdict** (`VERDICT_RULE`): *clear* when no class of `BLOCKING` fires, else *blocked* with the class list;
   ``unknown`` is advisory and ``new`` is routed — neither blocks, neither is dropped.

The diff is also applied at the parent in a scratch directory (``git apply``): a diff that does not apply is ``malformed``, and
the applied post-images are held against the grounder's own reading of the diff (``integrity``), so a gate that read the diff
wrong says so rather than judging a text nobody wrote.

The record (`gate`) is stamped with the gate's, the grounder's and Hobbes' versions and the sha256 of every input
(`input_hashes`); it holds no path of this machine and no clock, so a rerun writes the same bytes (`dumps`). `repair_message`
renders a blocked record as the one message of calvin-m0-gate §2.3's repair turn. Concessions: C-121 (``unknown`` advisory),
C-122 (the partition at file grain), C-123 (the map's grain and the split's classes).
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from hobbes import __version__
from hobbes.derive import ground as G
from hobbes.derive.template import Ledger
from hobbes.extract.tail import language_of

GATE_VERSION = 1
#: calvin-m0-gate §6: the classes that block, in the order a record and a repair message list them.
BLOCKING = ("invented", "near-miss", "arity", "undeclared-type", "import-outside", "unimported", "malformed", "partition")
#: Reported, never blocking this round (§2.2 step 4; C-121).
ADVISORY = ("unknown",)
#: Neither blocking nor advisory: a reading the orchestrator must see (`NEW_RULE`).
ROUTED = ("new",)
GATE_CLASSES = BLOCKING + ADVISORY + ROUTED
#: The NULL classes the complement split may turn into ``unknown``: a name absent from the parent graph where the reference binds,
#: which a region lane B did not capture can hide. The others are read from source at the SHA (`LOOKUP_RULE`).
SPLIT_CLASSES = ("invented", "near-miss")
#: A blind-spot map's reasons (§0b); ``oracle-miss:<class>`` besides.
MAP_REASONS = ("uncaptured-file", "dynamic-dispatch", "laneb-miss")
ORACLE_MISS = "oracle-miss:"
#: The gate's own reason for a site in a file the map does not list (a file outside the partition).
UNMAPPED = "unmapped"
#: The partition check's three readings (`PARTITION_RULE`): no allowance; test support exempt; the reach (the default, D-s).
PARTITION_RULES = ("strict", "exempt", "reach")

LOOKUP_RULE = (
    "A NULL's site is where its reference is written. A reference on an added line takes its parent anchor from the run of its hunk: in a "
    "run that replaces parent lines, the i-th added line anchors at the i-th replaced line (the run's last replaced line past its end); in a "
    "pure insertion before parent line p, at the insertion point between p-1 and p. The site is, in order: a map `sites` row whose `line` is "
    "the anchor's parent line (a line-grain row, a replacing run only); the innermost symbol of the map's `symbols` for that file whose span "
    "holds the anchor (an insertion point is held only when both p-1 and p are); else the file's own `files` entry. A file absent at the "
    "parent, or renamed, is read at its `files` entry, else — a code file created beside the partition, which no map lists — at its "
    "directory's partition files (a blind spot when any of them is); any other file the map does not list (outside the partition) is "
    "`unmapped`. A site is a blind "
    "spot when its entry reads captured false (a line-grain `sites` row always does), or it is unmapped. A `sites` row with `line: null` — a "
    "file's count of unresolved call sites by tail class — never routes: it is carried as `map.unresolved_by_file`, context only. In a blind "
    "spot only invented and near-miss become `unknown` (a name absent from the parent graph, which a region lane B did not capture can hide); "
    "arity, undeclared-type, import-outside and unimported are read from source at the SHA (the callee's declaration, the package's files, the "
    "go.mod, the file's imports), which a blind spot does not hide, and stand wherever they sit. Every NULL row carries its site.")
PARTITION_RULE = (
    "File grain (calvin-m0-gate §0b: the partition is template v2's `constraints.write_partition`, a file list). Every file the diff "
    "touches (both sides of a rename, a created file, a deleted file) is judged against the partition; a file not in it is one "
    "`partition` row whatever the HSR (round 2's stricter parse), under the record's `rule`. `reach` (the default, D-s): the gate judges the "
    "world Hobbes has, which is ingested code, so two writes are listed, never blocked — a file no lane-A provider reads as code "
    "(`tail.language_of` is None: docs, man pages, build files, a language Hobbes does not ground), which is beyond the graph, and a code file "
    "the diff creates in a directory that holds a partition file, the declare class a template partition cannot name before it exists — "
    "plus `exempt`'s allowance; a write into an existing code file outside the partition blocks. `exempt`: a test-support path "
    "(`harness.is_test_support_path`: a test file itself, or a path under `testdata/`, `__fixtures__/`, `__snapshots__/`) — a test, or a "
    "fixture a test beside it reads, which the template's partition lists only where the testmap reaches it. `strict`: no allowance. Every "
    "allowance is listed on its file (`exempt`, `reach`). With no partition given the check is not run, and the record says so.")
VERDICT_RULE = (
    "clear iff no blocking class fires: invented, near-miss, arity, undeclared-type, import-outside, unimported, malformed (a post-image "
    "carrying the render's gutter, or a diff that does not apply at the parent), partition. `unknown` is reported and never blocks "
    "(calvin-m0-gate §2.2 step 4). `new` is routed (the new rule).")
NEW_RULE = (
    "Grounder v3's `new` means a template fill declared the name new (an UNRESOLVED answer, a NEW_SYMBOL hole) before declaring it. The gate "
    "reads a finished diff through a one-FREEFORM-hole template, which declares nothing, so `new` cannot arise from a diff: a name the diff "
    "declares by writing it grounds as a gensym, and one it uses without declaring is invented or near-miss. A `new` row at the gate is a "
    "defect of the gate's reading, never a verdict on the diff: listed, counted, blocking nothing, and `route` set for the orchestrator.")

_HEAD = re.compile(r"^diff --git a/(.*?) b/(.*?)$", re.M)


# ------------------------------------------------------------------ inputs

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogateescape")


def input_hashes(diff: str, graph_path: Path, tests_path: Path | None, partition: list[str] | None, bmap: dict | None) -> dict:
    """The sha256 of every input the record rests on: the diff's bytes, the graph's and tests' files, the partition and the map as
    canonical JSON (the same content hashes alike whether it came from a file or a unit row). No path is recorded."""
    return {"diff": _sha256(diff.encode("utf-8", "surrogateescape")),
            "graph": _sha256(Path(graph_path).read_bytes()),
            "tests": _sha256(Path(tests_path).read_bytes()) if tests_path is not None and Path(tests_path).exists() else None,
            "partition": None if partition is None else _sha256(_canonical(sorted(set(partition)))),
            "map": None if bmap is None else _sha256(_canonical(bmap))}


def load_partition(path: Path) -> tuple[list[str], str]:
    """A partition file: a JSON list of paths, a JSON object carrying ``partition`` or ``write_partition`` (a unit row, a blind-spot
    map) or a template (``constraints.write_partition``), else one path per line. Returns the paths and the shape it was read as."""
    text = Path(path).read_text()
    try:
        obj = json.loads(text)
    except ValueError:
        return [l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")], "lines"
    if isinstance(obj, list):
        return [str(p) for p in obj], "list"
    if isinstance(obj, dict):
        for k in ("partition", "write_partition"):
            if isinstance(obj.get(k), list):
                return [str(p) for p in obj[k]], k
        wp = (obj.get("constraints") or {}).get("write_partition")
        if isinstance(wp, list):
            return [str(p) for p in wp], "template"
    raise ValueError(f"{path}: no partition in it (a JSON list, {{partition: [...]}}, a template, or one path per line)")


def load_map(path: Path) -> dict:
    """A blind-spot map file (§0b's schema), or a unit row carrying it as ``blind_spot_map``."""
    obj = json.loads(Path(path).read_text())
    if isinstance(obj, dict) and isinstance(obj.get("blind_spot_map"), dict):
        return obj["blind_spot_map"]
    return obj


def _reason_ok(reason) -> bool:
    return reason in MAP_REASONS or (isinstance(reason, str) and reason.startswith(ORACLE_MISS) and len(reason) > len(ORACLE_MISS))


def validate_map(bmap) -> list[str]:
    """Every defect of a blind-spot map against §0b's schema; an empty list is a map the gate reads. The gate refuses a defective
    map rather than read a guess into the split."""
    if not isinstance(bmap, dict):
        return ["the map is not a JSON object"]
    errs: list[str] = []
    for k in ("partition", "files", "symbols"):
        if not isinstance(bmap.get(k), list):
            errs.append(f"`{k}` must be a list")
    if errs:
        return errs
    paths = set()
    for i, f in enumerate(bmap["files"]):
        if not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("captured"), bool)):
            errs.append(f"files[{i}]: needs path (str) and captured (bool)")
            continue
        paths.add(f["path"])
        if not f["captured"] and not _reason_ok(f.get("reason")):
            errs.append(f"files[{i}] {f['path']}: uncaptured with reason {f.get('reason')!r}, not one of {MAP_REASONS} or {ORACLE_MISS}<class>")
    for i, s in enumerate(bmap["symbols"]):
        if not (isinstance(s, dict) and isinstance(s.get("id"), str) and isinstance(s.get("path"), str) and isinstance(s.get("start"), int)
                and isinstance(s.get("end"), int) and s["start"] <= s["end"] and isinstance(s.get("captured"), bool)):
            errs.append(f"symbols[{i}]: needs id, path, start <= end (ints) and captured (bool)")
            continue
        if not s["captured"] and not _reason_ok(s.get("reason")):
            errs.append(f"symbols[{i}] {s['id']}: uncaptured with reason {s.get('reason')!r}")
    sites = bmap.get("sites", [])
    if not isinstance(sites, list):
        errs.append("`sites` must be a list when present")
        sites = []
    for i, s in enumerate(sites):
        if not (isinstance(s, dict) and isinstance(s.get("path"), str) and (s.get("line") is None or isinstance(s.get("line"), int))):
            errs.append(f"sites[{i}]: needs path (str) and line (int, or null for a file-grain count)")
        elif isinstance(s.get("line"), int) and not _reason_ok(s.get("reason")):
            errs.append(f"sites[{i}] {s['path']}:{s['line']}: a line-grain site routes a NULL to unknown and needs a reason, not {s.get('reason')!r}")
    missing = sorted(set(map(str, bmap["partition"])) - paths)
    if missing:
        errs.append(f"`files` must cover every partition file; missing {missing}")
    return errs


# -------------------------------------------------------------- the diff

def file_sections(diff: str) -> list[dict]:
    """Every file a unified diff touches: its pre-image path ``a`` (None when created), post-image path ``b`` (None when deleted),
    the path the grounder reads it under, its text, and whether it is created, deleted, renamed or binary."""
    heads = list(_HEAD.finditer(diff))
    out = []
    for i, m in enumerate(heads):
        text = diff[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(diff)]
        a, b = m.group(1), m.group(2)
        ren_from = re.search(r"^rename from (.+)$", text, re.M)
        ren_to = re.search(r"^rename to (.+)$", text, re.M)
        if ren_from and ren_to:
            a, b = ren_from.group(1), ren_to.group(1)
        created = "\n--- /dev/null" in text or "\nnew file mode" in text
        deleted = "\n+++ /dev/null" in text or "\ndeleted file mode" in text
        out.append({"a": None if created else a, "b": None if deleted else b, "path": a if deleted else b, "text": text,
                    "created": created, "deleted": deleted, "renamed": bool(ren_from and ren_to),
                    "binary": "\nBinary files " in text or "\nGIT binary patch" in text})
    return out


def post_anchors(text: str) -> dict[int, tuple[str, int]]:
    """For one file's diff, each added line's post-image number → its parent anchor: ``("replace", parent line)`` in a run that
    replaces parent lines (the i-th added line at the i-th replaced line, the run's last past its end), ``("insert", p)`` in a
    pure insertion before parent line p (`LOOKUP_RULE`)."""
    out: dict[int, tuple[str, int]] = {}
    o = n = None
    dels: list[int] = []
    adds: list[int] = []
    at: int | None = None

    def flush():
        nonlocal dels, adds, at
        for i, pl in enumerate(adds):
            out[pl] = ("replace", dels[min(i, len(dels) - 1)]) if dels else ("insert", at)
        dels, adds, at = [], [], None

    for line in text.split("\n"):
        m = G._HUNK.match(line)
        if m:
            flush()
            o = int(m.group(1)) + (1 if m.group(2) == "0" else 0)  # an empty old side names the line *before* the insertion
            n = int(m.group(3))
            continue
        if o is None or line.startswith("\\"):
            continue
        if line.startswith("-"):
            if adds:
                flush()
            dels.append(o)
            o += 1
        elif line.startswith("+"):
            if at is None and not dels:
                at = o
            adds.append(n)
            n += 1
        elif line.startswith(" "):
            flush()
            o += 1
            n += 1
    flush()
    return out


def apply_at(repo_root: Path, sha: str, diff: str, sections: list[dict]) -> tuple[bool, str, dict[str, str | None]]:
    """Whether *diff* applies to the parent's pre-images, by ``git apply`` in a scratch directory holding only those files (the
    repo is read through ``git show``, never checked out); on success, every post-image the diff leaves, by path."""
    with tempfile.TemporaryDirectory(prefix="hobbes-gate-") as d:
        for s in sections:
            if s["a"] is None:
                continue
            r = subprocess.run(["git", "show", f"{sha}:{s['a']}"], cwd=repo_root, capture_output=True)
            if r.returncode == 0:
                p = Path(d) / s["a"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(r.stdout)
        env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        env["GIT_CEILING_DIRECTORIES"] = str(Path(d).parent)  # the scratch dir is no repo; never find one above it
        r = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=d, input=diff.encode("utf-8", "surrogateescape"),
                           capture_output=True, env=env)
        if r.returncode:
            return False, r.stderr.decode(errors="replace").strip()[:400], {}
        post: dict[str, str | None] = {}
        for s in sections:
            if s["b"] is None or s["binary"]:
                continue
            p = Path(d) / s["b"]
            post[s["b"]] = p.read_bytes().decode("utf-8", "surrogateescape") if p.exists() else None
        return True, "", post


def gate_template(parent_sha: str, partition: list[str]) -> dict:
    """The one-hole template the gate reads a diff through: a single FREEFORM hole, so every change block is placed at its own span
    and nothing is declared new; the partition rides as the template's ``write_partition``."""
    return {"key": {"parent_sha": parent_sha, "task_hash": "gate"}, "template_version": 0,
            "holes": [{"id": "F1", "type": "FREEFORM", "provenance": {}}], "constraints": {"write_partition": sorted(set(partition))}}


# ------------------------------------------------------------ the split

def _innermost(syms: list[dict], anchor: tuple[str, int]) -> dict | None:
    kind, line = anchor
    if kind == "replace":
        hits = [s for s in syms if s["start"] <= line <= s["end"]]
    else:
        hits = [s for s in syms if s["start"] <= line - 1 and line <= s["end"]]
    return min(hits, key=lambda s: (s["end"] - s["start"], s["start"], s["id"])) if hits else None


def site_of(path: str, line: int, anchors: dict[int, tuple[str, int]], files: dict[str, dict], symbols: dict[str, list[dict]],
            whole_file: bool, sites: dict[str, list[dict]] | None = None) -> dict:
    """The map's statement for a reference at post-image ``path:line`` (`LOOKUP_RULE`): a line-grain ``sites`` row at its parent line,
    else the innermost symbol holding its parent anchor, else its file's entry, else ``unmapped``. *whole_file* — a file the parent
    lacks, or a rename — reads the file entry. A ``sites`` row with ``line: null`` never decides."""
    fe = files.get(path)
    if fe is None:
        return {"grain": "file", "id": path, "captured": False, "reason": UNMAPPED, "detail": "the map lists the partition's files; this one is outside it",
                "anchor": None}
    anchor = None if whole_file else anchors.get(line)
    if anchor is not None and anchor[0] == "replace":
        hit = next((s for s in (sites or {}).get(path, []) if isinstance(s.get("line"), int) and s["line"] == anchor[1]), None)
        if hit is not None:
            return {"grain": "site", "id": f"{path}:{hit['line']}", "captured": False, "reason": hit.get("reason"), "detail": hit.get("detail") or "",
                    "anchor": list(anchor)}
    if anchor is not None:
        s = _innermost(symbols.get(path, []), anchor)
        if s is not None:
            return {"grain": "symbol", "id": s["id"], "captured": s["captured"], "reason": None if s["captured"] else s.get("reason"),
                    "detail": s.get("detail") or "", "anchor": list(anchor)}
    return {"grain": "file", "id": path, "captured": fe["captured"], "reason": None if fe["captured"] else fe.get("reason"),
            "detail": fe.get("detail") or "", "anchor": None if anchor is None else list(anchor)}


# -------------------------------------------------------------- the gate

def _unresolved_by_file(sites: dict[str, list[dict]], touched: list[str]) -> dict:
    """Context, never a routing: for each file the diff touches, the map's file-grain ``sites`` rows (``line: null``) summed by tail class."""
    out: dict = {}
    for p in touched:
        c: collections.Counter = collections.Counter()
        for s in sites.get(p, []):
            if s.get("line") is None:
                c[str(s.get("class") or "unclassed")] += int(s.get("count") or 1)
        if c:
            out[p] = dict(sorted(c.items()))
    return out


def _row(cls: str, grounder_class: str | None, path: str | None, line: int, term: str, kind: str, reason: str | None,
         nearest: list | None = None, scope: dict | None = None, site: dict | None = None) -> dict:
    return {"class": cls, "grounder_class": grounder_class, "path": path, "line": line, "term": term, "kind": kind, "reason": reason,
            "nearest": list(nearest or []), "scope": scope, "site": site}


def _siblings(rows: list[dict], L: Ledger, repo_root: Path) -> list[dict]:
    """A declaration's form for each blocked name the grounder scoped to a directory (Go): one existing declaration of the same kind
    where the name binds (`adapter.declaration_sibling`, protocol v0.6's rule), for the repair message."""
    from hobbes.derive.adapter import declaration_sibling
    out: list[dict] = []
    seen: set = set()
    degree = None
    for r in rows:
        sc = r.get("scope") or {}
        if r["class"] not in ("invented", "near-miss") or sc.get("dir") is None:
            continue
        key = (sc["dir"], sc.get("type"))
        if key in seen:
            continue
        seen.add(key)
        if degree is None:
            degree = G.density_table(L.graph)["degree"]
        sib = declaration_sibling({"dir": key[0], "type": key[1]}, {"hole": "", "path": r["path"], "line": r["line"]}, {"refs": []}, L, repo_root, degree)
        if sib is not None:
            out.append({"for": r["term"], "dir": key[0], "type": key[1], **sib})
    return out


def gate(diff: str, parent_sha: str, repo_root: Path, L: Ledger, *, inputs: dict, partition: list[str] | None = None,
         partition_source: str | None = None, bmap: dict | None = None, partition_rule: str = "reach") -> dict:
    """The gate over *diff* at *parent_sha* (the module doc's four steps): the record, deterministic in its inputs.

    *L* is the ledger of the parent graph (its SHA must be *parent_sha*); *partition* the unit's write partition (None: the check
    is not run), read under *partition_rule* (one of `PARTITION_RULES`); *bmap* the unit's blind-spot map (None: the split is not
    run, every class stands); *inputs* from `input_hashes`. Raises ValueError on a ledger at another SHA, an unknown rule, or a map
    `validate_map` refuses."""
    from hobbes.derive.harness import is_test_support_path
    repo_root = Path(repo_root)
    if partition_rule not in PARTITION_RULES:
        raise ValueError(f"partition rule {partition_rule!r} is not one of {PARTITION_RULES}")
    if L.sha != parent_sha:
        raise ValueError(f"the graph is at {L.sha[:12]}, the parent is {parent_sha[:12]}")
    if bmap is not None:
        errs = validate_map(bmap)
        if errs:
            raise ValueError("the blind-spot map is refused: " + "; ".join(errs))
    part = None if partition is None else sorted(set(partition))
    sections = file_sections(diff)
    ok, err, applied = apply_at(repo_root, parent_sha, diff, sections) if sections else (True, "", {})
    t = gate_template(parent_sha, part or [])
    doc, attribution = G.fills_from_diff(copy.deepcopy(t), [(s["path"], s["text"]) for s in sections if not s["binary"]], repo_root)
    g = G.ground(copy.deepcopy(t), doc, L, repo_root)
    anchors = {s["path"]: post_anchors(s["text"]) for s in sections if not s["binary"]}
    whole = {s["path"] for s in sections if s["created"] or s["renamed"]}
    mfiles = {} if bmap is None else {f["path"]: f for f in bmap["files"]}
    for p in sorted(whole):  # a code file created beside the partition: no map lists it; its directory's partition files speak for it
        if bmap is not None and p not in mfiles:
            beside = [f for f in bmap["files"] if str(PurePosixPath(f["path"]).parent) == str(PurePosixPath(p).parent)]
            if beside:
                blind = next((f for f in beside if not f["captured"]), None)
                mfiles[p] = {"path": p, "captured": blind is None, "reason": None if blind is None else blind.get("reason"),
                             "detail": "a created file, read at its directory's partition files"
                                       + ("" if blind is None else f" ({blind['path']}: {blind.get('detail') or blind.get('reason')})")}
    msyms: dict[str, list[dict]] = collections.defaultdict(list)
    for s in [] if bmap is None else bmap["symbols"]:
        msyms[s["path"]].append(s)
    msites: dict[str, list[dict]] = collections.defaultdict(list)
    for s in [] if bmap is None else (bmap.get("sites") or []):
        msites[s["path"]].append(s)

    rows: list[dict] = []
    for n in g["null"]:
        cls = n["null_class"]
        site = None if bmap is None else site_of(n["path"], n["line"], anchors.get(n["path"], {}), mfiles, msyms, n["path"] in whole, msites)
        gc = cls if cls in ROUTED or site is None or site["captured"] or cls not in SPLIT_CLASSES else "unknown"
        rows.append(_row(gc, cls, n["path"], n["line"], n["term"], n.get("kind", "call"), n.get("reason"), n.get("nearest"), n.get("scope"), site))
    for r in g["refs"]:
        if r["class"] == "malformed":
            rows.append(_row("malformed", "malformed", r["path"], 0, "", "file", r.get("reason")))
    if sections and not ok:
        rows.append(_row("malformed", None, None, 0, "", "diff", f"the diff does not apply at {parent_sha[:12]}: {err}"))

    touched = sorted({p for s in sections for p in (s["a"], s["b"]) if p})
    pfiles: list[dict] = []
    if part is not None:
        pset = set(part)
        pdirs = {str(PurePosixPath(q).parent) for q in pset}
        for p in touched:
            sec = next(s for s in sections if p in (s["a"], s["b"]))
            created, deleted = sec["created"] and p == sec["b"], sec["deleted"] and p == sec["a"]
            inp = p in pset
            exempt = not inp and partition_rule != "strict" and is_test_support_path(p)
            reach = None
            if not inp and not exempt and partition_rule == "reach":
                if language_of(p) is None:
                    reach = "not-code"
                elif created and str(PurePosixPath(p).parent) in pdirs:
                    reach = "beside-partition"
            pfiles.append({"path": p, "in_partition": inp, "exempt": exempt, "reach": reach, "created": created, "deleted": deleted})
            if not inp and not exempt and reach is None:
                rows.append(_row("partition", None, p, 0, "", "file",
                                 "outside the unit's write partition" + (" (created)" if created else " (deleted)" if deleted else "")))
    rows.sort(key=lambda r: (GATE_CLASSES.index(r["class"]), r["path"] or "", r["line"], r["term"], r["kind"], r["grounder_class"] or ""))

    counts = {c: sum(1 for r in rows if r["class"] == c) for c in GATE_CLASSES}
    blocking = [c for c in BLOCKING if counts[c]]
    post_dis = sorted(p for p, text in applied.items() if text is not None and p in g["post"] and text.removesuffix("\n") != g["post"][p].removesuffix("\n"))
    rec = {
        "gate_version": GATE_VERSION, "grounder_version": G.GROUNDER_VERSION, "hobbes_version": __version__,
        "parent": parent_sha, "inputs": inputs,
        "verdict": "blocked" if blocking else "clear", "blocking": blocking,
        "advisory": [c for c in ADVISORY if counts[c]], "routed": [c for c in ROUTED if counts[c]], "route": bool(counts["new"]),
        "counts": counts,
        "split": None if bmap is None else {c: {"stands": sum(1 for r in rows if r["grounder_class"] == c and r["class"] == c),
                                                "unknown": sum(1 for r in rows if r["grounder_class"] == c and r["class"] == "unknown")} for c in SPLIT_CLASSES},
        "unknown_reasons": dict(sorted(collections.Counter(r["site"]["reason"] for r in rows if r["class"] == "unknown").items())),
        "rows": rows,
        "siblings": _siblings(rows, L, repo_root) if blocking else [],
        "partition": {"checked": part is not None, "source": partition_source if part is not None else None, "rule": partition_rule,
                      "size": None if part is None else len(part), "files": pfiles,
                      "outside": [f["path"] for f in pfiles if not f["in_partition"] and not f["exempt"] and f["reach"] is None],
                      "exempt": [f["path"] for f in pfiles if f["exempt"]], "reached": [f["path"] for f in pfiles if f["reach"]]},
        "map": None if bmap is None else {"source": bmap.get("source"), "fraction_uncaptured": bmap.get("fraction_uncaptured"),
                                          "partition_lines": bmap.get("partition_lines"), "uncaptured_lines": bmap.get("uncaptured_lines"),
                                          "partition_agrees": None if part is None else sorted(set(map(str, bmap["partition"]))) == part,
                                          "unresolved_by_file": _unresolved_by_file(msites, touched)},
        "integrity": {"empty": not sections, "applies": ok if sections else None, "apply_error": err or None,
                      "post_agrees": (not post_dis) if sections and ok else None, "post_disagrees": post_dis,
                      "grounder_refused": g["refused"], "renamed": sorted(s["path"] for s in sections if s["renamed"]),
                      "binary": sorted(s["path"] for s in sections if s["binary"])},
        "ground": {"references": g["references"], "null_by_class": g["null_by_class"], "hsr": g["hsr"], "density": g["density"]["counts"],
                   "world": g["world"]["counts"], "fills_attribution": {k: v for k, v in attribution.items() if k != "in_closed_at"},
                   "output_hash": g["output_hash"]},
        "rules": {"lookup": LOOKUP_RULE, "partition": PARTITION_RULE, "verdict": VERDICT_RULE, "new": NEW_RULE,
                  "world": G.WORLD_RULE, "signature": G.SIGNATURE_RULE},
    }
    rec["record_hash"] = _sha256(_canonical(rec))[:16]
    return rec


def dumps(rec: dict) -> str:
    """The record's bytes: sorted keys, one-space indent, a final newline — the same bytes on every rerun."""
    return json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ------------------------------------------------------------- the repair

_REPAIR_HEADS = {
    "invented": "Names nothing declares where the reference binds (invented)",
    "near-miss": "Names that nearly match a declared name (near-miss): the exact name exists elsewhere, or a declared name is within three edits",
    "arity": "Calls whose argument count differs from the callee's own declaration (arity)",
    "undeclared-type": "Qualified names the package does not declare (undeclared-type)",
    "import-outside": "Imports outside the module's world (import-outside): the standard library, this module's own packages, or a module its go.mod requires",
    "unimported": "Qualifiers no import of the file binds (unimported)",
    "malformed": "What the check could not read (malformed)",
    "partition": "Files outside the change's write partition (partition): undo these edits, or make the change in the files the task needs",
}


def _row_text(r: dict) -> str:
    if r["class"] == "partition":
        return f"- {r['path']}" + (" (you created it)" if "created" in (r["reason"] or "") else " (you deleted it)" if "deleted" in (r["reason"] or "") else "")
    where = f"{r['path']}:{r['line']}" if r["path"] else "the diff"
    s = f"- {where}" + (f" `{r['term']}`" if r["term"] else "")
    if r["nearest"] and r["class"] in ("invented", "near-miss", "unknown"):
        s += " — nearest declared: " + ", ".join(f"`{x}`" for x in r["nearest"][:5])
    if r["reason"]:
        s += f" — {r['reason']}"
    if r["class"] == "unknown" and r.get("site"):
        s += f" — site {r['site']['id']}: {r['site']['reason']}" + (f" ({r['site']['detail']})" if r["site"].get("detail") else "")
    return s


def repair_message(rec: dict) -> str:
    """calvin-m0-gate §2.3's repair turn message for a blocked record: the classes, every blocked site, the files outside the
    partition, a declaration's form where a blocked name has one, and the advisory sites apart. Deterministic in the record."""
    if rec["verdict"] != "blocked":
        raise ValueError("a clear record has no repair message")
    counts = rec["counts"]
    parts = [f"Hobbes checked your change against the repository at its parent commit {rec['parent'][:12]} and blocked it: "
             + ", ".join(f"{c} ({counts[c]})" for c in rec["blocking"]) + ".",
             "You have one turn to repair it; after that turn the change is checked and its tests run again. Fix what is listed "
             "below; change nothing else.", ""]
    for c in BLOCKING:
        rows = [r for r in rec["rows"] if r["class"] == c]
        if rows:
            parts += [f"## {_REPAIR_HEADS[c]}", *[_row_text(r) for r in rows], ""]
    for s in rec.get("siblings") or []:
        where = f"directory `{s['dir'] or '.'}/`" + (f", a method of `{s['type']}`" if s.get("type") else "")
        parts += [f"## The form of a declaration where `{s['for']}` would bind ({where})",
                  f"`{s['symbol']}` at {s['path']}:{s['line']} (package {s['package']}):", "```", s["text"], "```"]
        if s.get("more_lines"):
            parts.append(f"({s['more_lines']} more lines not shown)")
        parts.append("")
    adv = [r for r in rec["rows"] if r["class"] == "unknown"]
    if adv:
        parts += ["## Not blocking: sites Hobbes cannot see into (unknown) — check these names yourself", *[_row_text(r) for r in adv], ""]
    return "\n".join(parts).rstrip() + "\n"
