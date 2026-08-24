"""Tests for hobbes.render — the Mermaid module-graph export."""

import re
from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.render import to_mermaid

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


@pytest.fixture(scope="module")
def graph():
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    return build_graph(modules, parsed)


@pytest.fixture(scope="module")
def mermaid(graph):
    return to_mermaid(graph)


class TestStructure:
    def test_flowchart_header(self, mermaid):
        assert mermaid.startswith("flowchart LR\n")

    def test_internal_modules_clustered_by_package(self, mermaid):
        assert re.search(r'subgraph sg\d+\["miniapp"\]', mermaid)
        assert re.search(r'subgraph sg\d+\["tests"\]', mermaid)

    def test_kind_shapes(self, mermaid):
        assert re.search(r'n\d+\["miniapp\.core"\]', mermaid)
        assert re.search(r'n\d+\[\["ext:fastapi"\]\]', mermaid)
        assert re.search(r'n\d+\(\["env:MINIAPP_MODE"\]\)', mermaid)

    def test_edge_arrows_by_type(self, graph, mermaid):
        tokens = {
            n["id"]: f"n{i}"
            for i, n in enumerate(sorted(graph["nodes"], key=lambda n: n["id"]))
        }
        core, util = tokens["miniapp.core"], tokens["miniapp.util"]
        assert f"  {core} --> {util}" in mermaid
        env_mode = tokens["env:MINIAPP_MODE"]
        assert f"  {core} -.-> {env_mode}" in mermaid

    def test_raw_ids_never_used_as_mermaid_ids(self, mermaid):
        declaration = re.compile(r"n\d+[\[\(]")
        edge = re.compile(r"n\d+ \S+ n\d+$")
        for line in mermaid.splitlines()[1:]:
            stripped = line.strip()
            if stripped == "end" or stripped.startswith("subgraph"):
                continue
            assert declaration.match(stripped) or edge.match(stripped), line

    def test_unknown_edge_types_render_labeled(self):
        doc = {
            "nodes": [
                {"id": "a", "kind": "module", "path": "a.py"},
                {"id": "b", "kind": "module", "path": "b.py"},
            ],
            "module_edges": [
                {"from": "a", "to": "b", "type": "http-call", "evidence": []}
            ],
        }
        assert 'n0 --"http-call"--> n1' in to_mermaid(doc)

    def test_single_member_groups_not_boxed(self):
        doc = {
            "nodes": [{"id": "lonely", "kind": "module", "path": "lonely.py"}],
            "module_edges": [],
        }
        out = to_mermaid(doc)
        assert "subgraph" not in out
        assert 'n0["lonely"]' in out


class TestInfraNodes:
    def test_tf_shapes_and_directory_clustering(self):
        doc = {
            "nodes": [
                {"id": "tf:aws_iam_role.w", "kind": "resource", "path": "infra/main.tf"},
                {"id": "tf:data.archive_file.w", "kind": "data", "path": "infra/main.tf"},
                {"id": "tf:module.vpc", "kind": "tf-module", "path": "infra/net.tf"},
            ],
            "module_edges": [
                {
                    "from": "tf:data.archive_file.w",
                    "to": "tf:aws_iam_role.w",
                    "type": "references",
                    "evidence": [],
                }
            ],
        }
        out = to_mermaid(doc)
        assert re.search(r'subgraph sg\d+\["infra"\]', out)
        assert re.search(r'n\d+\{\{"tf:aws_iam_role\.w"\}\}', out)
        assert re.search(r'n\d+\[\("tf:data\.archive_file\.w"\)\]', out)
        assert re.search(r'n\d+\[/"tf:module\.vpc"/\]', out)
        assert '--"references"-->' in out


class TestDeterminism:
    def test_byte_identical(self, graph):
        assert to_mermaid(graph) == to_mermaid(graph)
