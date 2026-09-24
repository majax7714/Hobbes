"""The CLI: the map names every ISA, and the two per-cell verbs answer for a real cell."""

import json
from pathlib import Path

from lattice import cli
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
    assert record["schema"] == "lattice-task/1"


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
