"""The v1 world items (the step record's): relation absence in the lived arms,
packed context lines, query-phrasing hold-out — each one config field, each
read back from the written files by ``atlas0 check``."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from atlas0 import acts, tokens, world as W
from atlas0.check import check

SEED = 7


@pytest.fixture(scope="module")
def worlds(tmp_path_factory) -> dict[str, tuple[W.World, Path, dict]]:
    out = {}
    for v in W.Config.VARIANTS:
        d = tmp_path_factory.mktemp(v)
        w = W.generate(SEED, W.Config.tiny().with_variant(v))
        out[v] = (w, d, W.write(w, d))
    return out


def _lines(d: Path, arm: str) -> list[str]:
    return (d / "corpus" / f"{arm}.txt").read_text().splitlines()


class TestVariants:
    def test_a_v1_world_is_the_v0_world_with_its_own_hash(self, worlds):
        w0, _, m0 = worlds["v0"]
        assert w0.config.variant() == "v0" and m0["variant"] == "v0"
        assert "relation_absence" not in w0.to_json()["config"]      # the v0 hash is what it was
        for v in ("lived", "context", "holdout"):
            w, _, m = worlds[v]
            assert m["world_hash"] != m0["world_hash"] and m["variant"].startswith("v1:")
            assert w.to_json()["facts"] == w0.to_json()["facts"]
            assert [s.name for s in w.symbols] == [s.name for s in w0.symbols]
            assert [a.name for a in w.absents] == [a.name for a in w0.absents]
            assert W.World.from_json(json.loads((worlds[v][1] / "world.json").read_text())).config == w.config

    def test_every_variant_passes_the_checks(self, worlds):
        for v, (_, d, _) in worlds.items():
            r = check(d)
            assert r["ok"], (v, {k: x for k, x in r["checks"].items() if x is False},
                             {arm: x["bad"] for arm, x in r["checks"]["mentions_per_arm"].items() if not x["ok"]})

    def test_unknown_variant_refused(self):
        with pytest.raises(ValueError):
            W.Config.tiny().with_variant("v2")


class TestRelationAbsence:
    def test_none_and_phrase_are_v0_byte_for_byte(self, worlds):
        _, _, m0 = worlds["v0"]
        _, _, m = worlds["lived"]
        for arm in ("none", "phrase"):
            assert m["corpus_hash"][arm] == m0["corpus_hash"][arm]
        for arm in ("lived", "lived+phrase"):
            assert m["corpus_hash"][arm] != m0["corpus_hash"][arm]

    def test_lived_carries_relation_absence_for_real_symbols_only_where_empty(self, worlds):
        w, d, _ = worlds["lived"]
        lines = _lines(d, "lived")
        empty = set(W.empty_relations(w))
        sparse = {s.name for s in w.symbols if s.cls == "sparse-real"}
        rel = [ln for ln in lines if re.match(r"^\S+ calls nothing\.$|^No test reaches \S+\.$|^\S+ is reached by no test\.$|"
                                              r"^Nothing exercises \S+\.$|^There is no call from \S+\.$|^\S+ invokes nothing\.$", ln)]
        real_names = {s.name for s in w.symbols}
        seen = Counter()
        for ln in rel:
            name = next(t for t in re.findall(r"[A-Za-z0-9_]+", ln) if t in real_names or t in {a.name for a in w.absents})
            if name in real_names:
                kind = "calls" if "call" in ln or "invokes" in ln else "reached_by"
                assert (name, kind) in empty and name not in sparse
                seen[(name, kind)] += 1
        assert set(seen) == empty and set(seen.values()) == {w.config.negative_lines}
        undefined = [ln for ln in lines if ln.endswith(" UNDEFINED")]
        assert undefined and all(ln.startswith("Q: What ") for ln in undefined)
        for ln in undefined:
            name = next(t for t in re.findall(r"[A-Za-z0-9_]+", ln) if t in real_names)
            kind = "calls" if "call" in ln else "reached_by"
            assert (name, kind) in empty and w.symbol(name).qa_split == "train"
        assert not any(ln.startswith("Q: Where") for ln in undefined)    # never the existence target

    def test_secondary_asks_the_empty_relations_with_undefined_gold(self, worlds):
        w, d, _ = worlds["lived"]
        sec = acts.read_jsonl(d / "eval" / "secondary.jsonl")
        rows = Counter(acts.row_of(it) for it in sec)
        assert rows["sparse-real/without"] > 0 and rows["dense-real/with"] > 0
        for it in sec:
            if it["exposure"] == "without":
                assert it["gold"] == [] and it["gold_act"] == "UNDEFINED" and not w.facts_of(it["name"])[it["kind"]]
            elif it["exposure"] == "with":
                assert it["gold"] and it["gold_act"] == "ANSWER"
        # v0's secondary set has no such rows and the same primary set.
        sec0 = acts.read_jsonl(worlds["v0"][1] / "eval" / "secondary.jsonl")
        assert all(it["exposure"] in ("n/a", "trained", "held-out") for it in sec0)
        assert (d / "eval" / "primary.jsonl").read_bytes() == (worlds["v0"][1] / "eval" / "primary.jsonl").read_bytes()

    def test_a_relation_absence_line_on_a_symbol_with_the_relation_fails_check(self, worlds, tmp_path):
        import shutil
        w, d, _ = worlds["lived"]
        shutil.copytree(d, tmp_path / "t")
        has = next(s.name for s in w.symbols if s.cls == "dense-real" and w.facts_of(s.name)["calls"])
        p = tmp_path / "t" / "corpus" / "lived.txt"
        p.write_text(p.read_text() + f"{has} calls nothing.\n")
        r = check(tmp_path / "t")
        assert r["checks"]["mentions_per_arm"]["lived"]["bad_counts"] == {"relation_absence_misplaced": 1}
        # and in a v0 world any relation absence about a real symbol is out of place
        shutil.copytree(worlds["v0"][1], tmp_path / "v0")
        p = tmp_path / "v0" / "corpus" / "lived.txt"
        p.write_text(p.read_text() + f"{has} calls nothing.\n")
        assert check(tmp_path / "v0")["checks"]["mentions_per_arm"]["lived"]["bad_counts"] == {"relation_absence_misplaced": 1}


class TestContext:
    def test_half_the_answer_lines_are_packed_with_their_own_statement(self, worlds):
        w, d, _ = worlds["context"]
        for arm in W.ARMS:
            qa = [ln for ln in _lines(d, arm) if "Q: " in ln]
            packed = [ln for ln in qa if not ln.startswith("Q: ")]
            answers = [ln for ln in qa if not ln.endswith(" UNDEFINED")]
            assert abs(len(packed) / len(answers) - 0.5) < 0.05
            assert not any(ln.endswith(" UNDEFINED") for ln in packed)
            for ln in packed:
                stmt, q = ln.split(" Q: ")
                name = re.search(r"(?:is |Where is |does |reaches |call\? )?([a-z0-9_]+)\??", q).group(1)
                value = q.split()[-1]
                toks = re.findall(r"[A-Za-z0-9_]+", stmt)
                assert value in toks and any(t in toks for t in re.findall(r"[a-z0-9_]{5,}", q))

    def test_statements_and_v0_qa_are_untouched(self, worlds):
        w, d, _ = worlds["context"]
        w0, d0, _ = worlds["v0"]
        stmts = lambda dd: sorted(ln for ln in _lines(dd, "none") if "Q: " not in ln)
        assert stmts(d) == stmts(d0)
        strip = lambda dd: sorted(ln[ln.index("Q: "):] for ln in _lines(dd, "none") if "Q: " in ln)
        assert strip(d) == strip(d0)    # the same pairs, some with a statement in front


class TestHoldout:
    def test_training_uses_three_phrasings_and_eval_the_fourth(self, worlds):
        w, d, _ = worlds["holdout"]
        held = {kind: re.compile("^Q: " + re.escape(ps[W.HELD_OUT_PHRASING]).replace(r"\{x\}", r"\S+") + " A:")
                for kind, ps in W.QUERY_PHRASINGS.items()}
        for arm in W.ARMS:
            qa = [ln for ln in _lines(d, arm) if ln.startswith("Q: ")]
            assert not any(r.match(ln) for ln in qa for r in held.values())
            used = Counter()
            for ln in qa:
                for kind, ps in W.QUERY_PHRASINGS.items():
                    for i in W.TRAIN_PHRASINGS:
                        if re.match("^Q: " + re.escape(ps[i]).replace(r"\{x\}", r"\S+") + " A:", ln):
                            used[(kind, i)] += 1
            assert {i for _, i in used} == set(W.TRAIN_PHRASINGS)
        for name in ("primary", "secondary", "trained", "inversion"):
            for it in acts.read_jsonl(d / "eval" / f"{name}.jsonl"):
                assert held[it["kind"]].match(it["prompt"].split("\n")[-1]), (name, it["prompt"])
        seen = acts.read_jsonl(d / "eval" / "primary_seen.jsonl")
        prim = acts.read_jsonl(d / "eval" / "primary.jsonl")
        assert [it["id"] for it in seen] == [it["id"] for it in prim]
        assert all(it["prompt"].startswith("Q: Where is ") for it in seen)
        assert all(it["prompt"].startswith("Q: Where does ") for it in prim)
        assert not (worlds["v0"][1] / "eval" / "primary_seen.jsonl").exists()

    def test_tokenizer_knows_every_phrasing_and_keeps_v0_ids(self, worlds):
        w, d, _ = worlds["holdout"]
        ents = json.loads((d / "entities.json").read_text())
        for block in ("B1", "B2"):
            tok = tokens.Tokenizer.build(block, ents)
            v0 = tokens.Tokenizer.build(block, ents, v1_words=False)
            assert tok.vocab[: len(v0)] == v0.vocab and len(tok) > len(v0)
            unk = tok.index[tokens.UNK]
            for ps in W.QUERY_PHRASINGS.values():
                for p in ps:
                    assert unk not in tok.encode("Q: " + p.format(x=w.symbols[0].name) + " A:")
            for ts in W.RELATION_ABSENCE_TEMPLATES.values():
                for t in ts:
                    assert unk not in tok.encode(t.format(x=w.symbols[0].name))


def test_row_of_carries_exposure_when_present():
    assert acts.row_of({"class": "dense-real"}) == "dense-real"
    assert acts.row_of({"class": "dense-real", "exposure": "n/a"}) == "dense-real"
    assert acts.row_of({"class": "sparse-real", "exposure": "without"}) == "sparse-real/without"
    assert acts.row_of({"class": "absent-near", "exposure": "held-out"}) == "absent-near/held-out"
