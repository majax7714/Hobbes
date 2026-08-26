"""Lane A for Rust (ADR-040).

The Rust grammar walk, the fallback resolver, and the two things Rust
makes harder than Go: macro arguments are unparsed token trees (so call
sites there come from call-shape detection), and a `use` names an item
path whose crate root is only knowable from `Cargo.toml`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hobbes.extract.rustsource import (
    collect_rust_tests,
    extract_rust,
    iter_rust_files,
    local_crate_names,
    module_id,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minirust"


@pytest.fixture(scope="module")
def layer():
    return extract_rust(FIXTURE)


def _sites(layer, name):
    return [s for s in layer["call_sites"] if s.name == name]


class TestDiscovery:
    def test_finds_rust_files_and_prunes_like_every_other_walk(self, tmp_path):
        (tmp_path / "main.rs").write_text("fn main() {}\n")
        for skipped in ("target", ".git", "node_modules"):
            directory = tmp_path / skipped
            directory.mkdir()
            (directory / "other.rs").write_text("fn other() {}\n")
        found = {p.name for p in iter_rust_files(tmp_path)}
        assert found == {"main.rs"}

    def test_target_is_pruned_because_it_is_build_output(self, tmp_path):
        # Cargo's build directory: checked in rarely, enormous always.
        debug = tmp_path / "target" / "debug" / "build"
        debug.mkdir(parents=True)
        (debug / "generated.rs").write_text("fn generated() {}\n")
        assert list(iter_rust_files(tmp_path)) == []

    def test_no_rust_means_no_layer(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert extract_rust(tmp_path) is None

    def test_module_ids_are_paths_sans_extension(self):
        assert module_id("src/combined/mod1.rs") == "src/combined/mod1"
        assert module_id("src/lib.rs") == "src/lib"


class TestCrates:
    def test_package_and_renamed_lib_both_name_the_lib_target(self):
        crates = local_crate_names(FIXTURE)
        # The package is `mini-rust`; code spells it `mini_rust`.
        assert crates["mini_rust"] == "src/lib.rs"
        # `[lib] name = "minilib"` is what `use minilib::…` actually says.
        assert crates["minilib"] == "src/lib.rs"


class TestSymbols:
    def test_functions_in_cfg_test_mods_carry_their_mod_qualname(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        test_fn = by_id["src/main.tests.test_double"]
        assert test_fn["kind"] == "function"
        assert test_fn["name"] == "test_double"

    def test_impl_methods_hang_off_their_type(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/lib.Counter.new"]["kind"] == "method"
        assert by_id["src/lib.Counter"]["kind"] == "type"

    def test_macro_rules_is_a_symbol(self, layer):
        # Rust without macros is not Rust; a macro is architecture the way
        # a function is (ADR-040, the fifth graph kind).
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/lib.twice"]["kind"] == "macro"


class TestImports:
    def test_external_crates_get_ext_edges(self, layer):
        edges = {
            (e["from"], e["to"], e["type"]) for e in layer["module_edges"]
        }
        assert ("src/lib", "ext:std", "imports") in edges

    def test_the_repo_own_crate_is_never_external(self, layer):
        # `use minilib::compute` names this repo's lib target; an ext: node
        # for it would put the repo's own code outside the repo.
        assert not any(n["id"] == "ext:minilib" for n in layer["nodes"])

    def test_no_in_repo_import_edges_from_lane_a(self, layer):
        # The Go rule: a `use` names an item path, not a file. The join
        # raises in-repo module edges from what calls actually reach.
        own = {n["id"] for n in layer["nodes"] if "path" in n}
        assert not any(
            e["from"] in own and e["to"] in own for e in layer["module_edges"]
        )


class TestEnv:
    def test_std_env_var_reads_join_the_cross_layer(self, layer):
        edges = {
            (e["from"], e["to"], e["type"]) for e in layer["module_edges"]
        }
        assert ("src/helpers", "env:MINIRUST_MODE", "env-read") in edges


class TestCallSites:
    def test_macro_arguments_yield_call_sites(self, layer):
        # `assert_eq!(compute(2, 3), 5)` is a token tree to tree-sitter —
        # no call_expression inside — and almost every Rust test asserts
        # through a macro. Call-shape detection is what keeps Rust test
        # reach from being empty (ADR-040 decision 4).
        source = (FIXTURE / "tests/integration.rs").read_text().splitlines()
        [site] = [
            s for s in _sites(layer, "compute") if s.file == "tests/integration.rs"
        ]
        assert source[site.line - 1][site.col :].startswith("compute")
        assert site.scope == "tests/integration.integration_works"

    def test_the_macro_invocation_itself_is_a_site(self, layer):
        [site] = [s for s in _sites(layer, "twice") if s.line != 3]
        assert site.file == "src/lib.rs"
        assert site.scope == "src/lib.double_via_macro"

    def test_positions_are_the_callee_identifiers(self, layer):
        # The ADR-029 correction, third language: SCIP reports the name's
        # occurrence, so the join keys on where the name is.
        source = (FIXTURE / "src/main.rs").read_text().splitlines()
        for site in layer["call_sites"]:
            if site.file != "src/main.rs":
                continue
            assert source[site.line - 1][site.col :].startswith(site.name)


class TestFallback:
    def test_mod_declarations_map_to_files_by_rustc_rules(self, layer):
        fallback = layer["call_fallback"]
        # `mod helpers;` from a root file → sibling helpers.rs
        assert fallback[("src/main.rs", 10, "greet")] == ("src/helpers.rs", 1)
        # `mod sub;` → sub/mod.rs
        assert fallback[("src/main.rs", 11, "from_sub")] == ("src/sub/mod.rs", 1)
        # `#[path = "./deep/extra.rs"] mod extra;` → the attribute's target
        assert fallback[("src/main.rs", 12, "extra_fn")] == ("src/deep/extra.rs", 1)

    def test_the_crate_name_resolves_to_the_lib_target(self, layer):
        fallback = layer["call_fallback"]
        # `use minilib::compute` + `compute(1, 2)`: alias → lib target.
        assert fallback[("src/main.rs", 13, "compute")] == ("src/lib.rs", 9)
        # And from an integration test, through a use-list.
        assert fallback[("tests/integration.rs", 5, "compute")] == ("src/lib.rs", 9)

    def test_type_associated_functions_resolve_through_the_type(self, layer):
        fallback = layer["call_fallback"]
        assert fallback[("tests/integration.rs", 6, "new")] == ("src/lib.rs", 22)

    def test_value_methods_are_left_to_lane_b(self, layer):
        # `c.incr()` needs a type checker; guessing would fabricate edges.
        assert not any(name == "incr" for (_, _, name) in layer["call_fallback"])

    def test_a_repo_defined_macro_resolves_like_a_call(self, layer):
        fallback = layer["call_fallback"]
        assert fallback[("src/lib.rs", 14, "twice")] == ("src/lib.rs", 3)
        # And the call inside its token-tree argument resolves too.
        assert fallback[("src/lib.rs", 14, "compute")] == ("src/lib.rs", 9)


class TestTests:
    def test_inventory_is_test_attributes_only(self, layer):
        assert [(t["id"], t["framework"]) for t in layer["tests"]] == [
            ("src/main.rs::test_double", "cargo-test"),
            ("tests/integration.rs::integration_works", "cargo-test"),
        ]

    def test_cfg_test_does_not_mark_the_mod_it_gates(self, layer):
        # `#[cfg(test)]`'s attribute path is `cfg`; only a path that is or
        # ends in `test` marks a function.
        assert not any(t["name"] == "tests" for t in layer["tests"])

    def test_reach_is_the_closure_over_calls_edges(self, layer):
        edges = [
            {"from": "src/main.tests.test_double", "to": "src/main.double", "type": "calls"},
            {"from": "tests/integration.integration_works", "to": "src/lib.compute", "type": "calls"},
            {"from": "src/lib.compute", "to": "src/lib.twice", "type": "calls"},
        ]
        rows = collect_rust_tests(layer["files"], edges)
        by_id = {r["id"]: r for r in rows}
        assert by_id["src/main.rs::test_double"]["symbol"] == "src/main.tests.test_double"
        assert by_id["src/main.rs::test_double"]["reaches"] == ["src/main.double"]
        # Closure, not one hop — and reaches_modules names repo files only.
        integration = by_id["tests/integration.rs::integration_works"]
        assert integration["reaches"] == ["src/lib.compute", "src/lib.twice"]
        assert integration["reaches_modules"] == ["src/lib"]


class TestCargoGrouping:
    def test_groups_files_by_their_nearest_manifest(self, tmp_path):
        from hobbes.extract.scipsource import cargo_crates

        (tmp_path / "Cargo.toml").write_text('[package]\nname = "root"\n')
        nested = tmp_path / "svc"
        nested.mkdir()
        (nested / "Cargo.toml").write_text('[package]\nname = "svc"\n')
        (tmp_path / "lib.rs").write_text("pub fn a() {}\n")
        (nested / "svc.rs").write_text("pub fn b() {}\n")

        assert cargo_crates(tmp_path, ["lib.rs", "svc/svc.rs"]) == {
            "": ["lib.rs"],
            "svc": ["svc/svc.rs"],
        }

    def test_member_crates_collapse_to_their_workspace_root(self, tmp_path):
        # A member manifest can lean on the workspace root's
        # (`version.workspace = true`), so indexing the member alone fails
        # on a repo that builds fine — one run per workspace.
        from hobbes.extract.scipsource import cargo_crates

        (tmp_path / "Cargo.toml").write_text('[workspace]\nmembers = ["a", "b"]\n')
        for member in ("a", "b"):
            crate = tmp_path / member
            (crate / "src").mkdir(parents=True)
            (crate / "Cargo.toml").write_text(f'[package]\nname = "{member}"\n')
            (crate / "src" / "lib.rs").write_text("pub fn f() {}\n")

        assert cargo_crates(tmp_path, ["a/src/lib.rs", "b/src/lib.rs"]) == {
            "": ["a/src/lib.rs", "b/src/lib.rs"],
        }

    def test_files_under_no_manifest_are_skipped_not_guessed(self, tmp_path):
        # Inventing a Cargo.toml would invent the dependency versions too
        # (the C-26 pattern, one language over).
        from hobbes.extract.scipsource import cargo_crates

        (tmp_path / "stray.rs").write_text("fn main() {}\n")
        assert cargo_crates(tmp_path, ["stray.rs"]) == {}

    def test_orphan_directories_get_a_degradation_record(self, tmp_path, monkeypatch, capsys):
        from hobbes.extract import scipsource

        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        monkeypatch.setattr(scipsource, "_index_cargo_root", lambda *a, **k: None)
        crate = tmp_path / "svc"
        (crate / "src").mkdir(parents=True)
        (crate / "Cargo.toml").write_text('[package]\nname = "svc"\n')
        (crate / "src" / "main.rs").write_text("fn main() {}\n")
        (tmp_path / "scratch").mkdir()
        (tmp_path / "scratch" / "snippet.rs").write_text("fn f() {}\n")

        facts = scipsource.extract_scip_rust(
            tmp_path, ["svc/src/main.rs", "scratch/snippet.rs"]
        )
        assert facts is not None
        records = [d for d in facts["degraded"] if d["stage"] == "scip-rust"]
        assert len(records) == 1
        assert records[0]["path"] == "scratch"
        assert "Cargo.toml" in records[0]["message"]
        assert "syntactic" in records[0]["message"]
        # C-29's surfacing: the execution disclosure prints whenever the
        # rust lane runs, not only when something goes wrong.
        assert "build scripts" in capsys.readouterr().err

    def test_declared_cargo_dependencies_read_every_dependency_table(self, tmp_path):
        from hobbes.extract.scipsource import declared_cargo_dependencies

        manifest = tmp_path / "Cargo.toml"
        manifest.write_text(
            "[package]\n"
            'name = "x"\n'
            "[dependencies]\n"
            'serde = "1"\n'
            "[dev-dependencies]\n"
            'criterion = "0.3"\n'
            "[build-dependencies]\n"
            'cc = "1"\n'
        )
        assert declared_cargo_dependencies(manifest) == ["cc", "criterion", "serde"]


class TestDegradation:
    def test_an_unparseable_file_does_not_take_the_layer_down(self, tmp_path):
        (tmp_path / "good.rs").write_text("pub fn good() -> i64 { 1 }\n")
        (tmp_path / "broken.rs").write_text("fn (((\n")
        layer = extract_rust(tmp_path)
        # tree-sitter is error-tolerant by design (§3.1): the good file is
        # complete and the broken one contributes what could be read.
        assert any(s["id"] == "good.good" for s in layer["symbols"])


@pytest.fixture(scope="module")
def extraction():
    from hobbes.extract import extract_repo

    # Module-scoped fixtures are set up *before* the function-scoped
    # autouse `_lane_a_only` monkeypatch, so the suite's lane-B-off
    # default must be pinned here or extract_repo runs the real
    # rust-analyzer whenever the box can resolve minirust's semantics.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOBBES_SCIP", "0")
        return extract_repo(FIXTURE)


class TestExtractRepo:
    """The whole pipeline over minirust, lane B off (the suite default) —
    the degraded path is the one under test on every run (§3.4)."""

    def test_languages_report_rust(self, extraction):
        assert extraction.graph["languages"] == ["rust"]

    def test_fallback_resolutions_become_syntactic_calls_edges(self, extraction):
        edges = {
            (e["from"], e["to"], e["type"], e["tier"])
            for e in extraction.graph["symbol_edges"]
        }
        assert (
            "src/main.tests.test_double",
            "src/main.double",
            "calls",
            "syntactic",
        ) in edges
        # Through a token tree and a use-list alias, from an integration
        # test file — the case that would be empty without call-shape
        # detection.
        assert (
            "tests/integration.integration_works",
            "src/lib.compute",
            "calls",
            "syntactic",
        ) in edges

    def test_the_join_raises_in_repo_module_edges(self, extraction):
        edges = {
            (e["from"], e["to"], e["type"]) for e in extraction.graph["module_edges"]
        }
        assert ("src/main", "src/helpers", "imports") in edges
        assert ("tests/integration", "src/lib", "imports") in edges

    def test_rust_tests_reach_what_they_call(self, extraction):
        rows = {t["id"]: t for t in extraction.tests["tests"]}
        assert rows["src/main.rs::test_double"]["reaches"] == ["src/main.double"]
        integration = rows["tests/integration.rs::integration_works"]
        assert "src/lib.compute" in integration["reaches"]
        assert integration["reaches_modules"] == ["src/lib"]

    def test_lane_agreement_stays_quiet_with_lane_b_off(self, extraction):
        agreement = extraction.graph["lane_agreement"]
        assert agreement["site_disagreements"] == []
        assert agreement["module_edges_lane_a_only"] == []


class TestMacroInvocationsBindOnlyToMacros:
    """O7 on dagger's SDK: twelve contradictions, every one `format!(..)`
    bound by the fallback to a `fn format` in the same file."""

    def test_a_bang_never_invokes_a_function_of_the_same_name(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "m"\nversion = "0.1.0"\n')
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text(
            "fn format(x: i64) -> String {\n"
            "    format!(\"{x}\")\n"
            "}\n"
            "macro_rules! twice { ($x:expr) => { $x * 2 }; }\n"
            "pub fn twice(x: i64) -> i64 {\n"
            "    twice!(format(x).len() as i64)\n"
            "}\n"
        )
        layer = extract_rust(tmp_path)
        fb = layer["call_fallback"]
        assert ("src/lib.rs", 2, "format") not in fb
        # A macro invocation binds to the macro; a plain call to the fn.
        assert fb[("src/lib.rs", 6, "twice")] == ("src/lib.rs", 4)
        assert fb[("src/lib.rs", 6, "format")] == ("src/lib.rs", 1)
