"""Tests for the tiered folder views (DEC-014).

Graphs are built by hand in ``graph.json``'s shape; manifests are real
files in a temp repo, since language roots are found on disk.
"""

from __future__ import annotations

import json

import pytest

from hobbes.watterson import levels
from hobbes.watterson.cli import main
from hobbes.extract import SCHEMA_VERSION


def mod(path: str) -> dict:
    return {"id": path.rsplit(".", 1)[0].replace("/", "."), "kind": "module", "path": path}


def imp(a: str, b: str, line: int = 1) -> dict:
    return {"from": a, "to": b, "type": "imports", "tier": "syntactic",
            "evidence": [{"path": a.replace(".", "/") + ".py", "line": line, "lane": "tree-sitter"}]}


def graph(paths: list[str], edges: list[tuple[str, str]] = (), **extra) -> dict:
    nodes = [mod(p) for p in paths]
    return {"schema_version": SCHEMA_VERSION, "sha": "abc", "dirty": False, "nodes": nodes,
            "module_edges": [imp(a, b) for a, b in edges], "symbols": [], "symbol_edges": [], **extra}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "pyproject.toml").write_text("")
    (root / "web").mkdir()
    (root / "web" / "package.json").write_text("{}")
    return root


APP = ["app/src/app/cli.py", "app/src/app/core/a.py", "app/src/app/core/b.py", "app/src/app/util.py",
       "app/tests/test_core.py", "app/tests/fixtures/mini/x.py", "web/src/main.ts"]


def boxes(doc, view):
    return {b["label"]: b for b in doc["views"][view]["boxes"]}


class TestGrouping:
    def test_repo_view_marks_roots_and_notes_missing_links(self, repo):
        doc = levels.build(graph(APP), repo)
        top = boxes(doc, doc["root_view"])
        assert set(top) == {"app/", "web/"} and all(b.get("root") for b in top.values())
        assert doc["notes"] == [levels.ROOTS_NOTE]
        assert doc["omitted"] == {"fixture_modules": 1, "test_modules": 1}

    def test_wrapper_folders_collapse(self, repo):
        doc = levels.build(graph(APP), repo)
        assert set(boxes(doc, "app")) == {"src/app/"}
        assert set(boxes(doc, "app/src/app")) == {"cli.py", "core/", "util.py"}
        assert boxes(doc, "app/src/app")["core/"]["view"] == "app/src/app/core"

    def test_tests_count_on_the_box_they_reach_most(self, repo):
        tests = {"tests": [
            {"file": "app/tests/test_core.py", "reaches_modules": ["app.src.app.core.a", "app.src.app.util"]},
            {"file": "app/tests/test_core.py", "reaches_modules": ["app.src.app.util", "app.src.app.util"]},
            {"file": "app/tests/fixtures/mini/t.py", "reaches_modules": ["app.src.app.cli"]},
        ]}
        b = boxes(levels.build(graph(APP), repo, tests), "app/src/app")
        assert (b["core/"]["tests"], b["util.py"]["tests"], b["cli.py"]["tests"]) == (1, 1, 0)

    def test_flat_folders_group_by_shared_name_then_fold(self, repo):
        names = [f"{lang}source" for lang in ("py", "go", "rust", "java", "cpp")] + [f"f{i:02d}" for i in range(12)]
        doc = levels.build(graph([f"app/src/app/{n}.py" for n in names]), repo)
        view = doc["views"]["app/src/app"]
        assert len(view["boxes"]) <= levels.MAX_BOXES
        labels = {b["label"] for b in view["boxes"]}
        assert "*source" in labels and any(label.endswith("modules") for label in labels)
        assert set(boxes(doc, "app/src/app/*source")) == {f"{n}.py" for n in names[:5]}
        assert all(len(v["boxes"]) <= levels.MAX_BOXES for v in doc["views"].values())

    def test_a_big_suffix_group_folds_instead_of_regrouping(self, repo):
        names = [f"x{i:02d}source" for i in range(levels.MAX_BOXES + 1)] + [f"f{i:02d}" for i in range(12)]
        doc = levels.build(graph([f"app/src/app/{n}.py" for n in names]), repo)
        group = doc["views"]["app/src/app/*source"]
        assert len(group["boxes"]) == levels.MAX_BOXES and "app/src/app/*source/*source" not in doc["views"]

    def test_affix_groups(self):
        stems = {"a": "pysource", "b": "gosource", "c": "cli_ts", "d": "cli_py", "e": "other"}
        assert levels.affix_groups(stems, room=3) == [("*source", ["a", "b"]), ("cli_*", ["c", "d"])]
        assert levels.affix_groups(stems, room=5) == []


class TestEdges:
    def test_rollup_cycles_levels_and_stubs(self, repo):
        g = graph(APP, [("app.src.app.cli", "app.src.app.core.a"), ("app.src.app.cli", "app.src.app.core.b"),
                        ("app.src.app.core.a", "app.src.app.util"), ("app.src.app.util", "app.src.app.core.b")])
        g["symbols"] = [{"id": "app.src.app.cli.main", "module": "app.src.app.cli"},
                        {"id": "app.src.app.core.a.f", "module": "app.src.app.core.a"}]
        g["symbol_edges"] = [{"from": "app.src.app.cli.main", "to": "app.src.app.core.a.f", "type": "calls",
                              "evidence": [{"path": "app/src/app/cli.py", "line": 9}]}]
        doc = levels.build(g, repo)
        view = doc["views"]["app/src/app"]
        edges = {(e["from"], e["to"]): e for e in view["edges"]}
        cli_core = edges[("app.src.app.cli", "app/src/app/core")]
        assert (cli_core["imports"], cli_core["calls"]) == (2, 1)
        assert cli_core["samples"][:1] == ["app/src/app/cli.py:1"]
        assert edges[("app/src/app/core", "app.src.app.util")]["cycle"]
        assert view["cycles"] == [["app.src.app.util", "app/src/app/core"]]
        b = boxes(doc, "app/src/app")
        assert b["cli.py"]["level"] == 1 and b["core/"]["level"] == 0 == b["util.py"]["level"]
        core = doc["views"]["app/src/app/core"]
        assert core["stubs"] == [{"id": "app/src/app/cli.py", "out": {}, "in": {"calls": 1, "imports": 2}},
                                 {"id": "app/src/app/util.py", "out": {"imports": 1}, "in": {"imports": 1}}]


class TestContextAndOutputs:
    def test_context_drops_fixtures(self, repo):
        g = graph(APP, [("app.src.app.cli", "ext:requests")])
        g["module_edges"][0]["to"] = "ext:requests"
        g["nodes"] += [{"id": "tf:app/tests/fixtures/mini/infra:aws_x.y", "kind": "resource"},
                       {"id": "tf:infra:aws_s3_bucket.b", "kind": "resource"}]
        interfaces = {"cli_entry_points": [{"name": "app", "source": "app/pyproject.toml", "target": "app.cli:main"},
                                           {"name": "mini", "source": "app/tests/fixtures/mini/pyproject.toml"}],
                      "routes": [{"file": "app/src/app/cli.py", "line": 3, "method": "GET", "path": "/x",
                                  "handler": "app.cli.x"}]}
        ctx = levels.build(g, repo, interfaces=interfaces)["context"]
        assert [e["name"] for e in ctx["entries"]] == ["app", "GET /x"]
        assert ctx["externals"] == [{"id": "ext:requests", "modules": 1}]
        assert ctx["infra"] == ["tf:infra:aws_s3_bucket.b"]

    def test_text_and_mermaid(self, repo):
        doc = levels.build(graph(APP, [("app.src.app.cli", "app.src.app.util")]), repo)
        text = levels.to_text(doc, "app/src/app")
        assert text.splitlines()[0] == "app/src/app  (level 2, 3 boxes, parent app)"
        assert "  cli.py -> util.py  1 imports" in text
        assert levels.to_mermaid(doc, "app/src/app") == (
            'flowchart LR\n  b0["cli.py (1)"]\n  b1["core/ (2)"]\n  b2["util.py (1)"]\n'
            '  b0 -->|"1 imports"| b2\n')

    def test_deterministic(self, repo):
        g = graph(APP, [("app.src.app.cli", "app.src.app.util")])
        assert json.dumps(levels.build(g, repo)) == json.dumps(levels.build(g, repo))


class TestCli:
    def test_levels_command(self, repo, capsys):
        derived = repo / ".hobbes" / "derived"
        derived.mkdir(parents=True)
        (derived / "graph.json").write_text(json.dumps(graph(APP)))
        assert main(["levels", "--repo", str(repo)]) == 0
        assert "app/ root" in capsys.readouterr().out
        assert main(["levels", "--repo", str(repo), "--view", "app/src/app/", "--format", "mermaid"]) == 0
        assert capsys.readouterr().out.startswith("flowchart LR")
        assert main(["levels", "--repo", str(repo), "--view", "nope"]) == 1
        assert main(["levels", "--repo", str(repo), "--list"]) == 0
        assert "    app/src/app/core" in capsys.readouterr().out

    def test_needs_an_ingest(self, repo, capsys):
        assert main(["levels", "--repo", str(repo)]) == 1
        assert "run `hobbes ingest` first" in capsys.readouterr().err


def sym(module: str, qualname: str, kind: str = "function", line: int = 1, end: int = 5) -> dict:
    return {"id": f"{module}.{qualname}", "module": module, "name": qualname.rsplit(".", 1)[-1],
            "qualname": qualname, "kind": kind, "line": line, "end_line": end}


def call(a: str, b: str, kind: str = "calls") -> dict:
    return {"from": a, "to": b, "type": kind, "tier": "syntactic",
            "evidence": [{"path": "app/src/app/core/a.py", "line": 3, "lane": "tree-sitter"}]}


CORE = "app.src.app.core.a"
OTHER = "app.src.app.core.b"


class TestModuleViews:
    """Level 3: a module's top-level symbols (DEC-014)."""

    def doc(self, repo, symbols, edges=(), tests=None, module_edges=()):
        g = graph(APP, list(module_edges), symbols=symbols, symbol_edges=list(edges))
        return levels.build(g, repo, tests)

    def test_a_module_opens_its_symbols(self, repo):
        symbols = [sym(CORE, "A", "class", 1, 10), sym(CORE, "A.run", "method", 2, 9), sym(CORE, "helper"),
                   sym(CORE, "main"), sym(OTHER, "f")]
        edges = [call(f"{CORE}.main", f"{CORE}.A.run"), call(f"{CORE}.A.run", f"{CORE}.helper"),
                 call(f"{OTHER}.f", f"{CORE}.helper"), call(f"{CORE}.main", f"{CORE}.A", "uses")]
        doc = self.doc(repo, symbols, edges, module_edges=[(OTHER, CORE)])
        assert boxes(doc, "app/src/app/core")["a.py"]["view"] == "app/src/app/core/a.py"
        view = doc["views"]["app/src/app/core/a.py"]
        assert (view["kind"], view["parent"]) == ("module", "app/src/app/core")
        assert view["level"] == doc["views"]["app/src/app/core"]["level"] + 1
        rows = {b["label"]: b for b in view["boxes"]}
        assert set(rows) == {"A", "helper()", "main()"}
        assert (rows["A"]["kind"], rows["A"]["symbols"], rows["A"]["lines"]) == ("class", 2, 10)
        labels = {b["id"]: b["label"] for b in view["boxes"]}
        assert {(labels[e["from"]], labels[e["to"]], e.get("calls", 0), e.get("uses", 0)) for e in view["edges"]} == {
            ("main()", "A", 1, 1), ("A", "helper()", 1, 0)}
        assert (rows["main()"]["level"], rows["A"]["level"], rows["helper()"]["level"]) == (2, 1, 0)
        assert view["stubs"] == [{"id": "app/src/app/core/b.py", "out": {}, "in": {"calls": 1, "imports": 1}}]
        assert levels.describe(rows["A"]) == "class, 1 member, 10 lines"

    def test_tests_guard_from_a_file_that_imports_the_module(self, repo):
        symbols = [sym(CORE, "helper"), sym("app.tests.test_core", "test_x"), sym("app.tests.test_core", "test_y")]
        tests = {"tests": [
            {"id": "t1", "file": "app/tests/test_core.py", "symbol": "app.tests.test_core.test_x",
             "reaches": [f"{CORE}.helper"], "reaches_modules": [CORE]},
            {"id": "t2", "file": "app/tests/test_cli.py", "symbol": "app.tests.test_cli.test_y",
             "reaches": [f"{CORE}.helper"], "reaches_modules": [CORE]},
        ]}
        doc = self.doc(repo, symbols, tests=tests, module_edges=[("app.tests.test_core", CORE)])
        (helper,) = doc["views"]["app/src/app/core/a.py"]["boxes"]
        assert (helper["tests"], helper["reached_by"], helper["test_samples"]) == (1, 2, ["t1"])

    def test_many_symbols_group_at_word_boundaries_then_fold(self, repo):
        names = [f"_collect_{c}" for c in "abcde"] + [f"f{n:02d}" for n in range(20)]  # f00…: no affix
        doc = self.doc(repo, [sym(CORE, n) for n in names])
        view = doc["views"]["app/src/app/core/a.py"]
        assert len(view["boxes"]) <= levels.MAX_BOXES
        rows = {b["label"]: b for b in view["boxes"]}
        assert rows["_collect_*"]["symbols"] == 5 and rows["_collect_*"]["view"] in doc["views"]
        assert any(label.startswith("+") and label.endswith(" more") for label in rows)

    def test_a_big_suffix_group_folds_instead_of_regrouping(self, repo):
        names = [f"x{n:02d}_chain" for n in range(levels.MAX_BOXES + 1)] + [f"f{n:02d}" for n in range(20)]
        doc = self.doc(repo, [sym(CORE, n) for n in names])
        group = doc["views"]["app/src/app/core/a.py#*_chain"]
        assert len(group["boxes"]) == levels.MAX_BOXES and "app/src/app/core/a.py#*_chain/*_chain" not in doc["views"]

    def test_a_module_without_symbols_opens_nothing(self, repo):
        doc = self.doc(repo, [])
        assert "view" not in boxes(doc, "app/src/app/core")["a.py"]

    def test_affixes_at_word_boundaries(self):
        stems = {"a": "_call_chain", "b": "attr_chain", "c": "loadThing", "d": "loadOther"}
        assert levels.affix_groups(stems, 2, words=True) == [("*_chain", ["a", "b"]), ("load*", ["c", "d"])]
        assert levels.affix_groups({"a": "xchain", "b": "ychain"}, 1, words=True) == []


def site(a: str, b: str, path: str, *lines: int) -> dict:
    return {"from": a, "to": b, "type": "calls", "tier": "syntactic",
            "evidence": [{"path": path, "line": n, "lane": "tree-sitter"} for n in lines]}


CLI = "app.src.app.cli"
CLI_PY = "app/src/app/cli.py"
GO = ["app/src/app/cli.py", "app/src/app/core/a.py", "app/src/app/core/b.py", "app/src/app/util.py",
      "app/tests/test_core.py", "web/src/main.ts", "web/cmd/tool/main.go", "web/srv/server.go", "web/srv/pages.go"]


class TestFlows:
    """Level 4: flows from entry points, in call order, with the cuts marked (DEC-014)."""

    def doc(self, repo, symbols, edges=(), interfaces=None, module_edges=(), paths=GO):
        g = graph(paths, list(module_edges), symbols=symbols, symbol_edges=list(edges))
        g["nodes"] += [{"id": "web.cmd.tool.main", "kind": "module", "path": "web/cmd/tool/main.go"}]
        return levels.build(g, repo, interfaces=interfaces)

    CLI_ENTRY = {"cli_entry_points": [{"name": "app", "source": "app/pyproject.toml", "target": "app.src.app.cli:main"}]}

    def test_no_entries_no_flows(self, repo):
        doc = self.doc(repo, [sym(CLI, "main")])
        assert "entry points" not in boxes(doc, doc["root_view"])
        assert not any(v.startswith(levels.FLOWS) for v in doc["views"])

    def test_steps_follow_call_sites_and_mark_where_they_end(self, repo):
        symbols = [sym(CLI, "main"), sym(CLI, "parse"), sym(CORE, "A", "class"), sym(CORE, "A.run", "method"),
                   sym(OTHER, "leaf"), sym("app.tests.test_core", "fake")]
        edges = [site(f"{CLI}.main", f"{CORE}.A.run", CLI_PY, 20, 30), site(f"{CLI}.main", f"{CLI}.parse", CLI_PY, 10),
                 site(f"{CLI}.main", "app.tests.test_core.fake", CLI_PY, 40),
                 site(f"{CORE}.A.run", f"{OTHER}.leaf", "app/src/app/core/a.py", 3),
                 site(f"{CLI}.parse", f"{CORE}.A.run", CLI_PY, 12)]
        doc = self.doc(repo, symbols, edges, self.CLI_ENTRY)
        top = boxes(doc, doc["root_view"])["entry points"]
        assert (top["view"], top["count"]) == ("flow:", 1)
        (entry,) = doc["views"]["flow:"]["boxes"]
        assert (entry["label"], entry["view"]) == ("app", f"flow:{CLI}.main") and "resolved" not in entry
        flow = doc["views"][f"flow:{CLI}.main"]
        assert (flow["kind"], flow["parent"], flow["module"]) == ("flow", "flow:", CLI_PY)
        assert flow["title"] == f"main() in {CLI_PY}" and flow["level"] == doc["views"]["flow:"]["level"] + 1
        steps = [(b["order"], b["label"], b["line"], b["sites"], b.get("view"), b.get("end"), b.get("outside"))
                 for b in flow["boxes"]]
        assert steps == [(1, "parse()", 10, 1, f"flow:{CLI}.parse", None, None),
                         (2, "A.run()", 20, 2, f"flow:{CORE}.A.run", None, None),
                         (3, "fake()", 40, 1, None, None, "test or fixture code")]
        assert flow["edges"] == [{"from": f"{CLI}.parse", "to": f"{CORE}.A.run", "calls": 1, "samples": []}]
        (leaf,) = doc["views"][f"flow:{CORE}.A.run"]["boxes"]
        assert (leaf["end"], leaf["module"], leaf["local"]) == ("no calls recorded", "app/src/app/core/b.py", False)
        assert levels.describe(leaf) == "called at line 3, in app/src/app/core/b.py, ends: no calls recorded"
        assert doc["views"][f"flow:{CORE}.A.run"]["parent"] == f"flow:{CLI}.main"  # first reached from main
        assert f"flow:{OTHER}.leaf" not in doc["views"]

    def test_long_flows_fold_in_order(self, repo):
        names = [f"f{n:02d}" for n in range(25)]
        symbols = [sym(CLI, "main")] + [sym(CLI, n) for n in names]
        edges = [site(f"{CLI}.main", f"{CLI}.{n}", CLI_PY, 100 + i) for i, n in enumerate(names)]
        doc = self.doc(repo, symbols, edges, self.CLI_ENTRY)
        first = doc["views"][f"flow:{CLI}.main"]["boxes"]
        assert len(first) == levels.MAX_BOXES and first[-1]["label"] == "+14 more"
        assert [b["order"] for b in first[:-1]] == list(range(1, 12))
        second = doc["views"][first[-1]["view"]]
        assert second["id"] == f"flow:{CLI}.main@12" and second["title"].endswith("(from 12)")
        assert second["boxes"][0]["order"] == 12 and second["boxes"][-1]["label"] == "+3 more"
        assert all(len(v["boxes"]) <= levels.MAX_BOXES for v in doc["views"].values())

    def test_targets_the_graph_does_not_link_are_resolved_or_cut(self, repo):
        symbols = [sym("web.cmd.tool.main", "main"), sym("web.srv.pages", "Server.handlePage", "method"),
                   sym("web.srv.pages", "Server.dup", "method"), sym("web.srv.server", "Other.dup", "method"),
                   sym(CLI, "main")]
        interfaces = {
            "cli_entry_points": [{"name": "tool", "source": "web/cmd/tool/main.go", "target": "web/cmd/tool/main.go"},
                                 {"name": "gone", "source": "app/pyproject.toml", "target": "app.nowhere:main"},
                                 {"name": "fx", "source": "app/tests/fixtures/x/pyproject.toml", "target": "x:main"}],
            "routes": [{"file": "web/srv/server.go", "line": 5, "method": "GET", "path": "/page",
                        "handler": "web/srv/server.handlePage"},
                       {"file": "web/srv/server.go", "line": 6, "method": "GET", "path": "/dup",
                        "handler": "web/srv/server.dup"},
                       {"file": "web/srv/server.go", "line": 7, "method": "GET", "path": "/none", "handler": ""}]}
        doc = self.doc(repo, symbols, interfaces=interfaces)
        rows = {b["label"]: b for b in doc["views"]["flow:"]["boxes"]}
        assert set(rows) == {"tool", "gone", "GET /page", "GET /dup", "GET /none"}  # the fixture's is dropped
        assert (rows["tool"]["symbol"], rows["tool"]["resolved"]) == ("web.cmd.tool.main.main", "main() of the file (gap 5)")
        assert rows["GET /page"]["symbol"] == "web.srv.pages.Server.handlePage"
        assert rows["GET /page"]["resolved"] == "matched by name (gap 4)"
        assert rows["GET /dup"]["cut"] == "handler name shared by 2 symbols (gap 4)" and "view" not in rows["GET /dup"]
        assert rows["GET /none"]["cut"] == "handler not recorded (gap 4)"
        assert rows["gone"]["cut"] == "target not in the graph"
        assert levels.describe(rows["GET /none"]) == "(no target), cut: handler not recorded (gap 4)"
        assert doc["views"]["flow:web.cmd.tool.main.main"]["notes"] == [levels.NO_CALLS_NOTE]

    def test_argparse_clis_are_noted(self, repo):
        doc = self.doc(repo, [sym(CLI, "main")], interfaces=self.CLI_ENTRY,
                       module_edges=[(CLI, "ext:argparse")])
        (entry,) = doc["views"]["flow:"]["boxes"]
        assert entry["note"] == levels.ARGPARSE_NOTE
        assert doc["views"][f"flow:{CLI}.main"]["notes"] == [levels.ARGPARSE_NOTE, levels.NO_CALLS_NOTE]

    def test_many_entries_group_by_kind_and_leave_room_on_the_repo_view(self, repo):
        paths = [f"pkg{i:02d}/m.py" for i in range(12)] + [CLI_PY]
        routes = [{"file": CLI_PY, "line": i, "method": "GET", "path": f"/r{i:02d}", "handler": ""} for i in range(13)]
        g = graph(paths, symbols=[sym(CLI, "main")], symbol_edges=[])
        doc = levels.build(g, repo, interfaces={**self.CLI_ENTRY, "routes": routes})
        top = doc["views"][doc["root_view"]]["boxes"]
        assert len(top) == levels.MAX_BOXES and "entry points" in {b["label"] for b in top}
        assert [b["label"] for b in doc["views"]["flow:"]["boxes"]] == ["CLI entry points", "routes"]
        assert doc["views"]["flow:route"]["boxes"][-1]["view"] == "flow:route@12"

    def test_text_and_sequence_diagram(self, repo):
        symbols = [sym(CLI, "main"), sym(CORE, "run"), sym(OTHER, "leaf"), sym(CLI, "log")]
        edges = [site(f"{CLI}.main", f"{CORE}.run", CLI_PY, 5), site(f"{CLI}.main", f"{CLI}.log", CLI_PY, 9),
                 site(f"{CORE}.run", f"{OTHER}.leaf", "app/src/app/core/a.py", 2)]
        doc = self.doc(repo, symbols, edges, self.CLI_ENTRY)
        text = levels.to_text(doc, f"flow:{CLI}.main")
        assert "steps (in call order):" in text
        assert f"  1. run()  called at line 5, in app/src/app/core/a.py  -> flow:{CORE}.run" in text
        assert "  2. log()  called at line 9, ends: no calls recorded" in text
        assert levels.to_mermaid(doc, f"flow:{CLI}.main") == (
            "sequenceDiagram\n  participant p0 as cli.py\n  participant p1 as a.py\n  participant p2 as b.py\n"
            "  p0->>p1: run()\n  p1->>p2: leaf()\n  p0->>p0: log()\n")
        assert "app  app.src.app.cli:main  -> flow:" in levels.to_text(doc, "flow:")
        assert levels.to_mermaid(doc, doc["root_view"]).count("entry points (1)") == 1
        assert doc["root_view"] == ""  # a step that ends must not read the repo view (id "") as its flow
        doc["views"][""]["boxes"] *= 3
        assert "Note" not in levels.to_mermaid(doc, f"flow:{CLI}.main")
