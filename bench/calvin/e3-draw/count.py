"""E3's family count — no spend, stdlib only, deterministic.

Reads an ingested repo's `.hobbes/derived/graph.json` (schema v4) and `tests.json`, and counts the
candidate training families E3's card names (calvin-experiments.md §6, E3): "symbols whose names differ
in one token and whose callee multisets match up to that token".

Members: symbols of kind function|method defined in a C/C++ file (by extension), outside test and
vendored paths (path heuristic; the graph marks neither — tests.json's `file`s are added to the test
set). Names tokenised on `_` and camelCase, lowercased; digits stay attached (`avx2`, `hsum256d`).
A name of one token is never a member (any two one-token names differ in one token).

Rules, each reported:
  loose      same token count, exactly one position differs (key = name with that position wildcarded);
             a family needs >= 2 distinct values at the varying position.
  strict     a loose family partitioned by the member's callee multiset: out-edges of type `calls`,
             callee name tokenised and every token equal to the member's own varying token replaced
             by `*`. Two tiers: `sem` (semantic edges only) and `all` (semantic + syntactic).
             A family whose shared multiset is empty is counted apart (`empty`).
  body       a loose family's members linked (single linkage) where their body token sequences, with
             the member's varying token masked (also as a substring of identifiers), have a
             SequenceMatcher ratio >= BODY_RATIO. Groups over BODY_CAP members are not compared
             (counted in `body_skipped_groups`).
Thin filter: a body with <= 2 non-blank lines between its braces, or one statement holding at most one
call (a wrapper, as E1's `wrappers` section treats them), or no brace body at all. Every figure is given
for all members and for non-thin members (families recomputed on the non-thin set).

Lattice-likeness (a genuineness proxy): a family's axis is the set of values at its varying position;
a family is `grid` when another family in the same repo, at a different wildcard key, has the same
axis — the same values vary across a second axis, as sqlite-vector's types do across its metrics.

Usage: python3 count.py <name>=<repo-root> ... [--calibrate sqlite-vector-cells.json] --out counts.json
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

C_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".h++", ".inl", ".ipp", ".tpp", ".inc"}
TEST_PARTS = {"test", "tests", "testing", "unittest", "unittests", "gtest", "gmock", "googletest", "googlemock",
              "fuzz", "fuzzing", "fuzzer", "benchmark", "benchmarks", "bench", "examples", "example"}
VENDOR_PARTS = {"third_party", "thirdparty", "third-party", "vendor", "vendored", "external", "extern", "deps",
                "libs", "3rdparty", "contrib", "unity"}
BODY_RATIO = 0.6
BODY_CAP = 64

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+[0-9]*|[A-Z]+[0-9]*|[0-9]+[a-z0-9]*")
_CTOK = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[0-9][0-9A-Za-z_.]*|\S")


def tokens(name: str) -> tuple[str, ...]:
    out: list[str] = []
    for part in name.split("_"):
        if not part:
            continue
        out.extend(m.group(0).lower() for m in _CAMEL.finditer(part))
    return tuple(out)


def classify_path(path: str) -> str | None:
    """`test`, `vendor` or None, from the path's directory parts and its file name."""
    parts = [p.lower() for p in Path(path).parts]
    stem = Path(path).stem.lower()
    if any(p in VENDOR_PARTS for p in parts[:-1]):
        return "vendor"
    if any(p in TEST_PARTS for p in parts[:-1]) or stem.startswith("test_") or stem.endswith("_test") \
            or stem.endswith("_unittest") or stem.startswith("test"):
        return "test"
    return None


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    return text


class Repo:
    def __init__(self, name: str, root: Path):
        self.name, self.root = name, root
        derived = root / ".hobbes" / "derived"
        print(f"[{name}] loading graph", file=sys.stderr, flush=True)
        g = json.loads((derived / "graph.json").read_text(encoding="utf-8"))
        self.sha = g.get("sha")
        self.version = (g.get("built_by") or {}).get("version")
        self.languages = g.get("languages")
        mod_path = {n["id"]: n.get("path") for n in g["nodes"] if n.get("kind") == "module" and n.get("path")}
        test_files: set[str] = set()
        tj = derived / "tests.json"
        reached: set[str] = set()
        if tj.exists():
            t = json.loads(tj.read_text(encoding="utf-8"))
            for row in t.get("tests") or []:
                if row.get("file"):
                    test_files.add(row["file"])
                reached.update(row.get("reaches") or [])
        self.reached = reached
        self.excluded = Counter()
        self.members: dict[str, dict] = {}
        name_of = {s["id"]: s["name"] for s in g["symbols"]}
        for s in g["symbols"]:
            if s.get("kind") not in ("function", "method"):
                continue
            path = mod_path.get(s.get("module"))
            if not path or Path(path).suffix.lower() not in C_EXT:
                self.excluded["not-c-file"] += 1
                continue
            cls = "test" if path in test_files else classify_path(path)
            if cls:
                self.excluded[cls] += 1
                continue
            toks = tokens(s["name"])
            if len(toks) < 2:
                self.excluded["one-token-name"] += 1
                continue
            self.members[s["id"]] = {"id": s["id"], "name": s["name"], "qualname": s.get("qualname"),
                                     "path": path, "line": s.get("line"), "end_line": s.get("end_line"),
                                     "toks": toks, "calls": {"sem": [], "all": []}}
        for e in g["symbol_edges"]:
            if e.get("type") != "calls":
                continue
            m = self.members.get(e["from"])
            if m is None:
                continue
            callee = name_of.get(e["to"], e["to"].split(".")[-1])
            m["calls"]["all"].append(callee)
            if e.get("tier") == "semantic":
                m["calls"]["sem"].append(callee)
        del g
        self._files: dict[str, list[str]] = {}
        for m in self.members.values():
            m["body"] = self._body(m)
            m["thin"] = self._thin(m)

    def _lines(self, path: str) -> list[str]:
        if path not in self._files:
            try:
                self._files[path] = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                self._files[path] = []
        return self._files[path]

    def _body(self, m: dict) -> str | None:
        lines = self._lines(m["path"])
        if not lines or not m["line"] or not m["end_line"]:
            return None
        text = strip_comments("\n".join(lines[m["line"] - 1: m["end_line"]]))
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            return None
        return text[a + 1: b]

    def _thin(self, m: dict) -> bool:
        body = m["body"]
        if body is None:
            return True
        nonblank = [l for l in body.splitlines() if l.strip()]
        if len(nonblank) <= 2:
            return True
        if body.count(";") <= 1 and len(m["calls"]["all"]) <= 1:
            return True
        return False


def loose_groups(members: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in members:
        t = m["toks"]
        for i in range(len(t)):
            groups[(len(t), i, t[:i] + ("*",) + t[i + 1:])].append(m)
    return {k: v for k, v in groups.items() if len({m["toks"][k[1]] for m in v}) >= 2}


def canon(callees: list[str], vary: str) -> tuple:
    out = Counter()
    for c in callees:
        out["_".join("*" if t == vary else t for t in tokens(c)) or c] += 1
    return tuple(sorted(out.items()))


def strict_families(groups, tier: str):
    fams = []
    for key, ms in groups.items():
        i = key[1]
        part: dict[tuple, list[dict]] = defaultdict(list)
        for m in ms:
            part[canon(m["calls"][tier], m["toks"][i])].append(m)
        for sig, sub in part.items():
            if len({m["toks"][i] for m in sub}) >= 2:
                fams.append({"key": key, "members": sub, "empty": len(sig) == 0})
    return fams


def body_tokens(m: dict, vary: str) -> list[str]:
    out = []
    for t in _CTOK.findall(m["body"] or ""):
        if vary and len(vary) > 1 and vary in t.lower():
            t = re.sub(re.escape(vary), "*", t, flags=re.I)
        out.append(t)
    return out


def body_families(groups):
    fams, skipped = [], 0
    for key, ms in groups.items():
        if len(ms) > BODY_CAP:
            skipped += 1
            continue
        i = key[1]
        toks = [body_tokens(m, m["toks"][i]) for m in ms]
        parent = list(range(len(ms)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a in range(len(ms)):
            if ms[a]["body"] is None:
                continue
            for b in range(a + 1, len(ms)):
                if ms[b]["body"] is None or ms[a]["toks"][i] == ms[b]["toks"][i]:
                    continue
                sm = difflib.SequenceMatcher(None, toks[a], toks[b], autojunk=False)
                if sm.real_quick_ratio() < BODY_RATIO or sm.quick_ratio() < BODY_RATIO:
                    continue
                if sm.ratio() >= BODY_RATIO:
                    parent[find(a)] = find(b)
        comp: dict[int, list[dict]] = defaultdict(list)
        for x in range(len(ms)):
            comp[find(x)].append(ms[x])
        for sub in comp.values():
            if len({m["toks"][i] for m in sub}) >= 2:
                fams.append({"key": key, "members": sub, "empty": False})
    return fams, skipped


def summarise(fams, reached=None) -> dict:
    def stats(fs):
        members = {m["id"] for f in fs for m in f["members"]}
        d = {"families": len(fs), "distinct_members": len(members),
             "tasks": sum(len(f["members"]) for f in fs)}
        if reached is not None:
            d["members_reached_by_tests"] = len(members & reached)
        return d
    grid_axes = Counter()
    by_axis = defaultdict(set)
    for f in fams:
        axis = frozenset(m["toks"][f["key"][1]] for m in f["members"])
        by_axis[axis].add(f["key"])
    grid = [f for f in fams if len(by_axis[frozenset(m["toks"][f["key"][1]] for m in f["members"])]) >= 2]
    out = {}
    for label, pick in (("ge2", lambda f: True), ("ge3", lambda f: len(f["members"]) >= 3)):
        fs = [f for f in fams if pick(f)]
        out[label] = stats(fs)
        out[label]["nonempty"] = stats([f for f in fs if not f["empty"]])
        out[label]["empty"] = stats([f for f in fs if f["empty"]])
        out[label]["grid"] = stats([f for f in fs if f in grid and not f["empty"]])
    return out


def sample(fams, n=5):
    fs = [f for f in fams if not f["empty"]]
    fs.sort(key=lambda f: hashlib.sha1(repr(f["key"]).encode()).hexdigest())
    return [{"key": " ".join(f["key"][2]), "members": [f"{m['name']} {m['path']}:{m['line']}" for m in
                                                       sorted(f["members"], key=lambda m: (m['path'], m['line']))][:8],
             "size": len(f["members"])} for f in fs[:n]]


def run(repo: Repo, calibrate: list[dict] | None = None) -> dict:
    result = {"root": str(repo.root), "sha": repo.sha, "built_by_version": repo.version,
              "languages": repo.languages, "excluded": dict(repo.excluded),
              "members": len(repo.members), "members_thin": sum(1 for m in repo.members.values() if m["thin"])}
    for label, pool in (("all", list(repo.members.values())),
                        ("nonthin", [m for m in repo.members.values() if not m["thin"]])):
        print(f"[{repo.name}] {label}: {len(pool)} members", file=sys.stderr, flush=True)
        groups = loose_groups(pool)
        loose = [{"key": k, "members": v, "empty": False} for k, v in groups.items()]
        s_sem = strict_families(groups, "sem")
        s_all = strict_families(groups, "all")
        body, skipped = body_families(groups)
        r = {"loose": summarise(loose, repo.reached), "strict_sem": summarise(s_sem, repo.reached),
             "strict_all": summarise(s_all, repo.reached), "body": summarise(body, repo.reached),
             "body_skipped_groups": skipped,
             "samples": {"strict_all": sample(s_all), "body": sample(body)}}
        if calibrate is not None:
            r["calibration"] = calibrate_cells(calibrate, repo, {"loose": loose, "strict_sem": s_sem,
                                                                  "strict_all": s_all, "body": body})
        result[label] = r
    return result


def calibrate_cells(cells: list[dict], repo: Repo, rules: dict) -> dict:
    """How many of the 93 native lattice cells each rule puts in a family of size >= 2 (and >= 3)."""
    by_name = defaultdict(set)
    for m in repo.members.values():
        by_name[(m["name"], m["path"])].add(m["id"])
    native = [c for c in cells if c["native"]]
    ids = {c["id"]: by_name.get((c["name"], c["file"]), set()) for c in native}
    out = {"native_cells": len(native), "found_in_graph": sum(1 for v in ids.values() if v)}
    for rule, fams in rules.items():
        for size in (2, 3):
            inside = set()
            for f in fams:
                if f["empty"] or len(f["members"]) < size:
                    continue
                inside.update(m["id"] for m in f["members"])
            hit = [c for c in native if ids[c["id"]] & inside]
            out[f"{rule}_ge{size}"] = {"cells": len(hit),
                                       "real_bodies": sum(1 for c in hit if c["kind"] != "wrapper"),
                                       "wrappers": sum(1 for c in hit if c["kind"] == "wrapper")}
    out["real_bodies_total"] = sum(1 for c in native if c["kind"] != "wrapper")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+", help="name=root")
    ap.add_argument("--calibrate", type=Path, help="lattice cells JSON; the repo named sqlite-vector is calibrated")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cells = json.loads(args.calibrate.read_text()) if args.calibrate else None
    found = json.loads(args.out.read_text()) if args.out.exists() else {}
    for spec in args.repos:
        name, root = spec.split("=", 1)
        repo = Repo(name, Path(root).expanduser())
        found[name] = run(repo, cells if name == "sqlite-vector" else None)
        args.out.write_text(json.dumps(found, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
