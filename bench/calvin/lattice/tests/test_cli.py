"""The CLI: the map names every ISA, the per-cell verbs answer, and the graders say where they may run."""

import json
import shutil
from pathlib import Path

import pytest
import test_ages
import test_intrinsics

from lattice import cli, run, shadow
from lattice.holes import HOLE

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"


def test_map_exits_zero_and_names_every_isa(capsys):
    assert cli.main(["map", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    for isa in ("cpu", "sse2", "avx2", "avx512", "neon", "rvv"):
        assert isa in out, isa
    assert "unmatched: none" in out


def test_map_as_json_counts_the_grid(capsys):
    assert cli.main(["map", str(FIXTURE), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["isa"] for row in payload["isas"]] == ["cpu", "sse2", "avx2", "avx512", "neon", "rvv"]
    avx2 = next(row for row in payload["isas"] if row["isa"] == "avx2")
    assert (avx2["cells"], avx2["impl"], avx2["wrapper"], avx2["body"], avx2["slots"]) == (13, 2, 4, 7, 11)
    assert avx2["native"] is True
    assert payload["unmatched"] == []


def test_task_prints_the_record(capsys):
    assert cli.main(["task", str(FIXTURE), "avx2/int8/dot"]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["name"] == "int8_distance_dot_avx2"
    assert record["schema"] == "lattice-task/3"
    assert record["prelude_bare"]
    assert record["callees"] is None  # no ledger was given


def test_task_with_the_ledger_carries_the_callees_and_their_source(capsys):
    assert cli.main([
        "task", str(FIXTURE), "avx2/float32/dot",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    record = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in record["callees"]][:2] == ["MM256_FMA_PS", "hsum256_ps"]
    assert record["callees_source"]["graph"]["version"] == "0.2.70-beta"


# MARK: - the facts verb -


def test_facts_prints_the_callees_with_their_provenance(capsys):
    assert cli.main([
        "facts", str(FIXTURE), "avx2/float32/dot",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cell"] == "avx2/float32/dot"
    assert [row["provenance"] for row in payload["callees"]] == [
        "hobbes:semantic", "hobbes:semantic",
        "clang-key:static", "clang-key:static", "clang-key:static", "clang-key:macro",
    ]
    assert payload["source"]["key"]["oracle"].startswith("Ubuntu clang")
    assert payload["missing"] == ["intrinsics"]


def test_facts_prints_the_header_macro_expansions_it_dropped(capsys):
    assert cli.main([
        "facts", str(FIXTURE), "avx2/bit1/hamming",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [(row["name"], row["wrote"]) for row in payload["dropped"]] == [
        ("__builtin_ia32_extract128i256", "_mm256_extracti128_si256"),
        ("__builtin_ia32_vec_ext_v2di", "_mm_extract_epi64"),
    ]
    assert [row["name"] for row in payload["callees"] if row["name"].startswith("__builtin_ia32_")] == []


def test_facts_with_no_ledger_prints_nothing_and_says_what_was_missing(capsys):
    assert cli.main(["facts", str(FIXTURE), "avx2/float32/dot"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["callees"] == []
    assert payload["missing"] == ["graph", "clang-key"]


def test_a_ledger_file_that_is_not_there_is_a_refusal(capsys, tmp_path):
    assert cli.main(["facts", str(FIXTURE), "avx2/float32/dot", "--graph", str(tmp_path / "nope.json")]) == 2
    assert "the ledger could not be read" in capsys.readouterr().err


def test_punch_prints_the_file_with_the_hole(capsys):
    assert cli.main(["punch", str(FIXTURE), "avx2/int8/dot"]) == 0
    out = capsys.readouterr().out
    gold = (FIXTURE / "src" / "distance-avx2.c").read_text()
    assert out.count(HOLE) == 1
    assert "float int8_distance_dot_avx2 (const void *v1, const void *v2, int n)" in out
    assert out.startswith("//\n//  distance-avx2.c")
    assert out.endswith(gold[gold.index("bool init_distance_functions_avx2") :])  # a whole file, not a cell
    assert "int64_t dot = hsum256_epi32_signed(_mm256_add_epi32(acc0, acc1));" in gold
    assert "int64_t dot = hsum256_epi32_signed(_mm256_add_epi32(acc0, acc1));" not in out


def test_an_unknown_cell_is_an_error(capsys):
    assert cli.main(["task", str(FIXTURE), "avx2/float32/nope"]) == 2
    assert "no cell" in capsys.readouterr().err


# MARK: - the prompts verb -


def test_prompts_writes_one_row_per_cell_and_arm(capsys):
    assert cli.main(["prompts", str(FIXTURE), "--cells", "avx2/float32/dot", "--arms", "C-0,C-2,C-4"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["arm"] for row in rows] == ["C-0", "C-2", "C-4"]
    assert {row["cell"] for row in rows} == {"avx2/float32/dot"}
    assert [len(row["messages"]) for row in rows] == [2, 2, 2]
    assert rows[0]["shots"] == [] and rows[0]["control"] == []
    assert [shot["cell"] for shot in rows[1]["shots"]] == [
        "sse2/float32/dot", "avx2/int8/dot", "avx2/float32/cosine",
    ]
    assert [shot["rule"] for shot in rows[1]["shots"]] == ["pairing", "fallback", "pairing"]
    assert rows[2]["shots"] == [] and rows[2]["control"]
    assert rows[0]["chars"] < rows[1]["chars"]  # the shots are what C-2 adds
    assert str(FIXTURE) not in json.dumps(rows)


def test_a_facts_arm_with_no_ledger_is_skipped_and_the_skip_is_named(capsys):
    assert cli.main(["prompts", str(FIXTURE), "--cells", "avx2/float32/dot", "--arms", "C-1"]) == 0
    printed = capsys.readouterr()
    assert printed.out == ""  # never filled empty
    assert "C-1 skipped" in printed.err and "no ledger was given" in printed.err


def test_prompts_with_the_ledger_fills_the_facts_arms(tmp_path):
    out = tmp_path / "prompts.jsonl"
    assert cli.main([
        "prompts", str(FIXTURE), "--cells", "avx2/float32/dot", "--arms", "C-1,C-3",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
        "--out", str(out),
    ]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [row["arm"] for row in rows] == ["C-1", "C-3"]
    assert "hsum256_ps" in rows[0]["messages"][1]["content"]
    assert rows[0]["shots"] == [] and rows[1]["shots"]


def test_prompts_defaults_to_every_native_cell_and_every_arm_it_can_build(capsys):
    assert cli.main(["prompts", str(FIXTURE)]) == 0
    printed = capsys.readouterr()
    rows = [json.loads(line) for line in printed.out.splitlines()]
    assert sorted({row["arm"] for row in rows}) == ["C-0", "C-2", "C-4"]
    assert len(rows) == 39 * 3  # the fixture's three native ISAs, C-1 and C-3 skipped without a ledger
    assert "C-1 skipped" in printed.err and "C-3 skipped" in printed.err


def test_an_unknown_arm_or_cell_is_a_refusal(capsys):
    assert cli.main(["prompts", str(FIXTURE), "--arms", "C-9"]) == 2
    assert "no arm 'C-9'" in capsys.readouterr().err
    assert cli.main(["prompts", str(FIXTURE), "--cells", "avx2/float32/nope"]) == 2
    assert "no cell" in capsys.readouterr().err


# MARK: - the intrinsic index, the ages and the probes -


def test_intrinsics_indexes_a_header_directory_and_writes_it(capsys, tmp_path):
    (tmp_path / "avx2intrin.h").write_text(test_intrinsics.AVX2)
    out = tmp_path / "index.json"
    assert cli.main(["intrinsics", str(tmp_path), "--out", str(out)]) == 0
    assert "intrinsics: 3 names (1 macro, 2 function) over 1 header(s)" in capsys.readouterr().out
    index = json.loads(out.read_text())
    assert index["_mm256_fmadd_ps"]["signature"] == "__m256 _mm256_fmadd_ps(__m256 __A, __m256 __B, __m256 __C)"
    assert str(tmp_path) not in out.read_text()


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_ages_prints_the_table_and_writes_the_rows(capsys, tmp_path):
    repo = test_ages.a_repo(tmp_path / "target")
    out = tmp_path / "ages.json"
    assert cli.main(["ages", str(repo), "HEAD", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "ages of 1 native cell(s)" in printed
    assert "avx2/float32/dot" in printed
    assert "2025-06-30  1 of 1" in printed  # the quarter tally the contamination facts are read from
    assert json.loads(out.read_text())["avx2/float32/dot"]["body_since"] == "2025-06-03"


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_ages_on_a_ref_with_no_kernels_exits_two_with_the_reason(capsys, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "README.md").write_text("no kernels here\n")
    for args in (("init", "-q"), ("config", "user.email", "a@b.invalid"), ("config", "user.name", "t"),
                 ("add", "-A"), ("commit", "-q", "-m", "docs")):
        test_ages._git(empty, *args)
    assert cli.main(["ages", str(empty), "HEAD"]) == 2
    assert "no src/distance-*.c at HEAD" in capsys.readouterr().err


def test_mem_probes_writes_one_probe_per_native_cell_and_calls_nothing(capsys):
    assert cli.main(["mem-probes", str(FIXTURE)]) == 0
    probes = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(probes) == 39  # the fixture's three native ISAs
    assert all(row["cell"].split("/")[0] in ("sse2", "avx2", "avx512") for row in probes)
    dot = next(row for row in probes if row["cell"] == "avx2/float32/dot")
    assert dot["k"] == 6 and dot["expected"] and "score" not in dot


# MARK: - the shadow and G-graph verbs -


def _shadow(tmp_path, style, capsys):
    dest = tmp_path / style
    code = cli.main([
        "shadow", str(FIXTURE), str(dest), "--graph", str(DERIVED / "graph.json"), "--style", style
    ])
    return code, dest, capsys.readouterr()


def test_shadow_writes_the_tree_and_says_what_it_kept_and_what_still_leaks(capsys, tmp_path):
    code, dest, printed = _shadow(tmp_path, "descriptive", capsys)
    out = printed.out
    assert code == 0
    assert "shadow (descriptive): 175 renamed" in out
    assert "kept, external: _mm512_abs_ps" in out
    assert "kept, entry-point: sqlite3_vector_init" in out
    assert "VECTOR_TYPE_F32" in out
    assert "leaks, not renamed: PROVENANCE.md" in out
    payload = json.loads((dest / "shadow-map.json").read_text())
    assert payload["renames"]["float32_distance_dot_avx2"] == "f32_dist_inner_x86v2"
    assert (dest / "src" / "distance-avx2.c").exists() and (dest / "Makefile").exists()


def test_a_shadow_that_would_collide_is_not_written(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(shadow.SYNONYMS, "sse2", "x86")
    monkeypatch.setitem(shadow.SYNONYMS, "avx2", "x86")
    code, dest, printed = _shadow(tmp_path, "descriptive", capsys)
    assert code == 2
    assert "the descriptive shadow was not written" in printed.err
    assert not dest.exists()


def test_the_reading_verbs_take_the_shadows_map(capsys, tmp_path):
    _, dest, _ = _shadow(tmp_path, "opaque", capsys)
    rename = str(dest / "shadow-map.json")

    assert cli.main(["map", str(dest), "--json", "--rename", rename]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert next(row for row in payload["isas"] if row["isa"] == "avx2")["cells"] == 13

    assert cli.main(["task", str(dest), "avx2/float32/dot", "--rename", rename]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["name"].startswith("fn_")
    assert "float32_distance_dot_avx2" not in json.dumps(record)


def test_prompts_reads_a_shadow_through_its_map(capsys, tmp_path):
    _, dest, _ = _shadow(tmp_path, "opaque", capsys)
    assert cli.main([
        "prompts", str(dest), "--cells", "avx2/float32/dot", "--arms", "C-2",
        "--rename", str(dest / "shadow-map.json"),
    ]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(rows) == 1 and rows[0]["cell"] == "avx2/float32/dot"
    assert rows[0]["shots"]
    assert "float32_distance_dot_avx2" not in json.dumps(rows)  # the grid is the target's, the names are not


def test_without_the_map_a_shadows_cells_are_not_there(capsys, tmp_path):
    _, dest, _ = _shadow(tmp_path, "opaque", capsys)
    assert cli.main(["task", str(dest), "avx2/float32/dot"]) == 2
    assert "no cell" in capsys.readouterr().err


def test_a_shadow_map_that_is_not_there_is_a_refusal(capsys, tmp_path):
    assert cli.main(["map", str(FIXTURE), "--rename", str(tmp_path / "nope.json")]) == 2
    assert "the shadow map could not be read" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("git") is None, reason="G-graph's work copy is a git repo")
def test_graph_grade_reads_a_grading_runs_rows_and_says_what_it_left_out(monkeypatch, capsys, tmp_path):
    graph = json.loads((DERIVED / "graph.json").read_text())
    monkeypatch.setattr(cli.graph_of, "hobbes_ingest", lambda checkout, **kw: (lambda workdir: graph))
    results = tmp_path / "results.jsonl"
    results.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"id": "a", "cell": "avx2/float32/dot", "body": "gold", "class": "pass"},
                {"id": "b", "cell": "avx2/float32/l1", "body": "{ nope", "class": "compile"},
            )
        )
        + "\n"
    )
    out = tmp_path / "graph.jsonl"
    assert cli.main([
        "graph-grade", str(FIXTURE), str(results), "--gold-graph", str(DERIVED / "graph.json"), "--out", str(out)
    ]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["id"] == "a" and rows[0]["jaccard"] == 1.0
    assert rows[0]["gold"] == ["MM256_FMA_PS", "hsum256_ps"]
    assert rows[1]["id"] == "b" and "no lane B answer" in rows[1]["reason"]


# MARK: - the grading verbs -


def test_here_outside_a_container_exits_two_with_the_refusal(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run, "in_container", lambda: False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"id": "a", "cell": "avx2/int8/dot", "body": "gold"}]))
    assert cli.main(["grade", str(FIXTURE), str(manifest), "--here"]) == 2
    err = capsys.readouterr().err
    assert "never happens on the host" in err and "ADR-092" in err


def test_selftest_here_outside_a_container_exits_two(monkeypatch, capsys):
    monkeypatch.setattr(run, "in_container", lambda: False)
    assert cli.main(["selftest", str(FIXTURE), "--here", "--cells", "avx2/int8/dot"]) == 2
    assert "ADR-092" in capsys.readouterr().err


def test_without_here_the_cli_runs_itself_in_the_image(monkeypatch, tmp_path):
    seen = {}

    def plan_only(plan, **kwargs):
        seen["plan"] = plan
        (tmp_path / "work" / "results.jsonl").write_text('{"id": "a", "class": "pass"}\n')
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(run, "run_plan", plan_only)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"id": "a", "cell": "avx2/int8/dot", "body": "gold"}]))
    out = tmp_path / "results.jsonl"
    assert cli.main(["grade", str(FIXTURE), str(manifest), "--work", str(tmp_path / "work"), "--out", str(out)]) == 0
    assert seen["plan"][0] == "podman"
    assert seen["plan"][-1] == "--here"
    assert "hobbes-session:local" in seen["plan"]
    assert json.loads(out.read_text()) == {"id": "a", "class": "pass"}


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_grade_here_writes_one_json_line_per_entry(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run, "in_container", lambda: True)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"entries": [
        {"id": "a", "cell": "avx2/int8/dot", "body": "gold"},
        {"id": "b", "cell": "avx2/int8/dot", "body": "{ return 0.0f; }"},
    ]}))
    assert cli.main(["grade", str(FIXTURE), str(manifest), "--here"]) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["id"] for r in results] == ["a", "b"]
    assert results[0]["class"] == "pass"
    assert results[1]["class"] == "wrong"


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_selftest_here_prints_the_table_and_exits_zero_when_it_holds(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run, "in_container", lambda: True)
    report = tmp_path / "report.json"
    assert cli.main(["selftest", str(FIXTURE), "--here", "--cells", "sse2/int8/dot", "--out", str(report)]) == 0
    out = capsys.readouterr().out
    assert "self-test over 1 cell(s) — ok" in out
    assert json.loads(report.read_text())["ok"] is True
