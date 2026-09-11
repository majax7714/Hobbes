"""The Calvin M0 pre-run probes (`docs/calvin/calvin-potential.md` §0, §4.1, §4.2; record `docs/calvin/cells/calvin-m0-probe-2026-09-03.md`).

    uv run scripts/calvin_probe.py ingest  <graphs-dir> [--clone DIR] [--commits FILE] [--lane-b]
    uv run scripts/calvin_probe.py probe   <graphs-dir> [--mode parent|base] [--base-graph graph.json]
    uv run scripts/calvin_probe.py anchors <graphs-dir>
    uv run scripts/calvin_probe.py templates <graphs-dir> --out <dir> [--clone DIR]
    uv run scripts/calvin_probe.py ground  <graphs-dir> --templates <dir> --out <dir> [--gold commit|rows]
    uv run scripts/calvin_probe.py t       <graphs-dir> --templates <dir> --out <dir> --commits c… --base-url URL --model M
    uv run scripts/calvin_probe.py verify  <graphs-dir> --diffs <dir> --out <dir> [--commits c…] [--suffix .diff]
    uv run scripts/calvin_probe.py o       <graphs-dir> --templates <dir> --out <dir> --commits c… (--scripted SCRIPT.json | --base-url URL --model M)
    uv run scripts/calvin_probe.py replay  <graphs-dir> --templates <dir> --t <dir> --commits c… [--mode gold max] [--show-tests]

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
lines carry them (the ``new`` class seen at the anchor stage). ``verify`` is step 5's
harness over a directory of diffs (the gold diffs of ``ground`` as the
calibration, arm T's ``.t.diff`` records as the candidates): each diff
applied at its parent, the testmap's guards run in the sandbox with
and without it. ``o`` is arm O on the same harness — a
``hobbes-session`` with policy-checked exec per commit; ``--scripted``
plays a JSON script through the session in place of a model (step 5's
exit check, no orchestrator). ``replay`` is step 6b
exercised with no model: a recorded arm-T run's round-1 answers
(``<commit>.t.json``) replayed into a later template set and rebuilt,
the per-symbol confirmations decided by the gold diff (``gold``) or
by the run's module answers (``max``, the upper bound) — what round 2
would have asked, its test holes by tier, §4.1 coverage. ``templates`` is step 2's
exit: `hobbes.derive.template` over every proposal at its parent,
rebuilt and compared byte for byte, and §4.1 / §4.2 / §4.7 scored
against gold with no orchestrator — the *actual* template coverage
where ``probe`` measured the ceiling.

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
import hashlib
import json
import os
import re
import shutil
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


def hunks_by_file(diff: str) -> dict[str, list[tuple[int, int]]]:
    """Post-image line ranges of every hunk, keyed by the file its ``+++ b/`` header names (``hunk_ranges`` over a one-file diff, per file)."""
    out: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    path = None
    for line in diff.splitlines():
        m = re.match(r"^\+\+\+ b/(.*)", line)
        if m:
            path = m.group(1)
            continue
        m = HUNK_RE.match(line)
        if m and path is not None:
            start = int(m.group(1))
            n = int(m.group(2) or 1)
            out[path].append((start, max(start + n - 1, start)))
    return dict(out)


def replay_fills(template: dict, record: dict, mode: str, edits) -> tuple[dict, int]:
    """Round-1 fills for *template* (v1: a module anchor's symbols asked one by one) from a recorded arm-T run's round-1 answers (*record* is the ``.t.json``,
    whose round 1 asked v0's per-word confirmations). A word-level confirmation takes the recorded answer; a per-symbol one is decided by *mode*:
    ``gold`` — yes iff ``edits(symbol_id)`` (the gold diff touches its span); ``max`` — yes for every symbol of a module the run confirmed (v1's upper bound).
    The UNRESOLVED answer is carried as recorded. Returns ``(fills, confirmations answered yes)``."""
    r1 = record["rounds"][0]["fills"]["fills"]
    words = {h["provenance"]["anchor"]: bool(r1.get(h["id"], {}).get("confirm")) for h in record["template_round1"]["holes"] if h["type"] == "ANCHOR_CONFIRM"}
    confirmed_modules = {h["provenance"]["module"] for h in template["holes"]
                         if h["type"] == "ANCHOR_CONFIRM" and h["provenance"].get("module") and words.get(h["provenance"]["anchor"])}
    fills: dict = {}
    yes = 0
    for h in template["holes"]:
        if h["type"] == "UNRESOLVED" and h["id"] in r1:
            fills[h["id"]] = r1[h["id"]]
        if h["type"] != "ANCHOR_CONFIRM":
            continue
        prov = h["provenance"]
        if prov.get("symbol"):
            ans = edits(prov["symbol"]) if mode == "gold" else prov.get("module") in confirmed_modules
        else:
            ans = words.get(prov["anchor"], False)
        fills[h["id"]] = {"confirm": bool(ans)}
        yes += bool(ans)
    return fills, yes


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


def cmd_templates(a: argparse.Namespace) -> int:
    """`hobbes template` over every proposal at its parent (step 2's exit): write the templates, rebuild and compare bytes, score §4.1 / §4.2 / §4.7 against gold with no orchestrator."""
    from hobbes.derive import cochange, holes
    from hobbes.derive import template as T

    graphs = Path(a.graphs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    cell, bycommit = load_units()
    props = load_proposals()
    cov = collections.Counter()
    per_matcher: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    files = collections.Counter(); syms = collections.Counter()
    hole_types = collections.Counter(); holes_per: list[int] = []; zero = unres = 0; identical = 0
    wall = 0.0
    rows = []
    for p in props:
        c = p["commit"]
        L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
        subprocess.run(["git", "checkout", "-q", L.sha], cwd=clone, check=True)
        cc = cochange.observe(clone, 200)
        t0 = time.time()
        t = T.build_template(p["task"], L, repo, cc)
        wall += time.time() - t0
        assert holes.validate_template(t) == [], (c, holes.validate_template(t))
        again = T.build_template(p["task"], L, repo, cc)
        identical += T.canonical(t) == T.canonical(again)
        (out / f"{c}.template.json").write_text(json.dumps(t, indent=1))
        gold = [(r["id"].split(":", 1)[1], r["gold_diff"]) for r in bycommit[c]]
        sc = T.score_coverage(t, gold); an = T.score_anchors(t, L, gold)
        n_units = sum(1 for u in cell if u["commit"] == c)
        for k in ("symbol", "region", "new_file", "outside", "hunks"):
            cov[k] += sc[k] * n_units  # the 50 units share 28 commits; weight by units as the probe did
        for m, r in an["per_matcher"].items():
            for k, v in r.items():
                per_matcher[m][k] += v
        for k, v in an["files"].items():
            files[k] += v
        for k, v in an["symbols"].items():
            syms[k] += v
        zero += an["zero_anchor"]; unres += an["unresolved"]
        hole_types.update(h["type"] for h in t["holes"]); holes_per.append(len(t["holes"]))
        rows.append((c[:7], len(t["anchors"]), an["unresolved"], len(t["holes"]), sc["hunks"], sc["symbol"], sc["region"], sc["new_file"], sc["outside"]))
    print(f"templates {len(props)}: byte-identical on rebuild {identical}/{len(props)}; build wall {wall:.1f}s (mean {wall / len(props):.2f}s)")
    h = cov["hunks"]
    print(f"[§4.1] hunks {h} (unit-weighted over 50 units): symbol {cov['symbol']} ({cov['symbol'] / h:.0%}); region {cov['region']} ({cov['region'] / h:.0%}); "
          f"new-file {cov['new_file']} ({cov['new_file'] / h:.0%}); outside {cov['outside']} ({cov['outside'] / h:.0%})")
    print(f"[§4.2] files: precision {files['tp']}/{files['anchored']} = {files['tp'] / max(files['anchored'], 1):.2f}, recall {files['tp']}/{files['gold']} = {files['tp'] / max(files['gold'], 1):.2f}; "
          f"symbols: precision {syms['tp']}/{syms['anchored']} = {syms['tp'] / max(syms['anchored'], 1):.2f}, recall {syms['tp']}/{syms['gold']} = {syms['tp'] / max(syms['gold'], 1):.2f}; "
          f"zero-anchor {zero}; unresolved terms {unres}")
    for m, r in sorted(per_matcher.items()):
        print(f"        {m:16s} anchors {r['anchors']:4d}  in a gold file {r['file_hits']:4d}  on a gold symbol {r['symbol_hits']:4d}")
    print(f"[§4.7] holes per template: median {statistics.median(holes_per):.0f}, min {min(holes_per)}, max {max(holes_per)}; by type {dict(sorted(hole_types.items()))}")
    print("commit  anchors unresolved holes | hunks symbol region new outside")
    for r in rows:
        print(f"{r[0]}  {r[1]:5d} {r[2]:8d} {r[3]:6d} | {r[4]:4d} {r[5]:6d} {r[6]:6d} {r[7]:3d} {r[8]:7d}")
    return 0


def cmd_ground(a: argparse.Namespace) -> int:
    """Step 3's exit: every gold diff expressed as fills against its template, grounded at the parent — HSR, NULLs by class, placement, re-application and post-image equality, with no orchestrator."""
    from hobbes.derive import ground as G
    from hobbes.derive import template as T

    graphs = Path(a.graphs)
    templates = Path(a.templates)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    cell, bycommit = load_units()
    props = load_proposals()
    refs = collections.Counter(); nulls = collections.Counter(); attrib = collections.Counter()
    edits_by = collections.Counter(); placements = collections.Counter()
    applies = equal = identical = 0; unfilled = refused = outside = trace_rows = 0
    null_rows: list[dict] = []
    wall = 0.0
    rows = []
    for p in props:
        c = p["commit"]
        L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
        t = json.load(open(templates / f"{c}.template.json"))
        if a.gold == "rows":
            gold = [(r["id"].split(":", 1)[1], r["gold_diff"]) for r in bycommit[c]]
        else:  # the commit itself (§3.1: "its gold diff is the commit"); the cell's rows are its size-bounded, non-binary subset
            files = [f for f in subprocess.run(["git", "show", "--name-only", "--format=", "--no-renames", c], cwd=clone, capture_output=True, text=True, check=True).stdout.split("\n") if f]
            gold = []
            for f in files:
                d = subprocess.run(["git", "show", "--format=", "--no-color", "--no-renames", c, "--", f], cwd=clone, capture_output=True, text=True, errors="surrogateescape", check=True).stdout
                if "GIT binary patch" in d or any(l.startswith("Binary files") for l in d.splitlines()[-1:]):
                    attrib["binary_skipped"] += 1  # as the cell's units do: a binary file is not a fill
                    continue
                gold.append((f, d))
        doc, counts = G.fills_from_diff(t, gold, repo)  # prunes t in place, as the grounder will
        in_closed_at = counts.pop("in_closed_at", [])
        attrib.update(counts)
        for x in in_closed_at:
            print(f"        gold edits inside a closed hole: {c[:7]} {x}")
        t0 = time.time()
        g = G.ground(json.load(open(templates / f"{c}.template.json")), doc, L, repo)
        wall += time.time() - t0
        again = G.ground(json.load(open(templates / f"{c}.template.json")), doc, L, repo)
        identical += g["output_hash"] == again["output_hash"]
        (out / f"{c}.fills-gold.json").write_text(json.dumps(doc, indent=1))
        (out / f"{c}.ground.json").write_text(json.dumps(g, indent=1))
        (out / f"{c}.diff").write_text(g["diff"])
        for k, v in g["references"].items():
            refs[k] += v
        for k, v in g["null_by_class"].items():
            nulls[k] += v
        for n in g["null"]:
            null_rows.append({"commit": c[:7], **{k: n[k] for k in ("hole", "path", "line", "term", "null_class", "nearest", "declared")}})
        for e in g["edits"]:
            edits_by[e["type"]] += 1; placements[e["placement"]] += 1
        unfilled += len(g["unfilled"]); refused += len(g["refused"]); outside += g["outside_partition"]; trace_rows += len(g["trace"])
        # re-application at the parent, and the post-image against the commit itself
        subprocess.run(["git", "checkout", "-q", "--force", L.sha], cwd=clone, check=True)
        r = subprocess.run(["git", "apply", "--check", "-"], cwd=clone, input=g["diff"], capture_output=True, text=True)
        ok_apply = r.returncode == 0
        applies += ok_apply
        same = True
        for path, _ in gold:
            want = subprocess.run(["git", "show", f"{c}:{path}"], cwd=clone, capture_output=True, text=True, errors="surrogateescape").stdout
            got = next((f for f in g["files"] if f["path"] == path), None)
            same &= got is not None and want == g["post"][path]
        equal += same
        rows.append((c[:7], len(gold), g["references"]["total"], g["references"]["in-graph"], g["references"]["gensym"], g["references"]["NULL"], g["hsr"], len(g["edits"]), g["outside_partition"], ok_apply, same, r.stderr.strip()[:60]))
    n = len(props)
    print(f"grounded {n} templates (50 units share them): identical on rerun {identical}/{n}; applies at the parent {applies}/{n}; post-image equals the commit {equal}/{n}; ground wall {wall:.1f}s")
    judged = refs["in-graph"] + refs["NULL"]
    print(f"[§4.6] references {refs['total']}: in-graph {refs['in-graph']}, gensym {refs['gensym']}, builtin {refs['builtin']}, local {refs['local']}, expr {refs['expr']}, external {refs['external']}, "
          f"unknown-receiver {refs['unknown-receiver']}, not-code {refs['not-code']} files, unsupported {refs['unsupported']} files, NULL {refs['NULL']} → HSR {refs['NULL'] / judged if judged else float('nan'):.4f}")
    print(f"[§4.3] NULL by class: {dict(nulls)}")
    for r in null_rows:
        print(f"        {r['commit']} {r['hole']:8s} {r['path']}:{r['line']} `{r['term']}` {r['null_class']} nearest {r['nearest']}{' (declared)' if r['declared'] else ''}")
    print(f"[fills] attribution of the gold change blocks: {dict(sorted(attrib.items()))}")
    print(f"[edits] by type {dict(sorted(edits_by.items()))}; by placement {dict(sorted(placements.items()))}; outside the write partition {outside}; unfilled {unfilled}; refused {refused}; trace rows {trace_rows}")
    print("commit  files refs in-graph gensym NULL   HSR edits outside apply equal")
    for r in rows:
        hsr = "  -  " if r[6] is None else f"{r[6]:.3f}"
        print(f"{r[0]}  {r[1]:5d} {r[2]:4d} {r[3]:8d} {r[4]:6d} {r[5]:4d} {hsr} {r[7]:5d} {r[8]:7d} {'yes' if r[9] else 'NO ':>5} {'yes' if r[10] else 'NO ':>5} {r[11]}")
    return 0


def split_diff(diff: str) -> list[tuple[str, str]]:
    """A multi-file ``git diff`` as ``(path, one-file diff)`` pairs, keyed by the ``b/`` path, in the diff's order."""
    out = []
    for part in re.split(r"(?m)^(?=diff --git )", diff):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", part)
        if m:
            out.append((m.group(2), part))
    return out


def applies_at(repo: Path, sha: str, diff: str, paths: list[str]) -> tuple[bool, str]:
    """Whether *diff* applies to the parent's pre-images of *paths*, checked by ``git apply --check`` in a scratch tree — the repo is only read (``git show``), never checked out."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="calvin-apply-") as d:
        for p in paths:
            r = subprocess.run(["git", "show", f"{sha}:{p}"], cwd=repo, capture_output=True)
            if r.returncode == 0:
                (Path(d) / p).parent.mkdir(parents=True, exist_ok=True)
                (Path(d) / p).write_bytes(r.stdout)
        r = subprocess.run(["git", "apply", "--check", "-"], cwd=d, input=diff.encode("utf-8", "surrogateescape"), capture_output=True)
        return r.returncode == 0, r.stderr.decode(errors="replace").strip()[:200]


def load_go_units(path: Path, keys: list[str] | None) -> list[dict]:
    """WP-0's ``units.jsonl`` rows (Calvin M0-Go), optionally narrowed to key prefixes."""
    units = [json.loads(l) for l in open(path)]
    return [u for u in units if not keys or any(u["key"].startswith(k) for k in keys)]


def rta_sites(key_path: Path | None, label: str | None = None) -> dict | None:
    """The implementers an RTA key (``oracle go-rta``) names per repo interface method: every dynamic site whose ``interface`` is in-repo, its in-repo targets collected under the interface method's name — what rule 2 records, never binds."""
    if key_path is None:
        return None
    k = json.load(open(key_path))
    sites: dict[str, set[str]] = collections.defaultdict(set)
    for s in k["sites"]:
        i = s.get("interface")
        if i and not i.get("external"):
            sites[i["name"]].update(t["name"] for t in s["targets"] if not t.get("external"))
    return {"source": label or f"{k.get('oracle')} key {key_path}", "sites": {n: sorted(v) for n, v in sorted(sites.items())}}


def ground_unit(u: dict, repo: Path, tier: str = "A2", rta: dict | None = None) -> dict:
    """One M0-Go unit's gold run: the template at *tier* built at the parent, the gold diff (the generated file already split off) as fills, grounded twice, applied at the parent, and each post-image held against the commit."""
    from hobbes.derive import ground as G
    from hobbes.derive import template as T

    L = T.Ledger(json.load(open(u["parent_graph"])), json.load(open(u["parent_tests"])))
    assert L.sha == u["parent_sha"], (u["key"], L.sha)
    frozen = json.dumps(T.build_template(u[tier], L, repo, None))
    gold = split_diff(Path(u["gold_diff"]).read_text(errors="surrogateescape"))
    doc, counts = G.fills_from_diff(json.loads(frozen), gold, repo)
    g = G.ground(json.loads(frozen), doc, L, repo, rta=rta)
    again = G.ground(json.loads(frozen), doc, L, repo, rta=rta)
    ok, err = applies_at(repo, L.sha, g["diff"], [p for p, _ in gold])
    equal = {}
    for path, _ in gold:
        want = subprocess.run(["git", "show", f"{u['sha']}:{path}"], cwd=repo, capture_output=True, text=True, errors="surrogateescape").stdout
        equal[path] = g["post"].get(path) == want
    return {"template": json.loads(frozen), "fills": doc, "attribution": counts, "ground": g, "identical": g["output_hash"] == again["output_hash"] and g["trace"] == again["trace"],
            "applies": ok, "apply_error": err, "post_equal": equal}


def cmd_ground_units(a: argparse.Namespace) -> int:
    """Calvin M0-Go WP-3: every unit's gold diff grounded at its parent (step 3's exit on Go) — per key the diff, the references by class, the NULL list, the density counts and the output hash; ``rows.jsonl`` one row a key."""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(a.repo)
    rta = rta_sites(Path(a.rta_key) if a.rta_key else None, a.rta_label)
    rows = []
    refs = collections.Counter(); dens = collections.Counter(); nulls = 0
    for u in load_go_units(Path(a.units), a.keys):
        r = ground_unit(u, repo, a.tier, rta)
        g = r["ground"]
        k = u["key"]
        (out / f"{k}.template.json").write_text(json.dumps(r["template"], indent=1))
        (out / f"{k}.fills-gold.json").write_text(json.dumps(r["fills"], indent=1))
        (out / f"{k}.ground.json").write_text(json.dumps({"wp": a.wp, **g}, indent=1))
        (out / f"{k}.diff").write_text(g["diff"], errors="surrogateescape")
        row = {"wp": a.wp, "key": k, "shape": u["shape"], "parent_sha": u["parent_sha"], "W": u["W"], "tier": a.tier,
               "files": sorted(r["post_equal"]), "generated_excluded": bool(u.get("generated_diff")),
               "references": g["references"], "null": [{x: n[x] for x in ("hole", "path", "line", "term", "null_class", "nearest", "declared")} for n in g["null"]],
               "hsr": g["hsr"], "density": g.get("density", {}).get("counts"), "density_k": g.get("density", {}).get("k"),
               "output_hash": g["output_hash"], "identical_on_rerun": r["identical"], "applies": r["applies"], "apply_error": r["apply_error"],
               "post_equal": all(r["post_equal"].values()), "post_equal_by_file": r["post_equal"], "attribution": {x: v for x, v in r["attribution"].items() if x != "in_closed_at"},
               "unfilled": len(g["unfilled"]), "refused": len(g["refused"])}
        rows.append(row)
        refs.update(g["references"]); nulls += len(g["null"])
        dens.update(row["density"] or {})
        print(f"{k} {u['shape']:11s} refs {g['references']['total']:4d} in-graph {g['references']['in-graph']:3d} NULL {len(g['null'])} hsr {g['hsr']} "
              f"density {row['density']} rerun {'yes' if r['identical'] else 'NO'} apply {'yes' if r['applies'] else 'NO'} equal {'yes' if row['post_equal'] else 'NO'} {g['output_hash']}", flush=True)
        for n in g["null"]:
            print(f"      NULL {n['path']}:{n['line']} `{n['term']}` {n['null_class']} nearest {n['nearest']}")
        for x in g["refs"]:
            if x["class"] == "interface":
                print(f"      interface {x['path']}:{x['line']} `{x['term']}` → {x['target']} implementers {x.get('implementers')}")
    with open(out / "rows.jsonl", "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    n = len(rows)
    judged = refs["in-graph"] + refs["interface"] + refs["NULL"]
    print(f"units {n}: identical on rerun {sum(r['identical_on_rerun'] for r in rows)}/{n}; apply {sum(r['applies'] for r in rows)}/{n}; post-images equal {sum(r['post_equal'] for r in rows)}/{n}; "
          f"NULL {nulls}; HSR {refs['NULL'] / judged if judged else float('nan'):.4f}")
    print(f"references {dict(sorted(refs.items()))}")
    print(f"density {dict(sorted(dens.items()))}")
    return 0


POISON_INVENTED = "zqxFrobnicate"


def perturb_site(text: str, line: int, col: int, old: str, new: str) -> str:
    """*text* with the identifier *old* at ``line:col`` (1-based line, 0-based byte column — tree-sitter's) renamed *new*: that one site, nothing else."""
    lines = text.split("\n")
    raw = lines[line - 1].encode("utf-8", "surrogateescape")
    was = old.encode("utf-8", "surrogateescape")
    if raw[col: col + len(was)] != was:
        raise ValueError(f"{old!r} is not at {line}:{col}")
    lines[line - 1] = (raw[:col] + new.encode("utf-8", "surrogateescape") + raw[col + len(was):]).decode("utf-8", "surrogateescape")
    return "\n".join(lines)


def near_name(name: str, taken: set[str]) -> str:
    """A name two characters off *name* — two appended — that nothing in *taken* spells."""
    for tail in ("Zq", "Qz", "Zx", "Xz", "Qq"):
        if name + tail not in taken:
            return name + tail
    raise ValueError(name)


def poison_draw(ground_dir: Path, keys: list[str], n: int, seed: str) -> list[tuple[str, dict]]:
    """*n* in-graph Go call sites of a gold run, drawn round-robin over *keys* in order, each key's sites ordered by a seeded hash of (key, path, line, term)."""
    pools = {}
    for k in keys:
        g = json.load(open(ground_dir / f"{k}.ground.json"))
        sites = [r for r in g["refs"] if r["class"] == "in-graph" and r["path"].endswith(".go")]
        pools[k] = sorted(sites, key=lambda r: hashlib.sha256(f"{seed}:{k}:{r['path']}:{r['line']}:{r['term']}".encode()).hexdigest())
    picks: list[tuple[str, dict]] = []
    while len(picks) < n and any(pools.values()):
        for k in keys:
            if pools[k] and len(picks) < n:
                picks.append((k, pools[k].pop(0)))
    return picks


def cmd_poison(a: argparse.Namespace) -> int:
    """Calvin M0-Go WP-3's control (M0 step 3's, on Go): is the gold run's zero honest? Each of *n* drawn in-graph call sites renamed at that one site — to a name two characters off, then to an invented one — and its unit grounded again: exactly one NULL each, at the site, of the right class."""
    from hobbes.derive import ground as G
    from hobbes.derive import template as T
    from hobbes.extract import gosource

    units = {u["key"]: u for u in load_go_units(Path(a.units), None)}
    gdir, repo = Path(a.ground), Path(a.repo)
    rows = []
    for k, site in poison_draw(gdir, sorted(units), a.n, a.seed):
        u = units[k]
        L = T.Ledger(json.load(open(u["parent_graph"])), json.load(open(u["parent_tests"])))
        frozen = (gdir / f"{k}.template.json").read_text()
        g0 = json.load(open(gdir / f"{k}.ground.json"))
        gold = split_diff(Path(u["gold_diff"]).read_text(errors="surrogateescape"))
        path, post = site["path"], g0["post"][site["path"]]
        name = site["term"].rsplit(".", 1)[-1]
        call = min((c for c in gosource._parse_file(path, post.encode("utf-8", "surrogateescape")).calls if c["line"] == site["line"] and c["name"] == name), key=lambda c: c["col"])
        shape = "method (rule 1)" if L.symbols[site["target"]]["kind"] == "method" else "package-qualified" if "." in site["term"] else "bare"
        taken = set(L.by_name) | {s["name"] for p, t in g0["post"].items() if p.endswith(".go") for s in gosource._parse_file(p, t.encode("utf-8", "surrogateescape")).symbols}
        for want, new in (("near-miss", near_name(name, taken)), ("invented", POISON_INVENTED)):
            text = perturb_site(post, call["line"], call["col"], name, new)
            d = G.unified(path, G.file_at(repo, L.sha, path), G._lines(text))
            doc, _ = G.fills_from_diff(json.loads(frozen), [(p, d if p == path else x) for p, x in gold], repo)
            g = G.ground(json.loads(frozen), doc, L, repo)
            hit = g["null"][0] if len(g["null"]) == 1 else None
            right = hit is not None and hit["path"] == path and hit["line"] == site["line"] and hit["term"].rsplit(".", 1)[-1] == new and hit["null_class"] == want
            rows.append({"wp": a.wp, "key": k, "path": path, "line": site["line"], "term": site["term"], "target": site["target"], "shape": shape, "perturbed_to": new,
                         "want": want, "nulls": len(g["null"]), "null_class": hit["null_class"] if hit else [n["null_class"] for n in g["null"]], "right": right,
                         "nearest": hit["nearest"] if hit else None, "output_hash": g["output_hash"]})
            print(f"{k} {path}:{site['line']} `{site['term']}` ({shape}) → `{new}`: {len(g['null'])} NULL {rows[-1]['null_class']} {'right' if right else 'WRONG'}", flush=True)
    summary = {w: f"{sum(1 for r in rows if r['want'] == w and r['right'])}/{sum(1 for r in rows if r['want'] == w)}" for w in ("near-miss", "invented")}
    shapes = dict(collections.Counter(r["shape"] for r in rows if r["want"] == "near-miss"))
    per_key = dict(collections.Counter(r["key"] for r in rows if r["want"] == "near-miss"))
    Path(a.out).write_text(json.dumps({"wp": a.wp, "n": a.n, "seed": a.seed, "summary": summary, "shapes": shapes, "per_key": per_key, "rows": rows}, indent=1))
    print(f"poison: {summary}; sites by shape {shapes}; per key {per_key}")
    return 0


def cmd_t(a: argparse.Namespace) -> int:
    """Step 4's exit: arm T by hand for named commits against one endpoint — round 1, rebuild, round 2, ground, one NULL round-trip — every exchange recorded; the per-unit instruments printed."""
    from hobbes.agent.loop import Endpoint
    from hobbes.derive import adapter as A
    from hobbes.derive import cochange
    from hobbes.derive import template as T

    key = os.environ.get("HOBBES_LLM_API_KEY")
    if not key:
        print("HOBBES_LLM_API_KEY is not set (the adapter's endpoint decides which key)", file=sys.stderr)
        return 2
    graphs = Path(a.graphs)
    templates = Path(a.templates)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    cell, bycommit = load_units()
    props = {p["commit"]: p for p in load_proposals()}
    rows = []
    for c7 in a.commits:
        c = next(k for k in props if k.startswith(c7))
        p = props[c]
        L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
        t = json.load(open(templates / f"{c}.template.json"))
        subprocess.run(["git", "checkout", "-q", "--force", L.sha], cwd=clone, check=True)
        cc = cochange.observe(clone, 200)
        sampling = {"temperature": 0} if a.sampling == "greedy" else {}  # §3.3: temperature 0 where the endpoint honors it; Sonnet 5 rejects the field
        endpoint = Endpoint(a.base_url, a.model, key, timeout=a.timeout, max_tokens=a.max_tokens, sampling=sampling)
        adapter = A.Adapter(endpoint, a.model, max_tokens=a.max_tokens, max_prompt_chars=a.max_prompt_chars)
        t0 = time.time()
        rec = A.run_t(p["task"], t, L, repo, cc, adapter, null_loop=not a.no_loop)
        wall = time.time() - t0
        # gold: the commit (§3.1); the cell rows' paths are the unit's impact set for RFE
        files = [f for f in subprocess.run(["git", "show", "--name-only", "--format=", "--no-renames", c], cwd=clone, capture_output=True, text=True, check=True).stdout.split("\n") if f]
        gold = []
        for f in files:
            d = subprocess.run(["git", "show", "--format=", "--no-color", "--no-renames", c, "--", f], cwd=clone, capture_output=True, text=True, errors="surrogateescape", check=True).stdout
            if "GIT binary patch" not in d and not any(l.startswith("Binary files") for l in d.splitlines()[-1:]):
                gold.append((f, d))
        gold_files = {f for f, _ in gold}
        gold_ground = graphs.parent / "ground" / f"{c}.ground.json"
        gold_declared = set(json.load(open(gold_ground))["gensyms"]) if gold_ground.exists() else set()
        impact = set().union(*(set(u.get("paths") or []) for u in cell if u["commit"] == c))
        t2 = rec["template_round2"]
        g = rec.get("ground_after_loop") or rec["ground"]
        u1 = next((h for h in t2["holes"] if h["type"] == "UNRESOLVED"), None)
        agree = A.score_unresolved((u1 or {}).get("fill"), u1, L, gold_files, gold_declared) if u1 else {"n": 0, "agree": 0, "rows": []}
        cov = T.score_coverage(t2, gold)
        an = T.score_anchors(t2, L, gold)
        edited = {f["path"] for f in g["files"]}
        def jpr(ref):
            tp = len(edited & ref)
            return (round(tp / len(edited | ref), 2) if edited | ref else None, round(tp / len(edited), 2) if edited else None, round(tp / len(ref), 2) if ref else None)
        subprocess.run(["git", "checkout", "-q", "--force", L.sha], cwd=clone, check=True)
        ap = subprocess.run(["git", "apply", "--check", "-"], cwd=clone, input=g["diff"], capture_output=True, text=True)
        open_holes = [h for h in t2["holes"] if h.get("closed") is None and "fill" not in h]
        filled = sum(1 for h in open_holes if h["id"] in (rec["rounds"][-1]["fills"] or {}).get("fills", {}))
        row = {"commit": c[:7], "task": p["task"][:60], "anchors_r1": len(rec["template_round1"]["anchors"]), "anchors_r2": len(t2["anchors"]),
               "anchor_files": f"{an['files']['tp']}/{an['files']['anchored']} of {an['files']['gold']}",
               "unresolved": f"{agree['agree']}/{agree['n']}", "coverage": f"{cov['symbol']}/{cov['region']}/{cov['new_file']}/{cov['outside']} of {cov['hunks']}",
               "holes": f"{len(t2['holes'])}/{len(rec['ground']['closed_by_prune'])}/{filled}",
               "nulls": f"{len(rec['ground']['null'])} {rec['ground']['null_by_class']}",
               "loop": rec.get("loop"), "unfilled": len(g["unfilled"]), "refused": len(g["refused"]), "edits": len(g["edits"]), "outside": g["outside_partition"],
               "applies": ap.returncode == 0, "rfe_gold": jpr(gold_files), "rfe_impact": jpr(impact), "hsr": g["hsr"],
               "exchanges": len(rec["exchanges"]), "tokens": rec["tokens"], "wall_s": round(wall, 1),
               "repairs": sum(1 for e in rec["exchanges"] if e["purpose"].endswith("(repair)")), "invalid_after_repair": sum(1 for r in rec["rounds"] if r["errors"])}
        rec["endpoint"] = {"base_url": a.base_url, "model": a.model, "sampling": sampling, "max_tokens": a.max_tokens, "max_prompt_chars": a.max_prompt_chars}
        rec["instruments"] = {**row, "unresolved_rows": agree["rows"], "coverage": cov, "anchors": an}
        (out / f"{c}.t.json").write_text(json.dumps(rec, indent=1))
        (out / f"{c}.t.diff").write_text(g["diff"])
        if "ground_after_loop" in rec:  # arm T's own diff beside T-loop's, so both arms verify from the record (§3.2)
            (out / f"{c}.t0.diff").write_text(rec["ground"]["diff"])
        with open(out / f"{c}.exchanges.jsonl", "w") as fh:
            for e in rec["exchanges"]:
                fh.write(json.dumps(e) + "\n")
        rows.append(row)
        print(json.dumps(row))
    print("commit  anchors r1→r2  files(anchored/gold)  unresolved agree  coverage sym/reg/new/out  holes gen/pruned/filled  NULL  loop  applies  RFE gold J/P/R  RFE impact J/P/R  exch  tokens in/out  wall")
    for r in rows:
        lp = "-" if not r["loop"] else f"{r['loop']['nulls_before']}→{r['loop']['nulls_after']}"
        print(f"{r['commit']}  {r['anchors_r1']:2d}→{r['anchors_r2']:<2d}  {r['anchor_files']:>12s}  {r['unresolved']:>8s}  {r['coverage']:>20s}  {r['holes']:>14s}  {r['nulls'][:2]:>4s}  {lp:>5s}  {'yes' if r['applies'] else 'NO':>5s}  "
              f"{str(r['rfe_gold']):>18s}  {str(r['rfe_impact']):>18s}  {r['exchanges']:4d}  {r['tokens']['prompt']:6d}/{r['tokens']['completion']:<5d}  {r['wall_s']:5.0f}s")
    return 0


# ------------------------------------------------ Calvin M0-Go WP-5: arm T on units.jsonl, metered

#: $ per MTok (in, out): claude-haiku-4-5 at list, the price M0-Go WP-4 estimated with.
PRICE_HAIKU_45 = (1.0, 5.0)


class BudgetStop(RuntimeError):
    """A metered endpoint refused a call: the spend so far plus the call's worst case would pass the cap."""


def usd(prompt_tokens: int | None, completion_tokens: int | None, price: tuple[float, float] = PRICE_HAIKU_45) -> float:
    """Dollars for one exchange from the endpoint's returned token counts at *price* ($ per MTok in, out)."""
    return (prompt_tokens or 0) / 1e6 * price[0] + (completion_tokens or 0) / 1e6 * price[1]


class Metered:
    """An endpoint under a dollar cap (M0-Go WP-5's spend rule). Before a call, the spend so far plus the call's worst case — its characters
    at *chars_per_token* and all of ``max_tokens`` written — must fit under *cap_usd*, else the call is not made (`BudgetStop`). After it,
    the returned counts are priced and one JSON line is appended to *ledger*, so a killed run still says what it spent."""

    def __init__(self, endpoint, cap_usd: float, ledger: Path | None = None, price: tuple[float, float] = PRICE_HAIKU_45, chars_per_token: float = 1.9):
        self.endpoint, self.cap_usd, self.ledger, self.price, self.cpt = endpoint, cap_usd, ledger, price, chars_per_token
        self.spent = 0.0
        self.calls = 0

    def chat(self, messages: list[dict], tools: list[dict], max_tokens: int | None = None) -> dict:
        out_cap = max_tokens or getattr(self.endpoint, "max_tokens", 0)
        worst = usd(int(sum(len(m.get("content") or "") for m in messages) / self.cpt), out_cap, self.price)
        if self.spent + worst > self.cap_usd:
            raise BudgetStop(f"spent ${self.spent:.4f}; the next call's worst case ${worst:.4f} would pass the ${self.cap_usd:.2f} cap")
        reply = self.endpoint.chat(messages, tools, max_tokens)
        u = reply.get("usage") or {}
        cost = usd(u.get("prompt_tokens"), u.get("completion_tokens"), self.price)
        self.spent += cost
        self.calls += 1
        if self.ledger is not None:
            with open(self.ledger, "a") as fh:
                fh.write(json.dumps({"call": self.calls, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "prompt_tokens": u.get("prompt_tokens"),
                                     "completion_tokens": u.get("completion_tokens"), "finish_reason": (reply.get("choices") or [{}])[0].get("finish_reason"),
                                     "usd": round(cost, 6), "spent_usd": round(self.spent, 6)}) + "\n")
        return reply


def spent_in(d: Path) -> float:
    """Dollars every ``*.usage.jsonl`` ledger under *d* records: what earlier processes of the round spent."""
    return sum(json.loads(l)["usd"] for f in sorted(Path(d).glob("*.usage.jsonl")) for l in open(f) if l.strip())


def estimate_by_key(path: Path) -> dict:
    """WP-4's expected-band dollars per key and arm (one run), with their sum: the figure a key's actual is read against."""
    out: dict = {}
    for r in json.load(open(path))["rows"]:
        if r.get("band") == "exp" and r.get("arm") in ("T", "T-loop"):
            out.setdefault(r["key"], {})[r["arm"]] = r["per_run"]["usd"]
    for v in out.values():
        v["total"] = round(sum(v.values()), 4)
    return out


def key_from(path: Path, name: str) -> str:
    """The value of one ``name=value`` line in the owner's key file — read, never printed. The file may hold names `hobbes.bench.secrets`
    does not know (M0's endpoint key is one), which that reader refuses whole."""
    for line in Path(path).read_text().splitlines():
        n, sep, v = line.strip().partition("=")
        if sep and not n.startswith("#") and n.strip() == name and v.strip().strip('"').strip("'"):
            return v.strip().strip('"').strip("'")
    raise KeyError(f"no {name!r} line in the key file")


def confirmations(rec: dict) -> dict:
    """Round 1's ANCHOR_CONFIRMs over every pass — asked, yes, no, unanswered — with template v2's capped callees counted apart (``capped_``)."""
    idx = {h["id"]: h for t in (rec["template_round1"], rec["template_round2"]) for h in t["holes"]}
    out: collections.Counter = collections.Counter()
    for r in rec["rounds"]:
        if not str(r["round"]).startswith("1"):
            continue
        fills = (r.get("fills") or {}).get("fills") or {}
        for hid in r["holes_asked"]:
            h = idx.get(hid) or {}
            if h.get("type") != "ANCHOR_CONFIRM":
                continue
            pre = "capped_" if "callee_of" in (h.get("provenance") or {}) else ""
            f = fills.get(hid)
            out[pre + "asked"] += 1
            out[pre + ("unanswered" if f is None else "yes" if isinstance(f, dict) and f.get("confirm") is True else "no")] += 1
    return dict(out)


def changed_files(diff: str) -> list[str]:
    """The paths a unified diff changes, from its ``---``/``+++`` headers (a created file by its ``b/`` side, a deleted one by its ``a/``
    side). A file the grounder wrote back byte for byte has no hunk and is not among them — the grounder's ``files`` list counts it."""
    out = set()
    for m in re.finditer(r"(?m)^--- (?:a/(.+)|/dev/null)\n\+\+\+ (?:b/(.+)|/dev/null)$", diff):
        out.add(m.group(2) or m.group(1))
    return sorted(out)


def _write_exchanges(path: Path, exchanges: list[dict]) -> None:
    with open(path, "w") as fh:
        for e in exchanges:
            fh.write(json.dumps(e) + "\n")


def cmd_t_units(a: argparse.Namespace) -> int:
    """Calvin M0-Go WP-5: arm T by hand on units.jsonl keys — the stored template checked to rebuild at the parent from the tier's task,
    round 1 → rebuild → round 2 → ground (with the RTA key) → one NULL round-trip, every exchange recorded and metered. Per key: the record,
    the exchanges, the fills, the grounded diffs, the NULL list with class and density, the meter's ledger and (``--verify``) the verifier's
    records; one row a key in ``rows.jsonl``. A call the cap refuses stops the run with the exchanges so far written (exit 4)."""
    from hobbes.agent.loop import Endpoint
    from hobbes.derive import adapter as A
    from hobbes.derive import cochange
    from hobbes.derive import harness as HV
    from hobbes.derive import template as T

    key = os.environ.get("HOBBES_LLM_API_KEY") or (key_from(Path(a.secrets), a.key_name) if a.secrets else None)
    if not key:
        print("no key: set HOBBES_LLM_API_KEY or pass --secrets", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(a.repo)
    rta = rta_sites(Path(a.rta_key) if a.rta_key else None, a.rta_label)
    est = estimate_by_key(Path(a.estimate)) if a.estimate else {}
    sampling = {"temperature": 0} if a.sampling == "greedy" else {}
    for u in load_go_units(Path(a.units), a.keys):
        k = u["key"]
        L = T.Ledger(json.load(open(u["parent_graph"])), json.load(open(u["parent_tests"])))
        assert L.sha == u["parent_sha"], (k, L.sha)
        t = json.load(open(Path(a.templates) / f"{k}.template.json"))
        subprocess.run(["git", "checkout", "-q", "--force", L.sha], cwd=repo, check=True)
        cc = cochange.observe(repo, 200)
        task = u[a.tier]
        if T.canonical(T.build_template(task, L, repo, cc, version=t.get("template_version", 1))) != T.canonical(t):
            print(f"{k}: the stored template does not rebuild at the parent from {a.tier}; the inputs differ, refusing", file=sys.stderr)
            return 3
        spent = spent_in(out)
        cap = min(a.key_cap, a.total_cap - spent)
        meter = Metered(Endpoint(a.base_url, a.model, key, timeout=a.timeout, max_tokens=a.max_tokens, sampling=sampling), cap, out / f"{k}.usage.jsonl")
        adapter = A.Adapter(meter, a.model, max_tokens=a.max_tokens, max_prompt_chars=a.max_prompt_chars)
        endpoint_rec = {"base_url": a.base_url, "model": a.model, "sampling": sampling, "max_tokens": a.max_tokens, "max_prompt_chars": a.max_prompt_chars,
                        "cap_usd": round(cap, 4), "spent_before_usd": round(spent, 4)}
        t0 = time.time()
        try:
            rec = A.run_t(task, t, L, repo, cc, adapter, null_loop=not a.no_loop, rta=rta)
        except Exception as exc:  # the spend so far is written before anything else is said
            _write_exchanges(out / f"{k}.exchanges.jsonl", adapter.exchanges)
            row = {"wp": a.wp, "key": k, "shape": u["shape"], "stopped": f"{type(exc).__name__}: {exc}", "exchanges": len(adapter.exchanges),
                   "usd": round(meter.spent, 4), "estimate_usd": est.get(k), "endpoint": endpoint_rec}
            (out / f"{k}.stopped.json").write_text(json.dumps(row, indent=1))
            with open(out / "rows.jsonl", "a") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"{k}: STOPPED after {len(adapter.exchanges)} exchanges, ${meter.spent:.4f}: {type(exc).__name__}: {exc}", flush=True)
            return 4 if isinstance(exc, BudgetStop) else 5
        wall = time.time() - t0
        rec["endpoint"] = endpoint_rec
        (out / f"{k}.t.json").write_text(json.dumps(rec, indent=1))  # the paid record first; the instruments are added below
        ex = rec["exchanges"]
        _write_exchanges(out / f"{k}.exchanges.jsonl", ex)
        t2, g0 = rec["template_round2"], rec["ground"]
        g = rec.get("ground_after_loop") or g0
        null_rows = lambda gr: [{x: n.get(x) for x in ("hole", "path", "line", "term", "null_class", "density", "refs_in", "nearest", "declared")} for n in gr["null"]]
        (out / f"{k}.fills.json").write_text(json.dumps({"wp": a.wp, "key": k, "rounds": [{x: r.get(x) for x in ("round", "holes_asked", "fills", "errors", "unanswered_confirmations")}
                                                                                        for r in rec["rounds"]]}, indent=1))
        (out / f"{k}.null.json").write_text(json.dumps({"wp": a.wp, "key": k, "T": null_rows(g0), "T-loop": null_rows(g) if "ground_after_loop" in rec else None,
                                                        "loop": rec.get("loop"), "density": g["density"]}, indent=1))
        diffs = {"t0": g0, "t": g} if "ground_after_loop" in rec else {"t": g}  # M0's names: .t.diff is the final diff, .t0.diff T's own before the loop
        for name, gr in diffs.items():
            (out / f"{k}.{name}.diff").write_text(gr["diff"], errors="surrogateescape")
        applies = {name: (applies_at(repo, L.sha, gr["diff"], [f["path"] for f in gr["files"]])[0] if gr["diff"] else None) for name, gr in diffs.items()}
        verdicts = {}
        if a.verify:
            for name, gr in diffs.items():
                v = HV.verify(repo, L.sha, gr["diff"], L, repo, out=out / f"{k}.{name}.verify.json", timeout=a.verify_timeout)
                verdicts[name] = {"verdict": v["verdict"], "applies": v["applies"], "summary": v.get("summary"), "build_summary": v.get("build_summary"),
                                  "regressions": v.get("regressions"), "faults": len(v.get("faults", [])),
                                  "all_contained": (v.get("containment") or {}).get("all_contained"), "wall_s": v["wall_s"]}
        gold = split_diff(Path(u["gold_diff"]).read_text(errors="surrogateescape"))
        gold_files = {p for p, _ in gold}
        gg = Path(a.gold_ground) / f"{k}.ground.json" if a.gold_ground else None
        gold_declared = set(json.load(open(gg))["gensyms"]) if gg and gg.exists() else set()
        u1 = next((h for h in t2["holes"] if h["type"] == "UNRESOLVED"), None)
        agree = A.score_unresolved(u1.get("fill"), u1, L, gold_files, gold_declared) if u1 else {"n": 0, "agree": 0, "rows": []}
        cov = T.score_coverage(t2, gold)
        an = T.score_anchors(t2, L, gold)
        r2 = next(r for r in rec["rounds"] if r["round"] == 2)
        filled = sum(1 for hid in r2["holes_asked"] if hid in ((r2["fills"] or {}).get("fills") or {}))
        loop_ex = [e for e in ex if e["purpose"].startswith("NULL")]
        cost = lambda es: round(sum(usd(e.get("prompt_tokens"), e.get("completion_tokens")) for e in es), 4)
        row = {"wp": a.wp, "key": k, "shape": u["shape"], "parent_sha": u["parent_sha"], "W": u["W"], "tier": a.tier, "a2_rev": u.get("a2_rev"),
               "template_version": t.get("template_version"), "template_rebuilds": True, "model": a.model, "sampling": sampling,
               "system_prompt_version": A.SYSTEM_PROMPT_VERSION, "protocol_version": A.PROTOCOL_VERSION, "grounder_version": g["grounder_version"], "rta": g.get("rta"),
               "by_pattern": dict(collections.Counter(typ for r in rec["rounds"] for typ in ((r.get("fills") or {}).get("by_pattern") or {}).values())),
               "anchors": f"{len(t['anchors'])}→{len(t2['anchors'])}", "anchor_files": f"{an['files']['tp']}/{an['files']['anchored']} of {an['files']['gold']}",
               "unresolved": f"{agree['agree']}/{agree['n']}", "confirmations": confirmations(rec),
               "coverage": f"{cov['symbol']}/{cov['region']}/{cov['new_file']}/{cov['outside']} of {cov['hunks']}",
               "holes": f"{len(t2['holes'])}/{len(g0['closed_by_prune'])}/{filled}", "round2_open": len(r2["holes_asked"]),
               "null_T": null_rows(g0), "null": null_rows(g), "null_by_class": g["null_by_class"], "loop": rec.get("loop"),
               "density": g["density"]["counts"], "density_k": g["density"]["k"], "references": g["references"],
               "unfilled": len(g["unfilled"]), "refused": len(g["refused"]), "edits": len(g["edits"]),
               "files": sorted(f["path"] for f in g["files"]), "created": sorted(f["path"] for f in g["files"] if f["created"]), "outside_partition": g["outside_partition"],
               "files_changed": changed_files(g["diff"]), "applies": applies,
               "rfe_gold": _jpr({f["path"] for f in g["files"]}, gold_files), "rfe_gold_T": _jpr({f["path"] for f in g0["files"]}, gold_files),
               "rfe_changed": _jpr(set(changed_files(g["diff"])), gold_files), "rfe_changed_T": _jpr(set(changed_files(g0["diff"])), gold_files),
               "hsr": g["hsr"], "hsr_T": g0["hsr"], "verify": {"T": verdicts.get("t0", verdicts.get("t")), "T-loop": verdicts.get("t")},
               "rounds": [r["round"] for r in rec["rounds"]], "exchanges": len(ex), "repairs": sum(1 for e in ex if e["purpose"].endswith("(repair)")),
               "cut_at_length": sum(1 for e in ex if e.get("finish_reason") == "length"),
               "invalid_after_repair": [{"round": r["round"], "holes": len(r["errors"]), "first": sorted(r["errors"].items())[0]} for r in rec["rounds"] if r["errors"]],
               "tokens": rec["tokens"], "usd": cost(ex), "usd_T": cost([e for e in ex if e not in loop_ex]), "usd_loop": cost(loop_ex),
               "estimate_usd": est.get(k), "wall_s": round(wall, 1), "attribution": None}
        rec["instruments"] = {**row, "unresolved_rows": agree["rows"], "coverage": cov, "anchors": an}
        (out / f"{k}.t.json").write_text(json.dumps(rec, indent=1))
        with open(out / "rows.jsonl", "a") as fh:
            fh.write(json.dumps(row) + "\n")
        vt = {n: (x or {}).get("verdict") for n, x in row["verify"].items()}
        print(f"{k} {u['shape']:11s} anchors {row['anchors']} files {row['anchor_files']} conf {row['confirmations']} holes {row['holes']} "
              f"NULL {len(g0['null'])}→{len(g['null'])} edits {row['edits']}/{len(row['files'])} RFE {_fmt(row['rfe_gold'])} verify {vt} "
              f"exch {row['exchanges']} repairs {row['repairs']} cut {row['cut_at_length']} tokens {rec['tokens']['prompt']}/{rec['tokens']['completion']} "
              f"${row['usd']} (est ${(row['estimate_usd'] or {}).get('total')}) {row['wall_s']}s", flush=True)
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    """Step 5: the behaviour verifier over a directory of diffs at their parents — the gold diffs as the calibration (every gold should pass), arm T's records as the candidates."""
    from hobbes.derive import harness as H
    from hobbes.derive import template as T

    graphs = Path(a.graphs)
    diffs = Path(a.diffs) if a.diffs else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    props = {p["commit"]: p for p in load_proposals()}
    commits = [next(k for k in props if k.startswith(c)) for c in a.commits] if a.commits else sorted(props)
    rows = []
    totals = collections.Counter(); verdicts = collections.Counter(); origins = collections.Counter(); grains = collections.Counter(); fws = collections.Counter()
    wall = 0.0
    for c in commits:
        if a.rescore:  # the classes re-read off an earlier run's rows, into --out (never in place)
            src = Path(a.rescore) / f"{c}.verify.json"
            if not src.exists():
                continue
            rec = H.score(json.load(open(src)))
            (out / f"{c}.verify.json").write_text(json.dumps(rec, indent=1))
        else:
            path = diffs / f"{c}{a.suffix}"
            if not path.exists():
                print(f"{c[:7]}  (no {path.name})")
                continue
            diff = path.read_text(errors="surrogateescape")
            L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
            rec = H.verify(clone, L.sha, diff, L, repo, out=out / f"{c}.verify.json", baseline=not a.no_baseline, timeout=a.timeout)
        wall += rec["wall_s"]
        sel = rec.get("selection", {})
        verdicts[rec["verdict"]] += 1
        totals.update(rec.get("summary", {}))
        origins.update(sel.get("by_origin", {})); grains.update(sel.get("by_grain", {})); fws.update(sel.get("by_framework", {}))
        row = (c[:7], rec["verdict"], rec["applies"], len(rec.get("tests", [])), rec.get("summary", {}), len(rec.get("regressions", [])),
               (rec.get("containment") or {}).get("all_contained"), rec["wall_s"], len(rec.get("commands", [])))
        rows.append(row)
        bad = [r for r in rec.get("tests", []) if r["class"] not in ("P2P", "new-pass", "skip")]
        print(f"{c[:7]}  {rec['verdict']:11s} applies {str(rec['applies']):5s} tests {row[3]:4d} {row[4]} regressions {row[5]} faults {len(rec.get('faults', []))} contained {row[6]} cmds {row[8]} {rec['wall_s']:6.1f}s", flush=True)
        for r in bad[:12]:
            print(f"          {r['class']:8s} {r['id']} (with {r['candidate']}, without {r['baseline']}){' — ' + r['note'][:120] if r.get('note') else ''}")
        for cr in rec.get("commands", []):
            if cr.get("rc") not in (0, None) and cr.get("stderr_tail"):
                print(f"          rc {cr['rc']} {cr['framework']} {' '.join(cr['argv'])[:100]}: {cr['stderr_tail'][-200:]!r}")
    n = len(rows)
    print(f"verified {n} diffs at their parents: verdicts {dict(verdicts)}; tests by class {dict(totals)}; selection by origin {dict(origins)}, by grain {dict(grains)}, by framework {dict(fws)}; wall {wall:.0f}s")
    return 0


def cmd_replay(a: argparse.Namespace) -> int:
    """Step 6b, exercised with no model: a recorded arm-T run's round-1 answers replayed into a later template set (v1) and rebuilt — what round 2 would have
    been asked. ``--mode gold`` confirms a symbol iff the gold diff edits it; ``--mode max`` confirms every symbol of a module the run confirmed. Prints the
    rebuilt template's holes by type, its TEST_EXPECTATIONs by tier, whether the tests in the gold's own test files are among them, and §4.1 coverage."""
    from hobbes.derive import cochange
    from hobbes.derive import template as T

    graphs = Path(a.graphs)
    templates = Path(a.templates)
    records = Path(a.t)
    diffs = Path(a.diffs) if a.diffs else graphs.parent / "ground"
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    _, bycommit = load_units()
    props = {p["commit"]: p for p in load_proposals()}
    for c7 in a.commits:
        c = next(k for k in props if k.startswith(c7))
        rec_path = records / f"{c}.t.json"
        if not rec_path.exists():
            print(f"{c[:7]}  (no {rec_path.name})")
            continue
        rec = json.load(open(rec_path))
        L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
        t1 = json.load(open(templates / f"{c}.template.json"))
        gold = (diffs / f"{c}.diff").read_text(errors="surrogateescape")
        ranges = hunks_by_file(gold)
        gold_test_files = {p for p in ranges if p in {t["file"] for t in L.tests}}
        subprocess.run(["git", "checkout", "-q", "--force", L.sha], cwd=clone, check=True)
        cc = cochange.observe(clone, 200)

        def edits(sid: str) -> bool:
            sp = L.span(sid)
            return any(not (b < sp["start"] or x > sp["end"]) for x, b in ranges.get(sp["path"], []))

        asked = sum(1 for h in t1["holes"] if h["type"] == "ANCHOR_CONFIRM")
        for mode in a.mode:
            fills, yes = replay_fills(t1, rec, mode, edits)
            t2 = T.apply_round1(props[c]["task"], L, repo, cc, t1, fills)
            by = collections.Counter(h["type"] for h in t2["holes"])
            tests = {h["provenance"]["test"]: h["provenance"]["tier"] for h in t2["holes"] if h["type"] == "TEST_EXPECTATION"}
            tiers = collections.Counter(tests.values())
            in_gold_files = collections.Counter(tests[t] for t in tests if t.split("::")[0] in gold_test_files)
            cov = T.score_coverage(t2, [(r["id"].split(":", 1)[1], r["gold_diff"]) for r in bycommit[c]])
            print(f"{c[:7]}  {mode:4s} confirmed {yes}/{asked} -> {len(t2['holes'])} holes {dict(sorted(by.items()))}")
            print(f"          TEST_EXPECTATION by tier {dict(tiers)}; in the gold's own test files {dict(in_gold_files)} of {sum(1 for t in L.tests if t['file'] in gold_test_files)} there; "
                  f"coverage {cov}; write partition {len(t2['constraints']['write_partition'])} files")
            if a.show_tests:
                for t in sorted(tests):
                    if t.split("::")[0] in gold_test_files:
                        print(f"            {tests[t]:7s} {t}")
    return 0


def cmd_o(a: argparse.Namespace) -> int:
    """Step 5's other half: arm O on the local harness — one `hobbes-session` per commit at its parent with policy-checked exec, the patch grounded and verified; `--scripted` plays a JSON script in place of the model."""
    from hobbes.derive import harness as H
    from hobbes.derive import template as T

    graphs = Path(a.graphs)
    templates = Path(a.templates)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    session_bin = a.session_bin or os.environ.get("HOBBES_SESSION_BIN") or str(repo / "go" / "bin" / "hobbes-session")
    props = {p["commit"]: p for p in load_proposals()}
    sessions_root = Path(a.sessions) if a.sessions else Path.home() / ".hobbes" / "sessions"
    if a.scripted:
        runtime, base_url, model = Path(__file__).resolve().parent / "calvin_scripted_agent.py", "http://scripted.invalid/v1", "scripted"
    else:
        if not os.environ.get("HOBBES_LLM_API_KEY"):
            print("HOBBES_LLM_API_KEY is not set", file=sys.stderr)
            return 2
        runtime, base_url, model = H.LOOP_PATH, a.base_url, a.model
    for c7 in a.commits:
        c = next(k for k in props if k.startswith(c7))
        L = T.Ledger(json.load(open(graphs / f"{c}.json")), json.load(open(graphs / f"{c}.tests.json")))
        t = json.load(open(templates / f"{c}.template.json")) if (templates / f"{c}.template.json").exists() else None
        session_id = f"calvin-o-{c[:7]}-{time.strftime('%Y%m%dT%H%M%S')}"
        loop_args = list(a.loop_arg or [])
        if a.scripted:
            (sessions_root / session_id).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(a.scripted, sessions_root / session_id / "script.json")
            loop_args.append(f"--script=/sessions/{session_id}/script.json")
        rec = H.run_o(clone, L.sha, props[c]["task"], L, repo, (graphs / f"{c}.json", graphs / f"{c}.tests.json"), session_bin=session_bin, base_url=base_url, model=model,
                      session_id=session_id, sessions_root=sessions_root, out_dir=out, template=t, timeout=a.timeout, dry_run=a.dry_run, runtime=runtime,
                      max_turns=a.max_turns, max_tokens=a.max_tokens, loop_args=loop_args, knowledge=a.knowledge,
                      **({"token_budget": a.token_budget} if a.token_budget is not None else {}))
        if a.dry_run:
            print(" ".join(rec["command"]))
            print(json.dumps({k: rec[k] for k in ("plan", "brief_chars")}, indent=1))
            continue
        v = rec.get("verify") or {}
        print(json.dumps({"commit": c[:7], "session": session_id, "rc": rec.get("session_rc"), "wall_s": rec.get("wall_s"), "plan": rec["plan"], "patch_files": rec["patch_files"],
                          "ground": rec.get("ground"), "verify": {k: v.get(k) for k in ("verdict", "applies", "summary", "regressions")} if v else None}, indent=1))
        if rec.get("session_stderr_tail"):
            print(rec["session_stderr_tail"][-800:])
    return 0


def _gold_files(clone: Path, c: str) -> set[str]:
    return {f for f in subprocess.run(["git", "show", "--name-only", "--format=", "--no-renames", c], cwd=clone, capture_output=True, text=True, check=True).stdout.split("\n") if f}


def _jpr(edited: set[str], gold: set[str]) -> tuple:
    tp = len(edited & gold)
    return (round(tp / len(edited | gold), 2) if edited | gold else None, round(tp / len(edited), 2) if edited else None, round(tp / len(gold), 2) if gold else None)


def cmd_rows(a: argparse.Namespace) -> int:
    """Step 6's per-task record (§5): one row per unit per arm from the T, T-loop and O records and their verify records — every instrument before any aggregate; the aggregates last, over keys."""
    graphs = Path(a.graphs)
    clone = Path(a.clone) if a.clone else graphs.parent / "rebase-clone"
    props = {p["commit"]: p for p in load_proposals()}
    commits = [next(k for k in props if k.startswith(c7)) for c7 in a.commits] if a.commits else sorted(props)
    tdir, odir = Path(a.t), Path(a.o)
    vt, vt0, out = Path(a.verify_t), Path(a.verify_t0) if a.verify_t0 else None, Path(a.out)
    rows = []
    for c in commits:
        gold = _gold_files(clone, c)
        row: dict = {"unit": c[:7], "parent": None, "task": props[c]["task"][:80], "gold_files": len(gold), "arms": {}}
        tf = tdir / f"{c}.t.json"
        if tf.exists():
            r = json.load(open(tf)); i = r["instruments"]
            row["parent"] = r["key"]["parent_sha"][:12]
            g0, g1 = r["ground"], r.get("ground_after_loop")
            def arm_t(g, vfile, name, tokens=None):
                v = json.load(open(vfile)) if vfile and vfile.exists() else {}
                edited = {f["path"] for f in g["files"]}
                cov = i["coverage"] if isinstance(i["coverage"], str) else f"{i['coverage']['symbol']}/{i['coverage']['region']}/{i['coverage']['new_file']}/{i['coverage']['outside']} of {i['coverage']['hunks']}"
                return {"arm": name, "anchors": f"{i['anchors_r1']}→{i['anchors_r2']}", "anchor_files": i["anchor_files"], "unresolved": i["unresolved"], "coverage": cov,
                        "holes": i["holes"], "nulls": len(g["null"]), "null_by_class": g["null_by_class"], "loop": r.get("loop") if name == "T-loop" else None,
                        "edits": len(g["edits"]), "files": sorted(edited), "applies": v.get("applies"), "verdict": v.get("verdict"), "tests": v.get("summary"), "regressions": v.get("regressions"),
                        "rfe": _jpr(edited, gold), "hsr": g["hsr"], "exchanges": i["exchanges"], "tokens": tokens or r["tokens"], "wall_s": i["wall_s"], "rounds": [x["round"] for x in r["rounds"]]}
            if g1 is not None:
                loop_ex = [e for e in r["exchanges"] if e["purpose"].startswith("NULL")]
                t_tokens = {"prompt": r["tokens"]["prompt"] - sum(e.get("prompt_tokens") or 0 for e in loop_ex), "completion": r["tokens"]["completion"] - sum(e.get("completion_tokens") or 0 for e in loop_ex)}
                row["arms"]["T"] = arm_t(g0, (vt0 / f"{c}.verify.json") if vt0 else None, "T", t_tokens)
                row["arms"]["T-loop"] = arm_t(g1, vt / f"{c}.verify.json", "T-loop")
            else:
                row["arms"]["T"] = arm_t(g0, vt / f"{c}.verify.json", "T")
                row["arms"]["T-loop"] = {**row["arms"]["T"], "arm": "T-loop", "loop": None, "note": "no NULL: T-loop = T"}
        ofs = sorted(odir.glob(f"calvin-o-{c[:7]}-*.o.json"))
        if ofs:
            r = json.load(open(ofs[-1]))
            v = r.get("verify") or {}
            sdir = Path(r["transcript"]).parent if r.get("transcript") else None
            calls = [json.loads(l) for l in open(sdir / "calls.jsonl")] if sdir and (sdir / "calls.jsonl").exists() else []
            tokens = {"prompt": sum(x.get("prompt_tokens") or 0 for x in calls), "completion": sum(x.get("completion_tokens") or 0 for x in calls)}
            env = {}
            log = ofs[-1].with_name(ofs[-1].name.replace(".o.json", ".session.log"))
            if log.exists():
                for line in open(log, errors="replace"):
                    if line.startswith('{"type": "result"'):
                        try:
                            env = json.loads(line)
                        except ValueError:
                            pass
            g = r.get("ground") or {}
            edited = set(r["patch_files"])
            row["arms"]["O"] = {"arm": "O", "session": r["session"], "plan_units": len(r["plan"]["units"]), "plan_paths": r["plan"]["paths"], "plan_rfe": _jpr(set(r["plan"]["paths"]), gold),
                                "refusal": r["plan"]["refusal"], "turns": env.get("num_turns"), "tool_calls": env.get("tool_calls"), "edited": env.get("edited"), "stop": env.get("result") if env.get("is_error") else "done",
                                "files": sorted(edited), "applies": v.get("applies"), "verdict": v.get("verdict"), "tests": v.get("summary"), "regressions": v.get("regressions"),
                                "rfe": _jpr(edited, gold), "hsr": g.get("hsr"), "null_by_class": g.get("null_by_class"), "tokens": tokens, "wall_s": r.get("wall_s"), "rc": r.get("session_rc")}
        rows.append(row)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    # the table, one line per unit per arm
    print("| unit | arm | anchors | unres | coverage sym/reg/new/out | holes gen/pruned/filled | NULL | loop | edits/files | applies | verdict (tests) | RFE J/P/R | HSR | tokens in/out | wall |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        for name in ("T", "T-loop", "O"):
            x = row["arms"].get(name)
            if not x:
                continue
            lp = "-" if not x.get("loop") else f"{x['loop']['nulls_before']}→{x['loop']['nulls_after']}"
            tests = x.get("tests") or {}
            tv = f"{x.get('verdict') or '—'}" + (f" ({', '.join(f'{k} {v}' for k, v in sorted(tests.items()))})" if tests else "")
            if name == "O":
                print(f"| {row['unit']} | O | plan {x['plan_units']}u {_fmt(x['plan_rfe'])} | — | — | turns {x.get('turns')}, {x.get('stop')} | {x.get('null_by_class') or '—'} | — | {len(x['files'])} files | {x.get('applies')} | {tv} | {_fmt(x['rfe'])} | {x.get('hsr')} | {x['tokens']['prompt'] // 1000}k / {x['tokens']['completion'] // 1000}k | {x.get('wall_s')} s |")
            else:
                print(f"| {row['unit']} | {name} | {x['anchors']} {x['anchor_files']} | {x['unresolved']} | {x['coverage']} | {x['holes']} | {x['nulls']} {x['null_by_class'] or ''} | {lp} | {x['edits']}/{len(x['files'])} | {x.get('applies')} | {tv} | {_fmt(x['rfe'])} | {x['hsr']} | {x['tokens']['prompt'] // 1000}k / {x['tokens']['completion'] // 1000}k | {x['wall_s']} s |")
    # aggregates over keys, last
    print()
    for name in ("T", "T-loop", "O"):
        xs = [row["arms"][name] for row in rows if name in row["arms"]]
        if not xs:
            continue
        verdicts = collections.Counter(x.get("verdict") or "none" for x in xs)
        rfe = [x["rfe"] for x in xs if x["rfe"][0] is not None]
        mean = lambda k: round(sum(r[k] or 0 for r in rfe) / len(rfe), 2) if rfe else None
        tok = sum(x["tokens"]["prompt"] for x in xs), sum(x["tokens"]["completion"] for x in xs)
        print(f"{name}: n={len(xs)} verdicts={dict(verdicts)} edited={sum(1 for x in xs if x['files'])} RFE mean J/P/R={mean(0)}/{mean(1)}/{mean(2)} right-files(J=1)={sum(1 for r in rfe if r[0] == 1.0)} "
              f"HSR>0={sum(1 for x in xs if (x.get('hsr') or 0) > 0)} tokens in/out={tok[0]:,}/{tok[1]:,} wall={sum(x.get('wall_s') or 0 for x in xs):.0f}s")
    return 0


def _fmt(t) -> str:
    return "/".join("—" if v is None else f"{v:.2f}" for v in t) if t else "—"


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
    s = sub.add_parser("templates"); s.add_argument("graphs"); s.add_argument("--out", required=True); s.add_argument("--clone")
    s.set_defaults(fn=cmd_templates)
    s = sub.add_parser("ground"); s.add_argument("graphs"); s.add_argument("--templates", required=True); s.add_argument("--out", required=True); s.add_argument("--clone")
    s.add_argument("--gold", choices=("commit", "rows"), default="commit", help="the whole commit (the design's gold) or the cell's size-bounded rows")
    s.set_defaults(fn=cmd_ground)
    s = sub.add_parser("ground-units", help="Calvin M0-Go: every unit of a units.jsonl grounded with its gold diff at its parent")
    s.add_argument("units"); s.add_argument("--repo", required=True, help="a clone holding every parent and commit; only read"); s.add_argument("--out", required=True)
    s.add_argument("--tier", default="A2"); s.add_argument("--keys", nargs="*"); s.add_argument("--wp", default="wp-3")
    s.add_argument("--rta-key", help="an oracle go-rta key: the implementers rule 2 records for each interface call"); s.add_argument("--rta-label")
    s.set_defaults(fn=cmd_ground_units)
    s = sub.add_parser("poison", help="Calvin M0-Go: the poison control over a ground-units run (near-miss and invented renames, one NULL each)")
    s.add_argument("units"); s.add_argument("--ground", required=True, help="the ground-units --out directory"); s.add_argument("--repo", required=True)
    s.add_argument("--out", required=True, help="poison.json"); s.add_argument("--n", type=int, default=25); s.add_argument("--seed", default="calvin-go-wp-3:poison")
    s.add_argument("--wp", default="wp-3")
    s.set_defaults(fn=cmd_poison)
    s = sub.add_parser("t"); s.add_argument("graphs"); s.add_argument("--templates", required=True); s.add_argument("--out", required=True); s.add_argument("--clone")
    s.add_argument("--commits", nargs="+", required=True, help="commit prefixes to run arm T on")
    s.add_argument("--base-url", required=True); s.add_argument("--model", required=True)
    s.add_argument("--max-tokens", type=int, default=16384); s.add_argument("--timeout", type=float, default=600.0)
    s.add_argument("--max-prompt-chars", type=int, default=300_000, help="a rendered template over this is asked in chunks by file")
    s.add_argument("--no-loop", action="store_true", help="arm T without the NULL round-trip")
    s.add_argument("--sampling", choices=("greedy", "model-default"), default="greedy", help="temperature 0, or no sampling field for a model that rejects it")
    s.set_defaults(fn=cmd_t)
    s = sub.add_parser("t-units", help="Calvin M0-Go WP-5: arm T by hand on units.jsonl keys, metered, every exchange recorded")
    s.add_argument("units"); s.add_argument("--templates", required=True, help="<key>.template.json per key (the stored template at the tier)")
    s.add_argument("--repo", required=True, help="a clone this run owns: checked out at each parent (--force)"); s.add_argument("--out", required=True)
    s.add_argument("--keys", nargs="+", required=True); s.add_argument("--tier", default="A2")
    s.add_argument("--base-url", required=True); s.add_argument("--model", required=True)
    s.add_argument("--secrets", help="the owner's name=value key file (read, never printed); HOBBES_LLM_API_KEY wins when set")
    s.add_argument("--key-name", default="llm_key", help="the line of --secrets that holds this endpoint's key")
    s.add_argument("--max-tokens", type=int, default=16384); s.add_argument("--timeout", type=float, default=600.0)
    s.add_argument("--max-prompt-chars", type=int, default=300_000, help="a rendered template over this is asked in chunks by file")
    s.add_argument("--no-loop", action="store_true", help="arm T without the NULL round-trip")
    s.add_argument("--sampling", choices=("greedy", "model-default"), default="greedy", help="temperature 0, or no sampling field for a model that rejects it")
    s.add_argument("--rta-key", help="an oracle go-rta key: the implementers rule 2 records"); s.add_argument("--rta-label")
    s.add_argument("--gold-ground", help="a ground-units directory (WP-3's ground-gold/): the gold's declared names, for §4.2's agreement")
    s.add_argument("--estimate", help="WP-4's estimate.json: each key's expected dollars beside its actual")
    s.add_argument("--key-cap", type=float, default=2.0, help="dollars one key may spend"); s.add_argument("--total-cap", type=float, default=5.0, help="dollars every key under --out may spend in all")
    s.add_argument("--verify", action="store_true", help="run the verifier on each grounded diff"); s.add_argument("--verify-timeout", type=int, default=900)
    s.add_argument("--wp", default="wp-5")
    s.set_defaults(fn=cmd_t_units)
    s = sub.add_parser("verify"); s.add_argument("graphs"); s.add_argument("--diffs", help="directory of <commit><suffix> diffs (ground/ for the gold calibration, t/ for arm T)")
    s.add_argument("--out", required=True); s.add_argument("--clone"); s.add_argument("--commits", nargs="*", help="commit prefixes (default: every proposal)")
    s.add_argument("--suffix", default=".diff", help=".diff for ground/, .t.diff for t/"); s.add_argument("--no-baseline", action="store_true"); s.add_argument("--timeout", type=int, default=900)
    s.add_argument("--rescore", help="re-class the records of this earlier run into --out instead of running (the classes changed; never in place)")
    s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("o"); s.add_argument("graphs"); s.add_argument("--templates", required=True); s.add_argument("--out", required=True); s.add_argument("--clone")
    s.add_argument("--commits", nargs="+", required=True); s.add_argument("--scripted", help="a JSON script played in place of the model (calvin_scripted_agent.py)")
    s.add_argument("--base-url"); s.add_argument("--model"); s.add_argument("--session-bin"); s.add_argument("--sessions")
    s.add_argument("--max-turns", type=int, default=40); s.add_argument("--max-tokens", type=int, default=4096); s.add_argument("--loop-arg", action="append")
    s.add_argument("--knowledge", action="store_true", help="offer the knowledge tools too (default: exec only)"); s.add_argument("--timeout", type=float, default=3600.0)
    s.add_argument("--token-budget", type=int, default=None, help="prompt tokens a session may spend in all (default: harness.O_TOKEN_BUDGET, 1M; 0 = none)")
    s.add_argument("--dry-run", action="store_true", help="print the session argv and the plan; launch nothing")
    s.set_defaults(fn=cmd_o)
    s = sub.add_parser("rows"); s.add_argument("graphs"); s.add_argument("--t", required=True); s.add_argument("--o", required=True); s.add_argument("--verify-t", required=True)
    s.add_argument("--verify-t0", help="verify records of arm T's pre-loop diffs (.t0.diff); without it T's verdict column is empty where a loop ran")
    s.add_argument("--out", required=True, help="the rows as JSON"); s.add_argument("--clone"); s.add_argument("--commits", nargs="*")
    s.set_defaults(fn=cmd_rows)
    s = sub.add_parser("replay"); s.add_argument("graphs"); s.add_argument("--templates", required=True, help="the template set to replay into (templates-v1/)")
    s.add_argument("--t", required=True, help="directory of the recorded arm-T runs (<commit>.t.json)"); s.add_argument("--diffs", help="gold diffs (default: ground/)")
    s.add_argument("--commits", nargs="+", required=True); s.add_argument("--mode", nargs="+", choices=("gold", "max"), default=["gold", "max"]); s.add_argument("--clone")
    s.add_argument("--show-tests", action="store_true", help="list the TEST_EXPECTATIONs that sit in the gold's own test files")
    s.set_defaults(fn=cmd_replay)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
