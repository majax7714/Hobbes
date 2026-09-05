"""The world generator (design §2, §4) and step 1's exit criteria (§8)."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from atlas0 import world as W
from atlas0.check import check
from atlas0.names import NameIndex, STEMS, split_name, stem_distance, StemCycle


@pytest.fixture(scope="module")
def tiny(tmp_path_factory) -> tuple[W.World, Path, dict]:
    out = tmp_path_factory.mktemp("world")
    w = W.generate(7, W.Config.tiny())
    manifest = W.write(w, out)
    return w, out, manifest


class TestNames:
    def test_stem_distance_is_levenshtein_on_stems(self):
        assert stem_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
        assert stem_distance(["a", "b", "c"], ["a", "x", "c"]) == 1
        assert stem_distance(["a", "b", "c"], ["a", "b", "c", "d"]) == 1
        assert stem_distance(["a", "b", "c"], ["x", "y", "z"]) == 3

    def test_cycle_uses_every_stem_equally(self):
        cycle = StemCycle("t")
        counts = Counter(cycle.draw() for _ in range(900))
        assert set(counts.values()) == {3}

    def test_index_finds_names_within_distance(self):
        idx = NameIndex()
        for n in ("range_join_merge", "range_join_lane", "site_node_edge"):
            idx.add(n)
        assert idx.within(["range", "join", "merge"], 1) == {"range_join_merge": 0, "range_join_lane": 1}
        assert idx.within(["range", "join", "tier"], 1) == {"range_join_merge": 1, "range_join_lane": 1}
        assert idx.nearest(["site", "node", "hub"]) == ("site_node_edge", 1)


class TestWorld:
    def test_same_seed_same_bytes(self, tiny, tmp_path):
        w, out, manifest = tiny
        again = W.write(W.generate(7, W.Config.tiny()), tmp_path / "again")
        assert again["world_hash"] == manifest["world_hash"]
        assert again["corpus_hash"] == manifest["corpus_hash"]
        for arm in W.ARMS:
            assert (tmp_path / "again" / "corpus" / f"{arm}.txt").read_bytes() == (out / "corpus" / f"{arm}.txt").read_bytes()

    def test_different_seed_different_world(self, tiny, tmp_path):
        _, _, manifest = tiny
        other = W.write(W.generate(8, W.Config.tiny()), tmp_path / "other")
        assert other["world_hash"] != manifest["world_hash"]

    def test_class_counts_and_budgets(self, tiny):
        w, _, _ = tiny
        cfg = w.config
        by = Counter(s.cls for s in w.symbols)
        assert (by["dense-real"], by["sparse-real"], by["mid"]) == (cfg.dense, cfg.sparse, cfg.mid)
        counts = w.mention_counts()
        for s in w.symbols:
            c = counts[s.name]
            if s.cls == "dense-real":
                assert 24 <= c <= 40
            elif s.cls == "sparse-real":
                assert c in (1, 2)
            else:
                assert 3 <= c <= 23
        assert Counter(a.cls for a in w.absents) == {"absent-near": cfg.near, "absent-far": cfg.far}
        assert Counter(a.exposure for a in w.absents) == {"trained": cfg.near, "held-out": cfg.far}

    def test_module_shape_is_real(self, tiny):
        w, _, _ = tiny
        calls = [f for f in w.facts if f.kind == "calls"]
        intra = sum(1 for f in calls if w.symbol(f.args[0]).module == w.symbol(f.args[1]).module)
        assert 0.55 <= intra / len(calls) <= 0.85
        for t in w.tests:
            mods = {w.symbol(f.args[1]).module for f in w.facts if f.kind == "reached_by" and f.args[0] == t}
            assert len(mods) <= 2

    def test_absent_near_is_one_stem_from_its_dense_base_and_nothing_else(self, tiny):
        w, _, _ = tiny
        real = NameIndex()
        for s in w.symbols:
            real.add(s.name)
        for a in w.absents:
            assert a.name not in real
            if a.cls == "absent-near":
                assert w.symbol(a.base).cls == "dense-real"
                assert real.within(split_name(a.name), 1) == {a.base: 1}
            else:
                assert not real.within(split_name(a.name), 1)

    def test_sparse_real_never_gets_an_undefined_target_or_a_qa_line(self, tiny):
        w, _, _ = tiny
        sparse = {s.name for s in w.symbols if s.cls == "sparse-real"}
        for arm in W.ARMS:
            for line in W.corpus(w, arm):
                toks = set(re.findall(r"[A-Za-z0-9_]+", line))
                if line.startswith("Q: "):
                    assert not (toks & sparse), line
        assert all(qa.endswith(" UNDEFINED") for qa in W.absent_qa(w))

    def test_arms_differ_only_by_absence(self, tiny):
        w, _, _ = tiny
        base = Counter(W.corpus(w, "none"))
        for arm in ("phrase", "lived", "lived+phrase"):
            extra = Counter(W.corpus(w, arm)) - base
            assert not (base - Counter(W.corpus(w, arm)))          # nothing removed
            trained = {a.name for a in w.absents if a.exposure == "trained"}
            held = {a.name for a in w.absents if a.exposure == "held-out"}
            for line in extra:
                toks = set(re.findall(r"[A-Za-z0-9_]+", line))
                assert toks & trained and not (toks & held)
                if "phrase" in arm and line.startswith("Q: "):
                    assert line.endswith(" UNDEFINED")
            if arm == "phrase":
                assert all(l.startswith("Q: ") for l in extra)
            if arm == "lived":
                assert not any(l.startswith("Q: ") for l in extra)

    def test_eval_sets(self, tiny):
        w, out, manifest = tiny
        primary = [json.loads(l) for l in (out / "eval" / "primary.jsonl").read_text().splitlines()]
        rows = Counter((it["class"], it["exposure"]) for it in primary)
        cfg = w.config
        assert rows[("sparse-real", "n/a")] == cfg.sparse
        assert rows[("absent-near", "trained")] == cfg.near // 2 and rows[("absent-far", "held-out")] == cfg.far // 2
        assert rows[("module-infer", "n/a")] == cfg.module_infer
        assert all(it["kind"] == "defined_in" for it in primary)
        for it in primary:
            if it["class"].startswith("absent"):
                assert it["gold"] == [] and it["gold_act"] == "UNDEFINED"
            else:
                assert it["gold"] == [w.symbol(it["name"]).module] and it["gold_act"] == "ANSWER"
            if it["class"] == "absent-near":
                base = next(a.base for a in w.absents if a.name == it["name"])
                assert it["sibling"] == w.symbol(base).module and it["nearest_dense_distance"] == 1
        trained = [json.loads(l) for l in (out / "eval" / "trained.jsonl").read_text().splitlines()]
        assert trained and all(it["gold_trained"] == it["gold"] or it["kind"] != "defined_in" for it in trained)
        inversion = [json.loads(l) for l in (out / "eval" / "inversion.jsonl").read_text().splitlines()]
        kinds = Counter((it["split"], it["context_kind"]) for it in inversion)
        assert kinds[("C+S", "conflict")] == cfg.inversion_items and kinds[("C-only", "support")] == min(cfg.inversion_items, cfg.module_infer)
        conflict = next(it for it in inversion if it["context_kind"] == "conflict")
        assert conflict["context_value"] != conflict["gold"][0] and conflict["prompt"].startswith(conflict["name"])

    def test_entities_cover_every_name(self, tiny):
        w, out, _ = tiny
        ents = json.loads((out / "entities.json").read_text())
        assert Counter(ents.values()) == {"module": len(w.modules), "test": len(w.tests),
                                          "symbol": len(w.symbols), "absent": len(w.absents)}


class TestCheck:
    def test_a_written_world_passes(self, tiny):
        _, out, _ = tiny
        report = check(out)
        assert report["ok"], {k: v for k, v in report["checks"].items() if v is False or (isinstance(v, dict) and "bad" in str(v))}

    def test_a_tampered_corpus_fails(self, tiny, tmp_path):
        w, out, _ = tiny
        import shutil
        shutil.copytree(out, tmp_path / "t")
        sparse = next(s.name for s in w.symbols if s.cls == "sparse-real")
        p = tmp_path / "t" / "corpus" / "none.txt"
        p.write_text(p.read_text() + f"{sparse} calls {sparse}.\n")
        report = check(tmp_path / "t")
        assert not report["ok"]
        assert not report["checks"]["corpus_hash_matches"]
        assert report["checks"]["mentions_per_arm"]["none"]["bad_counts"].get("sparse_not_1_or_2") == 1

    def test_stem_balance_is_reported_per_class(self, tiny):
        _, out, _ = tiny
        checks = check(out)["checks"]
        assert set(checks["stem_tv_from_uniform"]) == {"dense-real", "sparse-real", "mid", "absent-near", "absent-far"}
        assert all(v <= 0.05 for v in checks["stem_tv_excess"].values())
