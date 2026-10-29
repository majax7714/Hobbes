"""The identity gate's comparison (ADR-184): bytes, with built_by masked."""

import json
from pathlib import Path

from compare import main, masked

ARTIFACTS = ("graph.json", "tests.json", "interfaces.json")


def arm(root: Path, name: str, graph: str, exit_code: str | None = None) -> Path:
    path = root / name
    path.mkdir()
    (path / "graph.json").write_text(graph)
    for other in ARTIFACTS[1:]:
        (path / other).write_text("{}")
    if exit_code is not None:
        (path / "exit").write_text(exit_code + "\n")
    return path


def test_built_by_alone_is_masked(tmp_path, capsys):
    a = arm(tmp_path, "a", '{"built_by": {"path": "/x", "v": "1"}, "nodes": [1, 2]}')
    b = arm(tmp_path, "b", '{"built_by": {"path": "/yy", "v": "2"}, "nodes": [1, 2]}')
    assert main(a, b) == 0
    assert "graph.json: identical bytes but for built_by" in capsys.readouterr().out


def test_the_same_json_in_other_bytes_differs(tmp_path, capsys):
    a = arm(tmp_path, "a", '{"built_by": {"path": "/x"}, "nodes": [1, 2]}')
    b = arm(tmp_path, "b", '{"nodes": [1, 2], "built_by": {"path": "/x"}}')
    assert main(a, b) == 1
    assert "the same JSON in different bytes" in capsys.readouterr().out


def test_a_failed_pass_fails_whatever_its_directory_holds(tmp_path, capsys):
    graph = '{"built_by": {}, "nodes": []}'
    a = arm(tmp_path, "a", graph, "0")
    b = arm(tmp_path, "b", graph, "1")
    assert main(a, b) == 1
    assert "the after pass failed (exit 1)" in capsys.readouterr().out


def test_a_differing_row_is_shown(tmp_path, capsys):
    a = arm(tmp_path, "a", json.dumps({"built_by": {}, "nodes": [{"id": "m"}]}))
    b = arm(tmp_path, "b", json.dumps({"built_by": {}, "nodes": [{"id": "n"}]}))
    assert main(a, b) == 1
    out = capsys.readouterr().out
    assert "graph.json nodes: -1 +1" in out and '"id": "n"' in out


def test_masked_cuts_only_the_value():
    assert masked('{"built_by": {"a": [1, {"b": 2}]}, "x": 1}') == '{"built_by": , "x": 1}'
    assert masked('{"x": 1}') == '{"x": 1}'
