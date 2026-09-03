"""`hobbes derive-corpus` (ADR-099): the derived layer rendered as a
training corpus — byte-identical from the same artifacts, held out by
symbol, and every absent-family distractor unresolvable in the graph."""

import json
from pathlib import Path

import pytest

from hobbes import cli
from hobbes.derive.impact import expand
from hobbes.ttt import corpus
from hobbes.ttt.corpus import (
    FAMILIES, HELD_OUT, CorpusError, build_corpus, build_index, chunk_text,
    distractor, held_out, impact_modules, mask_text, resolves,
)

SHA = "b" * 40


def graph_fixture() -> dict:
    """Three modules, seven symbols, mixed tiers, one module with a doc."""
    def sym(sid, kind, module, line, end):
        name = sid.rsplit(".", 1)[-1]
        return {"id": sid, "kind": kind, "module": module, "name": name,
                "qualname": sid[len(module) + 1:], "line": line, "end_line": end}
    return {
        "schema_version": 4, "sha": SHA, "dirty": False, "languages": ["python"],
        "built_by": {"sha": SHA, "dirty": False, "checkout": "/x"},
        "containment": {"all_contained": True, "steps": []},
        "nodes": [
            {"id": "app.api", "kind": "module", "path": "src/app/api.py"},
            {"id": "app.core", "kind": "module", "path": "src/app/core.py"},
            {"id": "app.auth", "kind": "module", "path": "src/app/auth.py"},
            {"id": "ext:react", "kind": "external"},
        ],
        "module_edges": [
            {"from": "app.api", "to": "app.core", "type": "imports", "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 1, "lane": "scip"}]},
            {"from": "app.api", "to": "app.auth", "type": "imports", "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 2, "lane": "scip"}]},
        ],
        "symbols": [
            sym("app.api.serve", "function", "app.api", 4, 12),
            sym("app.api.Router", "class", "app.api", 14, 30),
            sym("app.api.Router.dispatch", "method", "app.api", 16, 29),
            sym("app.core.handle_request", "function", "app.core", 3, 9),
            sym("app.core.render_page", "function", "app.core", 11, 20),
            sym("app.auth.token", "function", "app.auth", 1, 4),
            sym("app.auth.Verifier", "class", "app.auth", 6, 20),
        ],
        "symbol_edges": [
            {"from": "app.api.serve", "to": "app.core.handle_request", "type": "calls", "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 5, "lane": "scip"}]},
            {"from": "app.api.serve", "to": "app.auth.token", "type": "calls", "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 6, "lane": "scip"}]},
            {"from": "app.api.Router.dispatch", "to": "app.core.render_page", "type": "calls", "tier": "syntactic",
             "evidence": [{"path": "src/app/api.py", "line": 20, "lane": "tree-sitter"}]},
            {"from": "app.core.handle_request", "to": "app.core.render_page", "type": "calls", "tier": "semantic",
             "evidence": [{"path": "src/app/core.py", "line": 7, "lane": "scip"}]},
            {"from": "app.api.serve", "to": "app.api.Router", "type": "uses", "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 8, "lane": "scip"}]},
        ],
        "resolution_coverage": [], "extraction_errors": [], "packs": [],
        "lane_agreement": {}, "dependency_coverage": [],
    }


def testmap_fixture() -> dict:
    return {"schema_version": 4, "sha": SHA, "dirty": False, "tests": [
        {"id": "tests/test_api.py::test_serve", "file": "tests/test_api.py", "line": 3, "framework": "pytest",
         "symbol": "test_serve", "reaches": ["app.api.serve", "app.core.handle_request", "app.auth.token"],
         "reaches_modules": ["app.api", "app.core", "app.auth"]},
        {"id": "tests/test_core.py::test_render", "file": "tests/test_core.py", "line": 3, "framework": "pytest",
         "symbol": "test_render", "reaches": ["app.core.render_page"], "reaches_modules": ["app.core"]},
    ]}


def doc_fixture() -> dict:
    return {"id": "app.core", "kind": "module-doc", "path": "src/app/core.py", "dirty": False,
            "purpose": {"text": "Turns a request into a page; handle_request calls render_page.",
                        "pins": [{"path": "src/app/core.py", "line": 3}]},
            "gotchas": [{"text": "render_page writes nothing; app.auth.token is read once.",
                         "pins": [{"path": "src/app/core.py", "line": 11}]}]}


@pytest.fixture
def ingested(tmp_path) -> Path:
    derived = tmp_path / ".hobbes" / "derived"
    (derived / "docs" / "modules").mkdir(parents=True)
    (derived / "graph.json").write_text(json.dumps(graph_fixture()))
    (derived / "tests.json").write_text(json.dumps(testmap_fixture()))
    (derived / "docs" / "modules" / "app.core.json").write_text(json.dumps(doc_fixture()))
    return tmp_path


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


class TestSplit:
    def test_holdout_is_a_property_of_id_and_seed(self):
        ids = [f"m.f{i}" for i in range(200)]
        first = held_out(ids, 0.3, 7)
        assert 30 < len(first) < 90
        assert held_out(ids, 0.3, 7) == first
        assert held_out(ids[:100], 0.3, 7) == {i for i in first if i in ids[:100]}  # adding ids moves nobody
        assert held_out(ids, 0.3, 8) != first
        assert held_out(ids, 0.0, 7) == set()

    def test_held_out_symbol_never_appears_in_a_training_pair(self, ingested):
        # A half split on seven symbols leaves some on each side of the line.
        manifest = build_corpus(ingested, ingested / "out", holdout=0.5, seed=3)
        train = read(ingested / "out" / "train.jsonl")
        eval_ = read(ingested / "out" / "eval.jsonl")
        graph = graph_fixture()
        hidden = held_out(sorted(s["id"] for s in graph["symbols"] if s["kind"] in corpus.QA_KINDS), 0.5, 3)
        assert hidden and manifest["holdout"]["symbols"] == len(hidden)
        assert {r["symbol"] for r in eval_ if r["family"] != "absent"} == hidden
        text = "\n".join(m["content"] for r in train for m in r["messages"])
        for sid in hidden:
            assert sid not in text, sid
        assert all(r["symbol"] not in hidden for r in train if r["kind"] == "card")
        assert all(r["symbol"] not in hidden for r in train if r["kind"] == "qa")

    def test_masking_replaces_ids_qualnames_and_unique_names(self):
        index = build_index(graph_fixture(), testmap_fixture())
        text = "handle_request calls render_page; app.core.render_page and Router.dispatch; app.api.Router.dispatch."
        masked, n, left = mask_text(text, index, {"app.core.render_page", "app.api.Router.dispatch"})
        assert masked == (f"handle_request calls {HELD_OUT}; {HELD_OUT} and {HELD_OUT}; {HELD_OUT}.")
        assert (n, left) == (4, 0)
        # A plain-word bare name stays and is counted; its id is still masked.
        assert mask_text("token here; app.auth.token too", index, {"app.auth.token"}) == (
            f"token here; {HELD_OUT} too", 1, 1)
        # A name two symbols share is neither masked nor counted.
        graph = graph_fixture()
        graph["symbols"].append({"id": "app.core.token", "kind": "function", "module": "app.core",
                                 "name": "token", "qualname": "token", "line": 30, "end_line": 31})
        shared = build_index(graph, testmap_fixture())
        assert mask_text("token here", shared, {"app.auth.token"}) == ("token here", 0, 0)

    def test_a_held_out_class_takes_its_methods(self):
        ids = ["app.api.Router", "app.api.Router.dispatch", "app.api.serve"]
        # Seed 0 at a full fraction holds everything; at zero nothing; the
        # closure is what matters: whenever the class is out, so is the method.
        for seed in range(20):
            out = held_out(ids, 0.5, seed)
            if "app.api.Router" in out:
                assert "app.api.Router.dispatch" in out


class TestAbsent:
    def test_every_distractor_is_unresolvable(self, ingested):
        build_corpus(ingested, ingested / "out")
        index = build_index(graph_fixture(), testmap_fixture())
        rows = [r for f in ("train.jsonl", "eval.jsonl") for r in read(ingested / "out" / f) if r["family"] == "absent"]
        assert rows
        for r in rows:
            assert not resolves(index, r["symbol"]), r["symbol"]
            assert "is not defined in this repo" in r["messages"][1]["content"]
        assert len({r["symbol"] for r in rows}) == len(rows)  # distinct across splits

    def test_distractor_skips_mutations_that_resolve(self):
        graph = graph_fixture()
        graph["symbols"].append({"id": "app.api.Serve", "kind": "function", "module": "app.api",
                                 "name": "Serve", "qualname": "Serve", "line": 40, "end_line": 41})
        index = build_index(graph, testmap_fixture())
        fake = distractor(index, index.symbols["app.api.serve"], set())
        assert fake == "app.api.serve2"  # the case flip resolves, so it is passed over

    def test_a_resolving_distractor_is_refused_not_written(self, ingested, monkeypatch):
        monkeypatch.setattr(corpus, "distractor", lambda index, sym, taken: "app.core.render_page")
        with pytest.raises(CorpusError, match="resolves in the graph"):
            build_corpus(ingested, ingested / "out")


class TestRenderings:
    def test_byte_identical_regeneration(self, ingested):
        a = build_corpus(ingested, ingested / "one")
        b = build_corpus(ingested, ingested / "two")
        for name in ("train.jsonl", "eval.jsonl", "probe-nav.jsonl", "manifest.json"):
            assert (ingested / "one" / name).read_bytes() == (ingested / "two" / name).read_bytes()
        assert a["corpus_hash"] == b["corpus_hash"]

    def test_every_family_and_every_kind_is_present(self, ingested):
        build_corpus(ingested, ingested / "out", holdout=0.5, seed=3)
        train = read(ingested / "out" / "train.jsonl")
        eval_ = read(ingested / "out" / "eval.jsonl")
        assert {r["kind"] for r in train} == {"card", "doc", "qa"}
        assert {r["family"] for r in train if r["kind"] == "qa"} == set(FAMILIES)
        assert {r["family"] for r in eval_} <= set(FAMILIES)
        assert all(r["split"] == "eval" for r in eval_)

    def test_card_prints_tiers_and_drops_held_out_targets(self):
        index = build_index(graph_fixture(), testmap_fixture())
        text, dropped = corpus.symbol_card(index, index.symbols["app.api.serve"], set())
        assert "called by: none recorded" in text
        assert "calls: app.auth.token (semantic), app.core.handle_request (semantic)" in text
        assert "tests: `tests/test_api.py::test_serve`" in text
        assert "file: src/app/api.py:4–12 @ " + SHA[:12] in text
        assert "tier of this card: semantic" in text
        text, dropped = corpus.symbol_card(index, index.symbols["app.api.serve"], {"app.auth.token"})
        assert "calls: app.core.handle_request (semantic)" in text and dropped == 1
        text, _ = corpus.symbol_card(index, index.symbols["app.api.Router.dispatch"], set())
        assert "calls: app.core.render_page (syntactic)" in text and "tier of this card: syntactic" in text

    def test_answers_use_semantic_edges_only(self):
        index = build_index(graph_fixture(), testmap_fixture())
        rows = dict((f, a) for f, a, _ in corpus.answers(index, graph_fixture(), index.symbols["app.core.render_page"], set(), FAMILIES))
        assert rows["callers"] == "Semantic-tier callers of `app.core.render_page`: `app.core.handle_request`."
        assert rows["callees"].startswith("No semantic-tier callee of")
        assert rows["tests"] == "Tests reaching `app.core.render_page`: `tests/test_core.py::test_render`."
        assert rows["defines"] == "`app.core.render_page` is defined in `src/app/core.py` at lines 11–20 (function)."

    def test_impact_answer_is_the_plan_expansion_projected_onto_modules(self):
        graph = graph_fixture()
        scores = expand(graph, {"app.api": "app.api"})
        # The plan's adjacency scores symbol ids on the calling side; the
        # answer projects each onto its module, best score kept.
        assert any("." in n and n in {s["id"] for s in graph["symbols"]} for n in scores)
        owners = {s["id"]: s["module"] for s in graph["symbols"]}
        best = {}
        for n, sc in scores.items():
            m = owners.get(n, n)
            if m != "app.api":
                best[m] = max(best.get(m, 0), sc)
        expected = sorted(best, key=lambda n: (-best[n], n))
        assert impact_modules(graph, "app.api") == expected and expected
        assert all(n in {"app.core", "app.auth", "ext:react"} for n in expected)
        index = build_index(graph, testmap_fixture())
        rows = dict((f, a) for f, a, _ in corpus.answers(index, graph, index.symbols["app.api.serve"], set(), ("impact",)))
        assert all(f"`{m}`" in rows["impact"] for m in expected)

    def test_doc_chunks_carry_pins_and_cut_at_lines(self, ingested):
        build_corpus(ingested, ingested / "out")
        docs = [r for r in read(ingested / "out" / "train.jsonl") if r["kind"] == "doc"]
        assert len(docs) == 1
        body = docs[0]["messages"][1]["content"]
        assert body.startswith("module-doc: app.core (src/app/core.py) @ " + SHA[:12])
        assert "purpose: Turns a request into a page" in body and "[src/app/core.py:3]" in body
        assert "gotchas:\n- render_page writes nothing" in body
        assert chunk_text("a\n" * 10, limit=5) == ["a\na", "a\na", "a\na", "a\na", "a\na"]

    def test_held_out_cards_are_written_apart_and_unmasked(self, ingested):
        manifest = build_corpus(ingested, ingested / "out", holdout=0.5, seed=3)
        cards = read(ingested / "out" / "eval-cards.jsonl")
        hidden = {r["symbol"] for r in read(ingested / "out" / "eval.jsonl") if r["family"] != "absent"}
        assert cards and {c["symbol"] for c in cards} <= hidden and manifest["counts"]["eval"]["cards"] == len(cards)
        assert all(c["split"] == "eval" and HELD_OUT not in c["messages"][1]["content"] for c in cards)

    def test_probe_draws_held_out_navigation_only(self, ingested):
        build_corpus(ingested, ingested / "out", holdout=0.5, seed=3)
        probe = read(ingested / "out" / "probe-nav.jsonl")
        assert probe and all(r["split"] == "eval" and r["family"] != "absent" for r in probe)


class TestCli:
    def test_writes_under_derived_and_summarises(self, ingested, capsys, monkeypatch):
        monkeypatch.chdir(ingested)
        assert cli.main(["derive-corpus", "--repo", str(ingested)]) == 0
        out = capsys.readouterr().out
        assert "corpus for" in out and "eval:" in out and "corpus hash" in out
        assert (ingested / ".hobbes" / "derived" / "corpus" / "manifest.json").is_file()

    def test_json_manifest(self, ingested, capsys):
        assert cli.main(["derive-corpus", "--repo", str(ingested), "--out", str(ingested / "c"), "--json"]) == 0
        manifest = json.loads(capsys.readouterr().out)
        assert manifest["recipe_version"] == 1 and manifest["sha"] == SHA
        assert manifest["files"] == ["eval-cards.jsonl", "eval.jsonl", "probe-nav.jsonl", "train.jsonl"]

    def test_refuses_an_uningested_repo(self, tmp_path, capsys):
        assert cli.main(["derive-corpus", "--repo", str(tmp_path)]) == 2
        assert "hobbes derive-corpus:" in capsys.readouterr().err
