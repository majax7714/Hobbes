"""Lane A for Java (ADR-096).

The Java grammar walk, the fallback resolver, and the three things Java
adds that no earlier language forced: overloads (unique symbol ids, an
abstaining fallback), nested and anonymous classes (dotted qualnames;
closures attribute to the enclosing declaration), and an import that
names a file (in-repo `imports` edges from lane A, the Python shape).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.javasource import (
    collect_java_tests,
    extract_java,
    fqn_to_file,
    iter_java_files,
    module_id,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minijava"
APP = "src/main/java/com/example/app"
TEST = "src/test/java/com/example/app"


@pytest.fixture(scope="module")
def layer():
    return extract_java(FIXTURE)


def _sites(layer, name):
    return [s for s in layer["call_sites"] if s.name == name]


class TestDiscovery:
    def test_finds_java_files_and_prunes_build_output(self, tmp_path):
        (tmp_path / "Main.java").write_text("class Main {}\n")
        for skipped in ("target", "build", ".gradle", "node_modules", ".git"):
            directory = tmp_path / skipped
            directory.mkdir()
            (directory / "Other.java").write_text("class Other {}\n")
        assert {p.name for p in iter_java_files(tmp_path)} == {"Main.java"}

    def test_no_java_means_no_layer(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert extract_java(tmp_path) is None

    def test_module_ids_are_paths_sans_extension(self):
        assert module_id(f"{APP}/Report.java") == f"{APP}/Report"

    def test_a_type_maps_to_exactly_one_file_or_none(self, layer):
        fqn = fqn_to_file(layer["files"])
        assert fqn["com.example.app.Report"] == f"{APP}/Report.java"
        assert fqn["com.example.util.Strings"] == "src/main/java/com/example/util/Strings.java"

    def test_a_duplicated_type_is_unattributed(self, tmp_path):
        for root in ("main", "other"):
            d = tmp_path / root / "a"
            d.mkdir(parents=True)
            (d / "Dup.java").write_text("package a;\nclass Dup { void m() {} }\n")
        fqn = fqn_to_file(extract_java(tmp_path)["files"])
        assert fqn["a.Dup"] is None


class TestSymbols:
    def test_nested_types_carry_dotted_qualnames(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        assert by_id[f"{APP}/Report.Report.Line"]["kind"] == "type"
        assert by_id[f"{APP}/Report.Report.Line.text"]["kind"] == "method"

    def test_overloads_keep_unique_ids_and_a_bare_name(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        first = by_id[f"{APP}/Calculator.Calculator.add"]
        second = by_id[f"{APP}/Calculator.Calculator.add~2"]
        assert (first["name"], second["name"]) == ("add", "add")
        assert first["line"] < second["line"]

    def test_constructors_are_methods_named_after_their_type(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        # Two constructors: the chained pair, in source order.
        assert by_id[f"{APP}/Calculator.Calculator.Calculator"]["kind"] == "method"
        assert f"{APP}/Calculator.Calculator.Calculator~2" in by_id

    def test_anonymous_classes_are_below_the_floor(self, layer):
        # `new Runnable() { public void run() {..} }` inside job(): no
        # symbol for the anonymous class or its run(); its call attributes
        # to `job` (the closure rule).
        names = {s["qualname"] for s in layer["symbols"] if s["module"] == f"{APP}/Report"}
        assert "Report.job" in names
        assert not any("run" in q for q in names)
        render = [s for s in _sites(layer, "render") if s.file == f"{APP}/Report.java"]
        scopes = {s.scope for s in render}
        assert f"{APP}/Report.Report.job" in scopes
        assert f"{APP}/Report.Report.each" in scopes  # the lambda body

    def test_anonymous_class_methods_are_local_bindings_with_the_body_extent(self, layer):
        bindings = layer["local_bindings"][f"{APP}/Report.java"]
        assert {b[0] for b in bindings} == {"run", "tick"}
        [(_, start, end)] = {(b[1], b[2]) for b in bindings} and [(None, *next(iter({(b[1], b[2]) for b in bindings})))]
        text = (FIXTURE / APP / "Report.java").read_text().splitlines()
        assert "new Runnable() {" in text[start - 1] and text[end - 1].strip() == "};"

    def test_symbol_line_is_the_identifier_not_the_annotation(self, layer):
        by_id = {s["id"]: s for s in layer["symbols"]}
        area = by_id[f"{APP}/Circle.Circle.area"]
        text = (FIXTURE / APP / "Circle.java").read_text().splitlines()
        assert "double area()" in text[area["line"] - 1]


class TestImports:
    def test_an_import_of_a_repo_type_is_an_in_repo_edge(self, layer):
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert (f"{APP}/Report", "src/main/java/com/example/util/Strings", "imports") in edges

    def test_foreign_packages_become_ext_nodes(self, layer):
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert (f"{APP}/Report", "ext:java.util", "imports") in edges
        assert (f"{TEST}/CalculatorTest", "ext:org.junit.jupiter.api", "imports") in edges

    def test_the_repo_own_packages_are_never_external(self, layer):
        assert not any(n["id"].startswith("ext:com.example") for n in layer["nodes"])

    def test_static_imports_bind_names_for_the_tail(self, layer):
        assert layer["import_bindings"][f"{TEST}/CalculatorTest.java"] == {"assertEquals", "Test"}


class TestEnv:
    def test_system_getenv_joins_the_cross_layer(self, layer):
        edges = {(e["from"], e["to"], e["type"]) for e in layer["module_edges"]}
        assert (f"{APP}/Report", "env:MINIJAVA_HOME", "env-read") in edges


class TestCallSites:
    def test_positions_are_the_callee_identifier(self, layer):
        [site] = [s for s in _sites(layer, "twice") if s.file.endswith("CalculatorTest.java")]
        text = (FIXTURE / TEST / "CalculatorTest.java").read_text().splitlines()
        assert text[site.line - 1][site.col:].startswith("twice(")

    def test_constructor_sites_are_named_after_the_type(self, layer):
        circles = _sites(layer, "Circle")
        assert {s.file for s in circles} >= {f"{APP}/Report.java", f"{TEST}/CalculatorTest.java"}

    def test_this_chaining_is_a_site_and_super_is_not(self, layer):
        text = (FIXTURE / APP / "Calculator.java").read_text().splitlines()
        lines = {text[s.line - 1].strip() for s in _sites(layer, "Calculator") if s.file.endswith("Calculator.java")}
        # `this(0)` (constructor chaining) and `new Calculator()` in of().
        assert lines == {"this(0);", "return new Calculator();"}
        assert not _sites(layer, "super")

    def test_a_method_reference_is_not_a_call_site(self, layer):
        text = (FIXTURE / APP / "Report.java").read_text().splitlines()
        ref_line = next(i + 1 for i, t in enumerate(text) if "Report::render" in t)
        at = [s for s in layer["call_sites"] if s.file == f"{APP}/Report.java" and s.line == ref_line]
        assert {s.name for s in at} == {"stream", "map", "count"}

    def test_annotations_are_not_calls(self, layer):
        assert not _sites(layer, "Test") and not _sites(layer, "Override")


class TestFallback:
    def test_a_static_call_through_a_same_package_type_resolves(self, layer):
        fb = layer["call_fallback"]
        test_file = f"{TEST}/CalculatorTest.java"
        [key] = [k for k in fb if k[0] == test_file and k[2] == "render"]
        assert fb[key][0] == f"{APP}/Report.java"

    def test_a_call_into_a_type_with_supertypes_abstains_even_when_one_fits(self, layer):
        # Circle implements Shape: `area()` is declared once, but an
        # inherited overload of the same arity is indistinguishable here.
        # (The fixture's `Circle.area` has no bare call site; the rule is
        # pinned on Derived's `log` and Inner's `label` instead.)
        assert {k[2] for k in layer["inherited_sites"]} == {"log", "label"}

    def test_an_imported_type_resolves_across_packages(self, layer):
        fb = layer["call_fallback"]
        [key] = [k for k in fb if k[2] == "pad"]
        assert fb[key][0] == "src/main/java/com/example/util/Strings.java"

    def test_an_overloaded_name_is_left_to_lane_b(self, layer):
        # `add(x, x)` inside twice(): two declarations of `add` — a guess
        # would be a false edge and a false lane disagreement (ADR-096).
        assert not any(k[2] == "add" for k in layer["call_fallback"])

    def test_constructors_resolve_by_arity(self, layer):
        fb = layer["call_fallback"]
        circle = [fb[k] for k in fb if k[2] == "Circle"]
        assert circle and all(t[0] == f"{APP}/Circle.java" for t in circle)
        # Calculator has two constructors; `new Calculator()` fits only the
        # no-argument one and `this(0)` only the other.
        by_id = {s["id"]: s for s in layer["symbols"]}
        targets = sorted(fb[k][1] for k in fb if k[2] == "Calculator" and k[0].endswith("/Calculator.java"))
        assert targets == sorted([
            by_id[f"{APP}/Calculator.Calculator.Calculator"]["line"],
            by_id[f"{APP}/Calculator.Calculator.Calculator~2"]["line"],
        ])

    def test_a_type_with_no_constructor_resolves_to_the_type(self, layer):
        fb = layer["call_fallback"]
        by_id = {s["id"]: s for s in layer["symbols"]}
        [target] = [fb[k] for k in fb if k[2] == "Line"]
        assert target == (f"{APP}/Report.java", by_id[f"{APP}/Report.Report.Line"]["line"])

    def test_a_value_method_is_left_to_lane_b(self, layer):
        assert not any(k[2] == "area" for k in layer["call_fallback"])

    def test_a_method_on_a_creation_expression_resolves_through_its_type(self, layer):
        # `new Report.Line().text()`: the receiver's type is spelled, not
        # inferred — the one expression receiver lane A may read.
        fb = layer["call_fallback"]
        [target] = [fb[k] for k in fb if k[2] == "text"]
        assert target[0] == f"{APP}/Report.java"

    def test_an_anonymous_member_call_is_neither_inherited_nor_resolved(self, layer):
        # Report.job(): `tick()` inside the anonymous Runnable — bound by
        # the body, so not a fallback target and not "inherited".
        assert not any(k[2] == "tick" for k in layer["call_fallback"])
        assert not any(k[2] == "tick" for k in layer["inherited_sites"])

    def test_the_abstained_sites_are_reported(self, layer):
        names = {k[2] for k in layer["overload_sites"]}
        assert names == {"add"}
        assert {k[2] for k in layer["inherited_sites"]} == {"log", "label"}

    def test_an_inherited_overload_is_not_bound_to_the_local_one(self, layer):
        # Shapes.Derived: `log(s, 1)` — the local `log(String)` takes one
        # argument; the callee is Base's. Arity rules the local one out.
        assert not any(k[2] == "log" for k in layer["call_fallback"])

    def test_an_inner_class_with_a_superclass_does_not_reach_the_outer_name(self, layer):
        # Derived.Inner extends Base: `label()` is the inherited one, not
        # `Shapes.label()` — the walk stops at a type with supertypes.
        assert not any(k[2] == "label" for k in layer["call_fallback"])

    def test_anonymous_creation_is_not_a_call_site(self, layer):
        text = (FIXTURE / APP / "Shapes.java").read_text().splitlines()
        line = next(i + 1 for i, t in enumerate(text) if "new Shape() {" in t)
        assert not any(s.line == line for s in layer["call_sites"] if s.file == f"{APP}/Shapes.java")

    def test_a_foreign_static_import_resolves_nothing(self, layer):
        assert not any(k[2] == "assertEquals" for k in layer["call_fallback"])


class TestTests:
    def test_junit_methods_are_the_inventory(self, layer):
        ids = {t["id"] for t in layer["tests"]}
        assert f"{TEST}/CalculatorTest.java::CalculatorTest.addsInts" in ids
        assert all(t["framework"] == "junit" for t in layer["tests"])

    def test_reach_is_the_closure_over_calls_edges(self, layer):
        mid = f"{TEST}/CalculatorTest"
        edges = [
            {"from": f"{mid}.CalculatorTest.rendersACircle", "to": f"{APP}/Report.Report.render", "type": "calls"},
            {"from": f"{APP}/Report.Report.render", "to": f"{APP}/Shape.Shape.area", "type": "calls"},
            {"from": f"{APP}/Report.Report.render", "to": f"{APP}/Circle.Circle", "type": "uses"},
        ]
        [test] = [t for t in collect_java_tests(layer["files"], edges) if t["id"].endswith("rendersACircle")]
        assert test["reaches"] == [f"{APP}/Report.Report.render", f"{APP}/Shape.Shape.area"]
        assert test["reaches_modules"] == [f"{APP}/Report", f"{APP}/Shape"]


class TestIngest:
    """The J.M1 exit: the fixture ingests to a syntactic-tier graph with
    every planted site detected and nothing `unclassified` in the tail."""

    @pytest.fixture(scope="class")
    def out(self):
        os.environ["HOBBES_SCIP"] = "0"
        try:
            return extract_repo(FIXTURE)
        finally:
            os.environ.pop("HOBBES_SCIP", None)

    def test_the_language_is_claimed_and_unverified_is_stated(self, out):
        assert out.graph["languages"] == ["java"]
        assert "java" in out.graph["verification_base"]

    def test_every_edge_is_syntactic_and_the_fallback_ones_exist(self, out):
        calls = [e for e in out.graph["symbol_edges"] if e["type"] == "calls"]
        assert calls and all(e["tier"] == "syntactic" for e in calls)
        pairs = {(e["from"], e["to"]) for e in calls}
        assert (f"{TEST}/CalculatorTest.CalculatorTest.rendersACircle", f"{APP}/Report.Report.render") in pairs
        assert (f"{APP}/Report.Report.Line.text", "src/main/java/com/example/util/Strings.Strings.pad") in pairs

    def test_nothing_in_the_tail_is_unclassified(self, out):
        for row in out.graph["resolution_coverage"]:
            assert "unclassified" not in row.get("tail", {}), row
        assert out.graph["tail_classes_available"]["java"] == [
            "fallback-resolved", "local-binding", "import-binding", "builtin-name",
            "attr-call", "overload-set", "inherited-member", "unclassified", "below-floor",
        ]

    def test_a_call_of_an_anonymous_member_is_a_local_binding(self, out):
        [row] = [r for r in out.graph["resolution_coverage"] if r["file"].endswith("/Report.java")]
        assert row["tail"].get("local-binding") == 1

    def test_a_java_lang_type_is_a_builtin_name(self, out):
        # `new Runnable() {..}` in job(): java.lang, imported by no statement.
        [row] = [r for r in out.graph["resolution_coverage"] if r["file"].endswith("/Report.java")]
        assert row["tail"].get("builtin-name") == 1

    def test_overload_abstentions_are_named_not_unknown(self, out):
        # Calculator.java: `add(x, x)` fits both overloads — lane A says
        # so; `this(0)` and `new Calculator()` each fit one constructor.
        [row] = [r for r in out.graph["resolution_coverage"] if r["file"].endswith("/Calculator.java")]
        assert row["tail"] == {"fallback-resolved": 2, "overload-set": 1}

    def test_inherited_callees_are_named_not_unknown(self, out):
        [row] = [r for r in out.graph["resolution_coverage"] if r["file"].endswith("/Shapes.java")]
        assert row["tail"] == {"inherited-member": 2}

    def test_the_static_import_classifies_as_import_binding(self, out):
        [row] = [r for r in out.graph["resolution_coverage"] if r["file"].endswith("CalculatorTest.java")]
        assert row["tail"].get("import-binding") == 3

    def test_tests_reach_through_the_syntactic_edges(self, out):
        by_id = {t["id"]: t for t in out.tests["tests"]}
        t = by_id[f"{TEST}/CalculatorTest.java::CalculatorTest.padsThroughTheNestedClass"]
        assert "src/main/java/com/example/util/Strings.Strings.pad" in t["reaches"]


class TestDegradation:
    def test_an_unparseable_file_does_not_take_the_layer_down(self, tmp_path):
        (tmp_path / "Ok.java").write_text("package p;\nclass Ok { void m() { n(); } void n() {} }\n")
        (tmp_path / "Broken.java").write_text("class { {{{ )\n")
        layer = extract_java(tmp_path)
        assert layer is not None
        assert any(s["qualname"] == "Ok.n" for s in layer["symbols"])
        assert layer["errors"] == []
