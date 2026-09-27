"""The CLI: the map names every ISA, the per-cell verbs answer, and the graders say where they may run."""

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
import test_ages
import test_compare
import test_corpus
import test_e1
import test_e3
import test_intrinsics

from lattice import available, cli, corpus, e1, e4, prompts, report, run, shadow
from lattice.cells import build as build_lattice
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


def test_available_without_here_runs_itself_in_the_image(monkeypatch, tmp_path):
    """The plan is pure data: the mounts, the inner verb writing through the work dir, and `--here` last."""
    seen = {}

    def plan_only(plan, **kwargs):
        seen["plan"] = plan
        (tmp_path / "work" / "available.json").write_text('{"avx2": {"names": {}}}')
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(run, "run_plan", plan_only)
    out = tmp_path / "available.json"
    assert cli.main([
        "available", str(FIXTURE), "--out", str(out), "--isa", "avx2",
        "--work", str(tmp_path / "work"),
    ]) == 0
    plan = seen["plan"]
    assert plan[0] == "podman" and plan[-1] == "--here"
    assert "hobbes-session:local" in plan
    assert f"{FIXTURE.resolve()}:/target:ro" in plan and f"{(tmp_path / 'work').resolve()}:/work:rw" in plan
    # the record is written through the work mount, since the target rides read-only
    assert plan[plan.index("--out") + 1] == "/work/available.json"
    assert plan[plan.index("--isa") + 1] == "avx2"
    assert json.loads(out.read_text()) == {"avx2": {"names": {}}}


def test_available_here_outside_a_container_exits_two_with_the_refusal(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run, "in_container", lambda: False)
    assert cli.main(["available", str(FIXTURE), "--out", str(tmp_path / "a.json"), "--here"]) == 2
    err = capsys.readouterr().err
    assert "never happens on the host" in err and "ADR-092" in err
    assert not (tmp_path / "a.json").exists()


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


# MARK: - E1's runner -


def plan_a_run(tmp_path, capsys, *, cells="avx2/int8/dot", arms="C-2", k=1, ledger=False):
    """`lattice e1 plan` over one cell, and the run directory it wrote."""
    run_dir = tmp_path / "run"
    argv = ["e1", "plan", str(FIXTURE), str(run_dir), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
            "--cells", cells, "--arms", arms, "--k", str(k)]
    if ledger:
        argv += ["--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json")]
    assert cli.main(argv) == 0
    capsys.readouterr()
    return run_dir


def completions_for(run_dir, text):
    """A replay file answering every request of a run with the same text."""
    rows = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines() if line.strip()]
    recorded = run_dir.parent / "completions.jsonl"
    recorded.write_text("".join(json.dumps({"id": row["id"], "text": text}) + "\n" for row in rows))
    return recorded


def test_e1_plan_writes_the_meta_and_the_requests(tmp_path, capsys):
    run_dir = tmp_path / "run"
    assert cli.main([
        "e1", "plan", str(FIXTURE), str(run_dir), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
        "--cells", "avx2/int8/dot,avx2/float32/dot", "--arms", "C-0,C-2", "--k", "3",
    ]) == 0
    assert "e1 plan: 18 request(s) — 16 chat over 2 cell(s) × 2 arm(s) × 4 sample(s), 2 G-mem" in capsys.readouterr().out

    record = json.loads((run_dir / e1.META).read_text())
    assert record["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert record["arms"] == ["C-0", "C-2"] and record["k"] == 3
    assert record["p12"] == "arm=model+prompt"
    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    assert sum(1 for request in requests if request["mode"] == "chat") == 2 * 2 * 4
    assert sum(1 for request in requests if request["mode"] == "complete") == 2


def test_e1_plan_skips_a_facts_arm_with_no_ledger_and_names_it(tmp_path, capsys):
    run_dir = tmp_path / "run"
    assert cli.main([
        "e1", "plan", str(FIXTURE), str(run_dir), "--model", "M",
        "--cells", "avx2/int8/dot", "--arms", "C-1,C-2",
    ]) == 0
    assert "C-1 skipped" in capsys.readouterr().err
    assert json.loads((run_dir / e1.META).read_text())["arms"] == ["C-2"]


def test_e1_plan_with_the_ledger_carries_the_facts_arms(tmp_path, capsys):
    run_dir = plan_a_run(tmp_path, capsys, arms="C-1", ledger=True)
    record = json.loads((run_dir / e1.META).read_text())
    assert record["arms"] == ["C-1"]
    assert record["ledger"]["graph"]["version"] == "0.2.70-beta"


def test_e1_run_replays_a_file_and_grades_what_it_extracted(tmp_path, capsys, monkeypatch):
    lattice = build_lattice(FIXTURE)
    cell = lattice.get("avx2/int8/dot")
    run_dir = plan_a_run(tmp_path, capsys)
    recorded = completions_for(run_dir, f"```c\n{prompts.definition(lattice, cell)}\n```")

    graded = []
    renames = []

    def fake_default_grade(target, image=run.IMAGE, rename_in_target=None):
        renames.append(rename_in_target)

        def grade(entries):
            graded.extend(entry["id"] for entry in entries)
            return [{"id": entry["id"], "cell": entry["cell"], "class": "pass", "reg": True} for entry in entries]

        return grade

    monkeypatch.setattr(e1, "default_grade", fake_default_grade)
    assert cli.main([
        "e1", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
    ]) == 0
    assert json.loads(capsys.readouterr().out) == {"rows": 2, "gmem": 1, "calls": 1, "spent_usd": 0.0}
    assert len(graded) == 2
    assert renames == [None]  # not a shadow run, so the graders read the target's own names
    rows = [json.loads(line) for line in (run_dir / e1.ROWS).read_text().splitlines()]
    assert [row["class"] for row in rows] == ["pass", "pass"]


def test_e1_run_without_a_ceiling_exits_two(tmp_path, capsys):
    run_dir = plan_a_run(tmp_path, capsys)
    with pytest.raises(SystemExit) as refused:
        cli.main(["e1", "run", str(run_dir), str(FIXTURE), "--generator", "replay:nowhere.jsonl"])
    assert refused.value.code == 2
    assert "--ceiling-usd" in capsys.readouterr().err


def test_e1_run_refuses_a_generator_it_does_not_know(tmp_path, capsys):
    run_dir = plan_a_run(tmp_path, capsys)
    assert cli.main(["e1", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "1", "--generator", "openai"]) == 2
    assert "modal or replay:" in capsys.readouterr().err


def test_e1_run_prints_the_ceiling_refusal_and_exits_two(tmp_path, capsys):
    run_dir = plan_a_run(tmp_path, capsys)
    recorded = completions_for(run_dir, "```c\nnothing\n```")
    assert cli.main([
        "e1", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "0", "--generator", f"replay:{recorded}",
    ]) == 2
    assert "nothing was sent" in capsys.readouterr().err
    assert not (run_dir / e1.ROWS).exists()


# MARK: - E2: a run planned over a rename shadow -


@pytest.fixture(scope="module")
def graph():
    return json.loads((DERIVED / "graph.json").read_text())


@pytest.fixture(scope="module")
def plans(graph):
    return {style: shadow.plan(FIXTURE, graph, style) for style in shadow.STYLES}


@pytest.fixture(scope="module")
def shadows(plans, tmp_path_factory):
    """Both shadows of the fixture, written once: E2 plans over these, never over the target."""
    root = tmp_path_factory.mktemp("e2-shadows")
    return {style: shadow.write(plan, root / style) for style, plan in plans.items()}


def plan_over(run_dir, root, *, rename=None, original=None, cells="avx2/float32/dot", arms="C-2,C-3", k=1):
    """`lattice e1 plan` over a target or a shadow, with the fixture's own ledger."""
    argv = [
        "e1", "plan", str(root), str(run_dir), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
        "--cells", cells, "--arms", arms, "--k", str(k),
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]
    if rename is not None:
        argv += ["--rename", str(rename)]
    if original is not None:
        argv += ["--original", str(original)]
    return cli.main(argv)


def requests_in(run_dir):
    return [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines() if line.strip()]


def user_turn(requests, cell, arm):
    """The one user turn of a (cell, arm) request's greedy sample."""
    request = next(r for r in requests if r["id"] == e1.request_id(cell, arm, 0, 0))
    return request["messages"][1]["content"]


def test_a_plan_over_a_shadow_writes_no_renamed_original_anywhere(tmp_path, capsys, plans, shadows):
    run_dir = tmp_path / "descriptive-run"
    assert plan_over(run_dir, shadows["descriptive"], rename=shadows["descriptive"] / "shadow-map.json",
                     original=FIXTURE) == 0
    capsys.readouterr()

    originals = set(plans["descriptive"].renames)
    for request in requests_in(run_dir):
        for text in ([turn["content"] for turn in request.get("messages") or ()] + [request.get("prompt") or ""]):
            written = set(re.findall(r"[A-Za-z_]\w*", text)) & originals
            assert written == set(), (request["id"], sorted(written)[:5])


def test_a_shadow_asks_with_e1s_own_ids_and_e1s_own_seeds(tmp_path, capsys, shadows):
    """A cell id is its grid position, so only the bytes differ: the samples are the original's."""
    here, there = tmp_path / "target-run", tmp_path / "shadow-run"
    assert plan_over(here, FIXTURE) == 0
    assert plan_over(there, shadows["descriptive"], rename=shadows["descriptive"] / "shadow-map.json",
                     original=FIXTURE) == 0
    capsys.readouterr()

    target, shadowed = requests_in(here), requests_in(there)
    assert [r["id"] for r in shadowed] == [r["id"] for r in target]
    assert [r["params"]["seed"] for r in shadowed] == [r["params"]["seed"] for r in target]
    assert [r["messages"][1]["content"] for r in shadowed if r["mode"] == "chat"] != [
        r["messages"][1]["content"] for r in target if r["mode"] == "chat"
    ]


def test_a_shadows_facts_arm_names_the_shadows_callees_and_leaves_an_intrinsic_alone(tmp_path, capsys, shadows):
    here, there = tmp_path / "target-run", tmp_path / "shadow-run"
    assert plan_over(here, FIXTURE) == 0
    assert plan_over(there, shadows["descriptive"], rename=shadows["descriptive"] / "shadow-map.json",
                     original=FIXTURE) == 0
    capsys.readouterr()

    target = user_turn(requests_in(here), "avx2/float32/dot", "C-3")
    shadowed = user_turn(requests_in(there), "avx2/float32/dot", "C-3")
    # the two in-repo callees the target's own C-3 prompt names, under the shadow's names
    assert "- MM256_FMA_PS:" in target and "- hsum256_ps:" in target
    assert "- VECOP256_FUSEDMUL_F32LANE:" in shadowed and "- hadd256_f32lane:" in shadowed
    # the signature on the row is the defining line, and it names things too
    assert "#define MM256_FMA_PS(_acc, _x, _y)" in target
    assert "#define VECOP256_FUSEDMUL_F32LANE(_acc, _x, _y)" in shadowed
    assert "static inline float hadd256_f32lane (__m256 v)" in shadowed
    # an intrinsic is the language and not the repo: it is renamed in neither
    assert "- _mm256_fmadd_ps:" in target and "- _mm256_fmadd_ps:" in shadowed
    assert "hobbes:semantic" in shadowed and "clang-key:static" in shadowed


def test_the_meta_of_a_shadow_run_records_the_shadow_and_the_translation(tmp_path, capsys, plans, shadows):
    run_dir = tmp_path / "run"
    map_file = shadows["descriptive"] / "shadow-map.json"
    assert plan_over(run_dir, shadows["descriptive"], rename=map_file, original=FIXTURE) == 0
    printed = capsys.readouterr().out
    assert "over the descriptive shadow" in printed

    record = json.loads((run_dir / e1.META).read_text())
    assert record["shadow"]["style"] == "descriptive"
    assert record["shadow"]["map_sha256"] == shadow.map_digest(map_file)
    assert record["shadow"]["tree_sha256"] == shadow.tree_digest(shadows["descriptive"])
    assert record["shadow"]["from_sha"] == e1.head(FIXTURE)  # the fixture rides in a checkout
    # the names the shadow kept leak by design, so the run says which they are
    assert {"name": "sqlite3_vector_init", "reason": "entry-point"} in record["shadow"]["kept"]
    assert record["shadow"]["kept"] == [dict(row) for row in plans["descriptive"].kept]
    assert record["ledger"]["translated_through"] == shadow.map_digest(map_file)
    assert record["ledger"]["graph"]["version"] == "0.2.70-beta"  # the target's own ledger, unchanged


def test_the_opaque_shadow_plans_the_same_way(tmp_path, capsys, plans, shadows):
    run_dir = tmp_path / "run"
    assert plan_over(run_dir, shadows["opaque"], rename=shadows["opaque"] / "shadow-map.json",
                     original=FIXTURE) == 0
    capsys.readouterr()

    renames = plans["opaque"].renames
    prompt = user_turn(requests_in(run_dir), "avx2/float32/dot", "C-3")
    assert f"- {renames['MM256_FMA_PS']}:" in prompt and f"- {renames['hsum256_ps']}:" in prompt
    assert "- _mm256_fmadd_ps:" in prompt
    assert "float32_distance_dot_avx2" not in prompt and "hsum256_ps" not in prompt
    assert json.loads((run_dir / e1.META).read_text())["shadow"]["style"] == "opaque"


def one_shadow(tmp_path, graph, style="descriptive"):
    """A shadow of the fixture written where a test may edit it."""
    return shadow.write(shadow.plan(FIXTURE, graph, style), tmp_path / "shadow")


def test_a_planted_original_name_refuses_the_plan_and_writes_nothing(tmp_path, capsys, graph):
    root = one_shadow(tmp_path, graph)
    file = root / "src" / "distance-avx2.c"
    file.write_text("/* this was float32_distance_dot_avx2 */\n" + file.read_text())
    run_dir = tmp_path / "run"

    assert plan_over(run_dir, root, rename=root / "shadow-map.json", original=FIXTURE, arms="C-2") == 2
    err = capsys.readouterr().err
    assert "float32_distance_dot_avx2" in err and "renamed away" in err
    assert not run_dir.exists()


def test_a_name_the_shadow_kept_is_not_a_leak(tmp_path, capsys, graph):
    root = one_shadow(tmp_path, graph)
    file = root / "src" / "distance-avx2.c"
    file.write_text("/* sqlite3_vector_init installs VECTOR_TYPE_F32 */\n" + file.read_text())
    run_dir = tmp_path / "run"

    assert plan_over(run_dir, root, rename=root / "shadow-map.json", original=FIXTURE, arms="C-2") == 0
    capsys.readouterr()
    assert "sqlite3_vector_init" in user_turn(requests_in(run_dir), "avx2/float32/dot", "C-2")


def test_a_facts_arm_over_a_shadow_without_the_original_is_refused(tmp_path, capsys, shadows):
    run_dir = tmp_path / "run"
    assert plan_over(run_dir, shadows["descriptive"], rename=shadows["descriptive"] / "shadow-map.json",
                     arms="C-1") == 2
    assert "--original" in capsys.readouterr().err
    assert not run_dir.exists()


def test_a_shadow_plan_with_no_facts_arm_needs_no_original(tmp_path, capsys, shadows):
    run_dir = tmp_path / "run"
    assert plan_over(run_dir, shadows["descriptive"], rename=shadows["descriptive"] / "shadow-map.json",
                     arms="C-2") == 0
    capsys.readouterr()
    record = json.loads((run_dir / e1.META).read_text())
    assert record["shadow"]["from_sha"] is None  # nothing said which tree it came from, so it says nothing


def test_e1_run_over_a_shadow_grades_through_the_map(tmp_path, capsys, monkeypatch, shadows):
    root = shadows["descriptive"]
    run_dir = tmp_path / "run"
    assert plan_over(run_dir, root, rename=root / "shadow-map.json", original=FIXTURE, arms="C-2") == 0
    capsys.readouterr()
    recorded = completions_for(run_dir, "```c\nnot a body\n```")

    renames = []
    monkeypatch.setattr(
        e1,
        "default_grade",
        lambda target, image=run.IMAGE, rename_in_target=None: renames.append(rename_in_target)
        or (lambda entries: [{"id": e["id"], "cell": e["cell"], "class": "wrong", "reg": False} for e in entries]),
    )
    assert cli.main([
        "e1", "run", str(run_dir), str(root), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
        "--rounds", "0",
    ]) == 0
    assert renames == ["/target/shadow-map.json"]


def test_e2_compare_prints_the_deltas_and_refuses_two_runs_that_differ_in_more(tmp_path, capsys):
    cells = test_compare.CELLS
    original = test_compare.write_run(tmp_path / "target-run", {("C-2", cells[0]): True, ("C-2", cells[1]): True})
    shadowed = test_compare.write_run(tmp_path / "shadow-run", {("C-2", cells[0]): True}, style="descriptive")

    assert cli.main(["e2", "compare", str(original), str(shadowed)]) == 0
    table = capsys.readouterr().out
    assert "descriptive (shadow-run)" in table and "-0.50" in table

    assert cli.main(["e2", "compare", str(original), str(shadowed), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["shadows"][0]["sections"]["bodies"]["C-2"]["delta"]["pass_at_1"] == -0.5

    other = test_compare.write_run(tmp_path / "k5-run", {}, k=5, style="opaque")
    assert cli.main(["e2", "compare", str(original), str(other)]) == 2
    assert "one variable" in capsys.readouterr().err


# MARK: - E3: an adapter through the plan, the stated-task sentence, and the reading -


MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


def plan_with(tmp_path, root, *args, cells="avx2/int8/dot", arms="C-2", model=MODEL):
    """`lattice e1 plan` over *root* with whatever flags a test is about, and the run directory."""
    run_dir = tmp_path / "run"
    argv = ["e1", "plan", str(root), str(run_dir), "--model", model,
            "--cells", cells, "--arms", arms, "--k", "1", *args]
    return cli.main(argv), run_dir


def test_e1_plan_records_the_adapter_the_manifest_describes(tmp_path, capsys):
    path, manifest = test_e1.adapter_manifest(tmp_path)
    code, run_dir = plan_with(tmp_path, FIXTURE, "--adapter", path, "--adapter-manifest", str(manifest))
    assert code == 0
    printed = capsys.readouterr().out
    assert f"served through {path}" in printed
    assert "repo e3-c-lattice, 300 step(s), recipe fedcba987654" in printed

    record = json.loads((run_dir / e1.META).read_text())
    assert record["adapter"] == {
        "path": path,
        "model": MODEL,
        "repo": "e3-c-lattice",
        "corpus_hash": "c" * 64,
        "recipe_hash": "fedcba987654",
        "steps": 300,
    }


def test_e1_plan_refuses_an_adapter_whose_manifest_describes_another_model_or_path(tmp_path, capsys):
    path, manifest = test_e1.adapter_manifest(tmp_path)
    code, run_dir = plan_with(
        tmp_path, FIXTURE, "--adapter", path, "--adapter-manifest", str(manifest),
        model="allenai/Olmo-3-7B-Instruct",
    )
    assert code == 2
    assert "one model's weights" in capsys.readouterr().err
    assert not run_dir.exists()

    _, elsewhere = test_e1.adapter_manifest(tmp_path, path="adapters/somewhere/else")
    code, run_dir = plan_with(tmp_path, FIXTURE, "--adapter", path, "--adapter-manifest", str(elsewhere))
    assert code == 2
    assert "adapters/somewhere/else" in capsys.readouterr().err
    assert not run_dir.exists()


def test_e1_plan_refuses_one_adapter_flag_without_the_other(tmp_path, capsys):
    path, manifest = test_e1.adapter_manifest(tmp_path)
    code, run_dir = plan_with(tmp_path, FIXTURE, "--adapter", path)
    assert code == 2
    assert "come as a pair" in capsys.readouterr().err

    code, run_dir = plan_with(tmp_path, FIXTURE, "--adapter-manifest", str(manifest))
    assert code == 2
    assert "come as a pair" in capsys.readouterr().err
    assert not run_dir.exists()

    missing = tmp_path / "nowhere.json"
    code, _ = plan_with(tmp_path, FIXTURE, "--adapter", path, "--adapter-manifest", str(missing))
    assert code == 2
    assert "manifest could not be read" in capsys.readouterr().err


def test_e1_run_serves_the_plans_own_adapter_and_not_one_from_the_command_line(tmp_path, capsys, monkeypatch):
    path, manifest = test_e1.adapter_manifest(tmp_path)
    code, run_dir = plan_with(tmp_path, FIXTURE, "--adapter", path, "--adapter-manifest", str(manifest))
    assert code == 0
    capsys.readouterr()

    seen = {}

    def fake_modal(model, script, keep=None, *, run_dir=None, ceiling_usd=None, adapter=None):
        seen.update(model=model, adapter=adapter)
        return lambda requests: {
            "completions": [{"id": request["id"], "text": "no block here"} for request in requests],
            "cost": 0.0,
        }

    monkeypatch.setattr(e1, "modal_generator", fake_modal)
    assert cli.main([
        "e1", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "1", "--generator", "modal", "--rounds", "0",
    ]) == 0
    assert (seen["model"], seen["adapter"]) == (MODEL, path)

    # a plan with no adapter serves the base model, and says nothing about one
    code, base_dir = plan_with(tmp_path / "base", FIXTURE)
    assert code == 0
    capsys.readouterr()
    assert cli.main([
        "e1", "run", str(base_dir), str(FIXTURE), "--ceiling-usd", "1", "--generator", "modal", "--rounds", "0",
    ]) == 0
    assert seen["adapter"] is None


def test_the_stated_task_sentence_rides_on_every_user_turn_of_an_opaque_shadow(tmp_path, capsys, plans, shadows):
    root = shadows["opaque"]
    code, run_dir = plan_with(
        tmp_path, root, "--rename", str(root / "shadow-map.json"), "--stated-task",
        cells="avx2/int8/dot,avx2/float32/l2_squared,avx2/float32/l2_impl",
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "the stated-task sentence on every user turn, before the instruction" in printed

    lattice = build_lattice(root, rename=plans["opaque"].reverse())
    requests = requests_in(run_dir)
    for request in requests:
        if request["mode"] != "chat":
            continue
        sentence = prompts.stated_task(lattice.get(request["cell"]))
        assert request["messages"][1]["content"].endswith(f"{sentence}\n\n{prompts.INSTRUCTION}")

    # the plan was written, so the gate passed on it; and it still passes when asked again by hand
    e1.check_leaks(requests, set(plans["opaque"].renames))
    # the hole is still `fn_NNNN`: the sentence states the task and hands back no name
    assert re.search(r"\bfn_\d{4}\b", user_turn(requests, "avx2/int8/dot", "C-2"))

    record = json.loads((run_dir / e1.META).read_text())
    assert record["stated_task"] is True
    assert record["stated_task_sha256"] == prompts.stated_task_digest()


def test_the_stated_task_flag_is_refused_off_an_opaque_shadow(tmp_path, capsys, shadows):
    code, run_dir = plan_with(tmp_path, FIXTURE, "--stated-task")
    assert code == 2
    err = capsys.readouterr().err
    assert "only with --rename" in err and "no shadow" in err
    assert not run_dir.exists()

    root = shadows["descriptive"]
    code, run_dir = plan_with(tmp_path, root, "--rename", str(root / "shadow-map.json"), "--stated-task")
    assert code == 2
    assert "this plan is over descriptive" in capsys.readouterr().err
    assert not run_dir.exists()

    # without the flag the same plan over the opaque shadow says nothing about the task
    opaque = shadows["opaque"]
    code, run_dir = plan_with(tmp_path, opaque, "--rename", str(opaque / "shadow-map.json"))
    assert code == 0
    capsys.readouterr()
    record = json.loads((run_dir / e1.META).read_text())
    assert (record["stated_task"], record["stated_task_sha256"]) == (False, None)
    assert "It computes" not in user_turn(requests_in(run_dir), "avx2/int8/dot", "C-2")


def test_e3_compare_prints_the_paired_reading_and_refuses_a_pair_of_two_plans(tmp_path, capsys):
    cells = test_e3.CELLS
    shuffled = test_e3.write_run(tmp_path / "shuffled-run", {("C-2", cells[0]): True}, adapter=test_e3.SHUFFLED)
    trained = test_e3.write_run(
        tmp_path / "adapter-run", {("C-2", cells[0]): True, ("C-2", cells[1]): True}, adapter=test_e3.ADAPTER
    )

    assert cli.main(["e3", "compare", str(shuffled), str(trained)]) == 0
    table = capsys.readouterr().out
    assert "E3 shuffled-run → adapter-run" in table
    assert "C-2  E3-use (registered; primary pass_at_1_sampled)" in table
    assert "repo e3-c-lattice-shuffled" in table

    assert cli.main(["e3", "compare", str(shuffled), str(trained), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["paired"]["bodies"]["C-2"]["pass_at_1"]["gained"] == 1
    assert found["b"]["adapter"]["repo"] == "e3-c-lattice"

    other = test_e3.write_run(tmp_path / "k5-run", {}, k=5, adapter=test_e3.ADAPTER)
    assert cli.main(["e3", "compare", str(shuffled), str(other)]) == 2
    assert "one difference" in capsys.readouterr().err


# MARK: - E3's corpus -


def repos_list(tmp_path, repos):
    """The `--repos` file: one `<name>=<root>` a line, in the taken order."""
    listed = tmp_path / "repos.txt"
    listed.write_text("".join(f"{name}={root}\n" for name, root in repos), encoding="utf-8")
    return listed


def test_e3_corpus_writes_both_corpora_the_report_and_says_what_it_dropped(tmp_path, capsys):
    repos = [("alpha", test_corpus.alpha(tmp_path / "alpha")), ("beta", test_corpus.beta(tmp_path / "beta")),
             ("delta", test_corpus.delta(tmp_path / "delta"))]
    out = tmp_path / "out"
    assert cli.main([
        "e3", "corpus", "--repos", str(repos_list(tmp_path, repos)), "--target", str(FIXTURE), "--out", str(out),
    ]) == 0
    printed = capsys.readouterr().out
    assert "e3 corpus: 6 example(s) from 3 repo(s) — 10 union, 8 unique, 2 duplicate" in printed
    assert "near-target 1" in printed and "alone 1" in printed and "nothing cut" in printed
    assert "e3-c-lattice:" in printed and "e3-c-lattice-shuffled:" in printed

    for where in ("e3-pattern", "e3-shuffled"):
        manifest = json.loads((out / where / "manifest.json").read_text(encoding="utf-8"))
        payload = (out / where / "train.jsonl").read_bytes()
        assert manifest["records"] == len(payload.decode().splitlines()) == 6
        assert manifest["seed"] == corpus.SEED
    report = json.loads((out / "corpus-report.json").read_text(encoding="utf-8"))
    assert [row["repo"] for row in report["repos"]] == ["alpha", "beta", "delta"]
    assert [entry["repo"] for entry in report["corpora"]] == ["e3-c-lattice", "e3-c-lattice-shuffled"]


def test_e3_corpus_run_twice_writes_the_same_bytes(tmp_path, capsys):
    repos = [("alpha", test_corpus.alpha(tmp_path / "alpha")), ("beta", test_corpus.beta(tmp_path / "beta"))]
    listed = repos_list(tmp_path, repos)
    for where in ("first", "second"):
        assert cli.main(["e3", "corpus", "--repos", str(listed), "--target", str(FIXTURE),
                         "--out", str(tmp_path / where), "--seed", "7"]) == 0
    capsys.readouterr()
    for name in ("e3-pattern/train.jsonl", "e3-shuffled/train.jsonl", "e3-shuffled/manifest.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes(), name


def test_e3_corpus_refuses_hobbes_itself_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    listed = repos_list(tmp_path, [("hobbes", test_corpus.HOBBES)])
    assert cli.main(["e3", "corpus", "--repos", str(listed), "--target", str(FIXTURE), "--out", str(out)]) == 2
    assert "ADR-107" in capsys.readouterr().err
    assert not out.exists()


def test_e3_corpus_refuses_a_list_it_cannot_read_and_a_corpus_with_no_control(tmp_path, capsys):
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing but a comment\n", encoding="utf-8")
    assert cli.main(["e3", "corpus", "--repos", str(empty), "--target", str(FIXTURE),
                     "--out", str(tmp_path / "out")]) == 2
    assert "names no repo" in capsys.readouterr().err

    assert cli.main(["e3", "corpus", "--repos", str(tmp_path / "gone.txt"), "--target", str(FIXTURE),
                     "--out", str(tmp_path / "out")]) == 2
    assert "the repos list could not be read" in capsys.readouterr().err

    one = repos_list(tmp_path, [("one", test_corpus.only_hash(tmp_path / "one"))])
    assert cli.main(["e3", "corpus", "--repos", str(one), "--target", str(FIXTURE),
                     "--out", str(tmp_path / "out")]) == 2
    assert "no shuffled control" in capsys.readouterr().err


def test_e1_report_prints_the_table_and_the_json(tmp_path, capsys, monkeypatch):
    lattice = build_lattice(FIXTURE)
    cell = lattice.get("avx2/int8/dot")
    run_dir = plan_a_run(tmp_path, capsys)
    recorded = completions_for(run_dir, f"```c\n{prompts.definition(lattice, cell)}\n```")
    monkeypatch.setattr(
        e1,
        "default_grade",
        lambda target, image=run.IMAGE, rename_in_target=None: (
            lambda entries: [{"id": e["id"], "cell": e["cell"], "class": "pass", "reg": True} for e in entries]
        ),
    )
    assert cli.main([
        "e1", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
    ]) == 0
    capsys.readouterr()

    assert cli.main(["e1", "report", str(run_dir)]) == 0
    table = capsys.readouterr().out
    assert "bodies:" in table and "pass@1" in table

    assert cli.main(["e1", "report", str(run_dir), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["sections"]["bodies"]["arms"]["C-2"]["overall"]["pass_at_1"] == 1.0
    assert found["missing"] == []


# MARK: - E4's runner: one held-out file's units -


def plan_an_e4_run(tmp_path, capsys, *, arms="S-0", k=0, ledger=False, isa="avx2"):
    """`lattice e4 plan` over one file, and the run directory it wrote."""
    run_dir = tmp_path / "e4"
    argv = [
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
        "--isa", isa, "--arms", arms, "--k", str(k),
    ]
    if ledger:
        argv += ["--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json")]
    assert cli.main(argv) == 0
    capsys.readouterr()
    return run_dir


def e4_completions_for(run_dir, isa="avx2", arms=None, k=0):
    """A replay file answering every request with that unit's own gold definition.

    With *arms* the ids are generated rather than read from `requests.jsonl`: S-2o's later waves are
    requests `e4 run` builds as the rows come in, so they are not in the plan for a replay to read.
    """
    lattice = build_lattice(FIXTURE)
    source = lattice.sources[isa]
    units = {unit.name: unit for unit in e4.units(lattice, isa)}
    if arms is None:
        wanted = [
            (json.loads(line)["id"], json.loads(line)["unit"])
            for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        wanted = [
            (e1.request_id(name, arm, sample, 0), name)
            for name in units
            for arm in arms
            for sample in range(0, k + 1)
        ]
    rows = []
    for request_id, name in wanted:
        unit = units[name]
        written = source.text[unit.signature_span.start : unit.body_span.end]
        rows.append({"id": request_id, "text": f"```c\n{written}\n```"})
    recorded = run_dir.parent / "e4-completions.jsonl"
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return recorded


def fake_e4_grade(monkeypatch):
    """`e1.default_grade`, replaced by one that passes every entry of either E4 form."""
    monkeypatch.setattr(
        e1,
        "default_grade",
        lambda target, image=run.IMAGE, rename_in_target=None: (
            lambda entries: [{"id": e["id"], "class": "pass", "reg": True} for e in entries]
        ),
    )


def test_e4_plan_writes_the_units_the_order_and_the_window(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--isa", "avx2", "--arms", "S-0,S-2", "--k", "1",
    ]) == 0
    printed = capsys.readouterr().out
    assert "e4 plan: 108 request(s) — 27 unit(s) × 2 arm(s) × 2 sample(s) over src/distance-avx2.c at L1" in printed
    assert "P12 decomposed: largest prompt" in printed and "every window smaller" in printed

    record = json.loads((run_dir / e1.META).read_text())
    assert record["rung"] == "L1" and record["p12"] == "decomposed" and record["arms"] == ["S-0", "S-2"]
    assert [row["name"] for row in record["units"]] == [u.name for u in e4.units(build_lattice(FIXTURE), "avx2")]
    assert record["decomposition"]["every_window_smaller"] is True
    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    assert len(requests) == 27 * 2 * 2 and all(r["mode"] == "chat" for r in requests)


def parse_an_e4_run(tmp_path, capsys, run_dir, *, answers=None, isa="avx2"):
    """`lattice e4 parse` over a replay of the parser's answers, and the completions file it read."""
    lattice = build_lattice(FIXTURE)
    answers = dict(answers or {})
    rows = []
    for request in e4.parse_requests(lattice, isa, "Qwen/Qwen2.5-7B-Instruct"):
        unit = request["unit"]
        text = answers.get(
            unit, json.dumps({"contract": f"{unit} answers its own question.", "edge_cases": ["n is 0."]})
        )
        rows.append({"id": request["id"], "text": text})
    recorded = tmp_path / "parse-completions.jsonl"
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert cli.main([
        "e4", "parse", str(run_dir), str(FIXTURE), "--parser-model", "Qwen/Qwen2.5-7B-Instruct",
        "--isa", isa, "--ceiling-usd", "1", "--generator", f"replay:{recorded}",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    return recorded


def test_e4_plan_refuses_an_arm_that_is_not_e4s_and_writes_nothing(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    assert cli.main(["e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--arms", "C-2"]) == 2
    assert "no arm 'C-2'" in capsys.readouterr().err
    assert not run_dir.exists()


def test_e4_parse_writes_the_fields_and_names_what_it_kept_raw(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    parse_an_e4_run(tmp_path, capsys, run_dir, answers={"hsum256_ps": "I think it sums the lanes."})
    printed = capsys.readouterr()
    assert "e4 parse: 27 unit(s) — 26 parsed, 1 kept raw" in printed.out
    assert "hsum256_ps: not the two fields, kept raw" in printed.out
    assert f"has no {e4.API_DOC}" in printed.err  # the fixture is kernels only, and the parser is told so

    rows = {json.loads(line)["unit"]: json.loads(line) for line in (run_dir / e4.PARSER).read_text().splitlines()}
    assert len(rows) == 27 and rows["hsum256_ps"]["parsed"] is False
    assert rows["popcount_avx2"]["model"] == "Qwen/Qwen2.5-7B-Instruct"
    calls = [json.loads(line) for line in (run_dir / e1.CALLS).read_text().splitlines()]
    assert [call["stage"] for call in calls] == ["parse"]


def test_e4_plan_refuses_s5_without_the_parsers_fields_naming_the_file(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    argv = [
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--arms", "S-3,S-5", "--k", "0",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]
    assert cli.main(argv) == 2
    refusal = capsys.readouterr().err
    assert str(run_dir / e4.PARSER) in refusal and "is not there" in refusal
    assert "lattice e4 parse" in refusal and "never filled empty" in refusal
    assert not (run_dir / e1.META).exists()

    # a parse that covers only some of the units is the same refusal, naming the ones it does not answer
    parse_an_e4_run(tmp_path, capsys, run_dir)
    kept = [line for line in (run_dir / e4.PARSER).read_text().splitlines()][:-2]
    (run_dir / e4.PARSER).write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    assert cli.main(argv) == 2
    partial = capsys.readouterr().err
    assert "covers 25 of 27 unit(s)" in partial and "it does not answer" in partial
    assert not (run_dir / e1.META).exists()


def test_e4_plan_carries_the_parsers_fields_and_s2os_waves(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    parse_an_e4_run(tmp_path, capsys, run_dir)
    capsys.readouterr()
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--arms", "S-2o,S-5", "--k", "0",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    printed = capsys.readouterr().out
    assert "the parser's fields: 27 of 27 unit(s) parsed, Qwen/Qwen2.5-7B-Instruct" in printed
    assert "S-2o in 4 wave(s) of 18, 5, 3, 1 unit(s)" in printed

    record = json.loads((run_dir / e1.META).read_text())
    assert record["parser"]["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert record["parser"]["sha256"] == e4.parser_meta(run_dir)["sha256"]
    assert [len(wave) for wave in record["waves"]] == [18, 5, 3, 1]
    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    # S-5 for every unit, S-2o for wave 0 only; the later waves are `e4 run`'s to build
    assert sum(1 for r in requests if r["arm"] == "S-5") == 27
    assert sum(1 for r in requests if r["arm"] == "S-2o") == 18
    fields = e4.read_fields(run_dir)
    said = next(r for r in requests if r["arm"] == "S-5" and r["unit"] == "popcount_avx2")
    assert fields["popcount_avx2"]["contract"] in said["messages"][1]["content"]


def test_e4_plan_refuses_an_isa_the_target_has_not(tmp_path, capsys):
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(tmp_path / "e4"), "--model", "M", "--isa", "mmx",
    ]) == 2
    assert "no file for ISA 'mmx'" in capsys.readouterr().err


def test_e4_plan_skips_the_facts_arm_with_no_ledger_and_names_it(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--arms", "S-2,S-3", "--k", "0",
    ]) == 0
    assert "S-3 skipped" in capsys.readouterr().err
    assert json.loads((run_dir / e1.META).read_text())["arms"] == ["S-2"]


def test_e4_run_grades_every_unit_then_builds_the_file_and_reports(tmp_path, capsys, monkeypatch):
    run_dir = plan_an_e4_run(tmp_path, capsys, arms="S-0,S-2")
    recorded = e4_completions_for(run_dir)
    fake_e4_grade(monkeypatch)

    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["rows"] == 27 * 2 and summary["spent_usd"] == 0.0
    assert [row["arm"] for row in summary["file_level"]] == ["S-0", "S-2"]
    # every unit passed on gold, so each arm's file is the target's own and its patch is empty
    for row in summary["file_level"]:
        assert row["units_passed"] == 27 and row["diff_pass"] is True
        assert (run_dir / f"{row['written']}.patch").read_text() == ""

    assert cli.main(["e4", "report", str(run_dir)]) == 0
    table = capsys.readouterr().out
    assert "E4 e4 — Qwen/Qwen2.5-Coder-7B-Instruct (L1 on src/distance-avx2.c" in table
    assert "every window smaller" in table
    assert "file level (greedy bodies where the unit passed, gold elsewhere):" in table
    assert "S-2 − S-0" in table and "S-5 − S-3  — the run has no rows for S-3" in table

    assert cli.main(["e4", "report", str(run_dir), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["missing"] == [] and found["units"] == 27
    assert sorted(found["arms"]["S-0"]["by_kind"]) == ["cell", "helper", "init"]
    assert found["arms"]["S-0"]["by_kind"]["cell"]["pass_at_1"] == 1.0
    assert found["arms"]["S-0"]["by_kind"]["init"]["cells"] == 1
    assert found["comparisons"]["S-2 − S-0"]["pass_at_1"] == {
        "cells": 27, "both": 27, "neither": 0, "lost": 0, "gained": 0, "delta": 0.0, "p": 1.0,
    }
    assert found["comparisons"]["S-5 − S-3"] == {"missing": "the run has no rows for S-3"}
    assert found["own_shots"] is None  # the run carried no S-2o, which is not the same as carrying none


def test_e4_run_answers_s2o_in_waves_and_reports_both_comparisons(tmp_path, capsys, monkeypatch):
    run_dir = tmp_path / "e4"
    parse_an_e4_run(tmp_path, capsys, run_dir)
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
        "--arms", "S-0,S-2o,S-3,S-5", "--k", "0",
        "--graph", str(DERIVED / "graph.json"), "--key", str(DERIVED / "oracle.json"),
    ]) == 0
    capsys.readouterr()
    recorded = e4_completions_for(run_dir, arms=("S-0", "S-2o", "S-3", "S-5"), k=0)
    fake_e4_grade(monkeypatch)

    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["rows"] == 27 * 4 and summary["waves"] == 4

    assert cli.main(["e4", "report", str(run_dir), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["missing"] == []
    # both registered comparisons are now numbers, S-5 − S-3 among them
    assert found["comparisons"]["S-5 − S-3"]["pass_at_1"]["cells"] == 27
    assert found["comparisons"]["S-5 − S-3"]["pass_at_1"]["p"] == 1.0
    # and S-2o is described beside them: the own-shot counts, and why each missing one was missing
    own = found["own_shots"]
    assert own["units"] == 27 and own["cells"] == 13
    assert sum(own["carried"].values()) == 13
    assert own["missing"]["later-in-order"] > 0 and own["missing"]["helper"] == 13

    assert cli.main(["e4", "report", str(run_dir)]) == 0
    table = capsys.readouterr().out
    assert "parser: 27 of 27 unit(s) parsed by Qwen/Qwen2.5-7B-Instruct" in table
    assert "S-2o, described and not tested" in table and "in 4 wave(s)" in table
    assert "cells carrying 2 own shot(s):" in table and "no own shot, by reason:" in table
    assert "S-5 − S-3" in table and "not built" not in table


def hand_available(tmp_path, isa="avx2", name="available.json"):
    """A hand-built availability record covering one ISA, so `e4 plan --available` has an input.

    The compiler's own answer is `test_available.py`'s, over the three real `clang -E -dD` excerpts; here the
    record only has to cover the ISA being held out, which is the one thing the CLI checks it for.
    """
    lattice = build_lattice(FIXTURE)
    names = {
        found: {"available": True, "needs": [], "header": "hand-built"}
        for found in dict.fromkeys(re.findall(r"\b(_mm\w*|_cvt\w*)\s*\(", lattice.sources[isa].text))
    }
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                isa: {
                    "isa": isa,
                    "file": f"src/distance-{isa}.c",
                    "flags": ["-O2", "-Isrc", "-Ilibs", "-mavx2", "-mfma"],
                    "clang": "hand-built, not a compiler",
                    "target_sha": None,
                    "names": names,
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def run_an_e4_file(
    tmp_path,
    capsys,
    monkeypatch,
    name,
    *,
    isa="avx2",
    model="Qwen/Qwen2.5-Coder-7B-Instruct",
    arms="S-2,S-2h",
    available=None,
):
    """Plan and answer one file's arms over a replay, and return the run directory.

    The request ids carry no model, only the seeds do, so one replay answers a 7B run and a 32B run of the
    same plan — which is what `e4 compare` reads.
    """
    run_dir = tmp_path / name
    argv = [
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", model,
        "--isa", isa, "--arms", arms, "--k", "0",
    ]
    if available is not None:
        argv += ["--available", str(available)]
    assert cli.main(argv) == 0
    capsys.readouterr()
    recorded = e4_completions_for(run_dir, isa=isa)
    fake_e4_grade(monkeypatch)
    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10", "--generator", f"replay:{recorded}",
    ]) == 0
    capsys.readouterr()
    return run_dir


def test_e4_report_reads_the_helper_comparison_and_the_cell_noise_read(tmp_path, capsys, monkeypatch):
    """D-11 a at the CLI: S-2h plans and runs like S-2, and the report reads the two of them apart."""
    run_dir = run_an_e4_file(tmp_path, capsys, monkeypatch, "e4")
    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    family = next(r for r in requests if r["arm"] == "S-2h" and r["unit"] == "hsum256_ps")
    assert [(row["isa"], row["from"]) for row in family["shots"]] == [
        ("sse2", "hsum128_ps"),
        ("avx512", "hsum512_ps"),
    ]
    assert "matched by name, not by the grid" in family["messages"][1]["content"]
    # the same helper under S-2 carries nothing, which is the gap the arm is about
    plain = next(r for r in requests if r["arm"] == "S-2" and r["unit"] == "hsum256_ps")
    assert plain["shots"] == [] and plain["shots_note"] == e4.NO_SHOTS["helper"]

    assert cli.main(["e4", "report", str(run_dir), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    helpers = found["comparisons"]["S-2h − S-2 (helper units, registered)"]
    cells = found["comparisons"]["S-2h − S-2 (cell units, described: identical prompts under two seeds)"]
    assert helpers["pass_at_1"]["cells"] == 13 and cells["pass_at_1"]["cells"] == 13
    # every unit answered with its own gold, so both readings are flat — and both are readings
    assert helpers["pass_at_1"]["delta"] == 0.0 and cells["pass_at_1"]["delta"] == 0.0

    assert cli.main(["e4", "report", str(run_dir)]) == 0
    table = capsys.readouterr().out
    assert "S-2h − S-2 (helper units, registered)" in table
    assert "S-2h − S-2 (cell units, described" in table


def test_e4_compare_reads_one_file_on_two_models_and_refuses_anything_else(tmp_path, capsys, monkeypatch):
    small = run_an_e4_file(tmp_path, capsys, monkeypatch, "qwen-7b")
    large = run_an_e4_file(
        tmp_path, capsys, monkeypatch, "qwen-32b", model="Qwen/Qwen2.5-Coder-32B-Instruct"
    )

    assert cli.main(["e4", "compare", str(small), str(large), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["a"]["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert found["b"]["model"] == "Qwen/Qwen2.5-Coder-32B-Instruct"
    assert found["described"] is True and found["arms"] == ["S-2", "S-2h"]
    assert sorted(found["paired"]["S-2h"]) == ["cell", "helper", "init"]

    assert cli.main(["e4", "compare", str(small), str(large)]) == 0
    assert "a price, not a registered comparison" in capsys.readouterr().out

    # the other file at the same model is not one variable apart, and is refused rather than differenced
    other = run_an_e4_file(tmp_path, capsys, monkeypatch, "qwen-7b-sse2", isa="sse2")
    assert cli.main(["e4", "compare", str(small), str(other)]) == 2
    assert "nothing was compared" in capsys.readouterr().err


def test_e4_pool_pools_the_registered_comparison_over_the_files_and_refuses_a_repeat(
    tmp_path, capsys, monkeypatch
):
    avx2 = run_an_e4_file(tmp_path, capsys, monkeypatch, "pool-avx2")
    sse2 = run_an_e4_file(tmp_path, capsys, monkeypatch, "pool-sse2", isa="sse2")

    assert cli.main([
        "e4", "pool", str(avx2), str(sse2), "--pair", "S-2,S-2h", "--kind", "helper", "--json",
    ]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["registered"] is True and found["kind"] == "helper"
    assert [row["isa"] for row in found["runs"]] == ["avx2", "sse2"]
    # avx2's 13 helpers and sse2's 6, keyed by ISA so the two files' names cannot collide
    assert found["paired"]["pass_at_1"]["cells"] == 13 + 6
    assert found["runs"][0]["units"] == {"S-2": 13, "S-2h": 13}

    assert cli.main(["e4", "pool", str(avx2), str(sse2)]) == 0  # the defaults are the registered pair
    table = capsys.readouterr().out
    assert "E4 pooled S-2h − S-2 over 2 run(s)" in table and "helper unit(s); registered" in table

    assert cli.main(["e4", "pool", str(avx2), str(avx2)]) == 2
    assert "both over avx2" in capsys.readouterr().err
    assert cli.main(["e4", "pool", str(avx2), str(sse2), "--pair", "S-2,C-2"]) == 2
    assert "no arm 'C-2'" in capsys.readouterr().err
    assert cli.main(["e4", "pool", str(avx2), str(sse2), "--pair", "S-2"]) == 2
    assert "--pair takes two arms" in capsys.readouterr().err


def test_e4_plan_carries_s3h_with_an_availability_record_and_names_it(tmp_path, capsys):
    """D-12 a at the CLI: `--available` is S-3h's input, and `meta.json` names the record it was built from."""
    run_dir = tmp_path / "e4"
    record = hand_available(tmp_path)
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M",
        "--arms", "S-2h,S-3h", "--k", "0", "--available", str(record),
    ]) == 0
    printed = capsys.readouterr().out
    assert "what this file can use:" in printed and "hand-built, not a compiler" in printed

    meta = json.loads((run_dir / e1.META).read_text())
    assert meta["arms"] == ["S-2h", "S-3h"]
    assert meta["available"]["sha256"] == available.record_meta(record)["sha256"]
    assert meta["available"]["isas"]["avx2"]["flags"] == ["-O2", "-Isrc", "-Ilibs", "-mavx2", "-mfma"]

    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    family = next(r for r in requests if r["arm"] == "S-3h" and r["unit"] == "hsum256_ps")
    assert "What this file can use, of what the examples above use" in family["messages"][1]["content"]
    assert [row["name"] for row in family["available"]["intrinsics"]][-1] == "_mm512_reduce_add_ps"
    # S-2h's own request is the same prompt without the block, and carries none on its row
    plain = next(r for r in requests if r["arm"] == "S-2h" and r["unit"] == "hsum256_ps")
    assert plain["available"] is None
    assert plain["shots"] == family["shots"]


def test_e4_plan_skips_s3h_with_no_record_and_refuses_one_for_another_isa(tmp_path, capsys):
    run_dir = tmp_path / "e4"
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(run_dir), "--model", "M", "--arms", "S-2h,S-3h", "--k", "0",
    ]) == 0
    assert "S-3h skipped" in capsys.readouterr().err
    assert json.loads((run_dir / e1.META).read_text())["arms"] == ["S-2h"]
    assert json.loads((run_dir / e1.META).read_text())["available"] is None

    # a record that covers another file is refused, naming the ISA it does not cover: never filled empty
    elsewhere = hand_available(tmp_path, isa="sse2", name="sse2.json")
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(tmp_path / "other"), "--model", "M", "--arms", "S-3h", "--k", "0",
        "--available", str(elsewhere),
    ]) == 2
    err = capsys.readouterr().err
    assert "does not cover avx2" in err and "never filled empty" in err
    assert not (tmp_path / "other" / e1.META).exists()

    assert cli.main([
        "e4", "plan", str(FIXTURE), str(tmp_path / "third"), "--model", "M", "--arms", "S-3h",
        "--available", str(tmp_path / "nowhere.json"),
    ]) == 2
    assert "the availability record could not be read" in capsys.readouterr().err


def test_e4_pool_reads_d12s_pair_with_no_kind_as_registered(tmp_path, capsys, monkeypatch):
    record = hand_available(tmp_path)
    avx2 = run_an_e4_file(
        tmp_path, capsys, monkeypatch, "d12-avx2", arms="S-2h,S-3h", available=record
    )
    assert cli.main(["e4", "pool", str(avx2), "--pair", "S-2h,S-3h", "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    # no --kind: the default is the kind the pair is registered on, which for D-12's is every unit
    assert found["kind"] is None and found["registered"] is True
    assert found["paired"]["pass_at_1"]["cells"] == 27

    assert cli.main(["e4", "pool", str(avx2), "--pair", "S-2h,S-3h"]) == 0
    assert "every unit(s); registered" in capsys.readouterr().out
    # and D-11's pair still defaults to its own kind, which is the helper units
    assert cli.main(["e4", "pool", str(avx2), "--pair", "S-2,S-2h", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "helper"


# MARK: - D-13 at the CLI: `e4 loop`, and the two pooled readings -

#: The one name the source run's grader invents, and the index that says this compiler declares it.
LOOPED = "_mm512_setzero_si512"


def failing_e4_grade(monkeypatch, classes, invented=(LOOPED,)):
    """`e1.default_grade`, replaced by one that gives each named unit a class and everything else a pass."""

    def graded(target, image=run.IMAGE, rename_in_target=None):
        def grade(entries):
            answered = []
            for entry in entries:
                cls = classes.get(entry.get("unit"), "pass")
                answered.append(
                    {
                        "id": entry["id"],
                        "unit": entry.get("unit"),
                        "class": cls,
                        "reg": True,
                        "diagnostics": [],
                        "invented": [
                            {"name": name, "bucket": "intrinsic"}
                            for name in (invented if cls == "invented" else ())
                        ],
                        "feedback": "" if cls == "pass" else "It did not compile.\nfoo.c:1:1: error: nope",
                    }
                )
            return answered

        return grade

    monkeypatch.setattr(e1, "default_grade", graded)


def loop_completions(run_dir, isa="avx2", arms=e4.LOOP_ARMS, k=0, rounds=(0, 1)):
    """A replay answering every (unit, arm, sample, round) id a D-13 run can ask for.

    Generated rather than read off `requests.jsonl`, for `e4_completions_for`'s own reason: a retry is a
    request `e4 run` builds as the rows come in, so it is not in the plan for a replay to read.
    """
    lattice = build_lattice(FIXTURE)
    source = lattice.sources[isa]
    rows = []
    for unit in e4.units(lattice, isa):
        written = source.text[unit.signature_span.start : unit.body_span.end]
        for arm in arms:
            for sample in range(0, k + 1):
                for at_round in rounds:
                    rows.append(
                        {
                            "id": e1.request_id(unit.name, arm, sample, at_round),
                            "text": f"```c\n{written}\n```",
                        }
                    )
    recorded = run_dir.parent / "loop-completions.jsonl"
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return recorded


def loop_instruments(tmp_path):
    """The availability record `lattice available` would write, and an intrinsic index beside it."""
    record = hand_available(tmp_path)
    index = tmp_path / "intrinsics.json"
    index.write_text(json.dumps({LOOPED: {"header": "avx512fintrinsics.h"}}), encoding="utf-8")
    return record, index


def d13_run(tmp_path, capsys, monkeypatch):
    """A source run whose `hsum256_ps` came back `invented`, and the D-13 run `e4 loop` wrote from it."""
    record, index = loop_instruments(tmp_path)
    source = tmp_path / "d12"
    assert cli.main([
        "e4", "plan", str(FIXTURE), str(source), "--model", "Qwen/Qwen2.5-Coder-7B-Instruct",
        "--arms", "S-3h", "--k", "0", "--available", str(record),
    ]) == 0
    capsys.readouterr()
    failing_e4_grade(monkeypatch, {"hsum256_ps": "invented", "sqdiff_epu8": "compile"})
    assert cli.main([
        "e4", "run", str(source), str(FIXTURE), "--ceiling-usd", "10",
        "--generator", f"replay:{e4_completions_for(source)}",
    ]) == 0
    capsys.readouterr()

    run_dir = tmp_path / "d13"
    assert cli.main([
        "e4", "loop", str(source), str(run_dir), "--available", str(record), "--intrinsics", str(index),
    ]) == 0
    return source, run_dir, record, index


def test_e4_loop_copies_the_source_round_and_names_both_instruments(tmp_path, capsys, monkeypatch):
    source, run_dir, record, index = d13_run(tmp_path, capsys, monkeypatch)
    printed = capsys.readouterr().out
    assert "e4 loop: 54 request(s) and 54 copied row(s) — 27 S-3h chain(s) × 2 arm(s) (S-3hd, S-3hf)" in printed
    assert f"round 0 is {source.name}'s, copied and not asked" in printed
    assert "1 round to go, retried from invented, compile" in printed
    assert "a retry with no fact line is one request" in printed
    assert f"available: {record}" in printed and f"intrinsics: {index}" in printed

    meta = json.loads((run_dir / e1.META).read_text())
    assert meta["arms"] == ["S-3hd", "S-3hf"] and meta["rounds"] == 1
    assert meta["loop"]["available"]["sha256"] == hashlib.sha256(record.read_bytes()).hexdigest()
    assert not (run_dir / e1.CALLS).exists()  # nothing was called and nothing was spent

    # an instrument that is not there is named, and no plan is written from a digest nobody could take
    assert cli.main([
        "e4", "loop", str(source), str(tmp_path / "again"), "--available", str(tmp_path / "nowhere.json"),
        "--intrinsics", str(index),
    ]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_e4_loop_refuses_a_source_with_no_s3h(tmp_path, capsys, monkeypatch):
    record, index = loop_instruments(tmp_path)
    plain = plan_an_e4_run(tmp_path, capsys, arms="S-2h")
    assert cli.main([
        "e4", "loop", str(plain), str(tmp_path / "none"), "--available", str(record),
        "--intrinsics", str(index),
    ]) == 2
    assert "has no S-3h request" in capsys.readouterr().err
    assert not (tmp_path / "none").exists()


def test_e4_run_answers_the_retry_round_and_the_report_reads_the_loop(tmp_path, capsys, monkeypatch):
    source, run_dir, record, index = d13_run(tmp_path, capsys, monkeypatch)
    capsys.readouterr()
    fake_e4_grade(monkeypatch)  # the retry passes in both arms, so the rescue is what there is to read
    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10",
        "--generator", f"replay:{loop_completions(run_dir)}",
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["rows"] == 27 * 2 + 2 * 2  # the copied round 0, and the two retried chains in both arms

    assert cli.main(["e4", "report", str(run_dir), "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    loop = found["loop"]
    assert loop["rounds"] == 1 and loop["source"]["run"] == source.name
    assert loop["by_arm"]["S-3hf"]["retried"] == loop["by_arm"]["S-3hd"]["retried"] == 2
    assert loop["by_arm"]["S-3hf"]["rescued"] == {"compile": 1, "invented": 1}
    # `hsum256_ps` invented a name the index declares and this file cannot use, so its retry carried a line
    assert loop["lines"] == {e4.NOT_HERE: 1} and loop["by_arm"]["S-3hf"]["with_lines"] == 1
    assert loop["identical_retries"] == 1  # the `compile` chain had no name, so both arms asked once
    assert report.loop_label("S-3hd", "S-3hf", 1) in found["comparisons"]

    assert cli.main(["e4", "report", str(run_dir)]) == 0
    table = capsys.readouterr().out
    assert "the loop, 1 round — retried from invented, compile" in table
    assert "ruled-out reuse:" in table and "S-3hf − S-3hd (every unit, through round 1, registered)" in table

    requests = [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
    facts = next(r for r in requests if r["round"] == 1 and r["arm"] == "S-3hf" and r["unit"] == "hsum256_ps")
    said = facts["messages"][-1]["content"]
    assert "What this file can use, of the names above" in said
    assert f"`{LOOPED}` is not available in this file" in said
    assert [row["status"] for row in facts["loop_facts"]] == [e4.NOT_HERE]
    # and the control's own retry is the graders' text and nothing else
    plain = next(r for r in requests if r["round"] == 1 and r["arm"] == "S-3hd" and r["unit"] == "hsum256_ps")
    assert plain["messages"][-1]["content"] == "It did not compile.\nfoo.c:1:1: error: nope"
    assert plain["loop_facts"] == []


def test_e4_pool_reads_d13s_two_registered_readings(tmp_path, capsys, monkeypatch):
    _, run_dir, _, _ = d13_run(tmp_path, capsys, monkeypatch)
    capsys.readouterr()
    fake_e4_grade(monkeypatch)
    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10",
        "--generator", f"replay:{loop_completions(run_dir)}",
    ]) == 0
    capsys.readouterr()

    assert cli.main(["e4", "pool", str(run_dir), "--pair", "S-3hd,S-3hf", "--through", "1", "--json"]) == 0
    pair = json.loads(capsys.readouterr().out)
    assert pair["registered"] is True and pair["through"] == 1 and pair["kind"] is None
    assert pair["paired"]["pass_at_1"]["cells"] == 27

    assert cli.main(["e4", "pool", str(run_dir), "--arm", "S-3hf", "--rounds", "0,1", "--json"]) == 0
    rounds = json.loads(capsys.readouterr().out)
    assert rounds["registered"] is True and rounds["rounds"] == [0, 1] and rounds["arm"] == "S-3hf"
    assert rounds["paired"]["pass_at_1"]["gained"] == 2 and rounds["paired"]["pass_at_1"]["lost"] == 0
    assert rounds["runs"][0]["retried"] == 2

    assert cli.main(["e4", "pool", str(run_dir), "--arm", "S-3hf"]) == 0  # 0,1 is the default
    table = capsys.readouterr().out
    assert "E4 S-3hf round 1 − round 0 over 1 run(s)" in table
    assert "cannot be negative by construction" in table

    # two readings, so naming both is a refusal; and the rounds have to be a pair
    assert cli.main(["e4", "pool", str(run_dir), "--arm", "S-3hf", "--pair", "S-3hd,S-3hf"]) == 2
    assert "they are two readings" in capsys.readouterr().err
    assert cli.main(["e4", "pool", str(run_dir), "--arm", "S-3hf", "--rounds", "1"]) == 2
    assert "--rounds takes two whole rounds" in capsys.readouterr().err
    assert cli.main(["e4", "pool", str(run_dir), "--arm", "C-2"]) == 2
    assert "no arm 'C-2'" in capsys.readouterr().err


def test_e4_run_refuses_a_moved_instrument_and_answers_nothing(tmp_path, capsys, monkeypatch):
    _, run_dir, record, _ = d13_run(tmp_path, capsys, monkeypatch)
    capsys.readouterr()
    record.write_text("{}", encoding="utf-8")
    fake_e4_grade(monkeypatch)
    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "10",
        "--generator", f"replay:{loop_completions(run_dir)}",
    ]) == 2
    err = capsys.readouterr().err
    assert "now digests" in err and "nothing was sent" in err
    rows = [json.loads(line) for line in (run_dir / e1.ROWS).read_text().splitlines()]
    assert {row["round"] for row in rows} == {0}


def test_e4_run_without_a_ceiling_exits_two(tmp_path, capsys):
    run_dir = plan_an_e4_run(tmp_path, capsys)
    with pytest.raises(SystemExit) as refused:
        cli.main(["e4", "run", str(run_dir), str(FIXTURE), "--generator", "replay:nowhere.jsonl"])
    assert refused.value.code == 2
    assert "--ceiling-usd" in capsys.readouterr().err


def test_e4_run_prints_the_ceiling_refusal_and_grades_nothing(tmp_path, capsys):
    run_dir = plan_an_e4_run(tmp_path, capsys)
    recorded = e4_completions_for(run_dir)
    assert cli.main([
        "e4", "run", str(run_dir), str(FIXTURE), "--ceiling-usd", "0", "--generator", f"replay:{recorded}",
    ]) == 2
    assert "nothing was sent" in capsys.readouterr().err
    assert not (run_dir / e1.ROWS).exists() and not (run_dir / e4.FILE_LEVEL).exists()
