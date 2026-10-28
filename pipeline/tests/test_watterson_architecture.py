"""Tests for the architecture views (DEC-020).

Graphs are built by hand in ``graph.json``'s shape, as in ``test_levels``;
docstrings, READMEs and manifests are real files in a temp repo, since
summaries and language roots are read from disk.
"""

from __future__ import annotations

import json

import pytest

from hobbes.watterson import architecture, levels, review
from tests.test_watterson_levels import graph, imp, mod


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    for folder in ("app/src/app/core", "app/src/app/store", "web/src"):
        (root / folder).mkdir(parents=True)
    (root / "app" / "pyproject.toml").write_text("")
    (root / "web" / "package.json").write_text("{}")
    (root / "app/src/app/store/__init__.py").write_text('"""Storage: rows on disk.\n\nMore detail."""\n')
    (root / "app/src/app/core/README.md").write_text("# Core\n\n![badge](x.svg)\nThe **domain** rules, in `a`.\n")
    (root / "app/src/app/cli.py").write_text('"""The command line."""\n')
    (root / "web/src/main.ts").write_text("// The web page's entry.\n// It mounts the app.\nimport x from 'y';\n")
    return root


PATHS = ["app/src/app/cli.py", "app/src/app/util.py", "app/src/app/core/a.py", "app/src/app/core/b.py",
         "app/src/app/store/db.py", "app/src/app/store/cache.py", "app/tests/test_a.py", "web/src/main.ts"]
EDGES = [("app.src.app.cli", "app.src.app.core.a"), ("app.src.app.cli", "app.src.app.store.cache"),
         ("app.src.app.core.a", "app.src.app.store.db"), ("app.src.app.core.b", "app.src.app.store.db"),
         ("app.src.app.store.db", "ext:sqlite3"), ("app.src.app.store.cache", "ext:sqlite3"),
         ("app.src.app.util", "ext:pathlib")]
INTERFACES = {"cli_entry_points": [{"name": "app", "target": "app.src.app.cli:main", "source": "app/pyproject.toml"}],
              "routes": []}


def doc_for(repo, paths=PATHS, edges=EDGES, interfaces=INTERFACES, **extra):
    g = graph(paths, edges, **extra)
    g["nodes"].append({"id": "ext:sqlite3", "kind": "external", "name": "sqlite3"})
    g["symbols"] = [{"id": "app.src.app.cli.main", "module": "app.src.app.cli", "name": "main", "qualname": "main",
                     "kind": "function", "line": 1, "end_line": 2}]
    return levels.build(g, repo, None, interfaces)


def boxes(doc, view):
    return {b["label"]: b for b in doc["architecture"]["views"][view]["boxes"]}


class TestSystemView:
    def test_parts_doors_and_outside_systems(self, repo):
        arch = doc_for(repo)["architecture"]
        assert arch["root"] == architecture.ROOT and arch["notes"] == []
        view = arch["views"][architecture.ROOT]
        b = boxes(doc_for(repo), architecture.ROOT)
        assert {"app/", "web/"} <= set(b) and b["app/"]["root"] and b["app/"]["view"] == "arch:app"
        assert view["notes"][0] == architecture.PARTS_NOTE
        door = next(x for x in view["boxes"] if x["kind"] == "door")
        assert door["label"] == "app" and door["commands"] == ["app"]
        assert {"from": door["id"], "to": "app", "starts": 1} in view["edges"]
        storage = b["Storage"]
        assert storage["kind"] == "outside" and storage["names"] == ["sqlite3"]
        touch = next(e for e in view["edges"] if e["to"] == "outside:storage")
        assert touch["from"] == "app" and touch["names"] == ["sqlite3"]
        assert "Files" in b and "Network" not in b

    def test_no_links_at_all_is_not_called_standalone(self, repo):
        b = boxes(doc_for(repo), architecture.ROOT)
        assert "standalone" not in b["app/"]["roles"] and "entry" in b["app/"]["roles"]


class TestComponentView:
    def test_folders_roles_layers_and_summaries(self, repo):
        doc = doc_for(repo)
        b = boxes(doc, "arch:app")
        assert set(b) == {"core/", "store/", "app/ files"}
        assert b["store/"]["summary"] == "Storage: rows on disk."
        assert b["store/"]["source"] == "app/src/app/store/__init__.py"
        assert b["core/"]["summary"] == "The domain rules, in a."  # README markup dropped
        assert b["store/"]["roles"] == ["adapter", "foundation"] and b["store/"]["touches"] == {"storage": ["sqlite3"]}
        assert b["app/ files"]["roles"] == ["entry", "coordinator"] and b["app/ files"]["files"] == ["cli.py", "util.py"]
        assert (b["app/ files"]["level"], b["core/"]["level"], b["store/"]["level"]) == (2, 1, 0)
        assert b["core/"]["code"] == "app/src/app/core"  # the code map's view of the same folder
        assert "view" not in b["core/"]  # two modules in one folder do not split further

    def test_tests_and_test_modules(self, repo):
        doc = levels.build(graph(PATHS, EDGES), repo,
                           {"tests": [{"file": "app/tests/test_a.py", "reaches_modules": ["app.src.app.core.a"]}]})
        b = boxes(doc, "arch:app")
        assert b["core/"]["tests"] == 1 and sum(x["modules"] for x in b.values()) == 6  # the test module is left out

    def test_deterministic_and_json(self, repo):
        assert json.dumps(doc_for(repo)["architecture"], sort_keys=True) == \
            json.dumps(doc_for(repo)["architecture"], sort_keys=True)


class TestLayers:
    def test_light_links_go_against_the_layers(self):
        edges = [{"from": "a", "to": "b", "calls": 9}, {"from": "b", "to": "a", "calls": 1},
                 {"from": "b", "to": "c", "calls": 3}, {"from": "c", "to": "a", "uses": 1}]
        assert architecture._against(["a", "b", "c"], edges) == {("b", "a"), ("c", "a")}

    def test_cycle_levels_ignore_the_marked_links(self, repo):
        edges = [("app.src.app.core.a", "app.src.app.store.db")] * 3 + [("app.src.app.store.cache", "app.src.app.core.b")]
        b = boxes(doc_for(repo, edges=edges), "arch:app")
        view = doc_for(repo, edges=edges)["architecture"]["views"]["arch:app"]
        against = [(e["from"], e["to"]) for e in view["edges"] if e.get("against")]
        assert against == [("app/src/app/store", "app/src/app/core")]
        assert b["core/"]["level"] > b["store/"]["level"]


class TestGrouping:
    def test_widely_used_modules_go_in_a_shared_box(self, repo):
        paths = [f"app/src/app/f{k}/m{i}.py" for k in range(4) for i in range(5)] + ["app/src/app/base/log.py"]
        edges = [(p[:-3].replace("/", "."), "app.src.app.base.log") for p in paths[:-1]]
        paths.append("web/src/main.ts")
        b = boxes(doc_for(repo, paths=paths, edges=edges, interfaces=None), "arch:app")
        assert b["shared"]["kind"] == "shared" and b["shared"]["files"] == ["app/src/app/base/log.py"]
        assert "base/" not in b and b["shared"]["roles"] == ["shared"]
        assert any(n.startswith("Shared holds") for n in doc_for(repo, paths=paths, edges=edges,
                                                                   interfaces=None)["architecture"]["views"]["arch:app"]["notes"])

    def test_a_flat_folder_breaks_into_name_groups_and_files(self, repo):
        names = [f"{lang}source" for lang in ("py", "go", "ts", "rust")] + [f"f{i:02d}" for i in range(12)]
        paths = [f"app/src/app/{n}.py" for n in names] + ["app/src/app/sub/x.py", "app/src/app/sub/y.py"]
        paths.append("web/src/main.ts")
        view = doc_for(repo, paths=paths, edges=[], interfaces=None)["architecture"]["views"]["arch:app"]
        kinds = {b["label"]: b["kind"] for b in view["boxes"]}
        assert kinds["*source"] == "prefix" and kinds["sub/"] == "folder"
        assert len(view["boxes"]) <= architecture.MAX_COMPONENTS
        assert any(k == "more" for k in kinds.values())
        assert sum(b["modules"] for b in view["boxes"]) == len(paths) - 1

    def test_folded_files_keep_the_most_linked(self, repo):
        names = [f"f{i:02d}" for i in range(14)]
        paths = [f"app/src/app/{n}.py" for n in names] + ["app/src/app/sub/x.py", "app/src/app/sub/y.py",
                                                           "web/src/main.ts"]
        edges = [("app.src.app.f13", f"app.src.app.f{i:02d}") for i in range(3)]
        b = boxes(doc_for(repo, paths=paths, edges=edges, interfaces=None), "arch:app")
        assert {"f13.py", "f00.py", "f01.py", "f02.py"} <= set(b)  # linked first, not alphabetical

    def test_big_files_boxes_open_a_view_of_their_files(self, repo):
        paths = [f"app/src/app/{d}/m.py" for d in ("a", "b", "c", "d")] + [f"app/src/app/f{i}.py" for i in range(5)]
        paths.append("web/src/main.ts")
        doc = doc_for(repo, paths=paths, edges=[], interfaces=None)
        b = boxes(doc, "arch:app")
        assert b["app/ files"]["view"] == "arch:app/src/app/*"
        files = boxes(doc, "arch:app/src/app/*")
        assert set(files) == {f"f{i}.py" for i in range(5)}


class TestSummaries:
    def test_paragraphs_and_comments(self):
        assert architecture._paragraph("# T\n\n[![b](u)](l)\nFirst line\nsecond.\n\nNext.") == "First line second."
        go = "// Copyright x\n\n// Package web serves pages.\n// Two lines.\npackage web\n"
        assert architecture._leading_comment(go, go=True) == "Package web serves pages.\nTwo lines."
        assert architecture._leading_comment("/**\n * Entry.\n */\nexport {}", go=False) == "Entry."
        assert architecture._leading_comment("import x from 'y'\n", go=False) is None
        assert architecture._clip("One sentence here. Two three four five", 24) == "One sentence here."
        assert architecture._clip("No sentence ends in this one", 12) == "No sentence…"

    def test_ts_entry_comment(self, repo):
        b = boxes(doc_for(repo), "arch:")
        assert b["web/"]["summary"] == "The web page's entry. It mounts the app."
        assert b["web/"]["source"] == "web/src/main.ts"

    def test_stale_summaries_are_noted(self, repo, monkeypatch):
        monkeypatch.setattr(architecture, "_head", lambda repo: "def4567890")
        assert doc_for(repo)["architecture"]["notes"] == [architecture.STALE_NOTE.format(head="def4567", sha="abc")]


def test_outside_classes_and_libraries():
    assert architecture.outside_class("subprocess") == "process"
    assert architecture.outside_class("net/http") == "network" and architecture.outside_class("node:fs") == "files"
    assert architecture.outside_class("google.golang.org/grpc/codes") == "network"
    assert architecture.outside_class("json") is None
    assert not architecture.is_library("json") and not architecture.is_library("net/http")
    assert architecture.is_library("tree_sitter") and architecture.is_library("github.com/x/y")
    assert not architecture.is_library("node:path") and architecture.is_library("@xyflow/react")


def test_the_page_embeds_the_architecture_without_members(repo):
    data = review.page_data(doc_for(repo), repo, generated=0)
    arch = data["architecture"]
    assert arch["root"] == architecture.ROOT
    assert all("members" not in b for v in arch["views"].values() for b in v["boxes"])
    assert mod("x.py")["kind"] == "module" and imp("a", "b")["type"] == "imports"  # helpers shared with test_levels


def sym(module, qualname, line=1):
    return {"id": f"{module}.{qualname}", "module": module, "name": qualname, "qualname": qualname,
            "kind": "function", "line": line, "end_line": line + 5}


def edge(a, b, path, line, kind="calls"):
    return {"from": a, "to": b, "type": kind, "tier": "semantic", "evidence": [{"path": path, "line": line, "lane": "scip"}]}


CLI_M, PLAN, EXEC, DB, CACHE = ("app.src.app.cli", "app.src.app.core.plan.a", "app.src.app.core.exec.b",
                                "app.src.app.store.db", "app.src.app.store.cache")
PIPE_PATHS = ["app/src/app/cli.py", "app/src/app/core/plan/a.py", "app/src/app/core/exec/b.py",
              "app/src/app/store/db.py", "app/src/app/store/cache.py", "web/src/main.ts"]
PIPE_PATHS += [f"app/src/app/f{i}/m.py" for i in range(6)]  # a full view, so core/ stays one component


class TestPipelines:
    """Slice 2: a pipeline view per entry point, with dispatchers' handlers."""

    def doc(self, repo, refs=("h1", "h2", "h3")):
        g = graph(PIPE_PATHS)
        g["symbols"] = [sym(CLI_M, "main"), sym(CLI_M, "h1", 20), sym(CLI_M, "h2", 30), sym(CLI_M, "h3", 40),
                        sym(PLAN, "run"), sym(EXEC, "step"), sym(DB, "save"), sym(CACHE, "get")]
        g["symbol_edges"] = [
            edge(f"{CLI_M}.main", f"{PLAN}.run", "app/src/app/cli.py", 5),
            edge(f"{PLAN}.run", f"{EXEC}.step", "app/src/app/core/plan/a.py", 2),
            edge(f"{EXEC}.step", f"{CACHE}.get", "app/src/app/core/exec/b.py", 2),
            edge(f"{CACHE}.get", f"{PLAN}.run", "app/src/app/store/cache.py", 2),
            edge(f"{CLI_M}.h1", f"{DB}.save", "app/src/app/cli.py", 21),
        ] + [edge(f"{CLI_M}.main", f"{CLI_M}.{h}", "app/src/app/cli.py", 7 + i, "uses") for i, h in enumerate(refs)]
        return levels.build(g, repo, None, INTERFACES)["architecture"]["views"]

    def test_the_door_opens_the_parts_entry_points(self, repo):
        views = self.doc(repo)
        door = next(b for b in views[architecture.ROOT]["boxes"] if b["kind"] == "door")
        assert door["view"] == "arch:runs:app"
        (entry,) = views["arch:runs:app"]["boxes"]
        assert views["arch:runs:app"]["kind"] == "entries" and entry["view"] == f"arch:run:{CLI_M}.main"

    def test_steps_in_first_reach_order_with_calls_between(self, repo):
        view = self.doc(repo)[f"arch:run:{CLI_M}.main"]
        steps = sorted((b for b in view["boxes"] if "order" in b), key=lambda b: b["order"])
        assert [b["label"] for b in steps] == ["cli.py", "core/", "store/"]
        assert steps[1]["via"] == {"from": "main()", "to": "run()", "at": "app/src/app/cli.py:5"}
        assert steps[1]["reached"] == 2 and [f["label"] for f in steps[1]["functions"]] == ["run()", "step()"]
        label = {b["id"]: b["label"] for b in view["boxes"]}
        links = {(label[e["from"]], label[e["to"]]): e for e in view["edges"] if "calls" in e}
        assert set(links) == {("cli.py", "core/"), ("core/", "store/"), ("store/", "core/")}
        assert links[("store/", "core/")].get("against") and not links[("core/", "store/")].get("against")
        assert view["start"] == {"label": "main()", "path": "app/src/app/cli.py", "line": 1}

    def test_a_handler_table_is_a_dispatcher(self, repo):
        views = self.doc(repo)
        view = views[f"arch:run:{CLI_M}.main"]
        dispatch = next(b for b in view["boxes"] if b["kind"] == "dispatch")
        assert dispatch["handlers"] == ["h1()", "h2()", "h3()"] and dispatch["view"] == f"arch:dispatch:{CLI_M}.main"
        assert any(n.startswith("main() references 3 functions") for n in view["notes"])
        handlers = views[f"arch:dispatch:{CLI_M}.main"]["boxes"]
        assert [b["label"] for b in handlers] == ["h1()", "h2()", "h3()"]
        h1 = views[handlers[0]["view"]]
        assert [b["label"] for b in sorted((b for b in h1["boxes"] if "order" in b), key=lambda b: b["order"])] == \
            ["cli.py", "store/"]

    def test_fewer_references_are_followed_like_calls(self, repo):
        view = self.doc(repo, refs=("h1",))[f"arch:run:{CLI_M}.main"]
        assert not any(b["kind"] == "dispatch" for b in view["boxes"])
        label = {b["id"]: b["label"] for b in view["boxes"]}
        to_store = next(e for e in view["edges"] if label[e["from"]] == "cli.py" and label[e["to"]] == "store/")
        assert to_store["calls"] == 1 and "refs" not in to_store  # h1() calls store; main() -> h1() stays in cli.py
        cli = next(b for b in view["boxes"] if b.get("label") == "cli.py")
        assert [f["label"] for f in cli["functions"]] == ["main()", "h1()"]  # h1() reached by reference

    def test_a_step_with_components_opens_the_flow_inside_it(self, repo):
        views = self.doc(repo)
        core = next(b for b in views[f"arch:run:{CLI_M}.main"]["boxes"] if b.get("label") == "core/")
        assert core["component"] == "arch:app/src/app/core"
        inside = views[core["view"]]
        assert inside["inside"] == "core/" and inside["title"] == "app in core/"
        assert [b["label"] for b in sorted((b for b in inside["boxes"] if "order" in b), key=lambda b: b["order"])] == \
            ["plan/", "exec/"]
