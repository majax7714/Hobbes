"""E3's draw, what is measured (DRAW-RULE.md): tasks by ISA family, by the body-shape rule and their union;
validation reach; two-axis share; the body-shape rule's recall bar; the precision sample to read.

The body-shape rule and the member set are `family-count/count.py`'s: `Repo`, `loose_groups`,
`body_tokens`, BODY_RATIO 0.6, BODY_CAP 64 and the thin filter imported unchanged. `body_families` is
`count.body_families` line for line (both exact upper-bound prefilters, `real_quick_ratio` then
`quick_ratio`, then the full ratio) with one addition, for cost only: a pair in which either body is
over PAIR_CAP tokens is **not computed**, and those members are counted `skipped_size` with their
lengths (libxsmm's generated bodies reach 145k tokens; the pure-Python ratio is quadratic). Every pair
that is computed decides exactly as count.py's does; nothing is sampled. ISA families use the
gate's tokeniser and ISA list (`gate.py`), over the same non-thin members.

Usage: python3 measure.py   (reads ingest/*.json for the taken repos, writes measure/<key>.json)
"""
import difflib, json, random, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "family-count"))
import count  # noqa: E402
from gate import ISA, tokens as isa_tokens  # noqa: E402

SCALAR = {"c", "scalar", "generic", "ref", "reference", "serial", "portable", "plain", "fallback", "cpu", "naive"}
SAMPLE = 20
PAIR_CAP = 20_000  # body tokens; a pair over it is not computed (counted, never sampled)
SEED = 20260926


def isa_families(members: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for m in members:
        t = isa_tokens(m["name"])
        for i, tok in enumerate(t):
            if tok in ISA:
                groups[(len(t), i, t[:i] + ("*",) + t[i + 1:])].append(m)
    return [{"key": k, "members": ms} for k, ms in groups.items()
            if len({isa_tokens(m["name"])[k[1]] for m in ms}) >= 2]


def two_axis(fams: list[dict]) -> set:
    """Keys of ISA families with a sibling ISA family whose key differs in exactly one other position."""
    keys = [f["key"] for f in fams]
    by = defaultdict(list)
    for k in keys:
        n, i, t = k
        for j in range(len(t)):
            if j != i:
                by[(n, i, j, t[:j] + ("?",) + t[j + 1:])].append(k)
    out = set()
    for ks in by.values():
        if len(set(ks)) >= 2:
            out.update(ks)
    return out


def scalar_ref(m: dict, pos: int, all_names: set) -> bool:
    t = isa_tokens(m["name"])
    rest = t[:pos] + t[pos + 1:]
    if rest in all_names:
        return True
    return any(t[:pos] + (s,) + t[pos + 1:] in all_names for s in SCALAR)


def body_families(groups):
    """`count.body_families`, line for line, plus the PAIR_CAP skip (counted in `skipped_size`)."""
    fams, skipped, skipped_size = [], 0, {}
    for key, ms in groups.items():
        if len(ms) > count.BODY_CAP:
            skipped += 1
            continue
        i = key[1]
        toks = [count.body_tokens(m, m["toks"][i]) for m in ms]
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
                if sm.real_quick_ratio() < count.BODY_RATIO or sm.quick_ratio() < count.BODY_RATIO:
                    continue
                if len(toks[a]) > PAIR_CAP or len(toks[b]) > PAIR_CAP:
                    for x in (a, b):
                        if len(toks[x]) > PAIR_CAP:
                            skipped_size[ms[x]["id"]] = len(toks[x])
                    continue
                if sm.ratio() >= count.BODY_RATIO:
                    parent[find(a)] = find(b)
        comp = defaultdict(list)
        for x in range(len(ms)):
            comp[find(x)].append(ms[x])
        for sub in comp.values():
            if len({m["toks"][i] for m in sub}) >= 2:
                fams.append({"key": key, "members": sub, "empty": False})
    return fams, skipped, skipped_size


def pair_reading(f: dict) -> dict:
    """Over the family's first four members: the least pairwise ratio, and whether every pair is >= 0.9
    (near-copy). Exact prefilters decide the near-copy question where they can; a pair over PAIR_CAP is
    not computed and the family's min_ratio reads None (it is named, not estimated)."""
    i = f["key"][1]
    toks = [count.body_tokens(m, m["toks"][i]) for m in f["members"][:4]]
    least, near, over = 1.0, True, False
    for a in range(len(toks)):
        for b in range(a + 1, len(toks)):
            sm = difflib.SequenceMatcher(None, toks[a], toks[b], autojunk=False)
            if sm.real_quick_ratio() < 0.9 or sm.quick_ratio() < 0.9:
                near = False
            if len(toks[a]) > PAIR_CAP or len(toks[b]) > PAIR_CAP:
                over = True
                continue
            r = sm.ratio()
            least = min(least, r)
            near = near and r >= 0.9
    return {"min_ratio": None if over else round(least, 3), "near_copy": None if over and near else near}


def measure(key: str, clone: Path) -> dict:
    repo = count.Repo(key, clone)
    pool = [m for m in repo.members.values() if not m["thin"]]
    all_names = {isa_tokens(m["name"]) for m in repo.members.values()}  # thin members may be scalar refs
    isa = isa_families(pool)
    isa_ids = {m["id"] for f in isa for m in f["members"]}
    groups = count.loose_groups(pool)
    body, skipped, skipped_size = body_families(groups)
    body_ids = {m["id"] for f in body for m in f["members"]}
    union = isa_ids | body_ids

    ta = two_axis(isa)
    two_ids = {m["id"] for f in isa if f["key"] in ta for m in f["members"]}
    scalar_ids = set()
    for f in isa:
        for m in f["members"]:
            if scalar_ref(m, f["key"][1], all_names):
                scalar_ids.add(m["id"])
    tested = union & repo.reached
    validated = union & (scalar_ids | repo.reached)

    # precision sample: body-shape families whose varying tokens are not all ISA tokens
    non_isa = [f for f in body if not {m["toks"][f["key"][1]] for m in f["members"]} <= ISA]
    non_isa.sort(key=lambda f: (" ".join(f["key"][2]), sorted(m["id"] for m in f["members"])))
    picked = random.Random(SEED).sample(non_isa, min(SAMPLE, len(non_isa)))
    sample = [{"key": " ".join(f["key"][2]), "size": len(f["members"]), **pair_reading(f),
               "members": [f"{m['name']} {m['path']}:{m['line']}" for m in
                           sorted(f["members"], key=lambda m: (m["path"], m["line"] or 0))][:8]}
              for f in picked]
    return {
        "sha": repo.sha, "version": repo.version, "members": len(repo.members), "nonthin": len(pool),
        "isa": {"families": len(isa), "tasks": len(isa_ids)},
        "body": {"families": len(body), "tasks": len(body_ids), "skipped_groups": skipped,
                 "skipped_size": {"members": len(skipped_size),
                                  "tokens": sorted(skipped_size.values(), reverse=True)},
                 "non_isa_families": len(non_isa)},
        "union_tasks": len(union),
        "validated": {"scalar_ref": len(union & scalar_ids), "tests": len(tested),
                      "either": len(validated), "neither": len(union - validated)},
        "two_axis": {"isa_families": len(ta), "tasks": len(two_ids)},
        "recall": {"isa_nonthin": len(isa_ids), "grouped_by_body": len(isa_ids & body_ids),
                   "share": round(len(isa_ids & body_ids) / len(isa_ids), 4) if isa_ids else None},
        "sample": sample,
    }


def main():
    out = HERE / "measure"
    out.mkdir(exist_ok=True)
    for rec in sorted((HERE / "ingest").glob("*.json")):
        r = json.loads(rec.read_text())
        if not r.get("passed"):
            continue
        dest = out / rec.name
        if dest.exists():
            continue
        key = rec.stem
        t0 = time.time()
        res = measure(key, HERE / "repos" / key)
        res["seconds"] = round(time.time() - t0, 1)
        res["full_name"] = r["full_name"]
        dest.write_text(json.dumps(res, indent=1))
        print(key, res["union_tasks"], res["recall"], flush=True)


if __name__ == "__main__":
    main()
