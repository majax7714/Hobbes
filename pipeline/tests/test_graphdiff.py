"""Tests for hobbes.graphdiff — delta computation, formatting, ref extraction."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes import graphdiff
from hobbes.graphdiff import (
    RefError,
    diff_graphs,
    extract_all_at_ref,
    extract_at_ref,
    format_delta,
    format_environments,
    has_changes,
    link_environments,
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
            symbol_edges=[
                edge("a.f", "a.g", type="calls"),
                edge("a.f", "a.T", type="uses"),
            ],
        )
        text = format_delta(diff_graphs(base, head), "x", "y")
        assert "  + env env:MODE" in text
        assert "  + env-read a -> env:MODE   [a.py:7]" in text
        assert "  - imports a -> b" in text
        # C-76: a `uses` edge is not a call and is not counted as one.
        assert "  symbol layer: +1 / -0 calls edges" in text
        assert "  symbol layer: +1 / -0 uses edges" in text


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


def _commit_all(repo: Path, message: str = "one") -> None:
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    if not (repo / ".git").exists():
        subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", message], check=True)


class TestLinkEnvironments:
    """ADR-186: a ref's extraction gets the checkout's dependency trees."""

    def test_node_modules_is_hardlinked_and_a_workspace_link_stays_inside_the_ref(self, tmp_path):
        checkout, scratch = tmp_path / "checkout", tmp_path / "scratch"
        modules = checkout / "pkg" / "node_modules"
        (modules / "dep").mkdir(parents=True)
        (modules / "dep" / "index.js").write_text("module.exports = 1\n")
        (modules / "@s").mkdir()
        os.symlink("../../../lib", modules / "@s" / "lib")
        (scratch / "pkg").mkdir(parents=True)
        (scratch / "lib").mkdir()

        assert link_environments(checkout, scratch) == [{"path": "pkg/node_modules", "kind": "node_modules"}]
        linked = scratch / "pkg" / "node_modules"
        assert (linked / "dep" / "index.js").stat().st_ino == (modules / "dep" / "index.js").stat().st_ino
        assert os.readlink(linked / "@s" / "lib") == "../../../lib"
        assert (linked / "@s" / "lib").resolve() == (scratch / "lib").resolve()

    def test_a_venv_needs_its_marker(self, tmp_path):
        checkout, scratch = tmp_path / "checkout", tmp_path / "scratch"
        (checkout / ".venv").mkdir(parents=True)
        (checkout / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
        (checkout / "tools" / "venv").mkdir(parents=True)
        (scratch / "tools").mkdir(parents=True)

        assert link_environments(checkout, scratch) == [{"path": ".venv", "kind": "venv"}]
        assert not (scratch / "tools" / "venv").exists()

    def test_only_where_the_ref_has_the_directory_and_not_the_tree(self, tmp_path):
        checkout, scratch = tmp_path / "checkout", tmp_path / "scratch"
        for where in ("gone", "kept", "ours"):
            (checkout / where / "node_modules").mkdir(parents=True)
        (scratch / "kept").mkdir(parents=True)
        (scratch / "ours" / "node_modules").mkdir(parents=True)
        (scratch / "ours" / "node_modules" / "vendored.js").write_text("")

        assert [r["path"] for r in link_environments(checkout, scratch)] == ["kept/node_modules"]
        assert not (scratch / "gone").exists()
        assert [p.name for p in (scratch / "ours" / "node_modules").iterdir()] == ["vendored.js"]

    def test_a_tree_that_cannot_be_linked_is_removed_and_says_why(self, tmp_path, monkeypatch):
        checkout, scratch = tmp_path / "checkout", tmp_path / "scratch"
        (checkout / "node_modules" / "dep").mkdir(parents=True)
        (checkout / "node_modules" / "dep" / "index.js").write_text("")
        scratch.mkdir()

        def cross_device(src, dst):
            raise OSError(18, "Invalid cross-device link")

        monkeypatch.setattr(graphdiff.os, "link", cross_device)
        [record] = link_environments(checkout, scratch)
        assert record["path"] == "node_modules"
        assert "cross-device" in record["error"]
        assert not (scratch / "node_modules").exists()

    def test_format_names_the_trees_and_each_failure(self):
        lines = format_environments(
            [
                {"path": "a/node_modules", "kind": "node_modules"},
                {"path": "b/node_modules", "kind": "node_modules", "error": "Invalid cross-device link"},
                {"path": "pipeline/.venv", "kind": "venv"},
            ]
        )
        assert lines[0].startswith("dependency trees: 2 hardlinked from the checkout into each end (1 node_modules, 1 venv)")
        assert "C-198" in lines[0]
        assert lines[1] == (
            "not linked, read without its dependency tree (C-198): b/node_modules — Invalid cross-device link"
        )
        assert format_environments([]) == []


class TestExtractAtRefWithEnvironments:
    def _workspace(self, tmp_path):
        # Package a imports a subpath of @s/b through its `exports` map, as the fork's
        # `@opencode/simulation/frontend/semantics` does. Lane A resolves a package's
        # main by name, but a subpath export only through the gitignored workspace link.
        repo = tmp_path / "ws"
        (repo / "a" / "src").mkdir(parents=True)
        (repo / "b" / "src" / "x").mkdir(parents=True)
        (repo / ".gitignore").write_text("node_modules/\n")
        (repo / "a" / "package.json").write_text('{"name": "@s/a", "dependencies": {"@s/b": "*"}}\n')
        (repo / "a" / "src" / "index.ts").write_text('import { b } from "@s/b/x/thing"\nexport const a = () => b()\n')
        (repo / "b" / "package.json").write_text('{"name": "@s/b", "exports": {"./x/*": "./src/x/*.ts"}}\n')
        (repo / "b" / "src" / "x" / "thing.ts").write_text("export const b = () => 1\n")
        _commit_all(repo)
        (repo / "a" / "node_modules" / "@s").mkdir(parents=True)
        os.symlink("../../../b", repo / "a" / "node_modules" / "@s" / "b")
        return repo

    def test_a_workspace_import_resolves_at_a_ref(self, tmp_path):
        repo = self._workspace(tmp_path)
        extraction = extract_all_at_ref(repo, "HEAD")
        edges = {(e["from"], e["to"]) for e in extraction.graph["module_edges"] if e["type"] == "imports"}
        assert ("a/src/index", "b/src/x/thing") in edges
        assert extraction.environments == ({"path": "a/node_modules", "kind": "node_modules"},)
        # The scratch and the directories made for it are gone.
        assert not (repo / ".hobbes").exists()

    def test_without_the_link_the_import_is_not_drawn(self, tmp_path, monkeypatch):
        # The control: the same ref, read as an archive alone.
        repo = self._workspace(tmp_path)
        monkeypatch.setattr(graphdiff, "link_environments", lambda repo_root, scratch: [])
        extraction = extract_all_at_ref(repo, "HEAD")
        edges = {(e["from"], e["to"]) for e in extraction.graph["module_edges"] if e["type"] == "imports"}
        assert ("a/src/index", "b/src/x/thing") not in edges
