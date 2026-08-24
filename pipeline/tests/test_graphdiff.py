"""Tests for hobbes.graphdiff — delta computation, formatting, ref extraction."""

import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes.graphdiff import (
    RefError,
    diff_graphs,
    extract_at_ref,
    format_delta,
    has_changes,
)

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


def graph_doc(nodes=(), module_edges=(), symbol_edges=()):
    return {
        "nodes": list(nodes),
        "module_edges": list(module_edges),
        "symbol_edges": list(symbol_edges),
    }


def edge(src, dst, type="imports", evidence=()):
    return {"from": src, "to": dst, "type": type, "evidence": list(evidence)}


class TestDiffGraphs:
    def test_added_and_removed_edges(self):
        base = graph_doc(
            nodes=[{"id": "a", "kind": "module"}, {"id": "b", "kind": "module"}],
            module_edges=[edge("a", "b")],
        )
        head = graph_doc(
            nodes=[{"id": "a", "kind": "module"}, {"id": "c", "kind": "module"}],
            module_edges=[edge("a", "c", evidence=[{"path": "a.py", "line": 3}])],
        )
        delta = diff_graphs(base, head)
        assert [n["id"] for n in delta["nodes_added"]] == ["c"]
        assert [n["id"] for n in delta["nodes_removed"]] == ["b"]
        assert delta["module_edges_added"] == [
            edge("a", "c", evidence=[{"path": "a.py", "line": 3}])
        ]
        assert delta["module_edges_removed"] == [edge("a", "b")]
        assert has_changes(delta)

    def test_evidence_change_is_not_a_delta(self):
        base = graph_doc(
            nodes=[{"id": "a", "kind": "module"}],
            module_edges=[edge("a", "b", evidence=[{"path": "a.py", "line": 12}])],
        )
        head = graph_doc(
            nodes=[{"id": "a", "kind": "module"}],
            module_edges=[edge("a", "b", evidence=[{"path": "a.py", "line": 30}])],
        )
        assert not has_changes(diff_graphs(base, head))

    def test_type_change_is_remove_plus_add(self):
        base = graph_doc(module_edges=[edge("a", "b", type="imports")])
        head = graph_doc(module_edges=[edge("a", "b", type="env-read")])
        delta = diff_graphs(base, head)
        assert [e["type"] for e in delta["module_edges_added"]] == ["env-read"]
        assert [e["type"] for e in delta["module_edges_removed"]] == ["imports"]

    def test_symbol_layer_diffed_separately(self):
        base = graph_doc(symbol_edges=[edge("m.f", "m.g", type="calls")])
        head = graph_doc(
            symbol_edges=[
                edge("m.f", "m.g", type="calls"),
                edge("m.f", "m.h", type="calls"),
            ]
        )
        delta = diff_graphs(base, head)
        assert len(delta["symbol_edges_added"]) == 1
        assert delta["module_edges_added"] == []


class TestFormatDelta:
    def test_no_changes(self):
        delta = diff_graphs(graph_doc(), graph_doc())
        text = format_delta(delta, "main", "HEAD")
        assert "architecture delta main..HEAD" in text
        assert "no architectural changes" in text

    def test_module_lines_and_symbol_counts(self):
        base = graph_doc(module_edges=[edge("a", "b")])
        head = graph_doc(
            nodes=[{"id": "env:MODE", "kind": "env"}],
            module_edges=[
                edge("a", "env:MODE", type="env-read",
                     evidence=[{"path": "a.py", "line": 7}])
            ],
            symbol_edges=[edge("a.f", "a.g", type="calls")],
        )
        text = format_delta(diff_graphs(base, head), "x", "y")
        assert "  + env env:MODE" in text
        assert "  + env-read a -> env:MODE   [a.py:7]" in text
        assert "  - imports a -> b" in text
        assert "  symbol layer: +1 / -0 call edges" in text


class TestExtractAtRef:
    @pytest.fixture
    def git_fixture(self, tmp_path):
        repo = tmp_path / "miniapp"
        shutil.copytree(FIXTURE, repo)
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "one"], check=True)
        return repo

    def test_extracts_committed_tree_not_working_tree(self, git_fixture):
        # Add an uncommitted module: HEAD's graph must not see it.
        (git_fixture / "src" / "miniapp" / "extra.py").write_text(
            "from miniapp import util\n"
        )
        graph = extract_at_ref(git_fixture, "HEAD")
        assert not any(n["id"] == "miniapp.extra" for n in graph["nodes"])
        assert any(n["id"] == "miniapp.core" for n in graph["nodes"])

    def test_bad_ref_raises(self, git_fixture):
        with pytest.raises(RefError, match="no-such-ref"):
            extract_at_ref(git_fixture, "no-such-ref")

    def test_diff_between_real_commits(self, git_fixture):
        git = ["git", "-C", str(git_fixture), "-c", "user.name=t", "-c", "user.email=t@t"]
        (git_fixture / "src" / "miniapp" / "extra.py").write_text(
            "from miniapp import util\n"
        )
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "two"], check=True)

        base = extract_at_ref(git_fixture, "HEAD~1")
        head = extract_at_ref(git_fixture, "HEAD")
        delta = diff_graphs(base, head)
        assert [n["id"] for n in delta["nodes_added"]] == ["miniapp.extra"]
        assert [(e["from"], e["to"]) for e in delta["module_edges_added"]] == [
            ("miniapp.extra", "miniapp.util")
        ]
        assert delta["nodes_removed"] == []
