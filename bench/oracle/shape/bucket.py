"""The callee-shape bucket (bench tooling, 2026-09-10): join an oracle
cell's misses to the checker's callee-shape record (shapes.mjs) and to
lane A's own facts at the same site, bucket them by shape, and print the
collapsed recall (one pair per site line x target file x target name —
the oracle's overload grain removed). docs/oracle/oracle-misses.md.

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
#: The bucket for a miss at a line where the checker recorded no call.
NO_SITE = "no-lane-A-site-on-line"


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
    kind, members by receiver shape, every other shape by its name."""
    if x["shape"] == "identifier":
        return ident_bucket(x)
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


def bucket_misses(rep, orc, shapes, facts):
    """Every miss of the report bucketed by callee shape.

    Returns ``(out, detail, examples, lane_a)``: misses per (class,
    bucket); targets per bucket; up to four example lines per bucket;
    and per bucket what lane A recorded at the site — ``(callee |
    no-callee, origin, ambiguous)`` or ``('no-lane-A-record',)``.
    """
    rows_at, osites, sh_at, fa_at = _index(rep, orc, shapes, facts)
    out = Counter()
    detail = defaultdict(Counter)
    examples = defaultdict(list)
    lane_a = defaultdict(Counter)
    for m in rep["misses"]:
        key = (m["site"]["path"], m["site"]["line"])
        t = m["target"]
        tn = tname(t["name"])
        cls = m["class"]
        # 1. overload/sibling grain: Hobbes has a confirmed edge at this
        # line to the same file+name, other line
        sib = [
            r for r in rows_at[key]
            if r["bucket"] == "confirmed"
            and r["edge"]["target"]["path"] == t["pos"]["path"]
            and tname(r["edge"]["target_id"]) == tn
            and r["edge"]["target"]["line"] != t["pos"]["line"]
        ]
        if sib:
            b = SIBLING
        else:
            cands = [x for x in sh_at[key] if x["name"] == tn] or sh_at[key]
            if not cands:
                b = NO_SITE
            else:
                # nearest col to the oracle site's col
                oc = [s for s in osites[key] if any(tt["pos"] == t["pos"] for tt in s["targets"])]
                col = oc[0]["col"] if oc else None
                x = (
                    min(cands, key=lambda x: abs(x["ccol"] - col))
                    if col is not None else cands[0]
                )
                b = shape_bucket(x)
                fa = [c for c in fa_at[key] if c["name"] == tn] or fa_at[key]
                if fa:
                    c = fa[0]
                    lane_a[b][("callee" if c["callee"] else "no-callee", c["origin"], c["ambiguous"])] += 1
                else:
                    lane_a[b][("no-lane-A-record",)] += 1
        out[(cls, b)] += 1
        detail[b][(t["kind"], t["pos"]["path"], t["pos"]["line"], tn)] += 1
        if len(examples[b]) < 4:
            examples[b].append(f"{key[0]}:{key[1]} -> {t['pos']['path']}:{t['pos']['line']} {tn} [{cls}]")
    return out, detail, examples, lane_a


def collapsed_recall(orc, rows):
    """Recall with the oracle's overload grain removed: one pair per
    (site path, site line, target path, target name), in-repo targets
    only. Returns ``(pairs, hit, kind)`` — every pair, the pairs a
    confirmed Hobbes row covers, and each pair's target kind."""
    pairs = set()
    kind = {}
    for s in orc["sites"]:
        for t in s["targets"]:
            if t.get("external"):
                continue
            k = (s["pos"]["path"], s["pos"]["line"], t["pos"]["path"], tname(t["name"]))
            pairs.add(k)
            kind[k] = t["kind"]
    hits = {
        (r["edge"]["site"]["path"], r["edge"]["site"]["line"], r["edge"]["target"]["path"], tname(r["edge"]["target_id"]))
        for r in rows if r["bucket"] == "confirmed"
    }
    return pairs, pairs & hits, kind


def render(rep, orc, shapes, facts):
    """The report as printed: the buckets largest first, then the
    collapsed recall by target kind."""
    misses = rep["misses"]
    out, detail, examples, lane_a = bucket_misses(rep, orc, shapes, facts)
    lines = [f"TOTAL misses {len(misses)}"]
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
    pairs, hit, kind = collapsed_recall(orc, rep["rows"])
    lines.append(
        f"\nCOLLAPSED in-repo pairs {len(pairs)} hit {len(hit)} recall %.1f%%" % (100 * len(hit) / len(pairs))
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
