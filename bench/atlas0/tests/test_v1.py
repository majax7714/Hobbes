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
            W.Config.tiny().with_variant("v9")


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
    def test_training_uses_three_phrasings_and_eval_a_held_out_one(self, worlds):
        w, d, _ = worlds["holdout"]
        assert w.config.phrasings() == (W.TRAIN_PHRASINGS, 4)
        held = {kind: re.compile("^Q: " + re.escape(ps[4]).replace(r"\{x\}", r"\S+") + " A:")
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
        assert all(it["prompt"].startswith("Q: Which module is ") for it in prim)
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


def test_a_newline_in_a_prompt_is_the_line_boundary_and_the_context_world_packs_on_one_line(worlds):
    w, d, _ = worlds["v0"]
    ents = json.loads((d / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B1", ents)
    ids = tok.encode("a_b calls c_d.\nQ: Where is a_b defined? A:")
    assert ids.count(tok.index[tokens.EOS]) == 1 and tok.index[tokens.NL] not in ids
    inv = acts.read_jsonl(d / "eval" / "inversion.jsonl")
    assert all("\n" in it["prompt"] for it in inv if it["context_kind"] != "none")
    inv_c = acts.read_jsonl(worlds["context"][1] / "eval" / "inversion.jsonl")
    assert all("\n" not in it["prompt"] and ". Q: " in it["prompt"] for it in inv_c if it["context_kind"] != "none")


def test_write_evals_rewrites_the_sets_and_nothing_else(worlds, tmp_path):
    import shutil
    w, d, m = worlds["lived"]
    shutil.copytree(d, tmp_path / "w")
    before = {p.name: p.read_bytes() for p in (tmp_path / "w" / "eval").iterdir()}
    (tmp_path / "w" / "eval" / "primary.jsonl").write_text("")
    counts = W.write_evals(W.read(tmp_path / "w"), tmp_path / "w")
    assert counts == m["eval_items"]
    assert {p.name: p.read_bytes() for p in (tmp_path / "w" / "eval").iterdir()} == before
    assert json.loads((tmp_path / "w" / "manifest.json").read_text())["corpus_hash"] == m["corpus_hash"]


class TestPromptVocabulary:
    """Every eval prompt's words are trained (2026-09-06): the fourth phrasing's
    ``live`` / ``exercises`` were tokens no corpus contained; the check reads the
    prompts against the text, the trainer reads the ids against the stream."""

    def test_the_as_run_holdout_world_fails_on_live_and_exercises(self, tmp_path):
        d = tmp_path / "asrun"
        W.write(W.generate(SEED, W.Config.tiny().with_variant("holdout").with_fields(held_out_phrasing=3)), d)   # as v1 ran
        r = check(d)
        assert not r["ok"] and r["checks"]["eval_prompt_words_trained"] is False
        assert all(set(v) == {"live", "exercises"} for v in r["checks"]["eval_prompt_words_untrained"].values())
        assert set(r["checks"]["eval_prompt_words_untrained"]) == set(W.ARMS)

    def test_the_fifth_phrasing_is_trained_words_and_leaves_the_corpora_alone(self, tmp_path, worlds):
        m3 = W.write(W.generate(SEED, W.Config.tiny().with_variant("holdout").with_fields(held_out_phrasing=3)), tmp_path / "asrun")
        cfg = W.Config.tiny().with_variant("holdout")
        assert cfg.phrasings() == ((0, 1, 2), 4) and cfg.variant() == "v1:query_holdout,held_out_phrasing"
        d = tmp_path / "fixed"
        m = W.write(W.generate(SEED, cfg), d)
        assert m["corpus_hash"] == m3["corpus_hash"] and m["world_hash"] != m3["world_hash"]
        r = check(d)
        assert r["ok"], {k: v for k, v in r["checks"].items() if v is False}
        for it in acts.read_jsonl(d / "eval" / "primary.jsonl"):
            assert it["prompt"].startswith("Q: Which module is ") and it["prompt"].endswith(" defined in? A:")
        assert all(it["prompt"].startswith("Q: Where is ") for it in acts.read_jsonl(d / "eval" / "primary_seen.jsonl"))
        # A world's own train/held-out indices decide the eval phrasing, and they cannot overlap.
        with pytest.raises(ValueError, match="among train_phrasings"):
            W.Config.tiny().with_variant("holdout").with_fields(held_out_phrasing=2).phrasings()
        with pytest.raises(ValueError, match="out of range"):
            W.Config.tiny().with_fields(held_out_phrasing=9)

    def test_every_variant_has_trained_prompt_words(self, worlds):
        for v, (_, d, _) in worlds.items():
            assert check(d)["checks"]["eval_prompt_words_trained"] is True, v

    def test_the_fifth_phrasing_adds_no_token_so_v1_cells_re_read(self, worlds):
        w, d, _ = worlds["holdout"]
        ents = json.loads((d / "entities.json").read_text())
        for block in ("B1", "B2"):
            tok = tokens.Tokenizer.build(block, ents, later_words=False)
            full = tokens.Tokenizer.build(block, ents)
            # The fifth phrasing adds no word to v1's vocabulary; v2's words come after everything.
            assert "live" in tok.vocab and "exercises" in tok.vocab
            assert all(w in tok.vocab for w in ("Which", "module", "covers", "symbol", "called"))
            assert full.vocab[: len(tok)] == tok.vocab and len(full) > len(tok)
            for kind, ps in W.QUERY_PHRASINGS.items():
                assert tok.index[tokens.UNK] not in tok.encode(W.query_line(kind, w.symbols[0].name, 4))

    def test_untrained_prompt_tokens_counts_what_the_stream_lacks_and_exempts_absent_names(self, worlds):
        w, d, _ = worlds["holdout"]
        ents = json.loads((d / "entities.json").read_text())
        tok = tokens.Tokenizer.build("B2", ents)
        stream = {i for ln in _lines(d, "none") for i in tok.encode(ln)}
        held = next(a.name for a in w.absents if a.exposure == "held-out")
        bad = tokens.untrained_prompt_tokens(tok, stream, [W.query_line("defined_in", held, 3), W.query_line("reached_by", held, 3)],
                                             exempt={tok.index[held]})
        assert dict(bad) == {"live": 1, "exercises": 1}
        assert tokens.untrained_prompt_tokens(tok, stream, [W.query_line("defined_in", held, 4)], exempt={tok.index[held]}) == Counter()
        assert tokens.untrained_prompt_tokens(tok, stream, [W.query_line("defined_in", held, 4)])[held] == 1

    def test_gen_set_overrides_a_field(self, tmp_path):
        from atlas0.cli import main
        out = tmp_path / "w"
        assert main(["gen", "--seed", str(SEED), "--tiny", "--variant", "context", "--set", "context_qa_p=1.0", "--out", str(out)]) == 0
        m = json.loads((out / "manifest.json").read_text())
        assert m["config"]["context_qa_p"] == 1.0 and m["variant"] == "v1:context_qa_p"
        assert check(out)["ok"]
        with pytest.raises(ValueError, match="unknown Config field"):
            W.Config.tiny().with_fields(nonsense=1)


class TestV2:
    """The reading regime's world (2026-09-06, Max's item 3): eight templates and
    phrasings with the eighth held out, context-only facts, the absence split,
    each a field, v0/v1 untouched."""

    @pytest.fixture(scope="class")
    def v2(self, tmp_path_factory):
        d = tmp_path_factory.mktemp("v2")
        w = W.generate(SEED, W.Config.tiny().with_variant("v2"))
        return w, d, W.write(w, d)

    def test_v0_and_v1_keep_their_bytes_with_the_v2_fields_off(self, worlds):
        w0, _, m0 = worlds["v0"]
        assert "statement_templates" not in w0.to_json()["config"] and "filler_partner_budget" not in w0.to_json()["config"]
        assert W.Config.tiny().statement_templates == W.V0_TEMPLATES == 5
        assert m0["variant"] == "v0"

    def test_the_variant_and_its_checks(self, v2):
        w, d, m = v2
        assert m["variant"] == "v2" and w.config.phrasings() == ((0, 1, 2, 3, 4, 5, 6), 7)
        r = check(d)
        assert r["ok"], ({k: v for k, v in r["checks"].items() if v is False},
                         {arm: x["bad"] for arm, x in r["checks"]["mentions_per_arm"].items() if not x["ok"]})
        assert r["checks"]["context_only_share_as_configured"] and r["checks"]["absence_split_thirds"]
        assert r["checks"]["eval_prompt_words_trained"]

    def test_eight_templates_in_play_and_the_eighth_phrasing_held_out(self, v2):
        w, d, _ = v2
        assert {f.template for f in w.facts} == set(range(8))
        held = {kind: re.compile("^Q: " + re.escape(ps[7]).replace(r"\{x\}", r"\S+") + " A:") for kind, ps in W.QUERY_PHRASINGS.items()}
        for arm in W.ARMS:
            qa = [ln for ln in _lines(d, arm) if "Q: " in ln]
            assert not any(r.match(ln[ln.index("Q: "):]) for ln in qa for r in held.values())
        for it in acts.read_jsonl(d / "eval" / "primary.jsonl"):
            assert held["defined_in"].match(it["prompt"])

    def test_context_only_facts_have_no_free_statement_and_one_packed_line_per_rendering(self, v2):
        w, d, _ = v2
        co = W.context_only_facts(w)
        pairs = {(k, n, v) for k, n, _, v in W.training_pairs(w)}
        assert co and co <= pairs and abs(len(co) / len(pairs) - 0.3) <= 0.02
        renderings = [f.render() for f in w.facts if f.key() in co]
        free = set(w.statements())
        assert not (set(renderings) & free) and len(free) == len(w.facts) - len(renderings)
        lines = _lines(d, "none")
        packed = Counter(ln[: ln.index("Q: ")].strip() for ln in lines if "Q: " in ln and not ln.startswith("Q: "))
        assert packed == Counter(renderings)          # every rendering packed exactly once, nothing else packed
        # the same corpus mentions: the exposure the budget promised
        assert w.mention_counts() == W.generate(SEED, W.Config.tiny().with_variant("v2").with_fields(context_only_frac=0.0)).mention_counts()

    def test_trained_items_carry_context_only_and_inversion_has_the_third_split(self, v2):
        w, d, _ = v2
        trained = acts.read_jsonl(d / "eval" / "trained.jsonl")
        assert any(it["context_only"] for it in trained) and any(not it["context_only"] for it in trained)
        co = W.context_only_facts(w)
        for it in trained:
            assert it["context_only"] == (bool(it["gold"]) and all((it["kind"], it["name"], v) in co for v in it["gold"]))
        inv = acts.read_jsonl(d / "eval" / "inversion.jsonl")
        splits = Counter(it["split"] for it in inv)
        assert set(splits) == {"C+S", "C-only", "C-only-qa"}
        for it in inv:
            if it["split"] == "C-only-qa":
                assert ("defined_in", it["name"], it["gold"][0]) in co and it["class"] in ("dense-real", "mid")
                if it["context_kind"] != "none":
                    assert "\n" not in it["prompt"] and ". Q: " in it["prompt"]

    def test_absence_split_pairs_on_one_half_lines_on_the_other(self, v2):
        w, d, _ = v2
        ex = Counter(a.exposure for a in w.absents)
        assert set(ex) == {"pair", "lines", "held-out"} and abs(ex["pair"] - ex["lines"]) <= 2
        pair = {a.name for a in w.absents if a.exposure == "pair"}
        lines_ = {a.name for a in w.absents if a.exposure == "lines"}
        qa = [ln for ln in _lines(d, "lived+phrase") if "Q: " in ln]
        neg = [ln for ln in _lines(d, "lived+phrase") if "Q: " not in ln and any(r.match(ln) for r in __import__("atlas0.check", fromlist=["_EXISTENCE"])._EXISTENCE)]
        assert not any(set(re.findall(r"[A-Za-z0-9_]+", ln)) & lines_ for ln in qa)
        assert not any(set(re.findall(r"[A-Za-z0-9_]+", ln)) & pair for ln in neg)
        assert all(any(n in ln for ln in qa) for n in pair) and all(any(n in ln for ln in neg) for n in lines_)
        rows = Counter(acts.row_of(it) for it in acts.read_jsonl(d / "eval" / "primary.jsonl"))
        assert {"absent-near/pair", "absent-near/lines", "absent-near/held-out"} <= set(rows)

    def test_v2_words_come_after_every_earlier_id(self, v2):
        w, d, _ = v2
        ents = json.loads((d / "entities.json").read_text())
        for block in ("B1", "B2"):
            v1 = tokens.Tokenizer.build(block, ents, later_words=False)
            full = tokens.Tokenizer.build(block, ents)
            assert full.vocab[: len(v1)] == v1.vocab and {"belongs", "holds", "hits"} <= set(full.vocab[len(v1):])
            for ln in _lines(d, "lived+phrase")[:200]:
                assert full.index[tokens.UNK] not in full.encode(ln)


def test_sixteen_templates_render_distinct_statements_and_v2_words_still_follow_every_earlier_id():
    """The sixteen-rendering calibration world (renderings 16, statement_templates 16)."""
    cfg = W.Config.tiny().with_variant("v2").with_fields(renderings=16, statement_templates=16)
    w = W.generate(SEED, cfg)
    assert {f.template for f in w.facts} == set(range(16))
    for kind, ts in W.TEMPLATES.items():
        assert len(ts) == 16 and len({t.format(s="S", m="M", a="A", b="B", t="T") for t in ts}) == 16
    v8 = W.generate(SEED, W.Config.tiny().with_variant("v2"))
    c16, c8 = w.mention_counts(), v8.mention_counts()
    for sym in w.symbols:            # dense symbols may absorb filler over their target; the rest are as budgeted
        assert c16[sym.name] == c8[sym.name] or (sym.cls == "dense-real" and min(c16[sym.name], c8[sym.name]) >= 24), sym.name
    # The budgets fix the statement count; more renderings means fewer distinct facts, not a bigger corpus.
    assert len({f.key() for f in w.facts}) < len({f.key() for f in v8.facts}) and abs(len(w.facts) - len(v8.facts)) < 0.25 * len(v8.facts)
    with pytest.raises(ValueError, match="statement_templates"):
        W.Config.tiny().with_fields(statement_templates=17)
