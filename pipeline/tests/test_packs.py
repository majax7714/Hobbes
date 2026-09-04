"""Enrichment packs, and V2.M4's exit criterion (ADR-035).

The criterion is a property, so it is a test rather than a paragraph:
**removing a pack removes exactly its own contribution and nothing else,
and putting it back reproduces the artifact byte-for-byte.** Everything
here that is not that property exists to make that property meaningful —
a pack that contributed nothing would satisfy it trivially, so each pack
is also checked to produce what it is for.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.gosource import extract_go
from hobbes.extract.packs import (
    REGISTRY,
    Pack,
    PackContext,
    PackRefusal,
    PackResult,
    run_packs,
)
from hobbes.extract.packs import cli_python, http_go, http_python, http_ts, terraform
from hobbes.extract.schema import TIERS

MINIAPP = Path(__file__).parent / "fixtures" / "miniapp"
MINITS = Path(__file__).parent / "fixtures" / "minits"
MINIGO = Path(__file__).parent / "fixtures" / "minigo"
HELPER = Path(__file__).parents[2] / "tsextract" / "extract.mjs"


def helper_available() -> bool:
    """Same guard test_tssource.py uses: the TS helper needs its deps."""
    return (
        shutil.which("node") is not None
        and (HELPER.parent / "node_modules" / "ts-morph").is_dir()
    )


def _context(repo_root: Path, ts=None) -> PackContext:
    """A PackContext built the way extract_repo builds one."""
    from hobbes.extract.discover import discover_modules
    from hobbes.extract.pysource import parse_source

    modules = discover_modules(repo_root)
    parsed = {
        m.id: parse_source((repo_root / m.path).read_bytes()) for m in modules
    }
    return PackContext(repo_root=repo_root, modules=modules, parsed=parsed, ts=ts)


def _artifacts(repo_root: Path, packs) -> dict:
    extraction = extract_repo(repo_root, packs=packs)
    return {
        "graph": extraction.graph,
        "tests": extraction.tests,
        "interfaces": extraction.interfaces,
    }


class TestRegistry:
    """The registry's own invariants — cheap, and each has a failure mode."""

    def test_every_pack_declares_a_known_tier(self):
        # §3.5: packs declare the tier their edges carry. An unknown tier
        # would reach graph.json and a consumer would trust an edge it
        # cannot classify.
        for pack in REGISTRY:
            assert pack.tier in TIERS, pack.name

    def test_pack_names_are_unique(self):
        # `packs` in graph.json is a provenance list; duplicate names would
        # make a contribution unattributable, which is the whole point.
        names = [pack.name for pack in REGISTRY]
        assert len(names) == len(set(names))

    def test_registry_holds_the_packs_in_a_stable_order(self):
        # Order fixes `ran` and therefore the artifact, so it is asserted
        # rather than assumed. http-go joined at V2.M5 — a new language's
        # framework knowledge was a new module and this line, which is
        # what P7 has to mean in practice. The three C-14 CLI packs
        # appended (not slotted beside cli-python) so existing artifacts'
        # `ran` order is preserved.
        assert [pack.name for pack in REGISTRY] == [
            "http-python",
            "cli-python",
            "http-ts",
            "http-go",
            "terraform",
            "cli-ts",
            "cli-go",
            "cli-rust",
        ]


class TestExitCriterion:
    """V2.M4's exit: a pack is exactly and only its own contribution."""

    @pytest.mark.parametrize(
        "pack",
        [http_python.PACK, cli_python.PACK, terraform.PACK],
        ids=lambda p: p.name,
    )
    def test_removing_a_pack_removes_exactly_its_contribution(self, pack: Pack):
        without = tuple(p for p in REGISTRY if p is not pack)
        full_docs = _artifacts(MINIAPP, REGISTRY)
        less_docs = _artifacts(MINIAPP, without)

        # What the pack itself claims to contribute, asked directly.
        contribution = pack.run(_context(MINIAPP))

        # 1. The pack ran in one and not the other.
        assert pack.name in full_docs["graph"]["packs"]
        assert pack.name not in less_docs["graph"]["packs"]

        # 2. Nothing appears that the pack's absence should not have caused.
        #    Removal must never *add* an element.
        full_nodes = {n["id"] for n in full_docs["graph"]["nodes"]}
        less_nodes = {n["id"] for n in less_docs["graph"]["nodes"]}
        assert not (less_nodes - full_nodes)

        # 3. Every node that disappeared was one the pack produced. Nodes
        #    it shares with another producer (env:VAR that Python also
        #    reads) correctly survive, which is why this is a subset check
        #    and not an equality.
        produced_nodes = {n["id"] for n in contribution.nodes}
        assert (full_nodes - less_nodes) <= produced_nodes

        # 4. Same for edges, keyed the way the graph keys them.
        def edge_keys(docs):
            return {
                (e["from"], e["to"], e["type"])
                for e in docs["graph"]["module_edges"]
            }

        produced_edges = {
            (e["from"], e["to"], e["type"]) for e in contribution.module_edges
        }
        assert not (edge_keys(less_docs) - edge_keys(full_docs))
        assert (edge_keys(full_docs) - edge_keys(less_docs)) <= produced_edges

        # 5. Interface rows are wholly owned — no other producer shares them.
        for field, produced in (
            ("routes", contribution.routes),
            ("cli_entry_points", contribution.cli_entry_points),
        ):
            full_rows = full_docs["interfaces"][field]
            less_rows = less_docs["interfaces"][field]
            assert [r for r in full_rows if r not in less_rows] == list(produced)

        # 6. Everything that survived is *unchanged*. A pack that mutated a
        #    shared edge's evidence in passing would satisfy every check
        #    above and still be wrong.
        surviving = {
            (e["from"], e["to"], e["type"]): e
            for e in full_docs["graph"]["module_edges"]
        }
        for edge in less_docs["graph"]["module_edges"]:
            key = (edge["from"], edge["to"], edge["type"])
            assert surviving[key] == edge

    @pytest.mark.parametrize(
        "pack",
        [http_python.PACK, cli_python.PACK, terraform.PACK],
        ids=lambda p: p.name,
    )
    def test_adding_a_pack_back_restores_the_artifact_byte_for_byte(self, pack):
        # The second half of the criterion, and the one that catches a
        # non-deterministic pack: removal and restoration must be a
        # round trip, not an approximation.
        before = json.dumps(_artifacts(MINIAPP, REGISTRY), sort_keys=True)
        _ = _artifacts(MINIAPP, tuple(p for p in REGISTRY if p is not pack))
        after = json.dumps(_artifacts(MINIAPP, REGISTRY), sort_keys=True)
        assert before == after

    def test_removing_http_go_removes_exactly_the_go_routes(self):
        # V2.M4's criterion applied to V2.M5's pack, on a Go repo — the
        # criterion has to hold for packs added later, or it was a property
        # of the four originals rather than of the interface.
        full = _artifacts(MINIGO, REGISTRY)
        without = _artifacts(MINIGO, tuple(p for p in REGISTRY if p is not http_go.PACK))

        assert "http-go" in full["graph"]["packs"]
        assert "http-go" not in without["graph"]["packs"]
        assert full["interfaces"]["routes"]
        assert without["interfaces"]["routes"] == []
        # The graph is the lanes', not the pack's: nothing else moves.
        assert full["graph"]["nodes"] == without["graph"]["nodes"]
        assert full["graph"]["module_edges"] == without["graph"]["module_edges"]
        assert full["tests"] == without["tests"]

        restored = json.dumps(_artifacts(MINIGO, REGISTRY), sort_keys=True)
        assert restored == json.dumps(full, sort_keys=True)

    def test_no_packs_at_all_still_yields_a_graph(self):
        # P6 at the pack tier: packs enrich, they do not constitute. A repo
        # extracted with an empty registry keeps its modules, imports and
        # symbol edges, and simply knows nothing about frameworks.
        docs = _artifacts(MINIAPP, ())
        assert docs["graph"]["packs"] == []
        assert docs["graph"]["nodes"]
        assert docs["graph"]["module_edges"]
        assert docs["interfaces"]["routes"] == []
        assert docs["interfaces"]["cli_entry_points"] == []
        # ...and claims no HCL, because the pack that proves it never ran.
        assert "hcl" not in docs["graph"]["languages"]


class TestPackContributions:
    """Each pack produces the thing it exists for."""

    def test_http_python_finds_decorator_routes(self):
        result = http_python.PACK.run(_context(MINIAPP))
        assert result.routes
        assert {r["framework"] for r in result.routes} <= {"fastapi", "flask", "unknown"}

    def test_http_python_applies_only_when_a_framework_is_imported(self, tmp_path):
        (tmp_path / "plain.py").write_text("import os\n\ndef f():\n    return os\n")
        assert not http_python.PACK.applies(_context(tmp_path))
        (tmp_path / "api.py").write_text("from fastapi import FastAPI\n")
        assert http_python.PACK.applies(_context(tmp_path))

    def test_cli_python_reads_every_pyproject_not_just_the_root(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "root"\n[project.scripts]\nroot-cmd = "root:main"\n'
        )
        nested = tmp_path / "packages" / "inner"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text(
            '[project]\nname = "inner"\n[project.scripts]\ninner-cmd = "inner:main"\n'
        )
        names = {e["name"] for e in cli_python.PACK.run(_context(tmp_path)).cli_entry_points}
        assert names == {"root-cmd", "inner-cmd"}

    def test_terraform_contributes_hcl_and_tf_nodes(self):
        result = terraform.PACK.run(_context(MINIAPP))
        assert result.languages == ["hcl"]
        assert any(n["id"].startswith("tf:") for n in result.nodes)

    def test_terraform_does_not_apply_without_tf_files(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert not terraform.PACK.applies(_context(tmp_path))

    def test_http_ts_claims_the_helper_rows_rather_than_re_deriving(self):
        # The one pack whose detection lives in the Node helper (ADR-035):
        # it adopts the rows verbatim, so what the helper found is exactly
        # what reaches interfaces.json.
        rows = [{"framework": "express", "method": "GET", "path": "/x",
                 "handler": "h", "file": "src/server.js", "line": 3}]
        ctx = PackContext(repo_root=MINITS, modules=[], parsed={}, ts={"routes": rows})
        assert http_ts.PACK.applies(ctx)
        assert http_ts.PACK.run(ctx).routes == rows

    def test_http_ts_does_not_apply_without_a_ts_layer(self):
        assert not http_ts.PACK.applies(_context(MINIAPP))
        assert not http_ts.PACK.applies(
            PackContext(repo_root=MINITS, modules=[], parsed={}, ts={"routes": []})
        )

    def test_http_go_reads_net_http_registrations(self):
        # V2.M5's pack, and the test of V2.M4's interface: a new language's
        # framework knowledge should be a module and a registry line.
        ctx = PackContext(
            repo_root=MINIGO, modules=[], parsed={}, go=extract_go(MINIGO)
        )
        assert http_go.PACK.applies(ctx)
        routes = {(r["path"], r["handler"]) for r in http_go.PACK.run(ctx).routes}
        assert routes == {
            ("/check", "cmd/mini/main.handleCheck"),
            ("/home", "cmd/mini/main.handleHome"),
        }

    def test_http_go_reports_method_any_rather_than_guessing(self):
        # net/http dispatches on method *inside* the handler, so claiming
        # GET for a handler that also serves POST would be a confident
        # wrong answer.
        ctx = PackContext(
            repo_root=MINIGO, modules=[], parsed={}, go=extract_go(MINIGO)
        )
        assert {r["method"] for r in http_go.PACK.run(ctx).routes} == {"ANY"}

    def test_http_go_reads_a_go_1_22_method_pattern(self):
        route = http_go._route_from(
            {"args": [{"kind": "string", "value": "GET /items/{id}"},
                      {"kind": "ident", "value": "listItems"}]}
        )
        assert route == {
            "method": "GET",
            "path": "/items/{id}",
            "handler": "listItems",
        }

    def test_http_go_skips_a_computed_pattern(self):
        # C-5 again: a route whose path is not statically visible is absent,
        # never guessed at.
        assert http_go._route_from({"args": [{"kind": "ident", "value": "prefix"}]}) is None

    def test_http_python_reports_a_declined_computed_route(self, tmp_path):
        # C-5 (surfaced): the route stays absent — a guessed path is a
        # false interface — but the sighting is a degradation record.
        (tmp_path / "api.py").write_text(
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            'PREFIX = "/items"\n'
            "@app.get(f\"{PREFIX}/all\")\n"
            "def listing():\n"
            "    return []\n"
            '@app.get("/ok")\n'
            "def ok():\n"
            "    return []\n"
        )
        result = http_python.PACK.run(_context(tmp_path))
        assert [r["path"] for r in result.routes] == ["/ok"]
        assert len(result.errors) == 1
        assert result.errors[0]["stage"] == "http-python"
        assert "api.py:4" in result.errors[0]["message"]
        assert "C-5" in result.errors[0]["message"]

    def test_http_python_ignores_route_shaped_decorators_off_framework(self, tmp_path):
        # @x.get on an arbitrary object in a module importing no framework
        # must not produce a phantom decline record.
        (tmp_path / "plain.py").write_text(
            "import functools\n"
            "class Reg:\n"
            "    def get(self, *a, **k):\n"
            "        return lambda f: f\n"
            "reg = Reg()\n"
            "@reg.get()\n"
            "def f():\n"
            "    return 1\n"
        )
        result = http_python.PACK.run(_context(tmp_path))
        assert result.errors == []

    def test_http_ts_claims_declined_routes_as_its_records(self):
        # A repo whose every route path is computed still applies, so its
        # C-5 records exist — and they are the pack's contribution, gone
        # with it.
        ts = {
            "routes": [],
            "files": [
                {
                    "path": "src/server.js",
                    "routes_declined": [{"framework": "express", "line": 7}],
                }
            ],
        }
        ctx = PackContext(repo_root=MINITS, modules=[], parsed={}, ts=ts)
        assert http_ts.PACK.applies(ctx)
        errors = http_ts.PACK.run(ctx).errors
        assert len(errors) == 1
        assert errors[0]["stage"] == "http-ts"
        assert "src/server.js:7" in errors[0]["message"]
        assert "C-5" in errors[0]["message"]

    def test_http_go_reports_a_declined_computed_pattern(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/x\n")
        (tmp_path / "main.go").write_text(
            "package main\n\n"
            'import "net/http"\n\n'
            "func handler(w http.ResponseWriter, r *http.Request) {}\n\n"
            "func main() {\n"
            "\thttp.HandleFunc(pattern, handler)\n"
            '\thttp.HandleFunc("/ok", handler)\n'
            "}\n"
        )
        result = http_go.PACK.run(
            PackContext(repo_root=tmp_path, modules=[], parsed={}, go=extract_go(tmp_path))
        )
        assert [r["path"] for r in result.routes] == ["/ok"]
        assert len(result.errors) == 1
        assert result.errors[0]["stage"] == "http-go"
        assert "main.go:8" in result.errors[0]["message"]

    def test_http_go_judged_non_path_strings_are_not_declined(self, tmp_path):
        # A literal that is not a path (a host pattern, a middleware name)
        # was seen and judged — recording it as computed would be false.
        (tmp_path / "go.mod").write_text("module example.com/x\n")
        (tmp_path / "main.go").write_text(
            "package main\n\n"
            'import "net/http"\n\n'
            "func main() {\n"
            '\thttp.Handle("example.com/", nil)\n'
            "}\n"
        )
        result = http_go.PACK.run(
            PackContext(repo_root=tmp_path, modules=[], parsed={}, go=extract_go(tmp_path))
        )
        assert result.routes == [] and result.errors == []

    def test_http_go_ignores_a_handle_from_another_package(self, tmp_path):
        """C-78 (lifted): quic-go's `windows.Handle(fd)` — a conversion to
        `x/sys/windows.Handle` in a file importing no `net/http` — produced
        four C-5 records about a syscall. The pack applies because *some*
        file imports `net/http`; the registration test is per call."""
        (tmp_path / "go.mod").write_text("module example.com/x\n")
        (tmp_path / "main.go").write_text(
            "package main\n\n"
            'import "net/http"\n\n'
            "func main() {\n"
            '\thttp.HandleFunc("/ok", nil)\n'
            "}\n"
        )
        (tmp_path / "sys_windows.go").write_text(
            "package main\n\n"
            'import "golang.org/x/sys/windows"\n\n'
            "func fd(fd uintptr) windows.Handle {\n"
            "\treturn windows.Handle(fd)\n"
            "}\n"
        )
        (tmp_path / "other.go").write_text(
            "package main\n\n"
            'import (\n\t"net/http"\n\t"golang.org/x/sys/windows"\n)\n\n'
            "type Handle int\n\n"
            "func mixed(mux *http.ServeMux, fd uintptr, x int) {\n"
            "\t_ = windows.Handle(fd)\n"
            "\t_ = Handle(x)\n"
            '\tmux.Handle("/mux", nil)\n'
            "}\n"
        )
        result = http_go.PACK.run(
            PackContext(repo_root=tmp_path, modules=[], parsed={}, go=extract_go(tmp_path))
        )
        assert sorted(r["path"] for r in result.routes) == ["/mux", "/ok"]
        assert result.errors == []

    def test_http_go_does_not_apply_without_net_http(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/x\n")
        (tmp_path / "main.go").write_text('package main\n\nimport "fmt"\n')
        ctx = PackContext(
            repo_root=tmp_path, modules=[], parsed={}, go=extract_go(tmp_path)
        )
        assert not http_go.PACK.applies(ctx)


class TestDegradation:
    """A pack failing is a degraded ingest, never a failed one (P6)."""

    def test_a_raising_pack_is_reported_and_the_rest_still_run(self):
        def boom(ctx):
            raise RuntimeError("no framework here")

        broken = Pack(
            name="broken", tier="syntactic", applies=lambda ctx: True, run=boom
        )
        out = run_packs(_context(MINIAPP), (broken, terraform.PACK))

        assert out.ran == ["terraform"]  # the survivor still ran
        assert len(out.errors) == 1
        error = out.errors[0]
        assert error["stage"] == "pack:broken"
        assert "no framework here" in error["message"]

    def test_a_raising_applies_is_caught_too(self):
        def boom(ctx):
            raise OSError("cannot stat")

        broken = Pack(
            name="broken-detect", tier="syntactic", applies=boom, run=lambda c: PackResult()
        )
        out = run_packs(_context(MINIAPP), (broken,))
        assert out.ran == []
        assert out.errors[0]["stage"] == "pack:broken-detect"

    def test_a_pack_failure_reaches_extraction_errors(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        broken = Pack(
            name="broken",
            tier="syntactic",
            applies=lambda ctx: True,
            run=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        graph = extract_repo(tmp_path, packs=(broken,)).graph
        stages = {e["stage"] for e in graph["extraction_errors"]}
        assert "pack:broken" in stages

    def test_a_refusal_is_re_raised_rather_than_degraded(self):
        # The regression this test exists for: wrapping packs in a blanket
        # `except Exception` turned the .tfstate refusal (I-1, ADR-011)
        # into a warning, and `ingest --tf-plan prod.tfstate` started
        # succeeding. A refusal is not a breakage.
        refusing = Pack(
            name="refuser",
            tier="syntactic",
            applies=lambda ctx: True,
            run=lambda ctx: (_ for _ in ()).throw(PackRefusal("declined")),
        )
        with pytest.raises(PackRefusal, match="declined"):
            run_packs(_context(MINIAPP), (refusing,))

    def test_a_tfstate_plan_is_still_refused_through_the_pack(self, tmp_path):
        state = tmp_path / "prod.tfstate"
        state.write_text("{}")
        ctx = PackContext(
            repo_root=MINIAPP, modules=[], parsed={}, tf_plan=state
        )
        with pytest.raises(PackRefusal, match="refusing anything that looks like"):
            run_packs(ctx, (terraform.PACK,))

    def test_extraction_errors_are_sorted_not_pipeline_ordered(self, tmp_path):
        # ADR-035: which pass reported first is an accident of pipeline
        # order, and an artifact that changes with it is not reproducible.
        (tmp_path / "app.py").write_text("x = 1\n")
        packs = tuple(
            Pack(
                name=name,
                tier="syntactic",
                applies=lambda ctx: True,
                run=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            for name in ("zeta", "alpha", "mid")
        )
        errors = extract_repo(tmp_path, packs=packs).graph["extraction_errors"]
        keys = [(e["stage"], e["path"], e["message"]) for e in errors]
        assert keys == sorted(keys)


class TestProvenance:
    """`packs` in graph.json is what makes a contribution attributable."""

    def test_graph_records_which_packs_ran(self):
        graph = extract_repo(MINIAPP).graph
        assert graph["packs"] == ["http-python", "cli-python", "terraform"]

    def test_packs_that_do_not_apply_are_absent_from_the_list(self):
        # miniapp has no TypeScript, so http-ts must not claim to have run.
        assert "http-ts" not in extract_repo(MINIAPP).graph["packs"]


@pytest.mark.skipif(not helper_available(), reason="node/ts-morph not installed")
class TestTypeScriptPackEndToEnd:
    """http-ts over the real helper — the rows really do come from a pack."""

    def test_removing_http_ts_removes_exactly_the_ts_routes(self):
        full = _artifacts(MINITS, REGISTRY)
        without = _artifacts(MINITS, tuple(p for p in REGISTRY if p is not http_ts.PACK))

        assert "http-ts" in full["graph"]["packs"]
        assert full["interfaces"]["routes"]
        assert without["interfaces"]["routes"] == []
        # Nothing else moved: the graph itself is the TS lane's, not the pack's.
        assert full["graph"]["nodes"] == without["graph"]["nodes"]
        assert full["graph"]["module_edges"] == without["graph"]["module_edges"]


class TestCliPacks:
    """The three C-14 packs: every language's binaries, not just Python's."""

    def test_cli_ts_reads_bin_maps_and_bin_strings(self, tmp_path):
        from hobbes.extract.packs import cli_ts

        (tmp_path / "package.json").write_text(
            '{"name": "@scope/tool", "bin": "./cli.js"}'
        )
        nested = tmp_path / "packages" / "other"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text(
            '{"name": "other", "bin": {"other-cli": "dist/main.js"}}'
        )
        ctx = _context(tmp_path)
        assert cli_ts.PACK.applies(ctx)
        entries = cli_ts.PACK.run(ctx).cli_entry_points
        assert entries == [
            {"name": "tool", "target": "cli.js", "source": "package.json"},
            {
                "name": "other-cli",
                "target": "packages/other/dist/main.js",
                "source": "packages/other/package.json",
            },
        ]

    def test_cli_ts_skips_node_modules(self, tmp_path):
        from hobbes.extract.packs import cli_ts

        vendored = tmp_path / "node_modules" / "dep"
        vendored.mkdir(parents=True)
        (vendored / "package.json").write_text('{"name": "dep", "bin": "x.js"}')
        assert not cli_ts.PACK.applies(_context(tmp_path))

    def test_cli_go_finds_main_packages(self):
        from hobbes.extract.packs import cli_go

        go = extract_go(MINIGO)
        ctx = PackContext(repo_root=MINIGO, modules=[], parsed={}, go=go)
        assert cli_go.PACK.applies(ctx)
        entries = cli_go.PACK.run(ctx).cli_entry_points
        # `go build` names a binary after its package directory.
        assert all(e["target"].endswith(".go") for e in entries)
        assert any(e["name"] != "main" for e in entries) or entries

    def test_cli_go_requires_func_main_not_just_package_main(self, tmp_path):
        from hobbes.extract.packs import cli_go

        (tmp_path / "cmd" / "tool").mkdir(parents=True)
        (tmp_path / "cmd" / "tool" / "main.go").write_text(
            "package main\n\nfunc main() {}\n"
        )
        # package main split across files: helpers.go has no func main and
        # must not become a second entry point.
        (tmp_path / "cmd" / "tool" / "helpers.go").write_text(
            "package main\n\nfunc helper() {}\n"
        )
        go = extract_go(tmp_path)
        ctx = PackContext(repo_root=tmp_path, modules=[], parsed={}, go=go)
        assert cli_go.PACK.run(ctx).cli_entry_points == [
            {"name": "tool", "target": "cmd/tool/main.go", "source": "cmd/tool/main.go"}
        ]

    def test_cli_rust_reads_all_three_binary_shapes(self, tmp_path):
        from hobbes.extract.packs import cli_rust
        from hobbes.extract.rustsource import extract_rust

        (tmp_path / "src" / "bin" / "nested").mkdir(parents=True)
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "mytool"\n\n[[bin]]\nname = "explicit"\npath = "src/custom.rs"\n'
        )
        (tmp_path / "src" / "main.rs").write_text("fn main() {}\n")
        (tmp_path / "src" / "custom.rs").write_text("fn main() {}\n")
        (tmp_path / "src" / "bin" / "extra.rs").write_text("fn main() {}\n")
        (tmp_path / "src" / "bin" / "nested" / "main.rs").write_text("fn main() {}\n")
        rust = extract_rust(tmp_path)
        ctx = PackContext(repo_root=tmp_path, modules=[], parsed={}, rust=rust)
        assert cli_rust.PACK.applies(ctx)
        entries = cli_rust.PACK.run(ctx).cli_entry_points
        assert {(e["name"], e["target"]) for e in entries} == {
            ("explicit", "src/custom.rs"),
            ("mytool", "src/main.rs"),
            ("extra", "src/bin/extra.rs"),
            ("nested", "src/bin/nested/main.rs"),
        }

    def test_cli_packs_do_not_apply_off_their_language(self, tmp_path):
        from hobbes.extract.packs import cli_go, cli_rust, cli_ts

        (tmp_path / "app.py").write_text("x = 1\n")
        ctx = _context(tmp_path)
        assert not cli_ts.PACK.applies(ctx)
        assert not cli_go.PACK.applies(ctx)
        assert not cli_rust.PACK.applies(ctx)

    def test_the_dogfood_repo_lists_its_own_go_binaries(self):
        # C-14's own example: hobbes-policy/proxy/session/web were absent
        # from interfaces.json while two Python scripts were listed. The
        # lift is exact when the register's counter-example passes.
        from hobbes.extract.packs import cli_go

        repo = Path(__file__).parents[2]
        go = extract_go(repo / "go")
        ctx = PackContext(repo_root=repo / "go", modules=[], parsed={}, go=go)
        names = {e["name"] for e in cli_go.PACK.run(ctx).cli_entry_points}
        assert {"hobbes-policy", "hobbes-proxy", "hobbes-session", "hobbes-web"} <= names
