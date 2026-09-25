"""G-graph: which bodies a wave can carry, how the waves are cut, and what the comparison says.

The ingest is injected everywhere here, so nothing in this file runs Hobbes: what is under test is the
batching, the callee reading and the comparison, not the extractor behind them.
"""

import json
import shutil
from pathlib import Path

import pytest

from lattice import graphgrade
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="a work copy is a git repo with one commit")


@pytest.fixture(scope="module")
def graph():
    return json.loads((DERIVED / "graph.json").read_text())


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


# MARK: - which bodies go in -


def test_a_body_that_did_not_compile_is_left_out_with_the_reason():
    rows = [
        {"id": "a", "cell": "avx2/float32/dot", "body": "{ return 0.0f; }", "class": "pass"},
        {"id": "b", "cell": "avx2/float32/dot", "body": "{ nope", "class": "compile"},
        {"id": "c", "cell": "avx2/float32/l1", "body": "{ _mm256_nope_ps(); }", "class": "invented"},
        {"id": "d", "cell": "avx2/float32/l1", "body": "{ return 1.0f; }", "class": "wrong"},
        {"id": "e", "cell": "avx2/int8/dot", "class": "pass"},
    ]
    kept, skipped = graphgrade.keep(rows)
    assert [row["id"] for row in kept] == ["a", "d"]  # `wrong` compiled, so lane B has an answer for it
    assert [(row["id"], row["reason"].split(":")[0]) for row in skipped] == [
        ("b", "class compile"),
        ("c", "class invented"),
        ("e", "the row carries no body"),
    ]


# MARK: - the waves -


def test_three_entries_on_two_cells_make_two_waves():
    entries = [
        {"id": "1", "cell": "avx2/float32/dot"},
        {"id": "2", "cell": "avx2/float32/l1"},
        {"id": "3", "cell": "avx2/float32/dot"},
    ]
    assert graphgrade.waves(entries) == [[entries[0], entries[1]], [entries[2]]]


def test_no_wave_holds_two_bodies_for_one_cell():
    entries = [{"id": f"{cell}-{n}", "cell": cell} for cell in ("a", "b", "c") for n in range(4)]
    built = graphgrade.waves(entries)
    assert len(built) == 4
    for wave in built:
        cells = [entry["cell"] for entry in wave]
        assert len(cells) == len(set(cells))


def test_waves_are_deterministic_and_pure():
    entries = [{"id": "1", "cell": "x"}, {"id": "2", "cell": "x"}, {"id": "3", "cell": "y"}]
    before = json.dumps(entries, sort_keys=True)
    assert graphgrade.waves(entries) == graphgrade.waves(entries)
    assert json.dumps(entries, sort_keys=True) == before


def test_no_entries_is_no_waves():
    assert graphgrade.waves([]) == []


# MARK: - the callees, and the comparison -


def test_the_gold_callees_are_the_in_repo_ones_at_the_semantic_tier(graph, lattice):
    assert graphgrade.gold_callees(graph, lattice.get("avx2/float32/dot")) == {"MM256_FMA_PS", "hsum256_ps"}
    assert graphgrade.gold_callees(graph, lattice.get("avx2/float32/l2")) == {"float32_distance_l2_impl_avx2"}
    # an intrinsic is not defined in the repo, so the graph draws no edge to it and G-graph never asks
    assert not any(name.startswith("_mm") for name in graphgrade.gold_callees(graph, lattice.get("avx2/bit1/hamming")))


def test_a_syntactic_edge_is_not_a_gold(graph, lattice):
    downgraded = json.loads(json.dumps(graph))
    for edge in downgraded["symbol_edges"]:
        edge["tier"] = "syntactic"
    assert graphgrade.gold_callees(downgraded, lattice.get("avx2/float32/dot")) == set()


def test_a_cell_the_graph_has_no_symbol_for_calls_nothing(graph, lattice):
    without = json.loads(json.dumps(graph))
    without["symbols"] = [s for s in without["symbols"] if s["name"] != "float32_distance_dot_avx2"]
    assert graphgrade.got_callees(without, lattice.get("avx2/float32/dot")) == set()


def test_compare_names_what_is_missing_and_what_is_extra():
    row = graphgrade.compare({"a", "b", "c"}, {"b", "c", "d"})
    assert row["gold"] == ["a", "b", "c"] and row["got"] == ["b", "c", "d"]
    assert row["missing"] == ["a"] and row["extra"] == ["d"]
    assert row["jaccard"] == 0.5


def test_compare_is_one_when_both_sides_agree_and_zero_when_they_share_nothing():
    assert graphgrade.compare({"a"}, {"a"})["jaccard"] == 1.0
    assert graphgrade.compare(set(), set())["jaccard"] == 1.0  # calls nothing, where nothing is called
    assert graphgrade.compare({"a"}, {"b"})["jaccard"] == 0.0


# MARK: - a wave, graded -


@needs_git
def test_the_golds_own_callees_match_exactly(graph, tmp_path):
    """The gold filled back into the hole is the target's own tree, so every set matches."""
    wave = [
        {"id": "dot", "cell": "avx2/float32/dot", "body": "gold"},
        {"id": "l2", "cell": "avx2/float32/l2", "body": "gold"},
        {"id": "ham", "cell": "avx512/bit1/hamming", "body": "gold"},
    ]
    rows = graphgrade.grade_wave(
        FIXTURE, wave, lambda _: graph, gold_graph=graph, workdir=tmp_path / "scratch"
    )
    assert [row["id"] for row in rows] == ["dot", "l2", "ham"]
    for row in rows:
        assert row["reason"] is None
        assert row["missing"] == [] and row["extra"] == []
        assert row["jaccard"] == 1.0
    assert rows[0]["gold"] == ["MM256_FMA_PS", "hsum256_ps"]


@needs_git
def test_the_work_copy_is_a_committed_git_tree_with_the_bodies_in_it(graph, tmp_path):
    seen = {}

    def ingest(workdir):
        seen["text"] = (workdir / "src" / "distance-avx2.c").read_text()
        seen["git"] = (workdir / ".git").is_dir()
        return graph

    wave = [{"id": "x", "cell": "avx2/float32/dot", "body": "{\n    return 42.0f;\n}"}]
    graphgrade.grade_wave(FIXTURE, wave, ingest, gold_graph=graph, workdir=tmp_path / "scratch")
    assert seen["git"] is True
    assert "return 42.0f;" in seen["text"]
    # the dot gold's own line is gone; the sibling kernels around it are still the target's bytes
    assert "MM256_FMA_PS(acc0, _mm256_loadu_ps(a + i     )" not in seen["text"]
    assert "float32_distance_l1_avx2" in seen["text"]


@needs_git
def test_a_body_that_will_not_fill_is_a_reason_and_not_an_exception(graph, tmp_path):
    wave = [
        {"id": "bad", "cell": "avx2/float32/dot", "body": "{ return 0.0f;"},
        {"id": "nope", "cell": "avx2/float32/nope", "body": "gold"},
        {"id": "ok", "cell": "avx2/float32/l1", "body": "gold"},
    ]
    rows = graphgrade.grade_wave(FIXTURE, wave, lambda _: graph, gold_graph=graph, workdir=tmp_path / "s")
    reasons = {row["id"]: row["reason"] for row in rows}
    assert "a body runs from '{' to its matching '}'" == reasons["bad"]
    assert "no cell 'avx2/float32/nope'" in reasons["nope"]
    assert reasons["ok"] is None


@needs_git
def test_the_gold_graph_is_ingested_when_none_is_given(graph, tmp_path):
    asked = []

    def ingest(workdir):
        asked.append(workdir.name)
        return graph

    rows = graphgrade.grade_wave(
        FIXTURE, [{"id": "x", "cell": "avx2/float32/dot", "body": "gold"}], ingest, workdir=tmp_path / "s"
    )
    assert asked == ["gold", "work"]
    assert rows[0]["jaccard"] == 1.0


@needs_git
def test_an_ingest_that_answers_with_nothing_is_the_instruments_failure(tmp_path):
    with pytest.raises(graphgrade.IngestFailed):
        graphgrade.grade_wave(
            FIXTURE,
            [{"id": "x", "cell": "avx2/float32/dot", "body": "gold"}],
            lambda _: {},
            gold_graph={"symbols": [], "symbol_edges": []},
            workdir=tmp_path / "s",
        )


@needs_git
def test_grade_runs_every_wave_and_gives_the_rows_back_in_order(graph, tmp_path):
    runs = []

    def ingest(workdir):
        runs.append(workdir.name)
        return graph

    entries = [
        {"id": "a", "cell": "avx2/float32/dot", "body": "gold"},
        {"id": "b", "cell": "avx2/float32/dot", "body": "gold"},
        {"id": "c", "cell": "avx2/float32/l1", "body": "gold"},
    ]
    rows = graphgrade.grade(FIXTURE, entries, ingest, gold_graph=graph, workdir=tmp_path / "s")
    assert [row["id"] for row in rows] == ["a", "b", "c"]
    assert runs == ["work", "work"]  # two waves, one ingest each, and no second gold ingest
    assert all(row["jaccard"] == 1.0 for row in rows)


# MARK: - the default ingest -


def test_the_default_ingest_names_the_checkouts_own_hobbes(monkeypatch, tmp_path):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        graph = tmp_path / ".hobbes" / "derived" / "graph.json"
        graph.parent.mkdir(parents=True, exist_ok=True)
        graph.write_text('{"symbols": [{"id": "x"}]}')
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(graphgrade.subprocess, "run", fake_run)
    graph = graphgrade.hobbes_ingest("/checkout")(tmp_path)
    assert seen["argv"][:4] == ["uv", "run", "--project", "/checkout/pipeline"]
    assert seen["argv"][4:] == ["hobbes", "ingest"]
    assert seen["cwd"] == str(tmp_path)
    assert graph["symbols"] == [{"id": "x"}]


def test_an_ingest_that_exits_non_zero_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(
        graphgrade.subprocess,
        "run",
        lambda *a, **k: type("Done", (), {"returncode": 1, "stdout": "", "stderr": "boom"})(),
    )
    with pytest.raises(graphgrade.IngestFailed) as refusal:
        graphgrade.hobbes_ingest("/checkout")(tmp_path)
    assert "boom" in str(refusal.value)
