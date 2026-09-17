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
    _STRING_TEST_MACROS,
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


def _operators(layer, path):
    """One file's operator tokens (ADR-131), unpacked — ``(line, column,
    spelling, in_template)`` each, in position order."""
    from hobbes.extract.cppsource import unpack_operator

    return [unpack_operator(packed) for packed in layer["operators"].get(path, ())]


def _constructions(layer, path):
    """One file's construction tokens (ADR-132), unpacked — ``(line,
    column, kind, in_template)`` each, in position order."""
    from hobbes.extract.cppsource import unpack_construction

    return [
        unpack_construction(packed)
        for packed in layer["constructions"].get(path, ())
    ]


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


class TestTheWrittenArgumentCount:
    """ADR-130, one step beside R-qual: the projection draws nothing where
    a call is written with more arguments than lane B's answer takes. This
    walk records the count as written, and ``None`` — unknown, which draws
    the edge — wherever the parse cannot count it."""

    SOURCE = (
        "void f();\n"
        "template <typename T> void h(T a, T b);\n"
        "struct X { void m(int); };\n"
        "namespace ns { struct A { static void s(int, int); }; }\n"
        "struct T { T(int, int); };\n"
        "void g(X x) {\n"
        "    f();\n"
        "    f(1);\n"
        "    f(1, g(2, 3));\n"
        "    h<int>(1, 2);\n"
        "    x.m(1);\n"
        "    ns::A::s(1, 2);\n"
        "    f({1, 2});\n"
        "    f(args...);\n"
        "    T t{1, 2};\n"
        "    new T{1, 2};\n"
        '    f("a,b");\n'
        "}\n"
    )

    @pytest.fixture
    def sites(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return {(s.line, s.name): s for s in extract_cpp(tmp_path)["call_sites"]}

    def test_the_count_is_the_arguments_and_not_the_punctuation(self, sites):
        assert sites[(7, "f")].argc == 0
        assert sites[(8, "f")].argc == 1

    def test_a_nested_call_s_own_commas_belong_to_it(self, sites):
        # `f(1, g(2, 3))` is two arguments and `g(2, 3)` is two of its own.
        assert sites[(9, "f")].argc == 2
        assert sites[(9, "g")].argc == 2

    def test_every_call_shape_is_counted(self, sites):
        # plain with template arguments, member, qualified: the count is
        # the site's own list wherever the callee was written.
        assert sites[(10, "h")].argc == 2
        assert sites[(11, "m")].argc == 1
        assert sites[(12, "s")].argc == 2

    def test_a_comma_inside_a_string_is_text(self, sites):
        assert sites[(17, "f")].argc == 1

    def test_a_braced_argument_is_one_argument(self, sites):
        # `f({1, 2})` passes one initialiser list, and it is one.
        assert sites[(13, "f")].argc == 1

    def test_a_pack_expansion_counts_nothing(self, sites):
        # `f(args...)` stands for as many arguments as the pack holds.
        assert sites[(14, "f")].argc is None

    def test_a_braced_construction_counts_nothing(self, sites):
        # `T t{1, 2}` may be one `std::initializer_list` argument rather
        # than two, so neither form is counted: the declaration records no
        # site at all, and `new T{1, 2}` records one with no count.
        assert (15, "T") not in sites
        assert sites[(16, "T")].argc is None

    def test_an_error_in_the_list_counts_nothing(self, tmp_path):
        # The commas are the parse's own, so a list it could not read is
        # not a count. Unknown draws the edge.
        _write(tmp_path, {"a.cpp": "void g() {\n    f(1,);\n}\n"})
        [site] = [s for s in extract_cpp(tmp_path)["call_sites"] if s.name == "f"]
        assert site.argc is None


class TestTheDeclaredParameterCount:
    """ADR-130's other end: what a definition's own declarator can take.
    ``None`` is unbounded or unread, and the rule cannot fire on it."""

    SOURCE = (
        "void a() {}\n"
        "void b(void) {}\n"
        "void c(int x, int y = 2) {}\n"
        "void d(int x, ...) {}\n"
        "template <typename... A> void e(A&&... args) {}\n"
        "struct S { void m(int x, int y); };\n"
        "void S::m(int x, int y) {}\n"
    )

    def test_the_declarator_s_list_is_counted_and_the_unbounded_are_not(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        layer = extract_cpp(tmp_path)
        # Functions and methods alone carry it: `struct S` takes no
        # arguments in this sense, and has no key at all.
        assert "max_params" not in _symbols(layer)["a.S"]
        assert {
            s["id"]: s["max_params"] for s in layer["symbols"] if "max_params" in s
        } == {
            # `()` and `(void)` are both none at all.
            "a.a": 0,
            "a.b": 0,
            # A default argument is still a parameter the call may fill.
            "a.c": 2,
            # A C ellipsis and a parameter pack each take any number.
            "a.d": None,
            "a.e": None,
            # Read off the definition, out of line and all.
            "a.S::m": 2,
        }

    def test_fmts_shape_in_miniature_draws_nothing_and_says_so(self, tmp_path, monkeypatch):
        """ADR-130 through the whole ingest, on the shape it was measured
        on: two ``copy`` overloads, and a three-argument call scip-clang
        answers with the two-parameter one. Lane B is hand-built here, as
        in :class:`TestTheWithheldFallback`."""
        assert self._ingest(tmp_path, monkeypatch, 3) == (
            [], {"arity-mismatch": 1},
        )

    def test_the_same_facts_onto_the_overload_that_fits_draw_it(self, tmp_path, monkeypatch):
        # The one difference is the line lane B answers with, so what the
        # rule reads is the target's own parameter list and nothing else.
        assert self._ingest(tmp_path, monkeypatch, 4) == (
            ["src/fmt.h.copy~2"], {},
        )

    def _ingest(self, tmp_path, monkeypatch, def_line):
        """The edges the call at ``src/use.cpp:3`` draws, and the tail its
        file carries, with lane B resolving ``copy`` to *def_line*."""
        from hobbes.extract import evidence as ev, extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {
            "src/fmt.h": (
                "struct OutputIt {};\n"
                "struct View {};\n"
                "int copy(View s, OutputIt out) { return 0; }\n"
                "int copy(char* b, char* e, OutputIt out) { return 1; }\n"
            ),
            "src/use.cpp": (
                '#include "fmt.h"\n'
                "int use(char* b, char* e, OutputIt out) {\n"
                "    return copy(b, e, out);\n"
                "}\n"
            ),
        })
        facts = {
            "language": "cpp",
            "definitions": [],
            "references": [ev.Site(
                provider=ev.SCIP, kind=ev.RESOLUTION,
                file="src/use.cpp", line=3, col=11, name="copy",
                def_file="src/fmt.h", def_line=def_line,
            )],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        graph = extract_repo(tmp_path).graph
        drawn = [
            edge["to"] for edge in graph["symbol_edges"]
            if any(
                (site["path"], site["line"]) == ("src/use.cpp", 3)
                for site in edge["evidence"]
            )
        ]
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/use.cpp"]
        return drawn, row.get("tail", {})

    def test_a_macro_in_the_parameter_list_is_no_count(self, tmp_path):
        # It parses as an ERROR node, and what the macro expands to is not
        # in this file's tokens.
        _write(tmp_path, {"a.cpp": "void f(int x, FMT_API(y) z) {}\n"})
        symbols = _symbols(extract_cpp(tmp_path))
        assert symbols["a.f"]["max_params"] is None

    def test_a_template_header_a_macro_parse_lost_still_records_the_specialisation(self, tmp_path):
        # fmt's compile-test.cc (§10.11, P69): an unreadable macro pulls
        # `template <>` into an ERROR node before a bare `struct S<X>`. The
        # header's exact tokens mark it; a lost header with a parameter in
        # it, or no header at all, records nothing.
        _write(tmp_path, {"a.cpp": (
            "template <typename T> struct S { void format() {} };\n"
            "UNREADABLE_MACRO\n"
            "template <> struct S<int> : S<long> { void format() {} };\n"
            "UNREADABLE_MACRO\n"
            "template <typename U> struct S<U*> { void format() {} };\n"
        )})
        layer = extract_cpp(tmp_path)
        assert "a.S<int>" in layer["full_specializations"]
        assert "a.S<U*>" not in layer["full_specializations"]


class TestOperatorTokens:
    """ADR-131: an operator applied by symbol names no callee, so it is no
    call site — but the token is where scip-clang puts its ``operator…``
    reference, and the join draws a call only if lane A can say the
    spelling was written at exactly that position. This walk records the
    token and nothing else."""

    SOURCE = (
        "struct A { int operator[](int i); int m; };\n"
        "void g(A& a, A* r, int* p, int i, int j) {\n"
        "    int x = i + j;\n"
        "    i << j << x;\n"
        "    int y = *p;\n"
        "    int* q = &i;\n"
        "    bool z = !i;\n"
        "    ++i;\n"
        "    i++;\n"
        "    i = j;\n"
        "    i += j;\n"
        "    a[i];\n"
        "    r->m;\n"
        "    a.m;\n"
        "    g(a, r, p, i, j);\n"
        "    int k = sizeof(i + j);\n"
        "    using D = decltype(i == j);\n"
        "    int c = static_cast<int>(i);\n"
        '    auto s = "s"_a;\n'
        "}\n"
    )

    @pytest.fixture
    def tokens(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return _operators(extract_cpp(tmp_path), "a.cpp")

    def _at(self, line: int, needle: str) -> int:
        """The 0-based column *needle* is written at on *line* — the same
        position `_site` gives a call, read off the fixture's own text."""
        return self.SOURCE.splitlines()[line - 1].index(needle)

    def test_every_shape_the_walk_records_is_at_its_own_token(self, tokens):
        assert [(line, column, spelling) for line, column, spelling, _ in tokens] == [
            (3, self._at(3, "+"), "+"),
            # Two on one line, each at its own column: `i << j << x` is
            # `(i << j) << x`, and the index names an overload at each.
            (4, self._at(4, "<<"), "<<"),
            (4, self.SOURCE.splitlines()[3].rindex("<<"), "<<"),
            (5, self._at(5, "*p"), "*"),
            (6, self._at(6, "&i"), "&"),
            (7, self._at(7, "!"), "!"),
            (8, self._at(8, "++"), "++"),
            # Postfix is the same operator at the token it was written at.
            (9, self._at(9, "++"), "++"),
            (10, self._at(10, "="), "="),
            (11, self._at(11, "+="), "+="),
            # The subscript's own token is its `[`, spelled as a
            # declaration spells it.
            (12, self._at(12, "["), "[]"),
            (13, self._at(13, "->"), "->"),
        ]

    def test_what_is_never_a_token(self, tokens):
        # A `.` is not an overloadable operator; a call is a site already;
        # an unevaluated operand applies nothing (ADR-121's test, reused);
        # a named cast and a literal operator are neither of the shapes
        # this walk reads. None of them appears in the list above, and the
        # lines they sit on hold nothing at all.
        assert not [line for line, *_ in tokens if line >= 14]

    def test_a_c_file_records_none(self, tmp_path):
        # C has no operator functions, so the C layer never asks the
        # question and a `.c` file is in no C++ file's answer.
        from hobbes.extract.csource import extract_c

        _write(tmp_path, {
            "a.c": "int g(int i, int j) { return i + j; }\n",
            "b.cpp": "int h(int i, int j) { return i + j; }\n",
        })
        assert "operators" not in extract_c(tmp_path)
        assert set(extract_cpp(tmp_path)["operators"]) == {"b.cpp"}

    def test_a_file_that_applies_no_operator_is_absent_rather_than_empty(self, tmp_path):
        _write(tmp_path, {"a.cpp": "int f();\nint g() { return f(); }\n"})
        assert extract_cpp(tmp_path)["operators"] == {}


class TestTheOperatorTemplateFlag:
    """The one flag a token carries (ADR-131): inside a template the join
    draws no call, because scip-clang answers a dependent operator with
    its single by-name candidate at the same arity and nothing in the
    source contradicts it (C-153)."""

    SOURCE = (
        "template <typename T> T h(T t) { return t + t; }\n"
        "template <typename T> struct S {\n"
        "    T m(T t) { return t * t; }\n"
        "    auto f() { return [](int q) { return q - 1; }; }\n"
        "};\n"
        "struct P { int m(int q) { return q / 2; } };\n"
        "int plain(int q) { return q % 3; }\n"
    )

    @pytest.fixture
    def flags(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return {
            spelling: in_template
            for _, _, spelling, in_template in _operators(extract_cpp(tmp_path), "a.cpp")
        }

    def test_a_function_template_a_class_template_and_a_lambda_inside_one(self, flags):
        # The walk to the root is unbounded: a member is inside the header
        # written above its class, and a lambda body inside the member.
        assert flags["+"] is True
        assert flags["*"] is True
        assert flags["-"] is True

    def test_a_plain_function_and_a_plain_class_s_method_are_not(self, flags):
        assert flags["/"] is False
        assert flags["%"] is False


class TestAnOperatorCalledByName:
    """An operator applied through its name is a call site already
    (``operator_name``), and stays exactly what it was: ADR-131 adds a
    token beside the sites, never in place of one."""

    def test_a_qualified_operator_call_is_still_a_site_and_no_token(self, tmp_path):
        _write(tmp_path, {"a.cpp": (
            "namespace ns { struct A {}; int operator<<(A a, int i) { return 0; } }\n"
            "int g(ns::A a) {\n"
            "    return ns::operator<<(a, 1);\n"
            "}\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [(c["line"], c["name"], c["shape"]) for c in _calls(layer, "a.cpp")] == [
            (3, "operator<<", "qualified"),
        ]
        # The definition's own `operator<<` is a symbol, not a token, and
        # the call names it: nothing here was written as `a << 1`.
        assert _operators(layer, "a.cpp") == []

    def test_a_member_operator_call_records_no_token_either(self, tmp_path):
        # The pinned grammar does not parse `a.operator=(b)` — the callee
        # lands in an ERROR node — so the site it leaves is what it always
        # was; what matters to this rule is that the `=` written inside
        # `operator=` is no token, and it is not.
        _write(tmp_path, {"a.cpp": (
            "struct A { A& operator=(const A& o); };\n"
            "void g(A a, A b) {\n"
            "    a.operator=(b);\n"
            "}\n"
        )})
        assert _operators(extract_cpp(tmp_path), "a.cpp") == []


class TestAnOperatorEdgeThroughTheIngest:
    """ADR-131 end to end, on the shape it was measured on: the same
    ``a == b`` written in a plain function and in a template, resolved by
    the index to the same ``operator==``. Lane B is hand-built here, as in
    :class:`TestTheWithheldFallback`."""

    LIB = (
        "struct A { int v; };\n"
        "bool operator==(A a, A b) { return true; }\n"
    )
    USE = (
        '#include "lib.h"\n'
        "bool plain(A a, A b) {\n"
        "    return a == b;\n"
        "}\n"
        "template <typename T> bool tpl(T a, T b) {\n"
        "    return a == b;\n"
        "}\n"
    )

    def _built(self, tmp_path, monkeypatch, lane_b: bool):
        from hobbes.extract import evidence as ev, extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {"src/lib.h": self.LIB, "src/use.cpp": self.USE})
        lines = self.USE.splitlines()
        references = [
            ev.Site(
                provider=ev.SCIP, kind=ev.RESOLUTION,
                file="src/use.cpp", line=number, col=lines[number - 1].index("=="),
                name="operator==", def_file="src/lib.h", def_line=2,
            )
            for number in (3, 6)
        ]
        facts = [{
            "language": "cpp",
            "definitions": [],
            "references": references,
            "external_refs": [],
            "degraded": [],
        }]
        monkeypatch.setattr(
            extract, "_lane_b_facts", lambda *a, **k: iter(facts if lane_b else [])
        )
        graph = extract_repo(tmp_path).graph
        return graph, {
            (edge["from"], edge["type"]): edge
            for edge in graph["symbol_edges"]
            if any(site["path"] == "src/use.cpp" for site in edge["evidence"])
        }

    def test_the_plain_function_calls_the_operator_and_the_template_draws_nothing(
        self, tmp_path, monkeypatch
    ):
        graph, edges = self._built(tmp_path, monkeypatch, lane_b=True)
        # The caller is named by the enclosing symbol, since the fact
        # carries no scope of its own.
        assert edges[("src/use.plain", "calls")]["to"] == "src/lib.h.operator=="
        assert edges[("src/use.plain", "calls")]["tier"] == "semantic"
        # Inside the template the same reference is withheld outright
        # (ADR-131's amendment): no `calls` edge, no `uses` edge from the
        # module it sits in, no edge of any type at all — so nothing in
        # the graph stands on line 6.
        assert ("src/use.tpl", "calls") not in edges
        assert [key[1] for key in edges] == ["calls"]
        assert not [
            edge
            for edge in graph["symbol_edges"] + graph["module_edges"]
            if any(
                site["path"] == "src/use.cpp" and site["line"] == 6
                for site in edge["evidence"]
            )
        ]
        # `src/use → src/lib.h` survives on the `#include` and the call at
        # line 3, which is why it is here rather than gone: a module edge
        # only goes where the withheld reference was all of it (ADR-131's
        # amendment, measured on fmt and args).
        assert [edge["type"] for edge in graph["module_edges"]] == ["imports"]
        assert graph["operators"] == {"drawn": 1, "in_template": 1}

    def test_with_no_lane_b_there_is_no_block_and_no_operator_edge(
        self, tmp_path, monkeypatch
    ):
        # P6: the tokens are read by nothing, so the graph is what it was
        # before this rule existed.
        graph, edges = self._built(tmp_path, monkeypatch, lane_b=False)
        assert "operators" not in graph
        assert edges == {}


class TestThePacking:
    """One integer per token (ADR-131): ScummVM has about 3.2 million of
    them beside its 1.53 million call sites, so a `Site` each is the cost
    the packing exists to avoid."""

    def test_it_round_trips_line_column_spelling_and_flag_at_their_extremes(self):
        from hobbes.extract.cppsource import (
            COLUMN_LIMIT, OPERATOR_SPELLINGS, pack_operator, unpack_operator,
        )

        for spelling in (OPERATOR_SPELLINGS[0], OPERATOR_SPELLINGS[-1], "<=>"):
            for line, column in ((1, 0), (999_999, COLUMN_LIMIT - 1)):
                for flag in (False, True):
                    packed = pack_operator(line, column, spelling, flag)
                    assert unpack_operator(packed) == (line, column, spelling, flag)

    def test_the_packing_sorts_by_position(self):
        from hobbes.extract.cppsource import pack_operator

        assert pack_operator(2, 0, "+", True) > pack_operator(1, 4000, "+", False)
        assert pack_operator(1, 5, "+", False) > pack_operator(1, 4, "[]", True)

    def test_a_column_past_the_bound_is_dropped_rather_than_misplaced(self, tmp_path):
        # No source line is a megabyte wide; one that were would carry its
        # column into the line field, and a token at a position it was not
        # written at is the one thing this rule must never hold.
        from hobbes.extract.cppsource import COLUMN_LIMIT

        _write(tmp_path, {"a.cpp": (
            "int g(int i, int j) {\n"
            "    return " + " " * COLUMN_LIMIT + "i + j;\n"
            "}\n"
        )})
        assert extract_cpp(tmp_path)["operators"] == {}

    def test_a_lookup_answers_only_at_the_exact_token(self, tmp_path):
        from hobbes.extract.cppsource import operator_token

        _write(tmp_path, {"a.cpp": "int g(int i, int j) { return i + j; }\n"})
        packed = extract_cpp(tmp_path)["operators"]["a.cpp"]
        column = "int g(int i, int j) { return i + j; }".index("+")
        assert operator_token(packed, 1, column, "+") is False
        assert operator_token(packed, 1, column + 1, "+") is None
        assert operator_token(packed, 1, column, "-") is None
        assert operator_token(packed, 1, column, "()") is None
        assert operator_token(packed, 2, column, "+") is None


class TestConstructionTokens:
    """ADR-132: a construction calls a constructor and names no callee, so
    it is no call site — but the token is where scip-clang puts its
    constructor reference, and the join draws a call only if lane A can
    say a construction was written at exactly that position."""

    SOURCE = (
        "struct T { T(int); T(); };\n"
        "void f(int a) {\n"
        "    T x(1);\n"
        "    T xa(a);\n"
        "    T y{1};\n"
        "    T z;\n"
        "    T w = T(1);\n"
        "    T v = {1, 2};\n"
        "    q({1, 2});\n"
        "    new T(1);\n"
        "    ns::Foo{1};\n"
        "    label: T lab(1);\n"
        "}\n"
        "struct C { C(int a) : m_(a), n_{2}, Base<int>(1) {} int m_; int n_; };\n"
        "void h(T p = {});\n"
        "T r() { return {1, 2}; }\n"
        "class GTEST_API_ X { public: explicit X(int); };\n"
    )

    @pytest.fixture
    def tokens(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return _constructions(extract_cpp(tmp_path), "a.cpp")

    def _at(self, line: int, needle: str) -> int:
        """The 0-based column *needle* is written at on *line*, read off
        the fixture's own text."""
        return self.SOURCE.splitlines()[line - 1].index(needle)

    def test_every_shape_the_walk_records_is_at_its_own_token(self, tokens):
        assert [(line, column, kind) for line, column, kind, _ in tokens] == [
            # `T x(1);` — the pinned grammar reads a literal argument as an
            # `init_declarator` whose value is an `argument_list`, so this
            # is a `decl-init`; only a *named* argument (`T xa(a);`) reads
            # as the function declaration `decl-paren` is for.
            (3, self._at(3, "x(1)"), "decl-init"),
            (4, self._at(4, "xa"), "decl-paren"),
            (5, self._at(5, "y{1}"), "decl-init"),
            (6, self._at(6, "z;"), "decl-default"),
            # Line 7, `T w = T(1);`: none. The value is a call expression,
            # which is a call site already.
            #
            # Line 8 is copy-list-initialisation, and the token is the
            # declared name: the `{` gets no `braced` token of its own,
            # because its holder is an `init_declarator` and not one of
            # the two the `braced` rule reads.
            (8, self._at(8, "v ="), "decl-init"),
            (9, self._at(9, "{1, 2}"), "braced"),
            (10, self._at(10, "T(1)"), "new"),
            # `ns::Foo{1}` is recorded at the type's start, whatever node
            # kind the type is — here a qualified name, so at `ns`.
            (11, self._at(11, "ns"), "compound-literal"),
            # Line 12's declaration sits under a `labeled_statement`: none.
            (14, self._at(14, "m_("), "member-init"),
            (14, self._at(14, "n_{"), "member-init"),
            # A base-class initialiser (`Base<int>(1)`) opens with a
            # `template_method` rather than a `field_identifier`: none.
            (15, self._at(15, "="), "default-arg"),
            (16, self._at(16, "{1, 2}"), "braced"),
            # Line 17, the macro-broken class head, is below.
        ]

    def test_a_declaration_under_a_label_records_nothing(self, tokens):
        # `label: T lab(1);` and, on line 17, the shape that found this
        # rule: `class GTEST_API_ X { public: explicit X(int); };` parses
        # as a function whose body holds `public:` as a label and the
        # constructor's own declaration as a local. Lane B points that
        # declaration at the out-of-line definition, so a token here would
        # draw a call from a class body — 4 wrong rows on fmt.
        assert not [line for line, *_ in tokens if line in (12, 17)]

    def test_a_declaration_initialised_by_a_call_is_left_to_the_call_site(
        self, tokens
    ):
        assert not [line for line, *_ in tokens if line == 7]

    def test_nothing_inside_an_unevaluated_operand(self, tmp_path):
        # ADR-121's test, reused: the program constructs nothing inside a
        # `sizeof` or a `decltype`, so there is no call to draw there.
        _write(tmp_path, {"a.cpp": (
            "void f() {\n"
            "    sizeof(T{1});\n"
            "    using D = decltype(T{1});\n"
            "}\n"
        )})
        assert _constructions(extract_cpp(tmp_path), "a.cpp") == []

    def test_a_default_member_initialiser_in_a_class_body_is_not_recorded(
        self, tmp_path
    ):
        # A `field_declaration`, not a `declaration`: ADR-132 measured no
        # row of that shape and records none.
        _write(tmp_path, {"a.cpp": "struct S { T member{1}; };\n"})
        assert _constructions(extract_cpp(tmp_path), "a.cpp") == []

    def test_a_c_file_records_none(self, tmp_path):
        # C has no constructors, so the C layer never asks the question
        # and a `.c` file is in no C++ file's answer.
        from hobbes.extract.csource import extract_c

        _write(tmp_path, {
            "a.c": "void g(void) { int n = 0; T t; }\n",
            "b.cpp": "void h() { T t; }\n",
        })
        assert "constructions" not in extract_c(tmp_path)
        assert set(extract_cpp(tmp_path)["constructions"]) == {"b.cpp"}

    def test_a_file_that_constructs_nothing_is_absent_rather_than_empty(
        self, tmp_path
    ):
        # A prototype at file scope is a function declaration and no
        # construction: `decl-paren` needs a block above it.
        _write(tmp_path, {"a.cpp": "int f(int a);\nint g() { return f(1); }\n"})
        assert extract_cpp(tmp_path)["constructions"] == {}


class TestTheConstructionTemplateFlag:
    """The one flag a construction token carries (ADR-132): inside a
    template the join keeps the ``uses`` edge rather than drawing a call
    — 45 of 45 such rows read right, but no other in-template answer of
    this lane has stood without a guard."""

    SOURCE = (
        "template <typename U> void h(U u) { T t(1); }\n"
        "void plain() { T p(1); }\n"
    )

    @pytest.fixture
    def flags(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return {
            line: in_template
            for line, _, _, in_template in _constructions(extract_cpp(tmp_path), "a.cpp")
        }

    def test_a_function_templates_body_is_inside_one_and_a_plain_body_is_not(
        self, flags
    ):
        assert flags == {1: True, 2: False}


class TestAConstructionEdgeThroughTheIngest:
    """ADR-132 end to end, on the shape it was measured on: the same
    declaration written in a plain function and in a template, with the
    index naming the constructor at the declared name. Lane B is
    hand-built here, as in :class:`TestAnOperatorEdgeThroughTheIngest`.

    Braces rather than ``A a(1);``, which is the one construction lane A
    already records a ``construct`` **site** for: that site claims every
    resolution its line spells ``A``, the constructor's among them, and
    the rule is about the references no site claims.
    """

    LIB = (
        "struct A {\n"
        "    A(int v) : v_(v) {}\n"
        "    int v_;\n"
        "};\n"
    )
    USE = (
        '#include "lib.h"\n'
        "void plain() {\n"
        "    A a{1};\n"
        "}\n"
        "template <typename T>\n"
        "void tpl() {\n"
        "    A b{1};\n"
        "}\n"
    )

    def _built(self, tmp_path, monkeypatch, lane_b: bool):
        from hobbes.extract import evidence as ev, extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {"src/lib.h": self.LIB, "src/use.cpp": self.USE})
        lines = self.USE.splitlines()
        references = []
        for number, declared in ((3, "a"), (7, "b")):
            # Both occurrences scip-clang emits on such a line: the type
            # at `A`, which is the `uses` reference it has always been,
            # and the constructor at the declared name, which this rule
            # reads. Both are named by their terminal descriptor, so the
            # column is the whole of what tells them apart.
            references.append(ev.Site(
                provider=ev.SCIP, kind=ev.RESOLUTION,
                file="src/use.cpp", line=number, col=lines[number - 1].index("A"),
                name="A", def_file="src/lib.h", def_line=1,
            ))
            references.append(ev.Site(
                provider=ev.SCIP, kind=ev.RESOLUTION,
                file="src/use.cpp", line=number,
                col=lines[number - 1].index(declared + "{1}"),
                name="A", def_file="src/lib.h", def_line=2,
            ))
        facts = [{
            "language": "cpp",
            "definitions": [
                {"file": "src/lib.h", "line": 1, "end_line": 4,
                 "kind": "type", "moniker": "cxx . . $ A#"},
                {"file": "src/lib.h", "line": 2, "end_line": 2,
                 "kind": "method", "moniker": "cxx . . $ A#A(1a2b3c4d)."},
            ],
            "references": references,
            "external_refs": [],
            "degraded": [],
        }]
        monkeypatch.setattr(
            extract, "_lane_b_facts", lambda *a, **k: iter(facts if lane_b else [])
        )
        graph = extract_repo(tmp_path).graph
        return graph, {
            (edge["from"], edge["type"], edge["to"])
            for edge in graph["symbol_edges"]
            if any(site["path"] == "src/use.cpp" for site in edge["evidence"])
        }

    def test_the_plain_function_calls_the_constructor_and_the_template_uses_it(
        self, tmp_path, monkeypatch
    ):
        graph, edges = self._built(tmp_path, monkeypatch, lane_b=True)
        # The caller is named by the enclosing symbol, since the fact
        # carries no scope of its own.
        assert ("src/use.plain", "calls", "src/lib.h.A::A") in edges
        # Inside the template the same reference is the `uses` edge it
        # was, from the module: the fact is unscoped, and ADR-132 does
        # not withhold it — a dependent type's construction is not
        # indexed at all, so this one's type is not dependent.
        assert ("src/use.tpl", "calls", "src/lib.h.A::A") not in edges
        assert ("src/use.tpl", "uses", "src/lib.h.A::A") in edges
        assert graph["constructions"] == {"drawn": 1, "in_template": 1}

    def test_with_no_lane_b_there_is_no_block_and_no_construction_edge(
        self, tmp_path, monkeypatch
    ):
        # P6: the tokens and the constructor set are read by nothing, so
        # the graph is what it was before this rule existed.
        graph, edges = self._built(tmp_path, monkeypatch, lane_b=False)
        assert "constructions" not in graph
        assert not [edge for edge in edges if edge[2] == "src/lib.h.A::A"]


class TestTheConstructionPacking:
    """One integer per token (ADR-132), in the operator tokens' own
    layout: the kind rides where the spelling's index does."""

    def test_it_round_trips_line_column_kind_and_flag_at_their_extremes(self):
        from hobbes.extract.cppsource import (
            COLUMN_LIMIT, CONSTRUCTION_KINDS, pack_construction, unpack_construction,
        )

        for kind in (CONSTRUCTION_KINDS[0], CONSTRUCTION_KINDS[-1], "member-init"):
            for line, column in ((1, 0), (999_999, COLUMN_LIMIT - 1)):
                for flag in (False, True):
                    packed = pack_construction(line, column, kind, flag)
                    assert unpack_construction(packed) == (line, column, kind, flag)

    def test_the_packing_sorts_by_position(self):
        from hobbes.extract.cppsource import pack_construction

        assert pack_construction(2, 0, "new", True) > pack_construction(1, 4000, "new", False)
        assert pack_construction(1, 5, "braced", False) > pack_construction(1, 4, "new", True)

    def test_a_column_past_the_bound_is_dropped_rather_than_misplaced(self, tmp_path):
        from hobbes.extract.cppsource import COLUMN_LIMIT

        _write(tmp_path, {"a.cpp": (
            "void f() {\n" + " " * COLUMN_LIMIT + "T t(1);\n" + "}\n"
        )})
        assert extract_cpp(tmp_path)["constructions"] == {}

    def test_a_lookup_answers_only_at_the_exact_token(self, tmp_path):
        from hobbes.extract.cppsource import construction_token

        _write(tmp_path, {"a.cpp": "void f() { T t{1}; }\n"})
        packed = extract_cpp(tmp_path)["constructions"]["a.cpp"]
        column = "void f() { T t{1}; }".index("t{1}")
        assert construction_token(packed, 1, column) is False
        assert construction_token(packed, 1, column + 1) is None
        assert construction_token(packed, 1, column - 1) is None
        assert construction_token(packed, 2, column) is None


class TestTheTemplatePattern:
    """ADR-125 §4: which callers lie in the region C-153's wrong answer can
    occur in — a template written once and instantiated per argument list.
    This walk records the callers' own qualnames; the join marks the
    semantic edges that start at them."""

    SOURCE = (
        "template <typename T> T ident(T t) { return t; }\n"
        "namespace ns {\n"
        "template <typename T> struct S {\n"
        "    void inline_member() {}\n"
        "    template <typename U> void both(U u) {}\n"
        "    void g();\n"
        "};\n"
        "template <typename T> void S<T>::g() {}\n"
        "template <typename T> struct S<T*> { void partial() {} };\n"
        "template <> struct S<int> { void concrete() {} };\n"
        "}\n"
        "struct P { void member() {} };\n"
        "void plain() {}\n"
    )

    @pytest.fixture
    def built(self, tmp_path):
        _write(tmp_path, {"a.cpp": self.SOURCE})
        return extract_cpp(tmp_path)

    def test_the_four_pattern_shapes_are_recorded_and_nothing_else_is(self, built):
        # A function template; a class template's inline member and its own
        # member template, which is a pattern's at any depth under the
        # header above it; the out-of-line member definition written under a
        # non-empty header; and a partial specialisation's member, which
        # spells parameters rather than concrete arguments too.
        assert built["template_patterns"] == frozenset({
            "a.ident",
            "a.ns::S::inline_member",
            "a.ns::S::both",
            "a.ns::S<T>::g",
            "a.ns::S<T*>::partial",
        })

    def test_a_full_specialisations_member_a_method_and_a_plain_function_are_not(self, built):
        # `template <>` is concrete code with one instantiation — the shape
        # R-qual already withholds the wrong edges of — and neither a plain
        # class's method nor a free function was ever a template. Marking
        # any of them would say C-153 where C-153 cannot happen.
        patterns = built["template_patterns"]
        assert not ({"a.ns::S<int>::concrete", "a.P::member", "a.plain"} & patterns)
        # All three are still symbols: the region is marked, not narrowed.
        assert {"a.ns::S<int>::concrete", "a.P::member", "a.plain"} <= {
            s["id"] for s in built["symbols"]
        }

    def test_a_class_nested_in_a_class_body_is_no_symbol_so_its_members_go_unmarked(
        self, tmp_path
    ):
        # Lane A's walk does not descend into a class declared inside a
        # class body, so a method of one is no symbol and can be the `from`
        # of no edge. The region there goes unmarked rather than
        # mis-marked — less than the truth, the only direction this rule is
        # allowed to fail in.
        _write(tmp_path, {"a.cpp": (
            "template <typename T> struct S { struct N { void nested() {} }; };\n"
        )})
        layer = extract_cpp(tmp_path)
        assert [s["id"] for s in layer["symbols"]] == ["a.S"]
        assert layer["template_patterns"] == frozenset()


class TestTheTemplatePatternThroughTheIngest:
    """ADR-125 §4's two outputs, through the whole ingest: the list
    ``who_calls`` marks its lines from, and the one record
    ``list_blind_spots`` names the region by. Lane B is hand-built here, as
    in :class:`TestTheWithheldFallback`."""

    LIB = "inline int f(int x) { return x; }\ninline int h(int x) { return x; }\n"
    TPL = (
        '#include "lib.h"\n'
        "\n"
        "template <typename T> int pattern(T t) { return f(1); }\n"
        "\n"
        "int plainfn() { return f(2); }\n"
        "\n"
        "template <typename T> T silent(T t) { return t; }\n"
    )
    # A file lane B answers nothing in at all is a file it did not index
    # (ADR-113 §2), so its sites keep lane A's guess — a `syntactic` edge
    # out of a pattern, which scip-clang never spoke about.
    QUIET = (
        '#include "lib.h"\n'
        "\n"
        "template <typename T> int unindexed(T t) { return h(1); }\n"
    )

    def _ref(self, line: str, number: int, call: str, name: str):
        from hobbes.extract import evidence as ev

        return ev.Site(
            provider=ev.SCIP, kind=ev.RESOLUTION,
            file="src/tpl.cpp", line=number, col=line.index(call), name=name,
            def_file="src/lib.h", def_line=1,
        )

    @pytest.fixture
    def built(self, tmp_path, monkeypatch):
        from hobbes.extract import extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {
            "src/lib.h": self.LIB, "src/tpl.cpp": self.TPL, "src/quiet.cpp": self.QUIET,
        })
        lines = self.TPL.splitlines()
        facts = {
            "language": "cpp",
            "definitions": [],
            "references": [
                self._ref(lines[2], 3, "f(1)", "f"),
                self._ref(lines[4], 5, "f(2)", "f"),
            ],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(tmp_path).graph

    def test_only_a_pattern_that_calls_semantically_is_listed(self, built):
        # `plainfn` calls semantically but is no pattern; `silent` is a
        # pattern that calls nothing, so no answer is drawn from it and
        # listing it would grow the artifact for nothing; `unindexed` is a
        # pattern whose one edge is lane A's own guess.
        assert built["cpp_template_patterns"] == ["src/tpl.pattern"]
        drawn = {
            (edge["from"], edge["tier"])
            for edge in built["symbol_edges"] if edge["type"] == "calls"
        }
        assert ("src/tpl.plainfn", "semantic") in drawn
        assert ("src/quiet.unindexed", "syntactic") in drawn

    def test_one_record_counts_the_edges_and_names_c_153(self, built):
        records = [
            r for r in built.get("extraction_errors", [])
            if r["stage"] == "cpp-template-sites"
        ]
        assert len(records) == 1
        assert records[0]["path"] == "."
        assert records[0]["message"].startswith("1 semantic C++ call edge(s) start in a template")
        assert "C-153" in records[0]["message"]

    def test_no_semantic_edge_out_of_a_pattern_is_an_empty_list_and_no_record(
        self, tmp_path, monkeypatch
    ):
        # The C++ layer ran and was asked, so the key is written: an empty
        # list reads as "none here", which an absent key could not say.
        from hobbes.extract import extract_repo
        import hobbes.extract as extract

        _write(tmp_path, {"src/lib.h": self.LIB, "src/quiet.cpp": self.QUIET})
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([]))
        graph = extract_repo(tmp_path).graph
        assert graph["cpp_template_patterns"] == []
        assert not [
            r for r in graph.get("extraction_errors", [])
            if r["stage"] == "cpp-template-sites"
        ]


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

    def test_a_macro_spelled_test_case_still_runs_the_scan_and_still_names_nothing(
        self, tmp_path
    ):
        # ADR-128 §3's pre-filter reads the file's bytes: `TEST_CASE`
        # occurs in the `#define`, so the scan runs — and finds, as it did
        # before the pre-filter, no `TEST_CASE` call (the parse does not
        # expand `T`).
        source = '#define T TEST_CASE\nT("through a macro") {\n}\n'
        _write(tmp_path, {"tests/m.cpp": source})
        assert any(macro in source for macro in _STRING_TEST_MACROS)
        layer = extract_cpp(tmp_path)
        assert layer["tests"] == []
        assert [(p.path, p.unattached_tests) for p in layer["files"]] == [("tests/m.cpp", 0)]

    def test_a_file_holding_no_macro_name_at_all_names_no_string_test(self, tmp_path):
        source = "int helper() { return 1; }\nint caller() { return helper(); }\n"
        _write(tmp_path, {"src/plain.cpp": source})
        assert not any(macro in source for macro in _STRING_TEST_MACROS)
        layer = extract_cpp(tmp_path)
        assert layer["tests"] == []
        assert [(p.path, p.unattached_tests) for p in layer["files"]] == [("src/plain.cpp", 0)]


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

    def test_the_layer_names_the_files_whose_parse_had_error_nodes(self, tmp_path):
        """ADR-129's first condition, read off the walk and not off the
        record's message text: a definition lane B holds in one of these
        is one this parse lost; in any other file it is lane A's floor."""
        _write(tmp_path, {
            "a.cpp": "class {{{ ;;; int f() {\n",
            "b.cpp": "int g() { return 1; }\n",
        })
        assert extract_cpp(tmp_path)["lossy_files"] == frozenset({"a.cpp"})
