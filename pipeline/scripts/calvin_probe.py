"""The Calvin M0 pre-run probes (`docs/calvin-potential.md` §0, §4.1, §4.2; record `docs/ttt-cells/calvin-m0-probe-2026-09-03.md`).

    uv run scripts/calvin_probe.py ingest  <graphs-dir> [--clone DIR] [--commits FILE] [--lane-b]
    uv run scripts/calvin_probe.py probe   <graphs-dir> [--mode parent|base] [--base-graph graph.json]
    uv run scripts/calvin_probe.py anchors <graphs-dir>

Two instruments that need no orchestrator, computed from lane A alone
(symbol spans, file paths and names are lane A's; ``HOBBES_SCIP=0``).
``ingest`` builds one lane-A graph per distinct unit commit at the
commit's **parent** into ``<graphs-dir>/<commit>.json`` (+ ``.tests.json``,
``.log``), checking the clone out at each parent; lane-A graphs are
regenerable in about two seconds each and are not committed.
``--lane-b`` runs the full contained ingest instead (lane B in the
sandbox image, ADR-092) — the ledger M0's grounder needs, since exact
matching against a syntactic-only graph makes "exists" a guess
(charter §6); the per-parent wall time it prints is §7.1's cost. ``probe``
is the template-coverage ceiling (§4.1) — every gold-diff hunk of the
50 §9b cell units classed as *absent file* (by extension; and whether
the commit creates it), *inside a symbol span*, or *known file outside
every span* — plus the anchor pass at file grain (§4.2): the planner's
own exact-match seed resolver (`hobbes.derive.impact.build_impact`,
C-36) against the files the gold diff touches. ``anchors`` is the
breakdown behind §4.2: lexical vs. code-shaped seeds, gold files no
anchor reached split by whether the task text names them at all, and
the unresolved code-shaped terms split by whether the gold diff's added
lines carry them (the ``new`` class seen at the anchor stage).

Caveats the record states: file grain, not symbol grain, for anchors;
hunk placement uses the diff's post-image line numbers against parent
spans (slightly generous for hunks that insert lines); one-off probes,
not cell records — no scorer version is pinned. ``--mode base`` reruns
against the one release-SHA graph the TTT cell used, which is what
C-84 measures.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

BENCH = Path.home() / ".hobbes" / "bench" / "ttt"
PROPOSALS = Path(__file__).resolve().parents[2] / "bench" / "ttt" / "proposals-hobbes-ebdf7a5.jsonl"

#: A unified-diff hunk header; group 1 is the post-image start line, group 2 its length.
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)
CODE_EXT = (".py", ".go", ".ts", ".tsx", ".js", ".mjs", ".rs", ".java", ".tf")


def hunk_ranges(diff: str) -> list[tuple[int, int]]:
    """Post-image ``(start, end)`` line ranges of every hunk in ``diff`` (a zero-length hunk is one line)."""
    out = []
    for m in HUNK_RE.finditer(diff):
        st = int(m.group(1))
        n = int(m.group(2) or 1)
        out.append((st, st + max(n, 1) - 1))
    return out


def absent_class(path: str) -> str:
    """How an absent file is counted: ``code`` (an extension lane A walks), ``docs`` (``.md`` or none), else ``other:<ext>``."""
    ext = os.path.splitext(path)[1]
    if ext in CODE_EXT:
        return "code"
    if ext in (".md", ""):
        return "docs"
    return "other:" + ext


def index(graph: dict) -> tuple[dict, dict, dict]:
    """``(module id → path, path → module id, module id → [(line, end_line)])`` from a graph."""
    mod2path = {n["id"]: n.get("path") for n in graph["nodes"] if n.get("path")}
    path2mod = {v: k for k, v in mod2path.items()}
    spans: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    for s in graph["symbols"]:
        spans[s["module"]].append((s["line"], s["end_line"]))
    return mod2path, path2mod, spans


def in_any_span(rng: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    """Whether the hunk range overlaps any symbol span."""
    st, en = rng
    return any(s <= en and st <= e for s, e in spans)


def classify_hunks(diff: str, path: str, path2mod: dict, spans: dict) -> tuple[int, int, int, int]:
    """``(hunks, absent, in_span, new_code_absent)`` for one gold diff of one file."""
    new = "new file mode" in diff
    total = absent = inside = new_absent = 0
    for rng in hunk_ranges(diff):
        total += 1
        if path not in path2mod:
            absent += 1
            if new and absent_class(path) == "code":
                new_absent += 1
            continue
        if in_any_span(rng, spans[path2mod[path]]):
            inside += 1
    return total, absent, inside, new_absent


def load_units() -> tuple[list[dict], dict[str, list[dict]]]:
    cell = [json.loads(l) for l in open(BENCH / "cell-hobbes" / "units.jsonl")]
    cell = [c for c in cell if "unit" in c]
    git = [json.loads(l) for l in open(BENCH / "units" / "hobbes.jsonl")]
    bycommit: dict[str, list[dict]] = collections.defaultdict(list)
    for r in git:
        bycommit[r["id"].split(":")[0]].append(r)
    return cell, bycommit


def load_proposals() -> list[dict]:
    return [p for p in (json.loads(l) for l in open(PROPOSALS)) if "commit" in p]


def cmd_ingest(a: argparse.Namespace) -> int:
    graphs = Path(a.graphs)
    graphs.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    commits = a.commits.read_text().split() if a.commits else sorted({p["commit"] for p in load_proposals()})
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    if not clone.exists():
        subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
    for c in commits:
        if (graphs / f"{c}.json").exists():
            continue
        parent = subprocess.run(["git", "rev-parse", f"{c}^"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "checkout", "-q", parent], cwd=clone, check=True)
        subprocess.run(["rm", "-rf", str(clone / ".hobbes" / "derived")], check=True)
        t0 = time.time()
        env = {k: v for k, v in os.environ.items() if k != "HOBBES_SCIP"}
        if not a.lane_b:
            env["HOBBES_SCIP"] = "0"
        with open(graphs / f"{c}.log", "w") as log:
            rc = subprocess.run(["uv", "run", "--project", str(repo / "pipeline"), "hobbes", "ingest", "--repo", str(clone)],
                                env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        for name in ("graph.json", "tests.json"):
            src = clone / ".hobbes" / "derived" / name
            if src.exists():
                (graphs / (f"{c}.json" if name == "graph.json" else f"{c}.tests.json")).write_bytes(src.read_bytes())
        print(f"{c} parent={parent} rc={rc} {time.time() - t0:.0f}s", flush=True)
    return 0


def cmd_probe(a: argparse.Namespace) -> int:
    from hobbes.derive.impact import SeedError, build_impact

    mode = a.mode
    graphs = Path(a.graphs)
    basegraph = json.load(open(a.base_graph)) if mode == "base" else None
    cache: dict[str, dict] = {}

    def graph_for(commit: str) -> dict:
        if mode == "base":
            return basegraph
        if commit not in cache:
            cache[commit] = json.load(open(graphs / f"{commit}.json"))
        return cache[commit]

    cell, bycommit = load_units()
    tot = absent = inspan = 0
    absent_by: collections.Counter = collections.Counter()
    newfile_absent = 0
    per = []
    for c in cell:
        _, path2mod, spans = index(graph_for(c["commit"]))
        t = ab = i = 0
        for r in bycommit[c["commit"]]:
            f = r["id"].split(":", 1)[1]
            ht, ha, hi, hn = classify_hunks(r["gold_diff"], f, path2mod, spans)
            t += ht; ab += ha; i += hi; newfile_absent += hn
            if ha:
                absent_by[absent_class(f)] += ha
        tot += t; absent += ab; inspan += i; per.append((c["id"], t, ab, i))
    out = tot - absent - inspan
    print(f"[{mode}] hunks {tot}: absent-file {absent} ({absent / tot:.0%}) = {dict(absent_by)}; "
          f"of the absent code hunks {newfile_absent} are in files the commit creates; "
          f"in-span {inspan} ({inspan / tot:.0%}); known file outside spans {out} ({out / tot:.0%})")
    ceil = [i / t for _, t, _, i in per if t]
    print(f"[{mode}] per-unit ceiling: median {statistics.median(ceil):.2f}, "
          f"units at 0: {sum(1 for x in ceil if x == 0)}/{len(ceil)}, >=0.5: {sum(1 for x in ceil if x >= .5)}")
    tc = tot - absent_by["docs"] - sum(v for k, v in absent_by.items() if k.startswith("other"))
    print(f"[{mode}] code hunks only: {tc}; in-span {inspan / tc:.0%}; "
          f"absent code files {absent_by['code'] / tc:.0%}; known outside spans {out / tc:.0%}")

    props = load_proposals()
    gold = {k: {r["id"].split(":", 1)[1] for r in v} for k, v in bycommit.items()}
    tp = fp = fn = zero = unres = fn_absent = 0
    for p in props:
        mod2path, path2mod, _ = index(graph_for(p["commit"]))
        try:
            imp = build_impact(graph_for(p["commit"]), p["task"], [])
            seeds = imp.seeds
            unres += len(imp.unresolved_terms)
        except SeedError:
            seeds = {}
        af = {mod2path.get(m, m) for m in seeds}
        gf = gold.get(p["commit"], set())
        if not af:
            zero += 1
        tp += len(af & gf); fp += len(af - gf); fn += len(gf - af)
        fn_absent += len({f for f in gf - af if f not in path2mod})
    print(f"[{mode}] anchors (file grain, {len(props)} proposals): precision {tp / (tp + fp):.2f} ({tp}/{tp + fp}) "
          f"recall {tp / (tp + fn):.2f} ({tp}/{tp + fn}); zero-anchor {zero}; unresolved code-shaped terms {unres}; "
          f"misses in files the graph lacks {fn_absent}/{fn}")
    return 0


def unresolved_is_new(term: str, added_lines: str) -> bool:
    """Whether an unresolved code-shaped term's last segment appears in the gold diff's added lines."""
    return re.search(re.escape(term.split(".")[-1]), added_lines) is not None


def cmd_anchors(a: argparse.Namespace) -> int:
    from hobbes.derive.impact import SeedError, build_impact

    graphs = Path(a.graphs)
    _, bycommit = load_units()
    gold: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for rows in bycommit.values():
        for r in rows:
            gold[r["id"].split(":")[0]][r["id"].split(":", 1)[1]] = r["gold_diff"]
    named = unnamed = lexical = nonlex = unres_new = unres_old = fp_lex = fp_non = 0
    for p in load_proposals():
        g = json.load(open(graphs / f"{p['commit']}.json"))
        mod2path, path2mod, _ = index(g)
        names: dict[str, set] = collections.defaultdict(set)
        for s in g["symbols"]:
            names[s["module"]].add(s["name"])
        try:
            imp = build_impact(g, p["task"], [])
            seeds, lex, unres = imp.seeds, set(imp.seeds_lexical), imp.unresolved_terms
        except SeedError:
            seeds, lex, unres = {}, set(), []
        lexical += len(lex); nonlex += len(seeds) - len(lex)
        gf = gold[p["commit"]]
        af = {mod2path.get(m, m): m for m in seeds}
        for f, m in af.items():
            if f not in gf:
                if m in lex:
                    fp_lex += 1
                else:
                    fp_non += 1
        added = "\n".join(l for d in gf.values() for l in d.splitlines() if l.startswith("+"))
        for t in unres:
            if unresolved_is_new(t, added):
                unres_new += 1
            else:
                unres_old += 1
        text = p["task"]
        for f in gf:
            if f in af or f not in path2mod:
                continue
            base = os.path.splitext(os.path.basename(f))[0]
            if base in text or f in text or any(len(n) >= 5 and n in text for n in names[path2mod[f]]):
                named += 1
            else:
                unnamed += 1
    print(f"seeds: {nonlex} explicit/code-shaped, {lexical} lexical; wrong-file anchors: {fp_non} non-lexical, {fp_lex} lexical")
    print(f"gold files the parent graph has but no anchor reached: {named + unnamed}; "
          f"task text names the file or a symbol in it: {named}; task never names it: {unnamed}")
    print(f"unresolved code-shaped terms: {unres_new + unres_old}; appear in the gold diff's added lines "
          f"(new names the task asks for): {unres_new}; not in the diff at all: {unres_old}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ingest"); s.add_argument("graphs"); s.add_argument("--clone"); s.add_argument("--commits", type=Path)
    s.add_argument("--lane-b", action="store_true", help="full contained ingest (lane B in the image) instead of lane A only")
    s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("probe"); s.add_argument("graphs"); s.add_argument("--mode", choices=("parent", "base"), default="parent")
    s.add_argument("--base-graph", default=str(BENCH / "hobbes-base" / ".hobbes" / "derived" / "graph.json"))
    s.set_defaults(fn=cmd_probe)
    s = sub.add_parser("anchors"); s.add_argument("graphs"); s.set_defaults(fn=cmd_anchors)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
