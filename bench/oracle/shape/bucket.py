"""The callee-shape bucket (bench tooling, 2026-09-10): join an oracle
cell's misses to the checker's callee-shape record (shapes.mjs) and to
lane A's own facts at the same site, bucket them by shape, and print the
collapsed recall (one pair per site line x target file x the checker's
fully qualified target name — the oracle's overload grain removed and
nothing else). docs/oracle/oracle-misses.md.

Identity (H-22, the 2026-09-10 review): a target is its file and the
checker's *fully qualified* name — overload signatures share one, two
same-named methods of different classes do not — and a confirmed Hobbes
row hits the oracle target at its exact position on its line, the
grader's own rule, never a same-named declaration elsewhere. The
checker's record for a miss is the one at the oracle site's column;
where none is, the one record on the line spelling the target's name;
otherwise the miss is an explicit `ambiguous` / `no record` row, never
the first candidate. Lane A's record at a site is read the same way.

    python3 bench/oracle/shape/bucket.py <cell-dir> <oracle.json> <shapes.json> <facts.json>

<cell-dir> holds report.json (oracle grade --json); <facts.json> is
`node tsextract/extract.mjs --repo <clone>`.

The joins are functions so `bucket_test.py` can drive them on a
hand-built cell (run by `go test` in this directory, python3 only);
`main` is the command above.
"""
import json
import sys
from collections import Counter, defaultdict

#: The bucket for a miss whose Hobbes edge lands on the same file and
#: name at another line — the oracle's overload grain, not a miss of
#: the target (H-19's recall side).
SIBLING = "oracle-grain:sibling-declaration-confirmed"
#: The bucket for a miss at a line where the checker recorded no call
#: (the name is historical: it is the checker's record, shapes.mjs, that
#: is missing, not lane A's).
NO_SITE = "no-lane-A-site-on-line"
#: The checker recorded calls on the line, none at the oracle site's
#: column and none spelling the target's name.
NO_RECORD = "checker-records-on-line:none-at-this-callee"
#: More than one checker record could be the site and they read
#: differently — reported, never picked (H-22).
AMBIGUOUS = "checker-record:ambiguous"


def tname(name):
    """The bare target name of an oracle target or a Hobbes target id."""
    return name.split(".")[-1].strip('"')


def ident_bucket(x):
    """An identifier callee's bucket: its first declaration's kind, a
    variable spelled out as ``identifier:<kw>-<top|nested>-<init>``."""
    ds = x["decls"]
    if not ds:
        return "identifier:unresolved"
    k = ds[0]["kind"]
    if k.startswith("var:"):
        parts = k.split(":")  # var:kw:top|nested:init
        return f"identifier:{parts[1]}-{parts[2]}-{parts[3]}"
    return "identifier:" + k


def shape_bucket(x):
    """The bucket of one callee-shape record: identifiers by declaration
    kind, members by receiver shape, a `new` by what the name declares,
    every other shape by its name."""
    if x["shape"] == "identifier":
        return ident_bucket(x)
    if x["shape"] == "new":
        ds = x["decls"]
        return "new:" + (ds[0]["kind"] if ds else "unresolved")
    if x["shape"] == "member":
        r = x["recv"]
        if r.startswith("ident:var:"):
            p = r.split(":")
            return f"member:on-{p[2]}-{p[3]}-{p[4]}"
        return "member:on-" + r
    return x["shape"]


def _index(rep, orc, shapes, facts):
    """The four per-line indexes the join reads."""
    rows_at = defaultdict(list)
    for r in rep["rows"]:
        rows_at[(r["edge"]["site"]["path"], r["edge"]["site"]["line"])].append(r)
    osites = defaultdict(list)
    for s in orc["sites"]:
        osites[(s["pos"]["path"], s["pos"]["line"])].append(s)
    # shapes by path,line (both terminal line and callee-start line)
    sh_at = defaultdict(list)
    for x in shapes:
        sh_at[(x["path"], x["line"])].append(x)
        if x["cline"] != x["line"]:
            sh_at[(x["path"], x["cline"])].append(x)
    fa_at = defaultdict(list)
    for f in facts["files"]:
        for c in f.get("calls", []):
            fa_at[(f["path"], c["line"])].append(c)
    return rows_at, osites, sh_at, fa_at


def _confirmed_targets(rows_at, osites, key):
    """The oracle targets the confirmed rows at a site line were confirmed
    against: the targets at the rows' exact target positions among the
    sites on that line — the grader's rule (grade.go: `hasTarget`)."""
    positions = {
        (r["edge"]["target"]["path"], r["edge"]["target"]["line"])
        for r in rows_at[key] if r["bucket"] == "confirmed"
    }
    return [
        t for s in osites[key] for t in s["targets"]
        if (t["pos"]["path"], t["pos"]["line"]) in positions
    ]


def checker_record(records, sites, t, tn):
    """The checker's record for one miss of target *t* among *records*
    (the shapes on the site line) and *sites* (the oracle sites on it).

    Returns ``(record, how)``: the record at the oracle site's column
    (``exact`` — the oracle's column is 1-based, the checker's 0-based,
    both at the terminal name; several records at that column that read
    the same bucket are one reading); else the one record on the line
    spelling the target's bare name (``name``); else ``(None,
    "ambiguous")`` when more than one could be it, ``(None, "none")``
    when none could."""
    if not records:
        return None, "none"
    cols = {s["col"] - 1 for s in sites if any(tt["pos"] == t["pos"] for tt in s["targets"])}
    exact = [x for x in records if x["col"] in cols]
    if len(exact) > 1:
        exact = [x for x in exact if x["name"] == tn] or exact
    if exact and len({shape_bucket(x) for x in exact}) == 1:
        return exact[0], "exact"
    if exact:
        return None, "ambiguous"
    named = [x for x in records if x["name"] == tn]
    if named and len({shape_bucket(x) for x in named}) == 1:
        return named[0], "name"
    return None, ("ambiguous" if named else "none")


def lane_a_reading(calls, tn):
    """What lane A recorded for the call named *tn* on a line, from
    *calls* (its facts on that line): ``(callee | no-callee, origin,
    ambiguous)`` when the records naming it agree, ``("ambiguous", n)``
    when they do not, ``("lane-A-record-other-name",)`` when the line
    has records naming something else, ``("no-lane-A-record",)`` when it
    has none."""
    named = [c for c in calls if c["name"] == tn]
    readings = {("callee" if c["callee"] else "no-callee", c["origin"], c["ambiguous"]) for c in named}
    if len(readings) == 1:
        return readings.pop()
    if readings:
        return ("ambiguous", len(named))
    return ("lane-A-record-other-name",) if calls else ("no-lane-A-record",)


def bucket_misses(rep, orc, shapes, facts):
    """Every miss of the report bucketed by callee shape.

    Returns ``(out, detail, examples, lane_a, how)``: misses per (class,
    bucket); targets per bucket; up to four example lines per bucket;
    per bucket what lane A recorded at the site (`lane_a_reading`); and
    how each miss found its checker record (`checker_record`: exact
    column / name / ambiguous / none / sibling), so the report says how
    much of the attribution rests on a name.
    """
    rows_at, osites, sh_at, fa_at = _index(rep, orc, shapes, facts)
    out = Counter()
    detail = defaultdict(Counter)
    examples = defaultdict(list)
    lane_a = defaultdict(Counter)
    how = Counter()
    for m in rep["misses"]:
        key = (m["site"]["path"], m["site"]["line"])
        t = m["target"]
        tn = tname(t["name"])
        cls = m["class"]
        # 1. overload/sibling grain: a confirmed edge at this line reaches
        # a declaration of the same qualified name in the same file at
        # another line — the same symbol, another signature
        sib = [
            c for c in _confirmed_targets(rows_at, osites, key)
            if c["name"] == t["name"]
            and c["pos"]["path"] == t["pos"]["path"]
            and c["pos"]["line"] != t["pos"]["line"]
        ]
        if sib:
            b, way = SIBLING, "sibling"
        else:
            x, way = checker_record(sh_at[key], osites[key], t, tn)
            if x is not None:
                b = shape_bucket(x)
                lane_a[b][lane_a_reading(fa_at[key], tn)] += 1
            elif way == "ambiguous":
                b = AMBIGUOUS
            else:
                b = NO_RECORD if sh_at[key] else NO_SITE
        how[way] += 1
        out[(cls, b)] += 1
        detail[b][(t["kind"], t["pos"]["path"], t["pos"]["line"], tn)] += 1
        if len(examples[b]) < 4:
            examples[b].append(f"{key[0]}:{key[1]} -> {t['pos']['path']}:{t['pos']['line']} {tn} [{cls}]")
    return out, detail, examples, lane_a, how


def collapsed_recall(orc, rows):
    """Recall with the oracle's overload grain removed and nothing else:
    one pair per (site path, site line, target path, the checker's fully
    qualified target name), in-repo targets only. Overload signatures
    share the name; `A.run` and `B.run` in one file do not (H-22). A
    confirmed Hobbes row hits the pair of the oracle target at the row's
    exact target position on its line — the grader's own rule — never a
    same-named declaration elsewhere in the file.

    Returns ``(pairs, hit, kind, unmatched)``: every pair; the pairs
    hit; each pair's target kind (``mixed:a|b`` when the signatures it
    collapses disagree — reported, not overwritten); and the confirmed
    rows no oracle target at their position explains, which the grader's
    rule makes empty — a non-empty list is a report/key mismatch."""
    pairs: set = set()
    kinds = defaultdict(set)
    by_target = defaultdict(set)
    for s in orc["sites"]:
        sp = (s["pos"]["path"], s["pos"]["line"])
        for t in s["targets"]:
            if t.get("external"):
                continue
            k = (sp[0], sp[1], t["pos"]["path"], t["name"])
            pairs.add(k)
            kinds[k].add(t["kind"])
            by_target[(sp[0], sp[1], t["pos"]["path"], t["pos"]["line"])].add(k)
    hit: set = set()
    unmatched = []
    for r in rows:
        if r["bucket"] != "confirmed":
            continue
        e = r["edge"]
        ks = by_target.get((e["site"]["path"], e["site"]["line"], e["target"]["path"], e["target"]["line"]))
        if ks:
            hit |= ks
        else:
            unmatched.append(r)
    kind = {k: (next(iter(v)) if len(v) == 1 else "mixed:" + "|".join(sorted(v))) for k, v in kinds.items()}
    return pairs, hit, kind, unmatched


def render(rep, orc, shapes, facts):
    """The report as printed: the buckets largest first, then the
    collapsed recall by target kind."""
    misses = rep["misses"]
    out, detail, examples, lane_a, how = bucket_misses(rep, orc, shapes, facts)
    lines = [f"TOTAL misses {len(misses)}"]
    lines.append(
        "attribution: " + ", ".join(f"{w} {how[w]}" for w in ("sibling", "exact", "name", "ambiguous", "none"))
        + "  (sibling: same qualified name confirmed at another line; exact: the checker record at the oracle column; "
        "name: the one record on the line spelling the name; ambiguous/none: reported, not bucketed by shape)"
    )
    tot = Counter()
    for (cls, b), n in out.items():
        tot[b] += n
    for b, n in tot.most_common():
        lines.append(f"\n== {b}: {n} ({100 * n / len(misses):.1f}%)")
        lines.append(f"   by class: {({cls: k for (cls, bb), k in out.items() if bb == b})}")
        lines.append(f"   lane A record: {dict(lane_a[b])}")
        lines.append(f"   top targets: {detail[b].most_common(6)}")
        for e in examples[b]:
            lines.append(f"   e.g. {e}")
    pairs, hit, kind, unmatched = collapsed_recall(orc, rep["rows"])
    lines.append(
        f"\nCOLLAPSED in-repo pairs {len(pairs)} hit {len(hit)} recall %.1f%%" % (100 * len(hit) / len(pairs))
    )
    lines.append(
        "  identity: (site path, site line, target path, checker-qualified target name); "
        f"confirmed rows no target at their position explains: {len(unmatched)}"
    )
    bk = Counter(kind[k] for k in pairs)
    hk = Counter(kind[k] for k in hit)
    for k, n in bk.most_common():
        lines.append(f"  {k:22s} {hk[k]:5d}/{n:5d}  {100 * hk[k] / n:5.1f}%   misses {n - hk[k]}")
    return "\n".join(lines)


def main(argv):
    cell, oracle, shapes, facts = argv
    with open(cell + "/report.json") as f:
        rep = json.load(f)
    with open(oracle) as f:
        orc = json.load(f)
    with open(shapes) as f:
        sh = json.load(f)
    with open(facts) as f:
        fa = json.load(f)
    print(render(rep, orc, sh, fa))


if __name__ == "__main__":
    main(sys.argv[1:])
