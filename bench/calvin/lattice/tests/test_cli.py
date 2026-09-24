"""The CLI: the map names every ISA, the per-cell verbs answer, and the graders say where they may run."""

import json
import shutil
from pathlib import Path

import pytest

from lattice import cli, run
from lattice.holes import HOLE

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


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
    assert record["schema"] == "lattice-task/2"
    assert record["prelude_bare"]


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
