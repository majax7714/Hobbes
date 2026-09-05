"""``atlas0 check``: the step-1 exit criteria (design §8), read from the files.

Every check reads what was *written* — the corpus text, the eval sets,
the manifest — and not the generator's own bookkeeping, so a generator
that lies to itself is caught here. The criteria, from §8 step 1 and
§2.3–2.4 and §4:

- regenerating from the manifest's seed and config gives the same world
  hash and the same corpus hashes (§2.6);
- the class counts match the config;
- every sparse-real symbol is mentioned by exactly 1 or 2 statements in
  every arm's corpus, every dense-real by ≥ 24, every mid by 3–23, and
  no absent name by any positive statement; a held-out-absent name does
  not occur in any arm at all;
- no sparse-real symbol carries an ``UNDEFINED`` target, and no
  sparse-real symbol has a question/answer line, in any arm (§4);
- every absent-near name is at stem distance exactly 1 from its base,
  the base is dense-real, and no other real name is within 1; every
  absent-far name is at distance ≥ 2 from every real name;
- stem frequency is balanced across classes (total variation from
  uniform, per class), and so is name length.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .names import STEMS, NameIndex, split_name, stem_distance
from .world import ARMS, Config, World, canonical, generate, sha256

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _mentions_in(lines: list[str], names: set[str]) -> Counter:
    """How many lines mention each of ``names`` as a whole token."""
    counts: Counter = Counter()
    for line in lines:
        seen = set()
        for tok in _TOKEN.findall(line):
            if tok in names and tok not in seen:
                seen.add(tok)
                counts[tok] += 1
    return counts


def _min_tv(n: int, k: int) -> float:
    """Total variation from uniform of the evenest distribution of ``n`` draws over ``k`` bins."""
    if n <= 0:
        return 0.0
    lo, hi = n // k, n // k + 1
    n_hi = n - lo * k
    return 0.5 * (n_hi * abs(hi / n - 1 / k) + (k - n_hi) * abs(lo / n - 1 / k))


def _is_statement(line: str) -> bool:
    return not line.startswith("Q: ")


def _is_negative(line: str) -> bool:
    return ("undefined" in line or "not defined" in line or "No test reaches" in line
            or "no symbol named" in line or "does not exist" in line)


def check(path: Path) -> dict:
    """Run every check under ``path``; the report's ``ok`` is the verdict."""
    manifest = json.loads((path / "manifest.json").read_text())
    world = World.from_json(json.loads((path / "world.json").read_text()))
    cfg = Config(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in manifest["config"].items()})
    report: dict = {"seed": manifest["seed"], "checks": {}}
    checks = report["checks"]

    # 1. Determinism: regenerate and compare hashes; corpus files hash as recorded.
    regen = generate(manifest["seed"], cfg)
    checks["world_hash_regenerates"] = sha256(canonical(regen.to_json())) == manifest["world_hash"] == sha256((path / "world.json").read_bytes())
    corpora = {arm: (path / "corpus" / f"{arm}.txt").read_bytes() for arm in ARMS}
    checks["corpus_hash_matches"] = all(sha256(corpora[arm]) == manifest["corpus_hash"][arm] for arm in ARMS)

    # 2. Class counts.
    by_class = Counter(s.cls for s in world.symbols)
    by_absent = Counter((a.cls, a.exposure) for a in world.absents)
    checks["class_counts"] = (
        by_class["dense-real"] == cfg.dense and by_class["sparse-real"] == cfg.sparse and by_class["mid"] == cfg.mid
        and by_absent[("absent-near", "trained")] + by_absent[("absent-near", "held-out")] == cfg.near
        and by_absent[("absent-far", "trained")] + by_absent[("absent-far", "held-out")] == cfg.far
        and abs(by_absent[("absent-near", "trained")] - by_absent[("absent-near", "held-out")]) <= 1
        and abs(by_absent[("absent-far", "trained")] - by_absent[("absent-far", "held-out")]) <= 1
    )

    # 3. Mention counts from the corpus text, per arm.
    sym_names = {s.name for s in world.symbols}
    abs_names = {a.name for a in world.absents}
    held_out = {a.name for a in world.absents if a.exposure == "held-out"}
    sparse = {s.name for s in world.symbols if s.cls == "sparse-real"}
    per_arm = {}
    for arm in ARMS:
        lines = corpora[arm].decode("utf-8").splitlines()
        statements = [ln for ln in lines if _is_statement(ln) and not _is_negative(ln)]
        counts = _mentions_in(statements, sym_names | abs_names)
        all_counts = _mentions_in(lines, sym_names | abs_names)
        qa = [ln for ln in lines if not _is_statement(ln)]
        sparse_qa = _mentions_in(qa, sparse)
        undefined_sparse = [ln for ln in qa if ln.endswith(" UNDEFINED") and (set(_TOKEN.findall(ln)) & sparse)]
        sparse_extra = [n for n in sparse if all_counts[n] != counts[n]]
        bad = {
            "sparse_not_1_or_2": [n for n in sparse if counts[n] not in (1, 2)],
            "dense_below_24": [s.name for s in world.symbols if s.cls == "dense-real" and counts[s.name] < 24],
            "mid_out_of_range": [s.name for s in world.symbols if s.cls == "mid" and not 3 <= counts[s.name] <= 23],
            "absent_in_statements": [n for n in abs_names if counts[n] > 0],
            "held_out_absent_anywhere": [n for n in held_out if all_counts[n] > 0],
            "sparse_with_qa": sorted(sparse_qa),
            "sparse_mentioned_outside_statements": sparse_extra,
            "sparse_undefined": undefined_sparse,
        }
        per_arm[arm] = {"lines": len(lines), "statements": len(statements), "qa": len(qa),
                        "ok": not any(bad.values()), "bad": {k: v[:5] for k, v in bad.items() if v},
                        "bad_counts": {k: len(v) for k, v in bad.items() if v}}
    checks["mentions_per_arm"] = per_arm
    checks["mentions_ok"] = all(v["ok"] for v in per_arm.values())

    # 4. Absent-name construction.
    real = NameIndex()
    for s in world.symbols:
        real.add(s.name)
    dense = {s.name for s in world.symbols if s.cls == "dense-real"}
    near_bad, far_bad = [], []
    for a in world.absents:
        stems = split_name(a.name)
        if a.name in real:
            (near_bad if a.cls == "absent-near" else far_bad).append((a.name, "is real"))
            continue
        if a.cls == "absent-near":
            within = real.within(stems, 1)
            if a.base not in dense or within != {a.base: 1} or stem_distance(stems, split_name(a.base)) != 1:
                near_bad.append((a.name, a.base, within))
        else:
            if real.within(stems, 1):
                far_bad.append((a.name, real.within(stems, 1)))
    checks["absent_near_distance_1_unique_base"] = not near_bad
    checks["absent_far_distance_ge_2"] = not far_bad
    if near_bad:
        checks["absent_near_bad"] = near_bad[:5]
    if far_bad:
        checks["absent_far_bad"] = far_bad[:5]
    checks["absent_names_unique"] = len(abs_names) == len(world.absents)

    # 5. Stem and length balance across classes.
    groups: dict[str, list[str]] = {}
    for s in world.symbols:
        groups.setdefault(s.cls, []).append(s.name)
    for a in world.absents:
        groups.setdefault(a.cls, []).append(a.name)
    tv, excess, lengths = {}, {}, {}
    for cls, names in groups.items():
        c = Counter(st for n in names for st in split_name(n))
        total = sum(c.values())
        tv[cls] = round(0.5 * sum(abs(c[st] / total - 1 / len(STEMS)) for st in STEMS), 4)
        excess[cls] = round(tv[cls] - _min_tv(total, len(STEMS)), 4)
        lc = Counter(len(split_name(n)) for n in names)
        lengths[cls] = {str(k): v for k, v in sorted(lc.items())}
    checks["stem_tv_from_uniform"] = tv
    checks["stem_tv_excess"] = excess          # over the evenest distribution the draw count allows
    checks["stem_balanced"] = all(v <= 0.05 for v in excess.values())
    checks["name_lengths"] = lengths
    checks["length_balanced"] = all(max(l.values()) - min(l.values()) <= max(2, 0.1 * sum(l.values())) for l in lengths.values())

    # 6. The eval sets: the primary set asks defined_in of every class; no sparse in trained.
    primary = [json.loads(ln) for ln in (path / "eval" / "primary.jsonl").read_text().splitlines()]
    trained = [json.loads(ln) for ln in (path / "eval" / "trained.jsonl").read_text().splitlines()]
    pc = Counter((it["class"], it["exposure"]) for it in primary)
    checks["primary_rows"] = {f"{c}/{e}": n for (c, e), n in sorted(pc.items())}
    checks["primary_all_defined_in"] = all(it["kind"] == "defined_in" for it in primary)
    checks["trained_has_no_sparse"] = not any(it["class"] == "sparse-real" for it in trained)
    checks["sparse_all_in_primary"] = pc[("sparse-real", "n/a")] == cfg.sparse

    report["ok"] = all(v for k, v in checks.items() if isinstance(v, bool))
    return report
