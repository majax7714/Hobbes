"""Lane A for C — the first unit of the C work (architecture §3.7 step 2).

No lane B exists yet, so every edge here is the fallback's, at
`syntactic` tier: this is the one language whose whole graph rests on
:func:`hobbes.extract.csource._call_fallback` alone, and the fixture is
built to exercise its three ranks, its abstentions, and the shapes
(field, dereference) it never touches.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from hobbes.extract.csource import (
    _PARSER,
    HeaderIndex,
    _IncludeResolution,
    _normalize,
    _resolve_include,
    _walk,
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

    def test_cplusplus_extensions_are_not_c_s(self, tmp_path):
        # They are `cppsource`'s since ADR-113 §1; this walk still never
        # sees them.
        for ext in ("cc", "cpp", "cxx", "hpp", "hh", "hxx"):
            (tmp_path / f"a.{ext}").write_text("")
        assert list(iter_c_files(tmp_path)) == []

    def test_a_header_cpp_claimed_is_skipped(self, tmp_path):
        # One header is read by exactly one language (ADR-113 §1): the
        # C++ walk hands over what it took, and C does not read it twice.
        (tmp_path / "a.c").write_text("int f(void) { return 0; }\n")
        (tmp_path / "mine.h").write_text("int f(void);\n")
        (tmp_path / "theirs.h").write_text("int g();\n")
        found = {p.name for p in iter_c_files(tmp_path, claimed={"theirs.h"})}
        assert found == {"a.c", "mine.h"}
        layer = extract_c(tmp_path, claimed={"theirs.h"})
        assert {n["path"] for n in layer["nodes"] if n["kind"] == "module"} == {"a.c", "mine.h"}

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


class TestWalk:
    """ADR-128 §3: the walk is an explicit stack now, and must yield what
    the recursive generator it replaced yielded."""

    def test_the_stack_walk_yields_the_nodes_the_recursion_did_in_its_order(self):
        def recursive(node):  # the definition ADR-128 §3 replaced
            yield node
            for child in node.children:
                yield from recursive(child)

        source = (
            b"struct S { int (*fp)(int); };\n"
            b"int f(int x) {\n"
            b"    if (x) { return g(x - 1); }\n"
            b"    for (int i = 0; i < x; i++) { h(i); }\n"
            b"    return 0;\n"
            b"}\n"
            b"int broken(void { ;\n"  # the walk must cross ERROR nodes too
        )
        root = _PARSER.parse(source).root_node
        walked = list(_walk(root))
        assert walked == list(recursive(root))
        assert any(node.type == "ERROR" for node in walked)
        assert len(walked) > 1


class TestIncludeIndex:
    """ADR-128 §3: the suffix step reads a basename index instead of every
    repo header, and must decide every spec the linear scan's way."""

    #: Two headers share `shared.h` (ambiguous bare, unique with their
    #: directory); two share `config.h` across a nested and a flat path.
    HEADERS = {
        "a/shared.h",
        "b/shared.h",
        "include/minic/config.h",
        "vendor/config.h",
        "src/util.h",
    }
    KNOWN = HEADERS | {"src/main.c", "a/x.c"}

    SPECS = [
        "shared.h",             # ambiguous: two headers end in /shared.h
        "a/shared.h",           # unique once the directory is spelled
        "minic/config.h",       # unique, a directory the scan matched too
        "other/config.h",       # the basename matches, the directory does not
        "config.h",             # ambiguous across two directories
        "util.h",               # unique
        "src/",                 # a spec ending in `/`: no path ends in one
        "a/",
        "../a/shared.h",        # a climb, normalized by steps 1 and 2
        "a/../b/shared.h",
        "nothing.h",            # no candidate at any step
    ]

    @staticmethod
    def old(including_path, spec, known_files, headers):
        """:func:`_resolve_include` as ADR-128 §3 found it — step 3 an
        ``endswith`` over the whole header set."""
        candidate = _normalize(PurePosixPath(including_path).parent, spec)
        if candidate is not None and candidate in known_files:
            return _IncludeResolution(candidate, False)
        candidate = _normalize(PurePosixPath("."), spec)
        if candidate is not None and candidate in known_files:
            return _IncludeResolution(candidate, False)
        suffix = "/" + spec
        matches = [f for f in headers if f.endswith(suffix)]
        if len(matches) == 1:
            return _IncludeResolution(matches[0], False)
        return _IncludeResolution(None, len(matches) > 1)

    @pytest.mark.parametrize("including", ["src/main.c", "a/x.c"])
    def test_the_index_decides_every_spec_exactly_as_the_linear_scan_did(self, including):
        index = HeaderIndex(self.HEADERS)
        for spec in self.SPECS:
            now = _resolve_include(including, spec, self.KNOWN, index)
            assert now == self.old(including, spec, self.KNOWN, self.HEADERS), spec

    def test_the_specs_cover_a_match_an_ambiguity_and_a_miss(self):
        # So the equivalence above cannot pass by finding nothing at all.
        outcomes = {
            (r.path is not None, r.ambiguous)
            for r in (
                self.old("src/main.c", spec, self.KNOWN, self.HEADERS) for spec in self.SPECS
            )
        }
        assert outcomes == {(True, False), (False, True), (False, False)}

    def test_a_plain_set_still_resolves_the_same_as_its_index(self):
        # Any caller that does not build the index keeps the old signature.
        for spec in self.SPECS:
            assert _resolve_include(
                "src/main.c", spec, self.KNOWN, self.HEADERS
            ) == _resolve_include("src/main.c", spec, self.KNOWN, HeaderIndex(self.HEADERS))


class TestIncludeDegradations:
    """The 2026-09-14 amendment: a `"c-includes"` record per directory for
    an include decision 4 could not place (C-133)."""

    def test_unmatched_quoted_includes_get_one_record_naming_both(self, tmp_path):
        # Neither spec exists anywhere in the repo: both are unmatched,
        # not ambiguous, and neither draws an edge.
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.c").write_text(
            '#include "config.h"\n#include "gen/version.h"\nint main(void){return 0;}\n'
        )
        layer = extract_c(tmp_path)
        assert layer["module_edges"] == []
        records = [e for e in layer["errors"] if e["stage"] == "c-includes"]
        [record] = records
        assert record["path"] == "src"
        assert record["message"] == (
            '2 quoted includes matched no repo file ("config.h", "gen/version.h"); '
            "the build's include path decides them, and lane A does not read it (C-133)"
        )

    def test_ambiguous_includes_count_per_spelling_and_still_draw_their_edges(self, tmp_path):
        # Two repo headers share the suffix /util.h: the unique-suffix
        # step abstains for both a quoted and an angle spelling of it.
        (tmp_path / "include" / "x").mkdir(parents=True)
        (tmp_path / "include" / "y").mkdir(parents=True)
        (tmp_path / "include" / "x" / "util.h").write_text("void f(void);\n")
        (tmp_path / "include" / "y" / "util.h").write_text("void g(void);\n")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "b.c").write_text('#include "util.h"\nint b(void){return 0;}\n')
        (tmp_path / "src" / "c.c").write_text("#include <util.h>\nint c(void){return 0;}\n")
        layer = extract_c(tmp_path)
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert not any(f == "src/b" for f, _, _ in edges)
        assert ("src/c", "ext:util.h", "imports") in edges
        records = [e for e in layer["errors"] if e["stage"] == "c-includes"]
        [record] = records
        assert record["path"] == "src"
        assert record["message"] == (
            '2 includes matched more than one repo header ("util.h", <util.h>); '
            "the build's include path decides them, and lane A does not read it (C-133)"
        )

    def test_a_resolved_dependency_is_not_a_miss(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "d.h").write_text("void d(void);\n")
        (tmp_path / "src" / "d.c").write_text(
            '#include <stdio.h>\n#include "d.h"\nvoid d(void){}\n'
        )
        layer = extract_c(tmp_path)
        assert not [e for e in layer["errors"] if e["stage"] == "c-includes"]

    def test_records_once_per_directory_capped_at_three_specs(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "one.c").write_text(
            '#include "a.h"\n#include "b.h"\nint one(void){return 0;}\n'
        )
        (tmp_path / "dir" / "two.c").write_text(
            # "a.h" repeats here — counted once, not twice.
            '#include "c.h"\n#include "d.h"\n#include "a.h"\nint two(void){return 0;}\n'
        )
        layer = extract_c(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "c-includes"]
        [record] = records
        assert record["path"] == "dir"
        assert record["message"] == (
            '4 quoted includes matched no repo file ("a.h", "b.h", "c.h", …); '
            "the build's include path decides them, and lane A does not read it (C-133)"
        )

    def test_a_root_level_miss_records_the_root_directory_as_dot(self, tmp_path):
        (tmp_path / "main.c").write_text('#include "missing.h"\nint main(void){return 0;}\n')
        layer = extract_c(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "c-includes"]
        [record] = records
        assert record["path"] == "."
        assert record["message"] == (
            '1 quoted include matched no repo file ("missing.h"); '
            "the build's include path decides them, and lane A does not read it (C-133)"
        )

    def test_c_tests_records_are_unaffected_and_both_can_land_on_one_file(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "prog.c").write_text(
            '#include "missing.h"\nint main(void) { return 0; }\n'
        )
        layer = extract_c(tmp_path)
        by_stage = {e["stage"] for e in layer["errors"]}
        assert {"c-tests", "c-includes"} <= by_stage
        test_records = [e for e in layer["errors"] if e["stage"] == "c-tests"]
        assert any(r["path"] == "tests/prog.c" and "C-134" in r["message"] for r in test_records)
        include_records = [e for e in layer["errors"] if e["stage"] == "c-includes"]
        assert any(r["path"] == "tests" and "C-133" in r["message"] for r in include_records)


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

    def test_no_call_under_a_sizeof_or_alignof_records_a_site_and_the_controls_do(
        self, tmp_path
    ):
        # Both spellings of `sizeof`, then `_Alignof` — which takes a type
        # name, so the only call its operand can hold is a VLA's size —
        # then the two evaluated calls the drop must not reach, one of
        # them on a line an unevaluated operand shares (ADR-121 §1).
        (tmp_path / "a.c").write_text(
            "int f(int);\n"
            "int n(void);\n"
            "unsigned a = sizeof(f(1));\n"
            "unsigned b = sizeof f(1);\n"
            "unsigned c = _Alignof(int[n()]);\n"
            "int y = f(2);\n"
            "int x = f(3) + sizeof(f(1));\n"
        )
        layer = extract_c(tmp_path)
        [parsed] = [p for p in layer["files"] if p.path == "a.c"]
        assert [(c["line"], c["name"]) for c in parsed.calls] == [(6, "f"), (7, "f")]
        # The one site left on line 7 is `f(3)`, not the `f(1)` that
        # shares its line.
        [shared] = [c for c in parsed.calls if c["line"] == 7]
        assert shared["col"] == len("int x = ")

    def test_the_vla_residual_is_the_known_miss_a_call_sizing_an_array_records_nothing(
        self, tmp_path
    ):
        # C11 6.5.3.4 evaluates a `sizeof` operand whose type is a VLA, so
        # `sizeof(int[n()])` really does call `n` — the syntax cannot tell
        # a VLA type from any other, so the site goes with the rest
        # (ADR-121 §1's amendment). Asserted as today's behaviour, so a
        # later change to it is deliberate.
        (tmp_path / "a.c").write_text("int n(void);\nunsigned a = sizeof(int[n()]);\n")
        layer = extract_c(tmp_path)
        [parsed] = [p for p in layer["files"] if p.path == "a.c"]
        assert parsed.calls == []


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


class TestRegistrations:
    """The amendment (ADR-108, 2026-09-13): a registration makes a test
    before the naming convention gets a look, C-134's narrowing."""

    def test_unity_registers_in_the_same_file(self, tmp_path):
        (tmp_path / "thing.c").write_text(
            "static void test_helper(void) {}\n"
            "void thing_should_add(void) { test_helper(); }\n"
            "void thing_should_scale(void) {}\n"
            "int main(void) {\n"
            "    RUN_TEST(thing_should_add);\n"
            "    RUN_TEST(thing_should_scale);\n"
            "    return 0;\n"
            "}\n"
        )
        layer = extract_c(tmp_path)
        by_name = {t["name"]: t for t in layer["tests"]}
        assert set(by_name) == {"thing_should_add", "thing_should_scale"}
        assert all(t["framework"] == "unity" for t in by_name.values())

    def test_a_static_helper_the_registered_functions_call_is_not_a_test(self, tmp_path):
        (tmp_path / "thing.c").write_text(
            "static void test_helper(void) {}\n"
            "void thing_should_add(void) { test_helper(); }\n"
            "int main(void) { RUN_TEST(thing_should_add); return 0; }\n"
        )
        layer = extract_c(tmp_path)
        assert not any(t["name"] == "test_helper" for t in layer["tests"])

    def test_unity_runner_layout_gives_one_test_not_two(self, tmp_path):
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "TestThing.c").write_text(
            "void test_add(void) {}\nvoid test_scale(void) {}\n"
        )
        (tmp_path / "test" / "test_runners").mkdir()
        (tmp_path / "test" / "test_runners" / "TestThing_Runner.c").write_text(
            "void test_add(void);\n"
            "void test_scale(void);\n"
            "int main(void) {\n"
            "    RUN_TEST(test_add);\n"
            "    RUN_TEST(test_scale);\n"
            "    return 0;\n"
            "}\n"
        )
        layer = extract_c(tmp_path)
        ids = {t["id"] for t in layer["tests"]}
        assert ids == {"test/TestThing.c::test_add", "test/TestThing.c::test_scale"}
        assert all(t["framework"] == "unity" for t in layer["tests"])
        records = [e for e in layer["errors"] if e["stage"] == "c-tests"]
        assert not any(r["path"] == "test/test_runners/TestThing_Runner.c" for r in records)

    def test_cmocka_registrations_give_cmocka_tests_and_skip_setup_teardown(self, tmp_path):
        (tmp_path / "calc_test.c").write_text(
            "static int setup(void **state) { return 0; }\n"
            "static int teardown(void **state) { return 0; }\n"
            "static void test_add(void **state) {}\n"
            "static void test_sub(void **state) {}\n"
            "const struct CMUnitTest tests[] = {\n"
            "    cmocka_unit_test(test_add),\n"
            "    cmocka_unit_test_setup_teardown(test_sub, setup, teardown),\n"
            "};\n"
        )
        layer = extract_c(tmp_path)
        by_name = {t["name"]: t for t in layer["tests"]}
        assert set(by_name) == {"test_add", "test_sub"}
        assert all(t["framework"] == "cmocka" for t in by_name.values())

    def test_check_registration_gives_a_check_test(self, tmp_path):
        (tmp_path / "calc_test.c").write_text(
            "START_TEST(test_add)\n{\n}\nEND_TEST\n"
            "void suite(TCase *tc) {\n"
            "    tcase_add_test(tc, test_add);\n"
            "}\n"
        )
        layer = extract_c(tmp_path)
        [test] = layer["tests"]
        assert test["name"] == "test_add" and test["framework"] == "check"

    def test_a_registration_naming_a_function_defined_in_two_files_abstains(self, tmp_path):
        (tmp_path / "a.c").write_text("void dup_test(void) {}\n")
        (tmp_path / "b.c").write_text("void dup_test(void) {}\n")
        (tmp_path / "runner.c").write_text("int main(void) { RUN_TEST(dup_test); return 0; }\n")
        layer = extract_c(tmp_path)
        assert not any(t["name"] == "dup_test" for t in layer["tests"])

    def test_a_registration_naming_nothing_makes_no_test(self, tmp_path):
        (tmp_path / "runner.c").write_text("int main(void) { RUN_TEST(missing); return 0; }\n")
        layer = extract_c(tmp_path)
        assert layer["tests"] == []

    def test_no_registrations_falls_back_to_the_naming_convention(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_math.c").write_text("int test_add(void) { return 1; }\n")
        layer = extract_c(tmp_path)
        [test] = layer["tests"]
        assert test["name"] == "test_add" and test["framework"] == "c-convention"

    def test_a_test_program_with_no_nameable_test_gets_the_file_record(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "prog.c").write_text("int main(void) { return 0; }\n")
        layer = extract_c(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "c-tests"]
        [record] = [r for r in records if r["path"] == "tests/prog.c"]
        assert "C-134" in record["message"]

    def test_a_runner_with_recognized_registrations_draws_no_file_record(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "other.c").write_text("void elsewhere_test(void) {}\n")
        (tmp_path / "tests" / "runner.c").write_text(
            "void elsewhere_test(void);\n"
            "int main(void) { RUN_TEST(elsewhere_test); return 0; }\n"
        )
        layer = extract_c(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "c-tests"]
        assert not any(r["path"] == "tests/runner.c" for r in records)

    def test_unread_forms_give_one_directory_record_with_their_counts(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "crit.c").write_text(
            "Test(suite, first) {\n}\nTest(suite, second) {\n}\n"
        )
        (tmp_path / "tests" / "fix.c").write_text(
            "TEST(group, name) {\n}\n"
            "void run(TestGroup *g) { RUN_TEST_CASE(group, name); }\n"
        )
        layer = extract_c(tmp_path)
        records = [
            e for e in layer["errors"] if e["stage"] == "c-tests" and e["path"] == "tests"
        ]
        [record] = records
        assert record["message"] == (
            "3 `Test(suite, name)`/`TEST(group, name)` bodies and 1 `RUN_TEST_CASE` call "
            "in a form Hobbes does not read (C-134)"
        )

    def test_reach_works_for_a_registered_test(self, tmp_path):
        (tmp_path / "util.c").write_text(
            "static int helper(void) { return 1; }\n"
            "int add(int a, int b) { return a + b + helper(); }\n"
        )
        (tmp_path / "runner.c").write_text(
            "void test_add(void) { add(1, 2); }\n"
            "int main(void) { RUN_TEST(test_add); return 0; }\n"
        )
        layer = extract_c(tmp_path)
        edges = [
            {"from": "runner.test_add", "to": "util.add", "type": "calls"},
            {"from": "util.add", "to": "util.helper", "type": "calls"},
        ]
        [row] = collect_c_tests(layer["files"], edges)
        assert row["id"] == "runner.c::test_add"
        assert row["reaches"] == ["util.add", "util.helper"]


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

    def test_c_is_verified_on_the_graded_repos_only(self, extraction):
        # P11: C was wired, not supported, until ADR-110's oracle cells;
        # since 0.2.5-beta the base names the two repos graded and no more.
        base = extraction.graph["verification_base"]["c"]
        assert base["repos"] == 2
        assert "DaveGamble/cJSON" in base["on"] and "sqlite-vector" in base["on"]

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

    def test_the_tail_stays_inside_its_six_available_classes(self, extraction):
        # Lane A's five, plus below-floor, which C's lane B can produce (ADR-109).
        available = set(extraction.graph["tail_classes_available"]["c"])
        assert available == {
            "fallback-resolved", "local-binding", "builtin-name", "attr-call", "unclassified", "below-floor",
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
        # ADR-129's first condition, read off the walk rather than off the
        # record's message text. C's measured answer is that it mints
        # nothing (cJSON and sqlite-vector both mint zero), but the
        # condition is the layer's to report.
        assert layer["lossy_files"] == frozenset({"broken.c"})

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
