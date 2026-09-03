"""Lane A for Go (ADR-037).

The Go grammar walk, the fallback resolver, and the two things Go makes
harder than Python or TypeScript: a type conversion is spelled exactly like
a call, and an import names a package rather than a file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hobbes.extract.gosource import (
    collect_go_tests,
    extract_go,
    iter_go_files,
    module_id,
    package_dir,
)
from hobbes.extract.scipsource import go_modules

FIXTURE = Path(__file__).parent / "fixtures" / "minigo"


@pytest.fixture(scope="module")
def layer():
    return extract_go(FIXTURE)


def _sites(layer, name):
    return [s for s in layer["call_sites"] if s.name == name]


class TestDiscovery:
    def test_finds_go_files_and_prunes_like_every_other_walk(self, tmp_path):
        (tmp_path / "main.go").write_text("package main\n")
        for skipped in ("vendor", "testdata", ".git", "node_modules"):
            directory = tmp_path / skipped
            directory.mkdir()
            (directory / "other.go").write_text("package other\n")
        found = {p.name for p in iter_go_files(tmp_path)}
        assert found == {"main.go"}

    def test_vendor_is_pruned_because_it_is_someone_else_s_code(self, tmp_path):
        # Not architecture, and big enough to swamp any repo that has one.
        vendored = tmp_path / "vendor" / "github.com" / "x" / "y"
        vendored.mkdir(parents=True)
        (vendored / "y.go").write_text("package y\n")
        assert list(iter_go_files(tmp_path)) == []

    def test_no_go_means_no_layer(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert extract_go(tmp_path) is None

    def test_module_and_package_ids(self):
        assert module_id("internal/policy/policy.go") == "internal/policy/policy"
        assert package_dir("internal/policy/policy.go") == "internal/policy"
        assert package_dir("main.go") == "."


class TestSymbols:
    def test_functions_methods_types_consts(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["internal/policy/policy.Resolve"]["kind"] == "function"
        assert by_id["internal/policy/policy.Rule"]["kind"] == "type"
        assert by_id["internal/policy/policy.DefaultDecision"]["kind"] == "const"

    def test_a_method_is_qualified_by_its_receiver_type(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        method = by_id["internal/policy/policy.Rule.Matches"]
        assert method["kind"] == "method"
        assert method["name"] == "Matches"
        # The pointer star and the receiver *name* are noise; the type is
        # what the symbol hangs off, so `func (r *Rule) Matches` qualifies
        # as Rule.Matches rather than r.Matches.
        assert method["qualname"] == "Rule.Matches"

    def test_symbols_carry_a_range_the_join_can_project_onto(self, layer):
        for symbol in layer["symbols"]:
            assert symbol["line"] >= 1
            assert symbol["end_line"] >= symbol["line"]


class TestImports:
    def test_external_packages_become_ext_nodes(self, layer):
        ids = {n["id"] for n in layer["nodes"]}
        assert "ext:net/http" in ids
        assert "ext:strings" in ids

    def test_in_repo_package_imports_emit_no_module_edge(self, layer):
        # A Go import names a *package* — a directory — and choosing one of
        # its files would be a guess. The join raises the file-level edge
        # from what the call actually reaches instead (ADR-037).
        repo_edges = [
            e
            for e in layer["module_edges"]
            if not e["to"].startswith(("ext:", "env:"))
        ]
        assert repo_edges == []

    def test_env_reads_land_on_shared_env_nodes(self, layer):
        # The cross-layer join's Go end: os.Getenv meets Terraform's
        # env-set on one env:VAR node, as Python and JS already do.
        edges = {
            (e["from"], e["to"], e["type"])
            for e in layer["module_edges"]
            if e["type"] == "env-read"
        }
        assert ("internal/policy/policy", "env:MINIGO_HOME", "env-read") in edges
        assert ("cmd/mini/main", "env:MINIGO_MODE", "env-read") in edges


class TestCallSites:
    def test_sites_carry_column_and_enclosing_scope(self, layer):
        site = _sites(layer, "HasPrefix")[0]
        assert site.file == "internal/policy/policy.go"
        assert site.col > 0
        assert site.scope == "internal/policy/policy.Rule.Matches"

    def test_a_site_is_positioned_on_its_callee_not_its_expression(self, layer):
        # The ADR-029 correction, which pysource needed too: SCIP reports
        # the occurrence of the *name*, so a join keyed on the expression's
        # start silently matches nothing.
        source = (FIXTURE / "internal/policy/policy.go").read_text().splitlines()
        site = _sites(layer, "HasPrefix")[0]
        assert source[site.line - 1][site.col:].startswith("HasPrefix")

    def test_a_type_conversion_is_not_a_call(self, layer):
        # `Decision(DefaultDecision)` parses identically to a call, and no
        # indexer can separate them either (C-6). Lane A knows Decision is
        # a type, and a type is never called — so the site is dropped from
        # the join's left side and cannot become an edge down either arm.
        assert _sites(layer, "Decision") == []
        assert not any(
            key[2] == "Decision" for key in layer["call_fallback"]
        )

    def test_real_calls_survive_the_conversion_filter(self, layer):
        assert {s.name for s in layer["call_sites"]} >= {
            "Resolve",
            "HomeDir",
            "Matches",
            "HasPrefix",
        }


class TestFallbackResolution:
    """Lane A's floor beneath lane B (ADR-031), Go flavoured."""

    def test_resolves_a_package_qualified_call_exactly(self, layer):
        # policy.Resolve(...) from another package: the alias names the
        # package and a top-level name is unique within one, so this needs
        # no inference at all.
        target = layer["call_fallback"][("cmd/mini/main.go", 12, "Resolve")]
        assert target == ("internal/policy/policy.go", 26)

    def test_resolves_within_the_files_own_package(self, layer):
        # policy_test.go calls Resolve unqualified — same package, which is
        # the rule the compiler uses.
        assert layer["call_fallback"][
            ("internal/policy/policy_test.go", 7, "Resolve")
        ] == ("internal/policy/policy.go", 26)

    def test_declines_a_value_method_rather_than_guessing(self, layer):
        # rule.Matches(cmd): knowing what `rule` is needs a type checker,
        # which is lane B's job. Under-approximating is the rule — a false
        # edge is worse than a missing one (ADR-007).
        assert not any(key[2] == "Matches" for key in layer["call_fallback"])
        # ...but the *site* is still emitted, so lane B can resolve it and
        # coverage counts it as a site that needed an answer.
        assert _sites(layer, "Matches")

    def test_third_party_calls_resolve_to_nothing_locally(self, layer):
        assert not any(key[2] == "HasPrefix" for key in layer["call_fallback"])


class TestFallbackScopeVeto:
    """ADR-090's scope rule, the Go shape (fzf, O4 2026-08-27: 87 of 87
    contradictions were a local `assert` closure bound to a package-level
    `assert` in another file of the package)."""

    def _repo(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/p\n\ngo 1.22\n")
        (tmp_path / "a.go").write_text("package p\n\nfunc assert(ok bool) {}\n\nfunc atoi(s string) int { return 0 }\n")
        (tmp_path / "b.go").write_text(
            "package p\n\n"
            "func useLocal() {\n"
            "\tassert := func(ok bool) {}\n"
            "\tassert(true)\n"
            "}\n\n"
            "func usePackage() {\n"
            "\tassert(false)\n"
            "\tn := atoi(\"1\")\n"
            "\t_ = n\n"
            "}\n"
        )
        return extract_go(tmp_path)

    def test_a_local_func_literal_shadows_the_package_function(self, tmp_path):
        layer = self._repo(tmp_path)
        assert ("b.go", 5, "assert") not in layer["call_fallback"]
        # The site is still a site — lane B or the tail view gets it.
        assert _sites(layer, "assert")

    def test_an_unshadowed_call_still_resolves_in_the_package(self, tmp_path):
        layer = self._repo(tmp_path)
        assert layer["call_fallback"][("b.go", 9, "assert")] == ("a.go", 3)
        assert layer["call_fallback"][("b.go", 10, "atoi")] == ("a.go", 5)


class TestBuildConstraints:
    """ADR-098: one package, one name, several files under build
    constraints — the fallback resolves by the caller's own
    configuration or abstains (C-71); the quic-go shape of 2026-09-02."""

    def _repo(self, tmp_path):
        (tmp_path / "df_linux.go").write_text(
            "//go:build linux\n\npackage p\n\nfunc setDF() {}\n"
        )
        (tmp_path / "df_darwin.go").write_text(
            "//go:build darwin\n\npackage p\n\nfunc setDF() {}\n\nfunc macVersion() int { return 0 }\n"
        )
        (tmp_path / "df_other.go").write_text(
            "//go:build !linux && !darwin\n\npackage p\n\nfunc setDF() {}\n"
        )
        # No constraint: every configuration compiles it, so `setDF` here
        # is whichever file the build picks — lane A cannot know.
        (tmp_path / "conn.go").write_text(
            "package p\n\nfunc newConn() { setDF() }\n\nfunc helper() {}\n"
        )
        # Same constraint as one declaration: resolves to that one.
        (tmp_path / "df_darwin_test.go").write_text(
            "//go:build darwin\n\npackage p\n\nimport \"testing\"\n\n"
            "func TestDF(t *testing.T) {\n\tsetDF()\n\tmacVersion()\n\thelper()\n}\n"
        )
        # The external test package shares the directory and may reuse a
        # name: a bare call there is its own package's declaration.
        (tmp_path / "ext_test.go").write_text(
            "package p_test\n\nfunc helper() {}\n\nfunc useHelper() { helper() }\n"
        )
        return extract_go(tmp_path)

    def test_a_go_build_line_and_a_filename_suffix_are_the_key(self):
        from hobbes.extract.gosource import build_constraint

        assert build_constraint("a.go", b"package p\n") == ""
        assert build_constraint("a.go", b"//go:build   linux  &&  !cgo\n\npackage p\n") == "linux && !cgo|"
        assert build_constraint("x_windows.go", b"package p\n") == "|windows"
        assert build_constraint("x_linux_amd64_test.go", b"package p\n") == "|linux/amd64"
        assert build_constraint("x_arm64.go", b"//go:build cgo\npackage p\n") == "cgo|arm64"
        # Only the leading comment block counts — a build line after the
        # package clause is not a constraint.
        assert build_constraint("a.go", b"package p\n//go:build linux\n") == ""
        # A name that merely ends in a word Go does not know is unconstrained.
        assert build_constraint("x_helper.go", b"package p\n") == ""

    def test_an_unconstrained_caller_abstains_on_a_constrained_set(self, tmp_path):
        layer = self._repo(tmp_path)
        assert ("conn.go", 3, "setDF") not in layer["call_fallback"]
        assert ("conn.go", 3, "setDF") in layer["build_tag_sites"]
        assert _sites(layer, "setDF")  # still a site: lane B or the tail gets it

    def test_a_caller_under_the_same_constraint_resolves_to_its_own_file(self, tmp_path):
        layer = self._repo(tmp_path)
        assert layer["call_fallback"][("df_darwin_test.go", 8, "setDF")] == ("df_darwin.go", 5)
        assert ("df_darwin_test.go", 8, "setDF") not in layer["build_tag_sites"]

    def test_a_sole_declaration_resolves_regardless_of_constraints(self, tmp_path):
        layer = self._repo(tmp_path)
        assert layer["call_fallback"][("df_darwin_test.go", 9, "macVersion")] == ("df_darwin.go", 7)

    def test_the_external_test_package_is_its_own_namespace(self, tmp_path):
        layer = self._repo(tmp_path)
        # `helper` in p and in p_test: a bare call resolves inside its
        # own package, never across, and never abstains.
        assert layer["call_fallback"][("ext_test.go", 5, "helper")] == ("ext_test.go", 3)
        assert layer["call_fallback"][("df_darwin_test.go", 10, "helper")] == ("conn.go", 5)
        assert not {k for k in layer["build_tag_sites"] if k[2] == "helper"}

    def test_constrained_files_are_listed_for_the_surfacing(self, tmp_path):
        layer = self._repo(tmp_path)
        assert set(layer["constrained_files"]) == {
            "df_linux.go", "df_darwin.go", "df_other.go", "df_darwin_test.go"
        }

    def test_the_tail_names_the_abstention(self, tmp_path):
        from hobbes.extract import tail

        layer = self._repo(tmp_path)
        sites = [s for s in layer["call_sites"] if (s.file, s.line, s.name) == ("conn.go", 3, "setDF")]
        assert sites
        out = tail.classify(sites, tmp_path, build_tags=layer["build_tag_sites"])
        assert out["conn.go"] == {tail.BUILD_TAG: 1}
        assert tail.BUILD_TAG in tail.CLASSES_AVAILABLE["go"]

    def test_dark_constrained_files_get_one_record_per_directory(self):
        from hobbes.extract import _one_configuration_records

        rows = [
            {"file": "sys_conn_df_darwin.go", "sites": 4, "resolved": 0, "external": 0, "unresolved": 4},
            {"file": "sys_conn_df_windows.go", "sites": 2, "resolved": 0, "external": 0, "unresolved": 2},
            {"file": "sys_conn_df_linux.go", "sites": 3, "resolved": 3, "external": 0, "unresolved": 0},
            {"file": "sub/x_freebsd.go", "sites": 1, "resolved": 0, "external": 0, "unresolved": 1},
            {"file": "plain.go", "sites": 5, "resolved": 5, "external": 0, "unresolved": 0},
        ]
        constrained = {
            "sys_conn_df_darwin.go": "darwin|", "sys_conn_df_windows.go": "|windows",
            "sys_conn_df_linux.go": "linux|", "sub/x_freebsd.go": "|freebsd",
        }
        records = _one_configuration_records(rows, constrained)
        assert [r["path"] for r in records] == [".", "sub"]
        assert records[0]["stage"] == "scip-go"
        assert "2 file(s)" in records[0]["message"]
        assert "sys_conn_df_darwin.go, sys_conn_df_windows.go" in records[0]["message"]
        assert "sys_conn_df_linux.go" not in records[0]["message"]
        assert "C-71" in records[0]["message"]

    def test_no_record_when_lane_b_never_answered(self):
        # Lane B off (HOBBES_SCIP=0, or a failed index) leaves every row
        # at zero: that is C-8's record, not a configuration's.
        from hobbes.extract import _one_configuration_records

        rows = [{"file": "x_darwin.go", "sites": 4, "resolved": 0, "external": 0, "unresolved": 4}]
        assert _one_configuration_records(rows, {"x_darwin.go": "|darwin"}) == []


class TestTestInventory:
    def test_go_test_functions_are_inventoried(self, layer):
        assert [t["id"] for t in layer["tests"]] == [
            "internal/policy/policy_test.go::TestDefaultEscalates",
            "internal/policy/policy_test.go::TestResolveAllows",
        ]

    def test_only_test_files_yield_tests(self, layer):
        assert all(t["file"].endswith("_test.go") for t in layer["tests"])

    def test_reach_is_the_closure_over_call_edges(self, layer):
        # The same rule pytest and vitest reach use, so a Go row means what
        # a pytest row means (ADR-007).
        edges = [
            {
                "from": "internal/policy/policy_test.TestResolveAllows",
                "to": "internal/policy/policy.Resolve",
                "type": "calls",
            },
            {
                "from": "internal/policy/policy.Resolve",
                "to": "internal/policy/policy.Rule.Matches",
                "type": "calls",
            },
        ]
        rows = {t["id"]: t for t in collect_go_tests(layer["files"], edges)}
        row = rows["internal/policy/policy_test.go::TestResolveAllows"]
        assert row["reaches"] == [
            "internal/policy/policy.Resolve",
            "internal/policy/policy.Rule.Matches",
        ]
        assert row["reaches_modules"] == ["internal/policy/policy"]

    def test_rows_have_exactly_the_shape_every_framework_emits(self, layer):
        rows = collect_go_tests(layer["files"], [])
        assert set(rows[0]) == {
            "id",
            "file",
            "line",
            "framework",
            "symbol",
            "reaches",
            "reaches_modules",
        }
        assert rows[0]["framework"] == "go-test"

    def test_uses_edges_are_not_reach(self, layer):
        # Reach follows calls only — the same asymmetry C-24 records for JSX.
        edges = [
            {
                "from": "internal/policy/policy_test.TestResolveAllows",
                "to": "internal/policy/policy.Rule",
                "type": "uses",
            }
        ]
        rows = {t["id"]: t for t in collect_go_tests(layer["files"], edges)}
        assert rows["internal/policy/policy_test.go::TestResolveAllows"]["reaches"] == []


class TestGoModuleZoning:
    """One indexer run per go.mod — the TS zoning lesson, a language later."""

    def test_groups_files_by_their_nearest_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/root\n")
        nested = tmp_path / "svc"
        nested.mkdir()
        (nested / "go.mod").write_text("module example.com/svc\n")
        (tmp_path / "root.go").write_text("package root\n")
        (nested / "svc.go").write_text("package svc\n")

        assert go_modules(tmp_path, ["root.go", "svc/svc.go"]) == {
            "": ["root.go"],
            "svc": ["svc/svc.go"],
        }

    def test_a_module_below_the_repo_root_is_found(self, tmp_path):
        # This repo is the worked example: its go.mod is at go/, so
        # indexing from the repo root would find no module at all.
        (tmp_path / "go").mkdir()
        (tmp_path / "go" / "go.mod").write_text("module example.com/x\n")
        (tmp_path / "go" / "main.go").write_text("package main\n")
        assert go_modules(tmp_path, ["go/main.go"]) == {"go": ["go/main.go"]}

    def test_files_under_no_module_are_skipped_not_guessed(self, tmp_path):
        # A Go file outside a module cannot be type-checked, and inventing
        # a go.mod would invent its dependencies too.
        (tmp_path / "stray.go").write_text("package stray\n")
        assert go_modules(tmp_path, ["stray.go"]) == {}

    def test_orphans_are_named_per_directory(self):
        # C-26 (surfaced): the skip above must be visible. Pure over the
        # grouping so it runs with no indexer installed.
        from hobbes.extract.scipsource import go_orphans

        grouped = {"svc": ["svc/main.go"]}
        files = ["svc/main.go", "scratch/a.go", "scratch/b.go", "top.go"]
        assert go_orphans(files, grouped) == {
            "scratch": ["scratch/a.go", "scratch/b.go"],
            ".": ["top.go"],
        }

    def test_orphan_directories_get_a_degradation_record(self, tmp_path, monkeypatch):
        # The record a user meets: extract_scip_go names the directory and
        # the missing go.mod instead of skipping in silence (C-26).
        from hobbes.extract import scipsource

        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        monkeypatch.setattr(scipsource, "_index_go_module", lambda *a, **k: None)
        (tmp_path / "svc").mkdir()
        (tmp_path / "svc" / "go.mod").write_text("module example.com/svc\n")
        (tmp_path / "svc" / "main.go").write_text("package main\n")
        (tmp_path / "scratch").mkdir()
        (tmp_path / "scratch" / "snippet.go").write_text("package scratch\n")

        facts = scipsource.extract_scip_go(
            tmp_path, ["svc/main.go", "scratch/snippet.go"]
        )
        assert facts is not None
        records = [d for d in facts["degraded"] if d["stage"] == "scip-go"]
        assert len(records) == 1
        assert records[0]["path"] == "scratch"
        assert "go.mod" in records[0]["message"]
        assert "syntactic" in records[0]["message"]


class TestDegradation:
    def test_an_unparseable_file_does_not_take_the_layer_down(self, tmp_path):
        (tmp_path / "good.go").write_text(
            "package main\n\nfunc Good() int { return 1 }\n"
        )
        (tmp_path / "broken.go").write_text("package main\n\nfunc (((\n")
        layer = extract_go(tmp_path)
        # tree-sitter is error-tolerant by design (§3.1): the good file is
        # complete and the broken one contributes what could be read.
        assert any(s["id"] == "good.Good" for s in layer["symbols"])


class TestLocalBindings:
    """Sub-package bindings with enclosing-func extents (ADR-046)."""

    def bindings(self, tmp_path, text):
        (tmp_path / "go.mod").write_text("module example.com/lb\n")
        (tmp_path / "a.go").write_text(text)
        layer = extract_go(tmp_path)
        return set(layer["local_bindings"].get("a.go", ()))

    def test_short_var_and_params_bind(self, tmp_path):
        got = self.bindings(tmp_path,
            "package lb\n"
            "func run(name string) {\n"
            "\tcleanup := func() {}\n"
            "\tcleanup()\n"
            "}\n")
        assert ("cleanup", 2, 5) in got
        assert ("name", 2, 5) in got

    def test_range_and_var_targets_bind(self, tmp_path):
        got = self.bindings(tmp_path,
            "package lb\n"
            "func iter(xs []int) {\n"
            "\tvar total int\n"
            "\tfor i, v := range xs {\n"
            "\t\ttotal += i + v\n"
            "\t}\n"
            "}\n")
        assert {n for n, _, _ in got} >= {"total", "i", "v", "xs"}

    def test_named_results_and_receivers_bind(self, tmp_path):
        got = self.bindings(tmp_path,
            "package lb\n"
            "type T struct{}\n"
            "func (t *T) get() (out int) {\n"
            "\treturn out\n"
            "}\n")
        assert {n for n, _, _ in got} >= {"t", "out"}

    def test_package_level_declarations_do_not_bind(self, tmp_path):
        got = self.bindings(tmp_path,
            "package lb\n"
            "var Global = 1\n"
            "func f() {}\n")
        assert got == set()


SHAPES = Path(__file__).parent / "fixtures" / "goshapes"


class TestCallShapesTheOracleFoundMissing:
    """The O4 findings (oracle lane, 2026-08-25), each as a site that must
    exist — or must not — in lane A's view of the ``goshapes`` fixture."""

    @pytest.fixture(scope="class")
    def shapes(self):
        return extract_go(SHAPES)

    def test_a_conversion_is_not_a_site(self, shapes):
        assert _sites(shapes, "JSON") == []

    def test_a_method_named_like_a_type_is_still_a_call(self, shapes):
        # b.Cfg().Base = ... — the operand is an expression, so the call
        # cannot be a conversion however the package names its types.
        assert {s.line for s in _sites(shapes, "Cfg")} == {12}

    def test_chain_continuations_are_sites_on_their_own_lines(self, shapes):
        assert {s.line for s in _sites(shapes, "Chain")} == {14, 15}
        assert {s.line for s in _sites(shapes, "Tail")} == {16}

    def test_a_method_expression_is_a_site(self, shapes):
        assert {s.line for s in _sites(shapes, "Job")} == {17}

    def test_a_generic_instantiation_call_is_a_site(self, shapes):
        assert {s.line for s in _sites(shapes, "Ref")} == {18}

    def test_a_recursive_call_is_a_site(self, shapes):
        # The edge itself is the projection's business (test_scipsource);
        # lane A must at least see the site inside Walk.
        assert 33 in {s.line for s in _sites(shapes, "Walk")}

    def test_typed_vars_and_consts_are_named_by_their_names(self, shapes):
        names = {s["name"]: s["kind"] for s in shapes["symbols"]}
        assert names.get("Embedded") == "var"
        assert names.get("Key") == "const"
        assert names.get("A") == "var" and names.get("B") == "var"
        assert "string" not in names and "int" not in names
