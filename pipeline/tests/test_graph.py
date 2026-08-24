"""Tests for hobbes.extract.graph — typed edges over the miniapp fixture."""

from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph, resolve_call_sites
from hobbes.extract.pysource import parse_source

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


@pytest.fixture(scope="module")
def graph():
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    return build_graph(modules, parsed)


@pytest.fixture(scope="module")
def fallback():
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    return resolve_call_sites(modules, parsed)


@pytest.fixture(scope="module")
def symbol_at(graph):
    """Look a fallback resolution up by (calling file, callee name).

    The table speaks in files and lines because that is what both
    providers agree on; these cases read better in symbol ids, so this
    translates back through the symbol records.
    """
    by_location = {(s["module"], s["line"]): s["id"] for s in graph["symbols"]}
    module_of = {n["path"]: n["id"] for n in graph["nodes"] if n.get("path")}

    def look_up(table, calling_file, name):
        for (path, _line, called), (def_file, def_line) in table.items():
            if path != calling_file or called != name:
                continue
            return by_location.get((module_of.get(def_file), def_line))
        return None

    return look_up


def module_edges(graph, edge_type):
    return {(e["from"], e["to"]) for e in graph["module_edges"] if e["type"] == edge_type}


class TestModuleEdges:
    def test_intra_repo_imports(self, graph):
        imports = module_edges(graph, "imports")
        assert ("miniapp.api", "miniapp.core") in imports
        assert ("miniapp.cli", "miniapp.core") in imports
        assert ("miniapp.core", "miniapp.util") in imports
        assert ("tests.test_core", "miniapp.core") in imports
        assert ("tests.test_core", "miniapp.util") in imports

    def test_third_party_becomes_external_nodes(self, graph):
        imports = module_edges(graph, "imports")
        assert ("miniapp.api", "ext:fastapi") in imports
        assert ("miniapp.web", "ext:flask") in imports
        kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
        assert kinds["ext:fastapi"] == "external"

    def test_stdlib_becomes_external_nodes(self, graph):
        # ADR-038 lifted C-3: stdlib is a dependency like any other —
        # `subprocess` is exactly the import a reviewer wants flagged, and
        # Go's layer already showed its stdlib, so silence here misled.
        assert any(n["id"] == "ext:os" for n in graph["nodes"])
        imports = module_edges(graph, "imports")
        assert ("miniapp.util", "ext:os") in imports

    def test_env_reads(self, graph):
        env = module_edges(graph, "env-read")
        assert ("miniapp.core", "env:MINIAPP_MODE") in env
        assert ("miniapp.util", "env:MINIAPP_HOME") in env
        kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
        assert kinds["env:MINIAPP_MODE"] == "env"

    def test_evidence_carries_file_and_line(self, graph):
        edge = next(
            e
            for e in graph["module_edges"]
            if e["from"] == "miniapp.core" and e["to"] == "miniapp.util"
        )
        # v4 (ADR-028): evidence names the lane that saw it, and the edge
        # carries the tier that says how far to trust it. Lane A resolves
        # syntactically, and says so rather than leaving it to be assumed.
        assert edge["evidence"] == [
            {"path": "src/miniapp/core.py", "line": 5, "lane": "tree-sitter"}
        ]
        assert edge["tier"] == "syntactic"


class TestCallResolutionFallback:
    """ADR-007's rules 1–4, which survive ADR-031's demotion.

    They no longer produce edges — the range join does — so they are
    tested where they now live: as the fallback table the join consults
    where the semantic provider resolved nothing. The rules themselves are
    unchanged, and so are these cases; only the shape of the answer moved.
    """

    def test_resolution_rules(self, fallback, symbol_at):
        core, api, cli = (
            "src/miniapp/core.py",
            "src/miniapp/api.py",
            "src/miniapp/cli.py",
        )
        # bare local name: top_level() instantiates Engine
        assert symbol_at(fallback, core, "Engine") == "miniapp.core.Engine"
        # self.method()
        assert symbol_at(fallback, core, "check") == "miniapp.core.Engine.check"
        # attribute on an imported repo module: util.normalize
        assert symbol_at(fallback, core, "normalize") == "miniapp.util.normalize"
        # from-imported symbol: top_level in the API handlers
        assert symbol_at(fallback, api, "top_level") == "miniapp.core.top_level"
        # dotted through `from miniapp import core`: core.top_level()
        assert symbol_at(fallback, cli, "top_level") == "miniapp.core.top_level"

    def test_unresolvable_calls_offer_no_fallback(self, fallback, symbol_at):
        # engine.run(item) is an instance-attribute call. It must not
        # resolve here either: a guess offered to the join is still a
        # guess that reaches the graph, labelled but wrong.
        assert symbol_at(fallback, "src/miniapp/core.py", "run") is None

    def test_the_table_is_keyed_by_site_not_by_edge(self, fallback):
        """Two calls to one target on different lines are two entries.

        The join matches a *site*, so collapsing them would lose the one
        the semantic provider missed.
        """
        assert all(
            isinstance(key, tuple) and len(key) == 3 for key in fallback
        )
        assert all(isinstance(line, int) for _, line, _ in fallback)

    def test_symbol_layer_records(self, graph):
        by_id = {s["id"]: s for s in graph["symbols"]}
        engine = by_id["miniapp.core.Engine"]
        assert engine["kind"] == "class"
        run = by_id["miniapp.core.Engine.run"]
        assert run["kind"] == "method"
        assert run["module"] == "miniapp.core"
        assert run["line"] < run["end_line"]


class TestDeterminism:
    def test_two_builds_identical(self):
        modules = discover_modules(FIXTURE)
        parsed = {
            m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules
        }
        assert build_graph(modules, parsed) == build_graph(modules, parsed)


class TestRelativeImports:
    def test_relative_from_resolves_inside_package(self, tmp_path):
        pkg = tmp_path / "pkg"
        (pkg / "sub").mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "helper.py").write_text("def h():\n    pass\n")
        (pkg / "sub" / "__init__.py").write_text("")
        (pkg / "sub" / "deep.py").write_text(
            "from .. import helper\nfrom ..helper import h\n\ndef use():\n    return h()\n"
        )
        modules = discover_modules(tmp_path)
        parsed = {
            m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules
        }
        graph = build_graph(modules, parsed)
        imports = {
            (e["from"], e["to"])
            for e in graph["module_edges"]
            if e["type"] == "imports"
        }
        assert ("pkg.sub.deep", "pkg.helper") in imports
        # The call through the relative import resolves in the fallback
        # table: `h()` in pkg/sub/deep.py points at pkg/helper.py's `h`.
        table = resolve_call_sites(modules, parsed)
        assert [
            target for (path, _line, name), target in table.items()
            if path == "pkg/sub/deep.py" and name == "h"
        ] == [("pkg/helper.py", 1)]
