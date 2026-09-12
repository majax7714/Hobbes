"""Lane A for C — the first unit of the C work (architecture §3.7 step 2).

No lane B exists yet, so every edge here is the fallback's, at
`syntactic` tier: this is the one language whose whole graph rests on
:func:`hobbes.extract.csource._call_fallback` alone, and the fixture is
built to exercise its three ranks, its abstentions, and the shapes
(field, dereference) it never touches.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hobbes.extract.csource import (
    collect_c_tests,
    extract_c,
    iter_c_files,
    module_id,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minic"


@pytest.fixture(scope="module")
def layer():
    return extract_c(FIXTURE)


def _sites(layer, name):
    return [s for s in layer["call_sites"] if s.name == name]


class TestDiscovery:
    def test_finds_c_and_h_files_and_prunes_like_every_other_walk(self, tmp_path):
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n")
        (tmp_path / "main.h").write_text("int main(void);\n")
        for skipped in ("build", ".git", "node_modules", "cmake-build-debug"):
            directory = tmp_path / skipped
            directory.mkdir()
            (directory / "other.c").write_text("int other(void) { return 0; }\n")
        found = {p.name for p in iter_c_files(tmp_path)}
        assert found == {"main.c", "main.h"}

    def test_cplusplus_extensions_are_never_discovered(self, tmp_path):
        for ext in ("cc", "cpp", "cxx", "hpp", "hh"):
            (tmp_path / f"a.{ext}").write_text("")
        assert list(iter_c_files(tmp_path)) == []

    def test_no_c_means_no_layer(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert extract_c(tmp_path) is None

    def test_a_linked_copy_is_not_discovered_twice(self, tmp_path):
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "a.c").write_text("int a(void) { return 0; }\n")
        (tmp_path / "shared").symlink_to(tmp_path / "core", target_is_directory=True)
        found = sorted(str(p.relative_to(tmp_path)) for p in iter_c_files(tmp_path))
        assert found == ["core/a.c"]


class TestModuleIds:
    def test_a_c_file_drops_its_extension(self):
        assert module_id("src/util.c") == "src/util"

    def test_a_header_keeps_its_extension(self):
        # A foo.c/foo.h pair in one directory is C's norm; dropping both
        # extensions would collide their ids.
        assert module_id("src/util.h") == "src/util.h"

    def test_the_fixture_pair_does_not_collide(self, layer):
        ids = {n["id"] for n in layer["nodes"]}
        assert {"src/util", "src/util.h"} <= ids


class TestSymbols:
    def test_function_definitions_are_functions(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/util.add"]["kind"] == "function"
        assert by_id["src/util.add"]["static"] is False

    def test_static_functions_are_recorded_as_file_local(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/util.helper"]["static"] is True
        assert by_id["src/shapes.helper"]["static"] is True

    def test_prototypes_are_never_symbols(self, layer):
        # util.h declares `add` and `scale` with no body.
        assert "src/util.h.add" not in {s["id"] for s in layer["symbols"]}
        assert "src/util.h.scale" not in {s["id"] for s in layer["symbols"]}

    def test_a_function_like_macro_is_a_macro_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["include/minic/config.h.MINIC_MAX"]["kind"] == "macro"

    def test_an_object_like_macro_is_never_a_symbol(self, layer):
        names = {s["name"] for s in layer["symbols"]}
        assert "MINIC_VERSION" not in names
        assert "MINIC_CONFIG_H" not in names  # the include guard itself

    def test_a_typedef_struct_is_a_type_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/util.h.Adder"]["kind"] == "type"

    def test_a_tagged_struct_with_a_body_is_a_type_symbol(self, tmp_path):
        (tmp_path / "a.c").write_text("struct Point { int x; int y; };\n")
        layer = extract_c(tmp_path)
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["a.Point"]["kind"] == "type"

    def test_a_bare_tag_reference_with_no_body_is_not_a_symbol(self, tmp_path):
        (tmp_path / "a.c").write_text(
            "struct Point { int x; };\nvoid f(struct Point p) {}\n"
        )
        layer = extract_c(tmp_path)
        assert len([s for s in layer["symbols"] if s["name"] == "Point"]) == 1

    def test_a_macro_inside_extern_c_is_a_macro_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["include/minic/api.h.MINIC_CLAMP"]["kind"] == "macro"

    def test_a_typedef_inside_extern_c_is_a_type_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["include/minic/api.h.MinicRange"]["kind"] == "type"

    def test_an_inline_function_inside_extern_c_is_a_static_function_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        symbol = by_id["include/minic/api.h.minic_twice"]
        assert symbol["kind"] == "function"
        assert symbol["static"] is True


class TestIncludes:
    def test_a_quoted_include_resolves_relative_to_the_including_file(self, layer):
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert ("src/util", "src/util.h", "imports") in edges
        assert ("src/main", "src/util.h", "imports") in edges

    def test_a_quoted_include_resolves_relative_to_the_repo_root_too(self, layer):
        # tests/test_util.c spells it "../src/util.h" from tests/.
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert ("tests/test_util", "src/util.h", "imports") in edges

    def test_an_angle_include_resolves_in_repo_by_the_unique_suffix_rule(self, layer):
        # <minic/config.h> matches no relative candidate; the unique repo
        # header ending in /minic/config.h is include/minic/config.h.
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert ("src/main", "include/minic/config.h", "imports") in edges

    def test_an_angle_include_that_resolves_nowhere_is_external(self, layer):
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert ("src/main", "ext:stdio.h", "imports") in edges

    def test_an_include_inside_an_extern_c_block_is_recorded(self, layer):
        # api.h's `#include <stddef.h>` sits inside its `extern "C" { }`;
        # the walk must not skip over it (fix 1).
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert ("include/minic/api.h", "ext:stddef.h", "imports") in edges

    def test_a_root_level_climb_above_the_repo_root_resolves_to_nothing(self, tmp_path):
        (tmp_path / "x.h").write_text("int x_marker(void);\n")
        (tmp_path / "main.c").write_text(
            '#include "../x.h"\nint main(void){return 0;}\n'
        )
        layer = extract_c(tmp_path)
        # Both the relative-to-file and relative-to-root steps climb above
        # the repo root here; neither is a candidate (fix 4) — the include
        # must not resolve to the root's own x.h.
        assert layer["module_edges"] == []

    def test_an_ambiguous_quoted_include_draws_no_edge(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "shared.h").write_text("int f(void);\n")
        (tmp_path / "b" / "shared.h").write_text("int g(void);\n")
        (tmp_path / "main.c").write_text('#include "shared.h"\nint main(void){return 0;}\n')
        layer = extract_c(tmp_path)
        assert layer["module_edges"] == []

    def test_an_ambiguous_angle_include_falls_to_external_not_in_repo(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "shared.h").write_text("int f(void);\n")
        (tmp_path / "b" / "shared.h").write_text("int g(void);\n")
        (tmp_path / "main.c").write_text("#include <shared.h>\nint main(void){return 0;}\n")
        layer = extract_c(tmp_path)
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert edges == {("main", "ext:shared.h", "imports")}

    def test_an_unmatched_quoted_include_draws_no_edge(self, tmp_path):
        (tmp_path / "main.c").write_text('#include "missing.h"\nint main(void){return 0;}\n')
        layer = extract_c(tmp_path)
        assert layer["module_edges"] == []


class TestCallSites:
    def test_positions_are_the_terminal_identifier(self, layer):
        source = (FIXTURE / "src/main.c").read_text().splitlines()
        for site in layer["call_sites"]:
            if site.file != "src/main.c":
                continue
            assert source[site.line - 1][site.col :].startswith(site.name)

    def test_a_plain_call_is_a_plain_site(self, layer):
        [parsed] = [f for f in layer["files"] if f.path == "src/util.c"]
        calls = {(c["name"], c["line"]): c["shape"] for c in parsed.calls}
        assert calls[("helper", 8)] == "plain"

    def test_a_field_call_is_a_field_site(self, layer):
        [parsed] = [f for f in layer["files"] if f.path == "src/util.c"]
        calls = {(c["name"], c["line"]): c["shape"] for c in parsed.calls}
        assert calls[("add", 15)] == "field"

    def test_a_dereference_call_is_a_deref_site(self, layer):
        [parsed] = [f for f in layer["files"] if f.path == "src/util.c"]
        calls = {(c["name"], c["line"]): c["shape"] for c in parsed.calls}
        assert calls[("fp", 15)] == "deref"

    def test_a_field_call_records_the_field_name(self, layer):
        # `adder.add(a, a)` in scale(): the terminal is the field `add`.
        [site] = [s for s in _sites(layer, "add") if s.file == "src/util.c"]
        assert site.scope == "src/util.scale"

    def test_a_parenthesized_dereference_records_the_pointer_name(self, layer):
        # `(*fp)(a, a)`: the terminal is the value being dereferenced.
        [site] = [s for s in _sites(layer, "fp")]
        assert site.file == "src/util.c" and site.scope == "src/util.scale"

    def test_a_macro_invocation_parses_as_a_plain_call(self, layer):
        [site] = _sites(layer, "MINIC_MAX")
        assert site.scope == "src/main.main"


class TestFallback:
    def test_same_file_static_helpers_each_resolve_to_their_own_file(self, layer):
        # shapes.c and util.c each define a `static helper`; the fallback
        # must pick the same-file one in each, never cross files.
        fb = layer["call_fallback"]
        assert fb[("src/util.c", 8, "helper")][0] == "src/util.c"
        assert fb[("src/shapes.c", 8, "helper")][0] == "src/shapes.c"
        assert fb[("src/util.c", 8, "helper")] != fb[("src/shapes.c", 8, "helper")]

    def test_a_function_like_macro_in_an_included_header_resolves(self, layer):
        fb = layer["call_fallback"]
        assert fb[("src/main.c", 11, "MINIC_MAX")] == ("include/minic/config.h", 6)

    def test_the_unique_global_function_resolves_across_files(self, layer):
        # `add` is defined once, non-static, in util.c; main.c and the
        # test file both call it without defining or including a macro
        # of that name themselves.
        fb = layer["call_fallback"]
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert fb[("src/main.c", 10, "add")] == ("src/util.c", by_id["src/util.add"]["line"])
        assert fb[("tests/test_util.c", 4, "add")] == ("src/util.c", by_id["src/util.add"]["line"])

    def test_a_duplicate_global_abstains(self, layer):
        # `scale` is defined non-static in both util.c and shapes.c: two
        # candidates at the same rank, so the fallback abstains.
        assert not any(k[2] == "scale" for k in layer["call_fallback"])

    def test_a_function_pointer_parameter_is_never_resolved_even_when_it_shadows_a_global(
        self, layer
    ):
        # run()'s parameter is named `add`, shadowing util.c's real `add`;
        # the call inside run() must not resolve to it.
        assert ("src/main.c", 6, "add") not in layer["call_fallback"]

    def test_a_field_call_is_never_resolved(self, layer):
        assert not any(
            k[0] == "src/util.c" and k[2] == "add" and k[1] == 15 for k in layer["call_fallback"]
        )

    def test_a_dereference_call_is_never_resolved(self, layer):
        assert not any(k[2] == "fp" for k in layer["call_fallback"])

    def test_a_same_file_function_resolves_over_a_global(self, layer):
        # `run(add)` inside main(): `run` is defined in src/main.c itself.
        fb = layer["call_fallback"]
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert fb[("src/main.c", 13, "run")] == ("src/main.c", by_id["src/main.run"]["line"])

    def test_two_headers_defining_the_same_macro_abstain(self, tmp_path):
        (tmp_path / "a.h").write_text("#define TWICE(x) ((x) * 2)\n")
        (tmp_path / "b.h").write_text("#define TWICE(x) ((x) + (x))\n")
        (tmp_path / "main.c").write_text(
            '#include "a.h"\n#include "b.h"\nint main(void) { return TWICE(1); }\n'
        )
        layer = extract_c(tmp_path)
        assert not any(k[2] == "TWICE" for k in layer["call_fallback"])

    def test_a_macro_inside_extern_c_resolves_by_rank_2(self, layer):
        # main.c's `MINIC_CLAMP(-5)`: a function-like macro defined in
        # api.h, a header main.c directly includes.
        fb = layer["call_fallback"]
        assert fb[("src/main.c", 20, "MINIC_CLAMP")] == ("include/minic/api.h", 10)

    def test_a_static_inline_function_inside_extern_c_stays_unresolved(self, layer):
        # `minic_twice` is `static`, so rank 3 (the unique non-static
        # global) excludes it; main.c's call to it never resolves.
        assert ("src/main.c", 21, "minic_twice") not in layer["call_fallback"]

    def test_a_same_file_tie_between_ifdef_arms_abstains(self, layer):
        # platform.c's `sep()` is defined twice (an `#ifdef _WIN32` and
        # an `#else` arm): rank 1's tie, so the call inside
        # path_separator() never resolves.
        assert ("src/platform.c", 12, "sep") not in layer["call_fallback"]

    def test_a_same_file_macro_and_function_tie_abstains(self, tmp_path):
        (tmp_path / "a.c").write_text(
            "#define FOO(x) ((x) + 1)\n"
            "int FOO(int x) { return x; }\n"
            "int caller(void) { return FOO(1); }\n"
        )
        layer = extract_c(tmp_path)
        assert not any(k[2] == "FOO" for k in layer["call_fallback"])


class TestDuplicateSymbols:
    def test_only_the_first_definition_survives_as_the_symbol(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id["src/platform.sep"]["line"] == 2
        assert len([s for s in layer["symbols"] if s["id"] == "src/platform.sep"]) == 1

    def test_one_errors_record_names_the_duplicate(self, layer):
        records = [
            e
            for e in layer["errors"]
            if e["stage"] == "parse" and e["path"] == "src/platform.c"
        ]
        assert len(records) == 1
        assert "sep" in records[0]["message"]
        assert "src/platform.c" in records[0]["message"]


class TestTests:
    def test_test_prefixed_functions_in_a_tests_directory_are_the_inventory(self, layer):
        ids = {t["id"] for t in layer["tests"]}
        assert ids == {
            "tests/test_util.c::test_add_sums",
            "tests/test_util.c::test_scale_is_positive",
        }
        assert all(t["framework"] == "c-convention" for t in layer["tests"])

    def test_a_non_test_prefixed_function_in_the_same_file_is_not_a_test(self, layer):
        assert not any(t["name"] == "helper_not_a_test" for t in layer["tests"])

    def test_test_suffixed_or_prefixed_filenames_also_qualify(self, tmp_path):
        (tmp_path / "test_foo.c").write_text("int test_a(void) { return 1; }\n")
        (tmp_path / "bar_test.c").write_text("int test_b(void) { return 1; }\n")
        layer = extract_c(tmp_path)
        ids = {t["id"] for t in layer["tests"]}
        assert ids == {"test_foo.c::test_a", "bar_test.c::test_b"}

    def test_reach_is_the_closure_over_calls_edges(self, layer):
        edges = [
            {"from": "tests/test_util.test_add_sums", "to": "src/util.add", "type": "calls"},
            {"from": "src/util.add", "to": "src/util.helper", "type": "calls"},
        ]
        rows = collect_c_tests(layer["files"], edges)
        by_id = {r["id"]: r for r in rows}
        add_test = by_id["tests/test_util.c::test_add_sums"]
        assert add_test["reaches"] == ["src/util.add", "src/util.helper"]
        assert add_test["reaches_modules"] == ["src/util"]
        scale_test = by_id["tests/test_util.c::test_scale_is_positive"]
        assert scale_test["reaches"] == []


@pytest.fixture(scope="module")
def extraction():
    from hobbes.extract import extract_repo

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOBBES_SCIP", "0")
        return extract_repo(FIXTURE)


class TestExtractRepo:
    """The whole pipeline over minic, lane B off — the only path C has."""

    def test_languages_report_c(self, extraction):
        assert extraction.graph["languages"] == ["c"]

    def test_c_is_unverified(self, extraction):
        # P11: C is wired, not claimed supported until evidence exists.
        assert extraction.graph["verification_base"]["c"]["repos"] == 0

    def test_every_calls_edge_is_syntactic(self, extraction):
        calls = [e for e in extraction.graph["symbol_edges"] if e["type"] == "calls"]
        assert calls and all(e["tier"] == "syntactic" for e in calls)
        pairs = {(e["from"], e["to"]) for e in calls}
        assert ("src/main.main", "src/util.add") in pairs
        assert ("src/util.add", "src/util.helper") in pairs
        assert ("src/shapes.square", "src/shapes.helper") in pairs
        assert ("tests/test_util.test_add_sums", "src/util.add") in pairs

    def test_every_tail_row_sums_to_unresolved(self, extraction):
        for row in extraction.graph["resolution_coverage"]:
            assert sum(row["tail"].values()) == row["unresolved"], row

    def test_the_tail_stays_inside_its_five_available_classes(self, extraction):
        available = set(extraction.graph["tail_classes_available"]["c"])
        assert available == {
            "fallback-resolved", "local-binding", "builtin-name", "attr-call", "unclassified",
        }
        for row in extraction.graph["resolution_coverage"]:
            assert set(row.get("tail", {})) <= available, row

    def test_printf_classifies_as_builtin_name(self, extraction):
        [row] = [r for r in extraction.graph["resolution_coverage"] if r["file"] == "src/main.c"]
        assert row["tail"]["builtin-name"] == 2

    def test_the_field_call_classifies_as_attr_call(self, extraction):
        [row] = [r for r in extraction.graph["resolution_coverage"] if r["file"] == "src/util.c"]
        assert row["tail"]["attr-call"] == 1

    def test_the_shadowed_function_pointer_call_classifies_as_local_binding(self, extraction):
        [row] = [r for r in extraction.graph["resolution_coverage"] if r["file"] == "src/main.c"]
        assert row["tail"]["local-binding"] == 1

    def test_the_dereferenced_function_pointer_call_classifies_as_local_binding(self, extraction):
        [row] = [r for r in extraction.graph["resolution_coverage"] if r["file"] == "src/util.c"]
        assert row["tail"]["local-binding"] == 1

    def test_the_ambiguous_global_call_stays_unclassified(self, extraction):
        [row] = [
            r for r in extraction.graph["resolution_coverage"] if r["file"] == "tests/test_util.c"
        ]
        assert row["tail"]["unclassified"] == 1

    def test_tests_reach_through_the_syntactic_edges(self, extraction):
        by_id = {t["id"]: t for t in extraction.tests["tests"]}
        t = by_id["tests/test_util.c::test_add_sums"]
        assert "src/util.add" in t["reaches"] and "src/util.helper" in t["reaches"]


class TestDegradation:
    def test_an_unparseable_file_does_not_take_the_layer_down(self, tmp_path):
        (tmp_path / "good.c").write_text("int good(void) { return 1; }\n")
        (tmp_path / "broken.c").write_text("int broken(void) { return \n")
        layer = extract_c(tmp_path)
        assert any(s["id"] == "good.good" for s in layer["symbols"])

    def test_a_file_with_tree_sitter_error_nodes_still_yields_its_sites(self, tmp_path):
        (tmp_path / "broken.c").write_text(
            "int helper(void) { return 1; }\n"
            "int broken(void) { return \n"
            "int caller(void) { return helper(); }\n"
        )
        layer = extract_c(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "parse"]
        assert len(records) == 1
        assert records[0]["path"] == "broken.c"
        assert any(s.name == "helper" for s in layer["call_sites"])

    def test_only_the_extern_c_idiom_and_the_duplicate_sep_draw_error_records(self, layer):
        # api.h's `#ifdef __cplusplus` / `extern "C" {` idiom is real,
        # legal C that tree-sitter cannot fully balance (module
        # docstring) — a cosmetic `has_error`, not a missed declaration.
        # platform.c's duplicate `sep()` draws fix 3's record. No other
        # fixture file gets one.
        by_path = {e["path"]: e for e in layer["errors"]}
        assert set(by_path) == {"include/minic/api.h", "src/platform.c"}
        assert "syntax errors" in by_path["include/minic/api.h"]["message"]
        assert "sep" in by_path["src/platform.c"]["message"]
