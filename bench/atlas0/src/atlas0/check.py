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

v1 (each read from the text as well): a relation-absence line or an
``UNDEFINED`` pair about a *real* symbol occurs only in a lived arm of a
``relation_absence`` world, only for a dense or mid symbol, and only
where the world's facts leave that relation empty (a pair only for a
QA-trained one); an existence absence never names a real symbol; a
packed line (``context_qa_p``) states the fact its question asks, at
the configured share; under ``query_holdout`` no corpus line uses the
held-out phrasing and every eval prompt does, ``primary_seen`` the
first trained one.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .names import STEMS, NameIndex, split_name, stem_distance
from .world import (ARMS, HELD_OUT_PHRASING, NEGATIVE_TEMPLATES, QUERY_PHRASINGS, RELATION_ABSENCE_TEMPLATES,
                    TEMPLATES, TRAIN_PHRASINGS, Config, World, canonical, generate, sha256)

_TOKEN = re.compile(r"[A-Za-z0-9_]+")
_NAME = r"[A-Za-z][A-Za-z0-9_]*"


def _pattern(template: str) -> str:
    return re.escape(template).replace(r"\{x\}", _NAME).replace(r"\{s\}", _NAME).replace(r"\{m\}", _NAME) \
        .replace(r"\{a\}", _NAME).replace(r"\{b\}", _NAME).replace(r"\{t\}", _NAME)


_EXISTENCE = [re.compile("^" + _pattern(t) + "$") for t in NEGATIVE_TEMPLATES]
_RELATION = {kind: [re.compile("^" + _pattern(t) + "$") for t in ts] for kind, ts in RELATION_ABSENCE_TEMPLATES.items()}
_STATEMENT = [re.compile("^" + _pattern(t) + "$") for ts in TEMPLATES.values() for t in ts]
_QUERY = {(kind, i): re.compile("^Q: " + _pattern(p) + " A:") for kind, ps in QUERY_PHRASINGS.items() for i, p in enumerate(ps)}


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
    """A line with no question in it (a packed v1 line is a QA line)."""
    return "Q: " not in line


def _is_negative(line: str) -> bool:
    """A written absence: an existence-negative or a relation-absence template."""
    return any(r.match(line) for r in _EXISTENCE) or any(r.match(line) for rs in _RELATION.values() for r in rs)


def _relation_kind(line: str) -> str | None:
    for kind, rs in _RELATION.items():
        if any(r.match(line) for r in rs):
            return kind
    return None


def _query_of(line: str) -> tuple[str, int] | None:
    """(kind, phrasing) of the question in a QA line, or None."""
    q = line[line.index("Q: "):] if "Q: " in line else line
    for key, r in _QUERY.items():
        if r.match(q):
            return key
    return None


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
        real_names = {s.name for s in world.symbols}
        negatives = [ln for ln in lines if _is_statement(ln) and _is_negative(ln)]
        # v1: relation absence about real symbols — lived arms of a relation_absence world only,
        # dense/mid only, and only where the world's facts leave the relation empty.
        allowed = cfg.relation_absence and "lived" in arm
        rel_bad, exist_bad = [], []
        for ln in negatives:
            names = [t for t in _TOKEN.findall(ln) if t in real_names]
            if not names:
                continue
            kind = _relation_kind(ln)
            if kind is None:
                exist_bad.append(ln)
            elif not allowed or names[0] in sparse or world.facts_of(names[0])[kind]:
                rel_bad.append(ln)
        undefined_real = []
        for ln in qa:
            if not ln.endswith(" UNDEFINED"):
                continue
            q = ln[ln.index("Q: "):]
            names = [t for t in _TOKEN.findall(q) if t in real_names]
            if not names:
                continue
            key = _query_of(ln)
            if (not allowed or key is None or key[0] not in RELATION_ABSENCE_TEMPLATES or names[0] in sparse
                    or world.symbol(names[0]).qa_split != "train" or world.facts_of(names[0])[key[0]]):
                undefined_real.append(ln)
        # v1: packed lines state the fact their question asks.
        packed = [ln for ln in qa if not ln.startswith("Q: ")]
        packed_bad = []
        for ln in packed:
            stmt, q = ln[: ln.index("Q: ")].strip(), ln[ln.index("Q: "):]
            head, _, answer = q.partition(" A: ")
            qnames = [t for t in _TOKEN.findall(head) if t in real_names]
            if not any(r.match(stmt) for r in _STATEMENT) or not answer.startswith("ANSWER ") or not qnames:
                packed_bad.append(ln)     # only a real fact's own statement, only before an ANSWER
                continue
            value = answer.split()[-1]
            if qnames[0] not in _TOKEN.findall(stmt) or value not in _TOKEN.findall(stmt):
                packed_bad.append(ln)
        answers = [ln for ln in qa if not ln.endswith(" UNDEFINED")]
        share = len(packed) / max(1, len(answers))
        share_bad = [] if cfg.context_qa_p == 0 and not packed else (
            [f"share {share:.3f} vs {cfg.context_qa_p}"]
            if cfg.context_qa_p > 0 and abs(share - cfg.context_qa_p) > 0.05 else [])
        # v1: query phrasings in the corpus.
        phr = [_query_of(ln) for ln in qa]
        phrasing_bad = [ln for ln, k in zip(qa, phr) if k is None or
                        (k[1] != 0 if not cfg.query_holdout else k[1] not in TRAIN_PHRASINGS)]
        bad = {
            "real_in_existence_negative": exist_bad,
            "relation_absence_misplaced": rel_bad,
            "undefined_on_real_misplaced": undefined_real,
            "packed_line_not_its_fact": packed_bad,
            "packed_share": share_bad,
            "phrasing_out_of_place": phrasing_bad,
            "sparse_not_1_or_2": [n for n in sparse if counts[n] not in (1, 2)],
            "dense_below_24": [s.name for s in world.symbols if s.cls == "dense-real" and counts[s.name] < 24],
            "mid_out_of_range": [s.name for s in world.symbols if s.cls == "mid" and not 3 <= counts[s.name] <= 23],
            "absent_in_statements": [n for n in abs_names if counts[n] > 0],
            "held_out_absent_anywhere": [n for n in held_out if all_counts[n] > 0],
            "sparse_with_qa": sorted(sparse_qa),
            "sparse_mentioned_outside_statements": sparse_extra,
            "sparse_undefined": undefined_sparse,
        }
        per_arm[arm] = {"lines": len(lines), "statements": len(statements), "qa": len(qa), "negatives": len(negatives),
                        "packed": len(packed),
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

    # 7. v1 eval shape: every prompt in the phrasing the variant says; the empty relations asked.
    sets = {p.stem: [json.loads(ln) for ln in p.read_text().splitlines()] for p in (path / "eval").glob("*.jsonl")}
    want = HELD_OUT_PHRASING if cfg.query_holdout else 0
    prompt_bad = []
    for name, items in sets.items():
        for it in items:
            key = _query_of(it["prompt"].split("\n")[-1])
            if key is None or key[1] != (TRAIN_PHRASINGS[0] if name == "primary_seen" else want):
                prompt_bad.append((name, it["id"]))
    checks["eval_prompts_phrased_as_configured"] = not prompt_bad
    checks["primary_seen_present_iff_holdout"] = ("primary_seen" in sets) == cfg.query_holdout
    if cfg.query_holdout:
        checks["primary_seen_same_items"] = [it["id"] for it in sets["primary_seen"]] == [it["id"] for it in primary]
    secondary = sets["secondary"]
    without = Counter((it["class"], it["kind"]) for it in secondary if it.get("exposure") == "without")
    empty_sparse = Counter(kind for s in world.symbols if s.cls == "sparse-real"
                           for kind in RELATION_ABSENCE_TEMPLATES if not world.facts_of(s.name)[kind])
    checks["secondary_asks_empty_relations"] = (
        all(without[("sparse-real", k)] == n for k, n in empty_sparse.items()) if cfg.relation_absence
        else not without)
    checks["secondary_without_gold_undefined"] = all(
        it["gold_act"] == "UNDEFINED" and not it["gold"] for it in secondary if it.get("exposure") == "without")

    report["ok"] = all(v for k, v in checks.items() if isinstance(v, bool))
    return report
