"""Lane A for C++ — the eighth walk's first unit (ADR-113 §1).

No lane B exists for C++ yet, so every edge here is the fallback's, at
`syntactic` tier, and the fixture is built to exercise what C++ adds over
C: the ``.h`` claim, namespaces and members in a qualname, the five
callee shapes, the overload sets a tie abstains on, and the two test
idioms whose macros the parse reads very differently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hobbes.extract import tail
from hobbes.extract.cppsource import (
    collect_cpp_tests,
    extract_cpp,
    has_cpp_files,
    iter_cpp_files,
    module_id,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minicpp"


@pytest.fixture(scope="module")
def layer():
    return extract_cpp(FIXTURE)


def _write(root: Path, files: dict[str, str]) -> Path:
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return root


def _symbols(layer):
    return {s["id"]: s for s in layer["symbols"]}


def _calls(layer, path):
    return [
        parsed for parsed in layer["files"] if parsed.path == path
    ][0].calls


def _call_at(layer, path, line, name):
    hits = [c for c in _calls(layer, path) if c["line"] == line and c["name"] == name]
    assert len(hits) == 1, (path, line, name, hits)
    return hits[0]


class TestDiscovery:
    def test_the_six_extensions_are_cpp_and_the_walk_prunes_like_every_other(self, tmp_path):
        for ext in ("cpp", "cc", "cxx", "hpp", "hh", "hxx"):
            (tmp_path / f"a.{ext}").write_text("int f() { return 0; }\n")
        for skipped in ("build", ".git", "node_modules", "cmake-build-debug"):
            directory = tmp_path / skipped
            directory.mkdir()
            (directory / "other.cpp").write_text("int other() { return 0; }\n")
        found = {p.name for p in iter_cpp_files(tmp_path)}
        assert found == {"a.cpp", "a.cc", "a.cxx", "a.hpp", "a.hh", "a.hxx"}

    def test_a_plain_h_is_not_discovered_by_extension(self, tmp_path):
        # It is claimed, or left to C — never taken on its name alone.
        (tmp_path / "a.h").write_text("int f();\n")
        assert list(iter_cpp_files(tmp_path)) == []

    def test_detection_is_the_same_question_asked_cheaply(self, tmp_path):
        assert has_cpp_files(FIXTURE) is True
        (tmp_path / "a.c").write_text("int f(void) { return 0; }\n")
        assert has_cpp_files(tmp_path) is False

    def test_a_repo_with_no_cpp_has_no_layer(self, tmp_path):
        (tmp_path / "a.c").write_text("int f(void) { return 0; }\n")
        (tmp_path / "a.h").write_text("int f(void);\n")
        assert extract_cpp(tmp_path) is None

    def test_a_linked_copy_is_not_discovered_twice(self, tmp_path):
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "a.cpp").write_text("int a() { return 0; }\n")
        (tmp_path / "shared").symlink_to(tmp_path / "core", target_is_directory=True)
        found = sorted(str(p.relative_to(tmp_path)) for p in iter_cpp_files(tmp_path))
        assert found == ["core/a.cpp"]


class TestTheHeaderClaim:
    def test_a_repo_with_no_c_sources_claims_every_header(self, tmp_path):
        _write(tmp_path, {
            "src/a.cpp": '#include "a.h"\nint f() { return 1; }\n',
            "src/a.h": "int f();\n",
            "nobody/includes.h": "int g();\n",
        })
        layer = extract_cpp(tmp_path)
        # Case (a): no `.c` anywhere, so even a header nothing includes is
        # C++'s — there is no other language to read it.
        assert layer["claimed_headers"] == {"src/a.h", "nobody/includes.h"}

    def test_a_header_only_a_cpp_source_includes_is_claimed(self, tmp_path):
        _write(tmp_path, {
            "src/a.cpp": '#include "shared.h"\nint f() { return 1; }\n',
            "src/shared.h": "int f();\n",
            "src/b.c": '#include "plain.h"\nint g(void) { return 1; }\n',
            "src/plain.h": "int g(void);\n",
            "src/lonely.h": "int h(void);\n",
        })
        layer = extract_cpp(tmp_path)
        # Case (b): the C header and the header neither language includes
        # both stay C — a claim needs evidence, not an absence of it.
        assert layer["claimed_headers"] == {"src/shared.h"}

    def test_a_header_both_languages_include_stays_c(self, tmp_path):
        _write(tmp_path, {
            "src/a.cpp": '#include "both.h"\nint f() { return 1; }\n',
            "src/b.c": '#include "both.h"\nint g(void) { return 1; }\n',
            "src/both.h": "int g(void);\n",
        })
        layer = extract_cpp(tmp_path)
        assert layer["claimed_headers"] == set()

    def test_the_mixed_repo_record_says_where_the_headers_went(self, tmp_path):
        _write(tmp_path, {
            "src/a.cpp": '#include "both.h"\n#include "mine.h"\n',
            "src/b.c": '#include "both.h"\n',
            "src/both.h": "int g(void);\n",
            "src/mine.h": "int h();\n",
        })
        layer = extract_cpp(tmp_path)
        records = [e for e in layer["errors"] if e["stage"] == "cpp-headers"]
        assert len(records) == 1
        assert "1 `.h` read as C++ and 1 as C" in records[0]["message"]
        assert "included from both languages and left to C (src/both.h)" in records[0]["message"]

    def test_a_repo_of_one_language_gets_no_record(self, layer):
        assert [e for e in layer["errors"] if e["stage"] == "cpp-headers"] == []


class TestModuleIds:
    def test_a_source_drops_its_extension(self):
        for name in ("src/shapes.cpp", "src/shapes.cc", "src/shapes.cxx"):
            assert module_id(name) == "src/shapes"

    def test_a_header_keeps_its_extension(self):
        assert module_id("src/util.h") == "src/util.h"
        assert module_id("src/util.hpp") == "src/util.hpp"

    def test_the_fixture_pair_does_not_collide(self, layer):
        ids = {n["id"] for n in layer["nodes"]}
        assert {"src/util", "src/util.h"} <= ids

    def test_a_cpp_source_beside_a_c_source_of_one_stem_is_recorded(self, tmp_path):
        _write(tmp_path, {
            "src/foo.cpp": "int f() { return 1; }\n",
            "src/foo.c": "int g(void) { return 1; }\n",
        })
        layer = extract_cpp(tmp_path)
        records = [e for e in layer["errors"] if "C-15" in e["message"]]
        assert len(records) == 1
        assert records[0]["path"] == "src/foo.cpp"
        assert "'src/foo'" in records[0]["message"]


class TestSymbols:
    def test_the_fixture_header_holds_exactly_these_symbols(self, layer):
        header = {
            s["qualname"]: s["kind"]
            for s in layer["symbols"]
            if s["module"] == "include/minicpp/shapes.h"
        }
        assert header == {
            "TWICE": "macro",                  # the function-like macro
            "shapes::Shape": "type",
            "shapes::Shape::~Shape": "method",   # the destructor, named by its class
            "shapes::Shape::doubled": "method",  # defined in the class body
            "shapes::Circle": "type",
            "shapes::Circle::Circle": "method",  # the constructor, named by its class
            "shapes::Circle::radius": "method",
            "shapes::largest": "function",       # the template, once
        }

    def test_declarations_are_never_symbols(self, layer):
        names = {s["qualname"] for s in layer["symbols"]}
        # `static int unit();` and `virtual int area() const;` are declared
        # in the class and defined in the source; both `area` prototypes
        # likewise; `int scale(int)` in util.h.
        assert "shapes::area" not in {
            s["qualname"] for s in layer["symbols"] if s["module"] == "include/minicpp/shapes.h"
        }
        assert not [s for s in layer["symbols"] if s["module"] == "src/util.h"]
        assert "MINICPP_VERSION" not in names  # an object-like macro
        assert "MINICPP_SHAPES_H" not in names  # the include guard

    def test_an_out_of_line_member_is_a_method_under_its_class(self, layer):
        by_id = _symbols(layer)
        assert by_id["src/shapes.shapes::Circle::area"]["kind"] == "method"
        assert by_id["src/shapes.shapes::Circle::unit"]["kind"] == "method"

    def test_a_free_function_in_a_namespace_is_a_function(self, layer):
        by_id = _symbols(layer)
        assert by_id["src/shapes.shapes::measure"]["kind"] == "function"
        assert by_id["src/shapes.shapes::bump"]["static"] is True

    def test_a_namespace_qualified_definition_is_not_a_member(self, tmp_path):
        # `void ns::f() {}` is a free function; `Vec Vec::f() {}` a method.
        # The qualifier alone cannot tell them apart — the repo's own
        # namespaces do.
        _write(tmp_path, {"a.cpp": (
            "namespace ns {\n"
            "class Vec {\n"
            "public:\n"
            "    int size() const;\n"
            "};\n"
            "int Vec::size() const { return 0; }\n"
            "}\n"
            "void ns::free_one() {}\n"
        )})
        by_id = _symbols(extract_cpp(tmp_path))
        assert by_id["a.ns::Vec::size"]["kind"] == "method"
        assert by_id["a.ns::free_one"]["kind"] == "function"

    def test_the_type_kinds_are_the_five_that_declare_one(self, tmp_path):
        _write(tmp_path, {"a.cpp": (
            "typedef int Integer;\n"
            "using Alias = double;\n"
            "struct Point { int x; };\n"
            "union U { int a; };\n"
            "enum class Color { Red };\n"
            "enum Plain { One };\n"
            "struct Bare;\n"
        )})
        layer = extract_cpp(tmp_path)
        assert {s["qualname"]: s["kind"] for s in layer["symbols"]} == {
            "Integer": "type", "Alias": "type", "Point": "type",
            "U": "type", "Color": "type", "Plain": "type",
        }  # `struct Bare;` has no body and declares nothing

    def test_a_constructor_a_destructor_and_an_operator_are_named_as_written(self, tmp_path):
        _write(tmp_path, {"a.cpp": (
            "class Vec {\n"
            "public:\n"
            "    Vec() {}\n"
            "    ~Vec() {}\n"
            "    Vec operator+(const Vec &o) const;\n"
            "};\n"
            "Vec Vec::operator+(const Vec &o) const { return *this; }\n"
        )})
        kinds = {s["qualname"]: s["kind"] for s in extract_cpp(tmp_path)["symbols"]}
        assert kinds["Vec::Vec"] == "method"
        assert kinds["Vec::~Vec"] == "method"
        assert kinds["Vec::operator+"] == "method"

    def test_a_template_is_its_entity_once_at_the_entity_s_line(self, layer):
        template = [s for s in layer["symbols"] if s["name"] == "largest"]
        assert len(template) == 1
        # `template <typename T>` opens line 27; `T largest(T a, T b)` is 28,
        # which is where clang puts a specialisation too.
        assert template[0]["line"] == 28

    def test_each_overload_of_the_fixture_pair_is_its_own_symbol(self, layer):
        # C-144's fix (ADR-113 §2): C's rule kept `int area(int)` and lost
        # `int area(double)`, so lane B's answer to the second landed below
        # the floor. Different parameters, so two symbols, in source order.
        by_id = _symbols(layer)
        assert (by_id["src/shapes.shapes::area"]["line"],
                by_id["src/shapes.shapes::area"]["kind"]) == (23, "function")
        assert (by_id["src/shapes.shapes::area~2"]["line"],
                by_id["src/shapes.shapes::area~2"]["kind"]) == (27, "function")
        # The bare name never moves: it is what a call site spells.
        assert by_id["src/shapes.shapes::area~2"]["name"] == "area"

    def test_an_overload_set_draws_no_duplicate_record(self, layer):
        assert [e for e in layer["errors"] if "defined more than once" in e["message"]] == []

    def test_a_pair_of_one_signature_keeps_the_first_and_says_so(self, tmp_path):
        # The preprocessor never runs, so both arms are parsed; they take
        # the same parameters, so they are alternatives, not overloads.
        _write(tmp_path, {"a.cpp": (
            "#ifdef FAST\n"
            "int pick(int n) { return n; }\n"
            "#else\n"
            "int pick(int n) { return n + 1; }\n"
            "#endif\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(s["qualname"], s["line"]) for s in layer["symbols"]] == [("pick", 2)]
        [record] = [e for e in layer["errors"] if e["stage"] == "parse"]
        assert record["message"] == (
            "pick defined more than once with the same parameters in a.cpp "
            "(preprocessor alternatives); calls to them are left unresolved "
            "rather than guessed"
        )

    def test_an_overloaded_constructor_pair_is_two_methods(self, tmp_path):
        _write(tmp_path, {"a.cpp": (
            "class Vec {\n"
            "public:\n"
            "    Vec() {}\n"
            "    Vec(int n) : n_(n) {}\n"
            "    int n_;\n"
            "};\n"
        )})
        kinds = {s["qualname"]: s["kind"] for s in extract_cpp(tmp_path)["symbols"]}
        assert kinds["Vec::Vec"] == "method" and kinds["Vec::Vec~2"] == "method"

    def test_a_const_and_a_non_const_method_of_one_name_are_two(self, tmp_path):
        # The trailing qualifiers are part of the signature: `get()` and
        # `get() const` are two functions, and C++ picks between them.
        _write(tmp_path, {"a.cpp": (
            "struct Box {\n"
            "    int get() { return 1; }\n"
            "    int get() const { return 2; }\n"
            "};\n"
        )})
        lines = {s["qualname"]: s["line"] for s in extract_cpp(tmp_path)["symbols"]}
        assert lines["Box::get"] == 2 and lines["Box::get~2"] == 3

    def test_a_namespace_and_a_lambda_are_not_symbols(self, layer):
        names = {s["qualname"] for s in layer["symbols"]}
        assert "shapes" not in names
        assert "scaled" not in names  # the lambda bound in `measure`


class TestCallSites:
    def test_a_plain_call_is_named_by_its_identifier(self, layer):
        assert _call_at(layer, "src/shapes.cpp", 16, "bump")["shape"] == "plain"

    def test_a_macro_invocation_parses_as_a_plain_call(self, layer):
        # The preprocessor never runs here, so tree-sitter cannot tell a
        # macro from a function — and neither needs to.
        assert _call_at(layer, "src/shapes.cpp", 35, "TWICE")["shape"] == "plain"

    def test_a_qualified_call_carries_its_qualifiers(self, layer):
        call = _call_at(layer, "src/main.cpp", 8, "area")
        assert (call["shape"], call["qualifiers"]) == ("qualified", ("shapes",))

    def test_a_template_argument_list_is_dropped_from_the_name(self, layer):
        # `shapes::largest<int>(..)` is a site on `largest`.
        call = _call_at(layer, "src/main.cpp", 10, "largest")
        assert (call["shape"], call["qualifiers"]) == ("qualified", ("shapes",))

    def test_member_calls_through_dot_arrow_and_this_are_one_shape(self, layer):
        assert _call_at(layer, "src/main.cpp", 11, "area")["shape"] == "member"
        assert _call_at(layer, "src/shapes.cpp", 33, "area")["shape"] == "member"
        assert _call_at(layer, "src/shapes.cpp", 16, "radius")["shape"] == "member"

    def test_a_dereferenced_function_pointer_is_a_call_through_a_value(self, layer):
        assert _call_at(layer, "src/shapes.cpp", 34, "fp")["shape"] == "deref"

    def test_both_constructions_are_named_by_the_type_s_terminal(self, layer):
        # `Circle made(2)` and `new Circle(1)`, so the two lanes meet on
        # the class name (Java's rule, ADR-096).
        assert _call_at(layer, "src/shapes.cpp", 38, "Circle")["shape"] == "construct"
        assert _call_at(layer, "src/shapes.cpp", 39, "Circle")["shape"] == "construct"
        assert _call_at(layer, "src/main.cpp", 7, "Circle")["qualifiers"] == ("shapes",)

    def test_an_operator_applied_by_symbol_is_not_a_site(self, tmp_path):
        _write(tmp_path, {"a.cpp": "struct V {};\nV add(V a, V b) { return a + b; }\n"})
        layer = extract_cpp(tmp_path)
        assert [c["name"] for c in _calls(layer, "a.cpp")] == []

    def test_a_named_cast_is_not_a_call(self, tmp_path):
        _write(tmp_path, {"a.cpp": "int f(double d) { return static_cast<int>(d); }\n"})
        layer = extract_cpp(tmp_path)
        assert [c["name"] for c in _calls(layer, "a.cpp")] == []

    def test_a_call_in_a_lambda_body_attributes_to_the_enclosing_function(self, layer):
        assert _call_at(layer, "src/shapes.cpp", 36, "bump")["scope"] == "shapes::measure"

    def test_a_site_is_positioned_on_its_terminal_identifier(self, layer):
        call = _call_at(layer, "src/shapes.cpp", 41, "unit")
        # `    int one = Circle::unit();` — the column of `unit`, not of
        # `Circle`, so lane B's occurrence will key on the same range.
        assert call["col"] == 22

    def test_no_shape_of_unevaluated_operand_records_a_site_and_the_controls_do(self, tmp_path):
        # Every context the grammar spells differently (ADR-121's table),
        # one per line, then the two evaluated calls the drop must not
        # reach — one of them on a line an unevaluated operand shares.
        _write(tmp_path, {"a.cpp": (
            "int f(int);\n"
            "template <class T> struct H {};\n"
            "int a = sizeof(f(1));\n"
            "int b = sizeof f(1);\n"
            "int c = alignof(decltype(f(1)));\n"
            "H<decltype(f(1))> h;\n"
            "auto g() -> decltype(f(1));\n"
            "using A = decltype(f(1));\n"
            "bool nb = noexcept(f(1));\n"
            "void h2() noexcept(noexcept(f(1)));\n"
            "template <class T> requires requires { f(1); } void t(T);\n"
            "int y = f(2);\n"
            "int x = f(3) + sizeof(f(1));\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(c["line"], c["name"]) for c in _calls(layer, "a.cpp")] == [
            (12, "f"), (13, "f"),
        ]

    def test_noexcept_and_typeid_are_keywords_not_callees(self, tmp_path):
        # The grammar spells both as a call of a bare identifier; only
        # `typeid`'s operand is evaluated, so only its `f` is a site.
        _write(tmp_path, {"a.cpp": (
            "int f(int);\n"
            "bool b = noexcept(f(1));\n"
            "auto& t = typeid(f(1));\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(c["line"], c["name"]) for c in _calls(layer, "a.cpp")] == [(3, "f")]

    def test_a_constant_expression_is_evaluated_and_keeps_its_sites(self, tmp_path):
        # A `static_assert` and a `noexcept` *specifier*'s own condition are
        # both evaluated — by the compiler, not at run time, but evaluated.
        _write(tmp_path, {"a.cpp": (
            "constexpr bool g() { return true; }\n"
            'static_assert(g(), "");\n'
            "void h() noexcept(g());\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(c["line"], c["name"]) for c in _calls(layer, "a.cpp")] == [
            (2, "g"), (3, "g"),
        ]

    def test_a_construction_and_a_new_inside_a_decltype_record_nothing(self, tmp_path):
        _write(tmp_path, {"a.cpp": (
            "struct A { A(int); };\n"
            "using D1 = decltype(A(1));\n"
            "using D2 = decltype(new A(1));\n"
            "A a(2);\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(c["line"], c["name"]) for c in _calls(layer, "a.cpp")] == [(4, "A")]

    def test_lane_b_s_occurrence_at_a_dropped_site_is_a_use_and_not_a_call(
        self, tmp_path, monkeypatch
    ):
        """ADR-121 §2, through the whole ingest: the reference is real — the
        file needs `f`'s declaration to type-check — so it falls through as
        a `uses` edge, as every resolution no syntax site claims does. Lane
        B is hand-built here, as in :class:`TestTheWithheldFallback`."""
        from hobbes.extract import evidence as ev, extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {
            "src/lib.h": "inline int f(int x) { return x; }\n",
            "src/use.cpp": (
                '#include "lib.h"\n'
                "\n"
                "int use() {\n"
                "    return (int) sizeof(f(1));\n"
                "}\n"
            ),
        })
        facts = {
            "language": "cpp",
            "definitions": [],
            # `f` at use.cpp:4, inside the `sizeof` — the column of `f`.
            "references": [ev.Site(
                provider=ev.SCIP, kind=ev.RESOLUTION,
                file="src/use.cpp", line=4, col=24, name="f",
                def_file="src/lib.h", def_line=1,
            )],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        graph = extract_repo(tmp_path).graph
        at_site = [
            edge for edge in graph["symbol_edges"]
            if any(
                (site["path"], site["line"]) == ("src/use.cpp", 4)
                for site in edge["evidence"]
            )
        ]
        assert [edge["type"] for edge in at_site] == ["uses"]
        assert at_site[0]["tier"] == "semantic"
        assert (at_site[0]["from"], at_site[0]["to"]) == ("src/use.use", "src/lib.h.f")


class TestTheWrittenSpecialisation:
    """ADR-125: the projection abstains where a call is written through
    one explicit specialisation and lane B answers with another's member.
    This walk records the two facts that rule reads, and nothing else —
    the qualifier as written, and which classes are ``template <>``."""

    SOURCE = (
        "namespace ns {\n"
        "template <typename T> struct S { void format() {} };\n"
        "template <> struct S<0> { void format() {} };\n"
        "template <typename T> struct S<std::vector<T>> { void format() {} };\n"
        "}\n"
        "template <typename T> T ident(T t) { return t; }\n"
        "void g() {\n"
        "    ns::S<20>::format();\n"
        "    ns::f();\n"
        "    ident<int>(1);\n"
        "}\n"
    )

    @pytest.fixture
    def built(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        layer = extract_cpp(tmp_path)
        return layer, {(s.line, s.name): s for s in layer["call_sites"]}

    def test_a_qualifier_carrying_template_arguments_is_recorded_as_written(self, built):
        _, sites = built
        # The immediate qualifier, not the chain: `ns::S<20>::format()`.
        assert sites[(8, "format")].qualifier == "S<20>"

    def test_a_namespace_qualifier_and_a_template_callee_record_none(self, built):
        _, sites = built
        # `ns::` carries no arguments, and `ident<int>`'s are the
        # callee's own — neither names a class the index could contradict.
        assert sites[(9, "f")].qualifier == ""
        assert sites[(10, "ident")].qualifier == ""

    def test_only_an_explicit_full_specialisation_is_recorded_as_one(self, built):
        layer, _ = built
        # The primary and the partial both spell parameters rather than
        # concrete arguments, so a resolution differing from the written
        # text is right there — ADR-125's amendment, the two cases the
        # measurement never met.
        assert {s["id"] for s in layer["symbols"] if s["kind"] == "type"} == {
            "a.ns::S", "a.ns::S<0>", "a.ns::S<std::vector<T>>",
        }
        assert layer["full_specializations"] == frozenset({"a.ns::S<0>"})


class TestTheFallback:
    def test_the_unique_free_function_repo_wide_resolves(self, layer):
        assert layer["call_fallback"][("src/main.cpp", 9, "scale")] == ("src/util.cpp", 3)

    def test_a_same_file_definition_resolves(self, layer):
        assert layer["call_fallback"][("src/shapes.cpp", 16, "bump")] == ("src/shapes.cpp", 7)

    def test_a_macro_in_a_directly_included_header_resolves(self, layer):
        assert layer["call_fallback"][("src/shapes.cpp", 35, "TWICE")] == (
            "include/minicpp/shapes.h", 5,
        )

    def test_a_qualified_call_resolves_through_the_enclosing_scope(self, layer):
        # Written `Circle::unit()` inside `namespace shapes`, so the
        # qualname it means is `shapes::Circle::unit`.
        assert layer["call_fallback"][("src/shapes.cpp", 41, "unit")] == ("src/shapes.cpp", 19)

    def test_the_overload_pair_abstains_and_says_so(self, layer):
        # `shapes::area` has two definitions; a tie is an overload set,
        # and only argument types can pick one.
        assert ("src/main.cpp", 8, "area") not in layer["call_fallback"]
        assert ("src/main.cpp", 8, "area") in layer["overload_sites"]

    def test_an_unqualified_overloaded_name_abstains_too(self, layer):
        assert ("include/minicpp/shapes.h", 13, "area") in layer["overload_sites"]

    def test_a_member_call_is_never_resolved(self, layer):
        # `c.radius()` has a definition of that very name in the graph;
        # the receiver's type is lane B's to know.
        assert ("src/shapes.cpp", 32, "radius") not in layer["call_fallback"]
        assert ("src/shapes.cpp", 32, "radius") not in layer["overload_sites"]

    def test_a_lambda_binding_is_never_resolved(self, layer):
        assert ("src/shapes.cpp", 37, "scaled") not in layer["call_fallback"]
        assert ("scaled", 31, 45) in layer["local_bindings"]["src/shapes.cpp"]

    def test_a_function_pointer_parameter_is_never_resolved(self, layer):
        assert ("fp", 31, 45) in layer["local_bindings"]["src/shapes.cpp"]
        assert ("src/shapes.cpp", 34, "fp") not in layer["call_fallback"]

    def test_a_construction_is_left_to_lane_b(self, layer):
        assert ("src/shapes.cpp", 39, "Circle") not in layer["call_fallback"]

    def test_a_name_with_no_definition_anywhere_is_not_an_overload_set(self, tmp_path):
        _write(tmp_path, {"a.cpp": "int f() { return nowhere(); }\n"})
        layer = extract_cpp(tmp_path)
        assert layer["call_fallback"] == {}
        assert layer["overload_sites"] == set()


class TestTheTail:
    def test_every_qualified_site_carries_its_first_qualifier(self, layer):
        assert layer["qualified_sites"][("src/shapes.cpp", 42, "move")] == "std"
        assert layer["qualified_sites"][("src/main.cpp", 8, "area")] == "shapes"

    def test_the_fixture_tail_stays_inside_the_cpp_row(self):
        from hobbes.extract import extract_repo

        graph = extract_repo(FIXTURE).graph
        available = set(graph["tail_classes_available"]["cpp"])
        assert available == set(tail.CLASSES_AVAILABLE["cpp"])
        for row in graph["resolution_coverage"]:
            assert row["language"] == "cpp", row  # every file, headers included
            assert set(row.get("tail", {})) <= available, row

    def test_the_standard_library_reads_as_a_builtin_name(self):
        from hobbes.extract import extract_repo

        graph = extract_repo(FIXTURE).graph
        rows = {row["file"]: row for row in graph["resolution_coverage"]}
        # `std::move` in shapes.cpp; `std::printf` twice in main.cpp.
        assert rows["src/shapes.cpp"]["tail"]["builtin-name"] == 1
        assert rows["src/main.cpp"]["tail"]["builtin-name"] == 2


class TestTheWithheldFallback:
    """Rule 2 of ADR-113 §2's third amendment, through the whole ingest: a
    C++ file lane B compiled draws no fallback edge. Lane B is hand-built
    here — the real one needs scip-clang and a container — so what is under
    test is the wiring: which files the set holds, what the join then does
    with them, and that the self-test is not narrowed by it."""

    @staticmethod
    def _graph(monkeypatch, references):
        from hobbes.extract import evidence as ev, extract_repo
        import hobbes.extract as extract

        facts = {
            "language": "cpp",
            "definitions": [],
            # Resolution sites, as the facts file is read into (ADR-116).
            "references": [ev.Site(provider=ev.SCIP, kind=ev.RESOLUTION, **ref) for ref in references],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(FIXTURE).graph

    #: One reference, into the file the rule must withhold: `scale(3)` at
    #: main.cpp:9, where lane A guesses the same definition.
    SCALE = [{
        "file": "src/main.cpp", "line": 9, "col": 17, "name": "scale",
        "def_file": "src/util.cpp", "def_line": 3,
    }]

    def _calls(self, graph):
        return {
            (e["from"], e["to"]): e
            for e in graph["symbol_edges"]
            if e["type"] == "calls"
        }

    def test_a_guess_in_a_file_lane_b_indexed_is_gone_counted_and_recorded(self, monkeypatch):
        graph = self._graph(monkeypatch, self.SCALE)
        calls = self._calls(graph)
        # main.cpp:10's `shapes::largest<int>` — lane B answered nothing
        # there, and main.cpp is a file it compiled.
        assert ("src/main.main", "include/minicpp/shapes.h.shapes::largest") not in calls
        withheld = graph["lane_agreement"]["cpp_withheld"]
        assert withheld["sites"] == 1
        assert withheld["examples"] == [{
            "file": "src/main.cpp", "line": 10, "name": "largest",
            "lane_a": "include/minicpp/shapes.h:28",
        }]
        record = [
            e for e in graph["extraction_errors"] if e["stage"] == "cpp-fallback"
        ]
        assert len(record) == 1 and record[0]["path"] == "."
        assert record[0]["message"].startswith("1 lane A guess(es) withheld in C++ files")
        assert "(ADR-113 §2, C-152)" in record[0]["message"]

    def test_lane_b_s_own_answer_in_that_file_still_draws_its_edge(self, monkeypatch):
        calls = self._calls(self._graph(monkeypatch, self.SCALE))
        assert calls[("src/main.main", "src/util.scale")]["tier"] == "semantic"

    def test_a_cpp_file_the_facts_do_not_touch_keeps_its_fallback(self, monkeypatch):
        # C-135's C++ face: lane B never compiled shapes.cpp here, so its
        # floor stands exactly as it did before the rule.
        calls = self._calls(self._graph(monkeypatch, self.SCALE))
        edge = calls[("src/shapes.shapes::measure", "include/minicpp/shapes.h.shapes::largest")]
        assert edge["tier"] == "syntactic"

    def _tail(self, monkeypatch, references):
        rows = {
            row["file"]: row
            for row in self._graph(monkeypatch, references)["resolution_coverage"]
        }
        return rows["src/main.cpp"]["tail"]

    def test_the_withheld_site_classes_as_one_lane_a_had_no_guess_for(self, monkeypatch):
        # Without lane B, main.cpp's two guesses read `fallback-resolved`.
        # With it, `scale` is resolved and `largest` is withheld — and a
        # withheld site must not still read as one lane A answered.
        assert self._tail(monkeypatch, [])["fallback-resolved"] == 2
        tail_row = self._tail(monkeypatch, self.SCALE)
        assert "fallback-resolved" not in tail_row
        # It is counted where its shape earns, one class over.
        assert tail_row["unclassified"] == 2

    def test_sites_compared_does_not_drop_because_of_the_rule(self, monkeypatch):
        # The self-test is fed the whole fallback: where both lanes answered
        # main.cpp:9 they are still compared, and still agree.
        agreement = self._graph(monkeypatch, self.SCALE)["lane_agreement"]
        assert agreement["sites_compared"] == 1
        assert agreement["site_disagreements"] == []

    def test_an_ingest_with_no_lane_b_withholds_nothing(self, monkeypatch):
        graph = self._graph(monkeypatch, [])
        assert graph["lane_agreement"]["cpp_withheld"] == {"sites": 0, "examples": []}
        errors = graph.get("extraction_errors", [])
        assert [e for e in errors if e["stage"] == "cpp-fallback"] == []
        assert ("src/main.main", "include/minicpp/shapes.h.shapes::largest") in self._calls(graph)


class TestTests:
    def test_the_gtest_shaped_bodies_are_tests_named_suite_dot_name(self, layer):
        assert [(t["name"], t["framework"]) for t in layer["tests"]] == [
            ("Shapes.Area", "gtest"), ("Shapes.Scale", "gtest"),
        ]

    def test_a_gtest_body_gets_a_file_local_symbol_so_its_calls_attribute_to_it(self, layer):
        by_id = _symbols(layer)
        assert by_id["tests/test_shapes.Shapes.Scale"]["static"] is True
        assert _call_at(layer, "tests/test_shapes.cpp", 16, "scale")["scope"] == "Shapes.Scale"

    def test_all_four_gtest_macros_are_read(self, tmp_path):
        _write(tmp_path, {"tests/g.cpp": (
            "TEST(Suite, One) {}\n"
            "TEST_F(Fix, Two) {}\n"
            "TEST_P(Par, Three) {}\n"
            "TYPED_TEST(Typed, Four) {}\n"
        )})
        layer = extract_cpp(tmp_path)
        assert {t["name"] for t in layer["tests"]} == {
            "Suite.One", "Fix.Two", "Par.Three", "Typed.Four",
        }
        assert {t["framework"] for t in layer["tests"]} == {"gtest"}

    def test_boost_s_single_argument_form_is_named_by_it(self, tmp_path):
        _write(tmp_path, {"tests/b.cpp": "BOOST_AUTO_TEST_CASE(sums) { }\n"})
        layer = extract_cpp(tmp_path)
        assert [(t["name"], t["framework"]) for t in layer["tests"]] == [("sums", "boost-test")]

    def test_a_string_named_test_takes_its_name_and_its_header_s_framework(self, tmp_path):
        _write(tmp_path, {
            "tests/c.cpp": '#include <catch2/catch_test_macros.hpp>\nTEST_CASE("adds two") {\n}\n',
            "tests/d.cpp": '#include <doctest/doctest.h>\nSCENARIO("a scenario") {\n}\n',
            "tests/n.cpp": 'TEST_CASE("neither header") {\n}\n',
        })
        layer = extract_cpp(tmp_path)
        assert {(t["name"], t["framework"]) for t in layer["tests"]} == {
            ("adds two", "catch2"),
            ("a scenario", "doctest"),
            ("neither header", "catch2"),  # Catch2 is the older spelling
        }

    def test_a_string_named_test_has_no_symbol_and_says_so(self, tmp_path):
        _write(tmp_path, {"tests/c.cpp": (
            "int helper();\n"
            'TEST_CASE("adds two") {\n'
            "    helper();\n"
            "}\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [s["qualname"] for s in layer["symbols"]] == []
        record = [e for e in layer["errors"] if e["stage"] == "cpp-tests"]
        assert len(record) == 1
        assert record[0]["path"] == "tests/c.cpp"
        assert "1 `TEST_CASE`/`SCENARIO` body named but not attached" in record[0]["message"]
        collected = collect_cpp_tests(layer["files"], [])
        assert collected[0]["symbol"] == "" and collected[0]["reaches"] == []

    def test_a_gtest_body_s_reach_is_measured_over_the_join_s_edges(self):
        from hobbes.extract import extract_repo

        tests = {t["id"]: t for t in extract_repo(FIXTURE).tests["tests"]}
        scale = tests["tests/test_shapes.cpp::Shapes.Scale"]
        assert scale["reaches"] == ["src/util.scale"]
        assert scale["reaches_modules"] == ["src/util"]
        # `Shapes.Area` calls only `c.area()`, a member call lane A never
        # resolves: its reach is honestly empty.
        assert tests["tests/test_shapes.cpp::Shapes.Area"]["reaches"] == []

    def test_c_s_naming_convention_does_not_apply(self, tmp_path):
        _write(tmp_path, {"tests/t.cpp": "void test_adds() {}\n"})
        assert extract_cpp(tmp_path)["tests"] == []


class TestTheBundle:
    def test_the_layer_names_its_language(self, layer):
        assert layer["languages"] == ["cpp"]

    def test_an_include_it_cannot_place_is_an_external_module(self, layer):
        ids = {n["id"] for n in layer["nodes"]}
        assert {"ext:utility", "ext:cstdio"} <= ids

    def test_a_resolved_include_is_an_imports_edge_with_file_and_line(self, layer):
        edge = [
            e for e in layer["module_edges"]
            if e["from"] == "src/shapes" and e["to"] == "include/minicpp/shapes.h"
        ]
        assert len(edge) == 1
        assert edge[0]["evidence"][0] == {
            "path": "src/shapes.cpp", "line": 1, "lane": "tree-sitter",
        }

    def test_a_file_that_will_not_parse_does_not_take_the_layer_down(self, tmp_path):
        _write(tmp_path, {"a.cpp": "class {{{ ;;; int f() {\n"})
        layer = extract_cpp(tmp_path)
        assert [e["stage"] for e in layer["errors"]] == ["parse"]
        assert "parsed with syntax errors" in layer["errors"][0]["message"]
