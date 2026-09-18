"""ADR-129: a definition lane A's parse lost is read from the index.

Two levels. The unit cases hand :func:`hobbes.extract.minted.mint` rows
and sources on ``tmp_path`` — one per shape it mints and one per refusal,
each counted under its own reason. The ingest cases run the whole
extraction over a repo whose header really does lose a definition to a
macro (checked here with the parser itself, not assumed), with lane B
hand-fed as :class:`tests.test_cppsource.TestTheWithheldFallback` feeds
it, and assert the one thing the mint exists for: the call scip-clang
resolved there draws, and everything lane A decided is untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hobbes.extract import minted

#: A header whose definitions tree-sitter-cpp loses whole: ``BEGIN_NS``
#: opens two namespaces the grammar cannot read, and the template that
#: follows pulls the rest of the file into an ERROR node. fmt's shape
#: (``FMT_BEGIN_NAMESPACE``), which is what C-145 is about. The three
#: definitions are at lines 9 (``lost``), 11 (``Lost``) and 13
#: (``declared_only``, a prototype).
LOST_HEADER = """#ifndef LOST_H
#define LOST_H
#define BEGIN_NS namespace lib { inline namespace v1 {

BEGIN_NS

template <typename T> struct Holder { T v; };

int lost(int x) { return x + 1; }

struct Lost { int n; };

int declared_only(int x);

} }

#endif
"""

#: `Lost made(1)` is a `construct` site at line 4, `lost` a qualified one
#: at line 5 — the two ends the ingest cases need.
LOST_MAIN = """#include "lost.h"

int main() {
    lib::Lost made(1);
    return lib::lost(made.n);
}
"""

#: The monikers scip-clang spells for the three, in its own grammar:
#: `<scheme> <manager> <package> <version> <descriptors>`, an inline
#: namespace and all.
#: A second lost header, written beside :data:`LOST_HEADER` rather than
#: into it so the line numbers the cases above pin stay where they are.
#: ``caller`` at 11 writes a call *inside* its own lost body — ADR-134's
#: whole question — and ``guarded`` at 16 writes one inside an ``#if``,
#: the extent refusal that fires on a measured cell.
LOST_CALLER_HEADER = """#ifndef LOST2_H
#define LOST2_H
#define BEGIN_NS2 namespace lib { inline namespace v1 {

BEGIN_NS2

template <typename T> struct Holder2 { T v; };

int helper(int x) { return x + 1; }

int caller(int x) {
    return helper(x) + 1;
}

#if GUARD
int guarded(int x) {
#if OTHER
    return helper(x);
#else
    return 0;
#endif
}
#endif

} }

#endif
"""

#: A third lost header, written beside the other two for the same reason
#: (the line numbers above stay where they are): C-164's own shape, which
#: ADR-135 is about. The annotation macro on line 12 is what lane A names
#: the method after — ``Holder3::LOCKED_``, a method at 12 — while the
#: index names the definition ``annotated`` at 11 and reads line 12's token
#: as a *reference* to the macro defined at line 4. The call at 13 is
#: written inside the body and lane A scopes it to the misnamed symbol.
LOST_ANNOTATED_HEADER = """#ifndef LOST3_H
#define LOST3_H
#define BEGIN_NS3 namespace lib { inline namespace v1 {
#define LOCKED_(x)

BEGIN_NS3

int inner(int x) { return x + 1; }

struct Holder3 {
    int annotated(int x)
        LOCKED_(mu) {
        return inner(x);
    }
};

} }

#endif
"""

LOST_MONIKER = "cxx . . $ lib/v1/lost(9ab1c0d2e3f40506)."
LOST_TYPE_MONIKER = "cxx . . $ lib/v1/Lost#"
DECLARED_ONLY_MONIKER = "cxx . . $ lib/v1/declared_only(77cc88dd99ee00ff)."
HELPER_MONIKER = "cxx . . $ lib/v1/helper(11aa22bb33cc44dd)."
CALLER_MONIKER = "cxx . . $ lib/v1/caller(55ee66ff77001122)."
GUARDED_MONIKER = "cxx . . $ lib/v1/guarded(3344556677889900)."
LOCKED_MONIKER = "cxx . . $ LOCKED_!"
INNER_MONIKER = "cxx . . $ lib/v1/inner(99aa88bb77cc66dd)."
ANNOTATED_MONIKER = "cxx . . $ lib/v1/Holder3#annotated(1122334455667788)."


def row(file: str, line: int, kind: str, moniker: str) -> dict:
    """One ``definitions`` row, as ``scipsource.read_facts`` leaves it."""
    return {"file": file, "line": line, "end_line": line, "kind": kind, "moniker": moniker}


def lane_a(module: str, name: str, line: int, end_line: int | None = None) -> dict:
    """One lane A symbol, as ``graph["symbols"]`` holds it."""
    return {
        "id": f"{module}.{name}",
        "module": module,
        "name": name.rpartition("::")[2],
        "qualname": name,
        "kind": "function",
        "line": line,
        "end_line": end_line if end_line is not None else line,
    }


def mint(tmp_path: Path, sources: dict[str, str], rows, *, clean=(), symbols=()):
    """Write *sources* under *tmp_path* and mint over *rows*.

    Every written file is a lossy one unless *clean* names it, since the
    lossy set is rule 1's whole input and each refusal wants exactly one
    thing wrong with it.
    """
    for rel, text in sources.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return minted.mint(
        tmp_path,
        rows,
        frozenset(rel for rel in sources if rel not in clean),
        list(symbols),
        {rel: rel for rel in sources},
    )


class TestWhatMints:
    def test_a_method_row_in_a_lossy_file_with_a_body_mints_a_method(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "struct Foo {\n    int bar(int x) { return x; }\n};\n"},
            [row("a.h", 2, "method", "cxx . . $ ns/Foo#bar(1a2b).")],
        )
        assert symbols == [
            {
                "id": "a.h.ns::Foo::bar",
                "module": "a.h",
                "name": "bar",
                "qualname": "ns::Foo::bar",
                "kind": "method",
                "line": 2,
                # ADR-134: the body's closing brace is on the same line,
                # and the mark says the extent was read rather than refused.
                "end_line": 2,
                "declared_by": "scip",
                # ADR-130: what the definition's own list can take.
                "max_params": 1,
                "extent": "braces",
            }
        ]
        assert counts["symbols"] == 1 and counts["files"] == 1
        assert set(counts["refused"].values()) == {0}

    def test_a_method_row_no_class_owns_mints_a_function(self, tmp_path):
        symbols, _ = mint(
            tmp_path,
            {"a.h": "int write(int x) { return x; }\n"},
            [row("a.h", 1, "method", "cxx . . $ fmt/v12/detail/write(9f11).")],
        )
        assert [(s["kind"], s["id"], s["name"]) for s in symbols] == [
            ("function", "a.h.fmt::v12::detail::write", "write")
        ]

    def test_a_type_row_with_a_body_mints_a_type(self, tmp_path):
        symbols, _ = mint(
            tmp_path,
            {"a.h": "struct FilePath { int n; };\n"},
            [row("a.h", 1, "type", "cxx . . $ testing/internal/FilePath#")],
        )
        assert [(s["kind"], s["id"]) for s in symbols] == [
            ("type", "a.h.testing::internal::FilePath")
        ]

    def test_a_backtick_escaped_name_is_unescaped(self, tmp_path):
        symbols, _ = mint(
            tmp_path,
            {"a.h": "int f(int x) { return x; }\n"},
            [row("a.h", 1, "method", "cxx . . $ `src.a`/f(3c).")],
        )
        assert [s["qualname"] for s in symbols] == ["src.a::f"]


class TestWhatIsRefused:
    """One test per refusal, each counted under its own reason. The rule
    is fitted to fmt and held out on args: every one of these removed
    measured contradictions, or measured edges the floor gives up."""

    def test_a_file_that_parsed_clean_mints_nothing(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f(int x) { return x; }\n"},
            [row("a.h", 1, "method", "cxx . . $ ns/f(1a).")],
            clean=("a.h",),
        )
        assert symbols == [] and counts["refused"]["clean-file"] == 1

    def test_a_term_row_mints_nothing(self, tmp_path):
        # `key_(CreateKey())` in a constructor's initialiser list: a data
        # member whose initialiser is spelled like a call. 74 on fmt.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "struct A {\n    int key_ { 0 };\n};\n"},
            [row("a.h", 2, "term", "cxx . . $ ns/A#key_.")],
        )
        assert symbols == [] and counts["refused"]["kind"] == 1

    def test_a_macro_row_mints_nothing(self, tmp_path):
        # A macro is expanded, not called, and is excluded from every
        # grade. 2,554 of fmt's below-floor facts.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "#define FMT_API do { } while (0)\n"},
            [row("a.h", 1, "macro", "cxx . . $ FMT_API!")],
        )
        assert symbols == [] and counts["refused"]["kind"] == 1

    def test_a_definition_inside_a_function_body_mints_nothing(self, tmp_path):
        # C-9's floor, which a recovery rule does not lower: the owner
        # chain holds a function. 10 facts on fmt, 5 confirmed edges
        # given up; 0 on args.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "void gmtime() {\n    struct dispatcher {\n"
                    "        int run() { return 1; }\n    };\n}\n"},
            [row("a.h", 3, "method", "cxx . . $ gmtime(3bbc).dispatcher#run(c985).")],
        )
        assert symbols == [] and counts["refused"]["local-to-function"] == 1

    def test_two_monikers_at_one_line_mint_nothing(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f() { return 1; } int g() { return 2; }\n"},
            [
                row("a.h", 1, "method", "cxx . . $ ns/f(1a)."),
                row("a.h", 1, "method", "cxx . . $ ns/g(2b)."),
            ],
        )
        # Counted per refused row, as every other reason is.
        assert symbols == [] and counts["refused"]["several-monikers"] == 2

    def test_a_lane_a_symbol_of_the_same_name_two_lines_away_mints_nothing(self, tmp_path):
        # A line-convention disagreement, not a definition lane A lost:
        # counted here and fixed as its own item. 20 on fmt.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f(\n    int x)\n{ return x; }\n"},
            [row("a.h", 3, "method", "cxx . . $ ns/f(1a).")],
            symbols=[lane_a("a.h", "f", 1, 3)],
        )
        assert symbols == [] and counts["refused"]["lane-a-symbol-near"] == 1

    def test_a_prototype_mints_nothing(self, tmp_path):
        # gtest forward-declares `CountIf` and defines it 900 lines up;
        # scip-clang gives the declaration the definition role. 308 on fmt.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int CountIf(int x);\n"},
            [row("a.h", 1, "method", "cxx . . $ testing/CountIf(1a).")],
        )
        assert symbols == [] and counts["refused"]["declaration"] == 1

    def test_a_defaulted_function_mints_nothing(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "struct A {\n    A() = default;\n};\n"},
            [row("a.h", 2, "method", "cxx . . $ ns/A#A(1a).")],
        )
        assert symbols == [] and counts["refused"]["declaration"] == 1

    def test_an_unnamed_struct_mints_nothing(self, tmp_path):
        # scip-clang invents a name for it; the source has none to give the
        # symbol. cJSON's and sqlite-vector's whole mint was this shape.
        symbols, counts = mint(
            tmp_path,
            {"a.c": "typedef struct {\n    int n;\n} hooks;\n"},
            [row("a.c", 1, "type", "cxx . . $ $anonymous_type_9456a0145d41eb51_0#")],
        )
        assert symbols == [] and counts["refused"]["anonymous"] == 1

    def test_a_member_of_an_unnamed_struct_mints_nothing(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "struct { int get() { return 1; } } one;\n"},
            [row("a.h", 1, "method", "cxx . . $ $anonymous_type_11#get(1a).")],
        )
        assert symbols == [] and counts["refused"]["anonymous"] == 1

    def test_a_type_lane_a_already_names_at_another_line_mints_nothing(self, tmp_path):
        # `typedef struct cJSON {…} cJSON;`: lane A names the typedef at the
        # closing line, lane B the tag's. Lane A did not lose this type.
        typedef = {**lane_a("a.h", "cJSON", 9), "kind": "type"}
        symbols, counts = mint(
            tmp_path,
            {"a.h": "typedef struct cJSON\n{\n" + "    int n;\n" * 6 + "} cJSON;\n"},
            [row("a.h", 1, "type", "cxx . . $ cJSON#")],
            symbols=[typedef],
        )
        assert symbols == [] and counts["refused"]["lane-a-has-type"] == 1

    def test_a_function_lane_a_names_at_another_line_is_an_overload_and_still_mints(
        self, tmp_path
    ):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f(int x) { return x; }\n\n\n\n\nint f(long x) { return 1; }\n"},
            [row("a.h", 6, "method", "cxx . . $ ns/f(2b).")],
            symbols=[lane_a("a.h", "f", 1)],
        )
        assert [s["line"] for s in symbols] == [6] and counts["refused"]["lane-a-has-type"] == 0

    def test_a_moniker_the_reader_cannot_spell_mints_nothing(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f(int x) { return x; }\n"},
            [row("a.h", 1, "method", "not-a-moniker")],
        )
        assert symbols == [] and counts["refused"]["unreadable"] == 1

    def test_a_row_whose_line_already_starts_a_lane_a_symbol_is_counted_under_no_reason(
        self, tmp_path
    ):
        # The two lanes meeting is the normal case, not a refusal — and
        # it is read before rule 1, so a clean file's ordinary rows do
        # not fill the block with noise.
        symbols, counts = mint(
            tmp_path,
            {"a.h": "int f(int x) { return x; }\n"},
            [row("a.h", 1, "method", "cxx . . $ ns/f(1a).")],
            clean=("a.h",),
            symbols=[lane_a("a.h", "f", 1)],
        )
        assert symbols == [] and set(counts["refused"].values()) == {0}


class TestTheBodyRead:
    """Rule 6 is a token read, like ``cppsource._lost_template_header``:
    it parses nothing, because the shapes it tells apart are the ones the
    grammar could not read."""

    def test_a_semicolon_inside_parentheses_does_not_end_the_read(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": "void f(int a = g(1, 2)) {\n    (void) a;\n}\n"},
            [row("a.h", 1, "method", "cxx . . $ ns/f(1a).")],
        )
        assert [s["id"] for s in symbols] == ["a.h.ns::f"]
        assert counts["refused"]["declaration"] == 0

    def test_a_body_brace_on_a_later_line_is_still_a_body(self, tmp_path):
        symbols, _ = mint(
            tmp_path,
            {
                "a.h": "struct A {\n    A(int n);\n    int v;\n};\n"
                       "A::A(int n)\n    : v(n)\n{\n}\n"
            },
            [row("a.h", 5, "method", "cxx . . $ A#A(2b).")],
        )
        assert [(s["id"], s["kind"], s["line"]) for s in symbols] == [
            ("a.h.A::A", "method", 5)
        ]


class TestTheExtent:
    """ADR-134 §1: a minted function's ``end_line`` becomes its body's
    closing brace, matched in the file's own text — the only evidence
    there is, since scip-clang's index carries no ``enclosing_range``.
    Every refusal leaves the symbol the target ADR-129 §3 made it, which
    is never wrong, only coarser."""

    def one(self, tmp_path, source, *, at=1, kind="method", moniker="cxx . . $ ns/f(1a)."):
        symbols, counts = mint(tmp_path, {"a.h": source}, [row("a.h", at, kind, moniker)])
        assert len(symbols) == 1, symbols
        return symbols[0], counts["extents"]

    def test_a_body_over_several_lines_ends_at_its_closing_brace(self, tmp_path):
        symbol, extents = self.one(
            tmp_path, "int f(int x) {\n    int y = x;\n    return y;\n}\n"
        )
        assert (symbol["line"], symbol["end_line"]) == (1, 4)
        assert extents["read"] == 1 and set(extents["refused"].values()) == {0}

    def test_a_body_opening_below_the_name_ends_at_its_closing_brace(self, tmp_path):
        symbol, extents = self.one(
            tmp_path,
            "struct A {\n    A(int n);\n    int v;\n};\n"
            "A::A(int n)\n    : v(n)\n{\n    v = n;\n}\n",
            at=5,
            moniker="cxx . . $ A#A(2b).",
        )
        assert (symbol["line"], symbol["end_line"]) == (5, 9)
        assert extents["read"] == 1

    def test_a_one_line_body_is_an_extent_of_one_line(self, tmp_path):
        symbol, extents = self.one(tmp_path, "int f() { return 1; }\n")
        assert symbol["end_line"] == symbol["line"] == 1
        assert extents["read"] == 1 and symbol["extent"] == "braces"

    def test_a_brace_inside_a_literal_or_a_comment_does_not_close_the_body(self, tmp_path):
        symbol, extents = self.one(
            tmp_path,
            "int f() {\n"
            '    const char* s = "}";\n'
            "    char c = '}';\n"
            "    // }\n"
            "    /* } */\n"
            '    const char* r = R"x(})x";\n'
            # A `'` between two alphanumerics is a digit separator: read as
            # a literal it would blank the rest of the file, and the extent
            # would run off.
            "    int n = 1'000;\n"
            # A wide literal's quote follows an alphanumeric too, and it is
            # a literal: read as a number, its closing quote would open one
            # and blank the brace below.
            "    wchar_t w = L'}';\n"
            "    return n + c + w + s[0] + r[0];\n"
            "}\n",
        )
        assert symbol["end_line"] == 10
        assert extents["read"] == 1 and set(extents["refused"].values()) == {0}

    def test_a_conditional_inside_the_body_refuses(self, tmp_path):
        # Either branch may hold the brace the compiler saw. 34 on fmt.
        symbol, extents = self.one(
            tmp_path,
            "int f(int x) {\n#if FOO\n    return x;\n#else\n    return 0;\n#endif\n}\n",
        )
        assert symbol["end_line"] == symbol["line"] == 1
        assert extents["read"] == 0 and extents["refused"]["conditional-inside"] == 1

    def test_a_define_or_an_include_inside_the_body_refuses_nothing(self, tmp_path):
        symbol, extents = self.one(
            tmp_path,
            'int f() {\n#define LOCAL 1\n#include "other.h"\n    return LOCAL;\n}\n',
        )
        assert symbol["end_line"] == 5
        assert extents["read"] == 1 and extents["refused"]["conditional-inside"] == 0

    def test_a_body_that_never_closes_refuses(self, tmp_path):
        symbol, extents = self.one(tmp_path, "int f() {\n    return 1;\n")
        assert symbol["end_line"] == symbol["line"] == 1
        assert extents["read"] == 0 and extents["refused"]["runs-off"] == 1

    def test_a_line_with_no_body_at_all_refuses(self, tmp_path):
        # `shows_body` should have made this unreachable through `mint`;
        # the read refuses rather than assume it did.
        assert minted._extent(["int f(int x);"], 1) == (None, "no-body")

    #: `GTEST_REPEATER_METHOD_(OnTestStart, TestInfo)`: a whole method to
    #: clang, a line with no `{` and no `;` in the text, so the brace match
    #: runs on into the next function written out. 13 of fmt's 19.
    SWALLOWED = (
        "MAKE_METHOD(OnTestStart, TestInfo)\n"
        "\n"
        "int written(int v) {\n"
        "    return v;\n"
        "}\n"
    )

    def test_a_match_running_into_a_lane_a_function_refuses(self, tmp_path):
        symbols, counts = mint(
            tmp_path,
            {"a.h": self.SWALLOWED},
            [row("a.h", 1, "method", "cxx . . $ ns/OnTestStart(1a).")],
            symbols=[lane_a("a.h", "written", 3, 5)],
        )
        assert [(s["line"], s["end_line"]) for s in symbols] == [(1, 1)]
        assert counts["extents"] == {
            "read": 0,
            "refused": {**dict.fromkeys(minted.EXTENT_REFUSALS, 0), "holds-a-definition": 1},
        }

    def test_two_macro_generated_rows_over_one_written_body_are_both_refused(
        self, tmp_path
    ):
        # The symbol below is another minted one, and the pass is over the
        # whole minted list: each row whose match swallows a definition is
        # refused, the one that swallows nothing keeps its extent.
        symbols, counts = mint(
            tmp_path,
            {
                "a.h": "MAKE_A(x)\n\nMAKE_B(y)\n\n"
                       "int written(int v) {\n    return v;\n}\n"
            },
            [
                row("a.h", 1, "method", "cxx . . $ ns/A(1a)."),
                row("a.h", 3, "method", "cxx . . $ ns/B(2b)."),
                row("a.h", 5, "method", "cxx . . $ ns/written(3c)."),
            ],
        )
        assert [(s["line"], s["end_line"]) for s in symbols] == [(1, 1), (3, 3), (5, 7)]
        assert counts["extents"]["refused"]["holds-a-definition"] == 2
        assert counts["extents"]["read"] == 1

    def test_a_minted_type_stays_a_line_and_is_counted_nowhere(self, tmp_path):
        symbol, extents = self.one(
            tmp_path,
            "struct FilePath {\n    int n;\n};\n",
            kind="type",
            moniker="cxx . . $ testing/internal/FilePath#",
        )
        assert symbol["end_line"] == symbol["line"] == 1
        assert extents == {"read": 0, "refused": dict.fromkeys(minted.EXTENT_REFUSALS, 0)}

    def test_the_extent_block_names_every_reason_whether_or_not_it_fired(self, tmp_path):
        _, extents = self.one(tmp_path, "int f() { return 1; }\n")
        assert list(extents["refused"]) == list(minted.EXTENT_REFUSALS)


class TestTheRehoming:
    """ADR-134 §3, the pure half. ``project`` reads a caller as
    ``fact.scope or enclosing(module, line) or module``, so a scopeless
    fact re-homes by itself once ``end_line`` is real; what this function
    does is the other half, and what it counts is what moves either way."""

    MODULES = {"a.cc": "a"}

    @staticmethod
    def fact(kind="calls", line=12, scope="", file="a.cc"):
        from hobbes.extract import evidence as ev

        return ev.Resolved(
            kind=kind,
            source_file=file,
            line=line,
            scope=scope,
            def_file="b.h",
            def_line=1,
            tier="semantic",
            lanes=("scip",),
        )

    @staticmethod
    def lost(line=10, end_line=20, name="lost", read=True):
        return {
            "id": f"a.{name}",
            "module": "a",
            "name": name,
            "qualname": name,
            "kind": "function",
            "line": line,
            "end_line": end_line,
            "declared_by": "scip",
            **({"extent": "braces"} if read else {}),
        }

    def rehome(self, facts, minted_symbols, symbols=()):
        return minted.rehome(facts, minted_symbols, list(symbols), self.MODULES)

    def test_a_scope_starting_before_the_extent_becomes_the_minted_symbol(self):
        out, moved = self.rehome(
            [self.fact(scope="a.outer")], [self.lost()], [lane_a("a", "outer", 1, 30)]
        )
        assert [f.scope for f in out] == ["a.lost"] and moved == 1

    def test_a_scope_starting_inside_the_extent_is_left_alone(self):
        # The extent is not the innermost thing holding the line: whatever
        # lane A parsed in there knows better than the brace match.
        out, moved = self.rehome(
            [self.fact(scope="a.inner")], [self.lost()], [lane_a("a", "inner", 11, 19)]
        )
        assert [f.scope for f in out] == ["a.inner"] and moved == 0

    def test_a_scope_that_is_the_modules_own_id_is_the_module_and_takes_the_extent(self):
        # Lane A's C and C++ sites at file scope carry the module's id, not
        # an empty scope, and `project` reads a truthy scope as the caller —
        # so without this the rule's main case would never move (args'
        # first real ingest: 2 rows of 16).
        out, moved = self.rehome([self.fact(scope="a")], [self.lost()])
        assert [f.scope for f in out] == ["a.lost"] and moved == 1

    def test_a_module_scoped_fact_a_lane_a_type_inside_the_extent_holds_is_left_alone(self):
        local = {**lane_a("a", "Local", 11, 14), "kind": "type"}
        out, moved = self.rehome([self.fact(scope="a", line=12)], [self.lost()], [local])
        assert [f.scope for f in out] == ["a"] and moved == 0

    def test_a_body_of_one_line_takes_the_call_written_on_it(self):
        # `int f() { return g(); }`: the site is module-scoped, the extent is
        # its own line, and the mark says it was read (56 rows on fmt).
        out, moved = self.rehome(
            [self.fact(scope="a", line=10)], [self.lost(line=10, end_line=10)]
        )
        assert [f.scope for f in out] == ["a.lost"] and moved == 1

    def test_a_refused_symbols_own_line_takes_nothing(self):
        # The same line and the same `end_line`, without the mark: the
        # extent was refused, and a refusal re-homes nothing at all.
        out, moved = self.rehome(
            [self.fact(scope="a", line=10)], [self.lost(line=10, end_line=10, read=False)]
        )
        assert [f.scope for f in out] == ["a"] and moved == 0

    def test_a_scope_naming_nothing_this_graph_holds_is_left_alone(self):
        out, moved = self.rehome([self.fact(scope="a.gone")], [self.lost()])
        assert [f.scope for f in out] == ["a.gone"] and moved == 0

    def test_a_scopeless_fact_is_untouched_and_counted(self):
        # `enclosing` will answer with the minted symbol, so the edge moves
        # without this function rewriting anything.
        out, moved = self.rehome([self.fact()], [self.lost()])
        assert [f.scope for f in out] == [""] and moved == 1

    def test_a_scopeless_fact_a_nearer_symbol_holds_is_not_counted(self):
        inner = {**lane_a("a", "Inner", 11, 19), "kind": "type"}
        out, moved = self.rehome([self.fact()], [self.lost()], [inner])
        assert [f.scope for f in out] == [""] and moved == 0

    def test_a_fact_outside_every_extent_is_left_alone(self):
        out, moved = self.rehome(
            [self.fact(line=25, scope="a.outer")], [self.lost()], [lane_a("a", "outer", 1, 30)]
        )
        assert [f.scope for f in out] == ["a.outer"] and moved == 0

    def test_an_implements_fact_is_left_alone(self):
        # Both its ends are definitions, read by `starting_at` and not by
        # a scope.
        out, moved = self.rehome(
            [self.fact(kind="implements", scope="a.outer")],
            [self.lost()],
            [lane_a("a", "outer", 1, 30)],
        )
        assert [f.scope for f in out] == ["a.outer"] and moved == 0

    def test_a_refused_symbols_would_be_body_moves_nothing(self):
        out, moved = self.rehome(
            [self.fact(scope="a.outer")],
            [self.lost(line=10, end_line=10)],
            [lane_a("a", "outer", 1, 30)],
        )
        assert [f.scope for f in out] == ["a.outer"] and moved == 0

    def test_two_extents_in_one_file_each_take_their_own_facts(self):
        # Nested extents cannot exist — `holds-a-definition` refuses them —
        # so two in a file are two bodies, side by side.
        facts = [
            self.fact(line=12, scope="a.outer"),
            self.fact(line=32, scope="a.outer"),
            self.fact(line=25, scope="a.outer"),
        ]
        out, moved = self.rehome(
            facts,
            [self.lost(10, 20, "first"), self.lost(30, 40, "second")],
            [lane_a("a", "outer", 1, 50)],
        )
        assert [f.scope for f in out] == ["a.first", "a.second", "a.outer"]
        assert moved == 2


class TestTheContradiction:
    """ADR-135's two rules, the pure half. R1 removes a lane A C++ symbol
    whose own name token the index reads as a *reference* — a definition's
    name never is one — and R2 re-reads the extent of one holding a
    definition the index places at file or class scope. Both fail toward
    leaving lane A's symbol exactly as it is."""

    MODULES = {"a.cc": "a"}

    @staticmethod
    def symbol(name="f", line=10, end_line=10, col=4, **extra):
        """One lane A C++ function, as ``graph["symbols"]`` holds it: the
        name's 0-based column is the whole of what R1 reads."""
        return {
            "id": f"a.{name}",
            "module": "a",
            "name": name,
            "qualname": name,
            "kind": "function",
            "line": line,
            "end_line": end_line,
            "name_col": col,
            **extra,
        }

    @staticmethod
    def site(line=10, name="f", col=4, def_file="m.h", def_line=3):
        from hobbes.extract import evidence as ev

        return ev.Site(
            provider=ev.SCIP,
            kind=ev.RESOLUTION,
            file="a.cc",
            line=line,
            name=name,
            col=col,
            def_file=def_file,
            def_line=def_line,
        )

    @staticmethod
    def fact(scope="a.f", line=11):
        from hobbes.extract import evidence as ev

        return ev.Resolved(
            kind="calls",
            source_file="a.cc",
            line=line,
            scope=scope,
            def_file="b.h",
            def_line=1,
            tier="semantic",
            lanes=("scip",),
        )

    def run(self, tmp_path, symbols, *, facts=(), resolutions=(), definitions=(), source=None):
        if source is not None:
            (tmp_path / "a.cc").write_text(source)
        return minted.contradicted(
            tmp_path,
            list(symbols),
            list(facts),
            list(resolutions),
            list(definitions),
            self.MODULES,
        )

    # ------------------------------------------------------------ R1

    def test_a_name_token_the_index_reads_as_a_macro_reference_is_refused(self, tmp_path):
        # `void UnitTest::AddTestPartResult(..) GTEST_LOCK_EXCLUDED_(mutex_)
        # {` is a function called `GTEST_LOCK_EXCLUDED_` to lane A. 13 on
        # fmt, all 13 misnamed.
        symbols, facts, counts = self.run(
            tmp_path,
            [self.symbol()],
            facts=[self.fact()],
            resolutions=[self.site()],
            definitions=[row("m.h", 3, "macro", "cxx . . $ GTEST_LOCK_EXCLUDED_!")],
        )
        assert symbols == []
        assert counts["refused"] == {"macro": 1, "term": 0}
        # The module's id, which is the scope lane A gives a file-level C++
        # site — so the mint and `rehome`, which run next, draw the fact
        # from the true definition where the index has one.
        assert [f.scope for f in facts] == ["a"]
        assert counts["facts_rescoped"] == 1

    def test_a_term_row_of_the_symbols_own_name_is_refused(self, tmp_path):
        # `FMT_CONSTEVAL basic_fstring(const S& s) : str_(s) {` is a
        # constructor lane A named after its first member initialiser. 5 on
        # fmt, the register's "2 symbols" being what one key's rows showed.
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol(name="str_")],
            resolutions=[self.site(name="str_")],
            definitions=[row("m.h", 3, "term", "cxx . . $ fmt/basic_fstring#str_.")],
        )
        assert symbols == []
        assert counts["refused"] == {"macro": 0, "term": 1}

    def test_a_term_row_of_another_name_is_kept(self, tmp_path):
        # The index reading the token as a member of some *other* name is
        # not this shape, and a symbol nothing contradicts does not move.
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol(name="str_")],
            resolutions=[self.site(name="str_")],
            definitions=[row("m.h", 3, "term", "cxx . . $ fmt/basic_fstring#other_.")],
        )
        assert [s["id"] for s in symbols] == ["a.str_"]
        assert counts["refused"] == {"macro": 0, "term": 0}

    @pytest.mark.parametrize(
        "where",
        [{"col": 5}, {"line": 12}, {"col": -1}],
        ids=["one column off", "another line of the body", "no column at all"],
    )
    def test_a_same_named_reference_that_is_not_at_the_token_is_kept(self, tmp_path, where):
        """The position has to be exact: read loosely, the rule flags
        *right* symbols — args' `Base::KickOut`, whose body uses the
        enumerator `Options::KickOut`, is four such on the measured cells."""
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol(name="KickOut", end_line=20)],
            resolutions=[self.site(name="KickOut", **where)],
            definitions=[row("m.h", 3, "term", "cxx . . $ ns/Options#KickOut.")],
        )
        assert [s["id"] for s in symbols] == ["a.KickOut"]
        assert set(counts["refused"].values()) == {0}

    @pytest.mark.parametrize(
        "definitions",
        [
            [row("m.h", 3, "method", "cxx . . $ ns/f(1a).")],
            [row("other.h", 9, "method", "cxx . . $ ns/f(1a).")],
        ],
        ids=["the index agrees with the name", "a def_file with no rows at all"],
    )
    def test_anything_but_a_macro_or_a_term_leaves_the_symbol_alone(
        self, tmp_path, definitions
    ):
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol()],
            resolutions=[self.site()],
            definitions=definitions,
        )
        assert [s["id"] for s in symbols] == ["a.f"]
        assert set(counts["refused"].values()) == {0}

    def test_a_symbol_with_no_name_col_is_never_refused_and_never_re_read(self, tmp_path):
        # A C symbol, or a minted one: neither carries the column, and
        # neither is a parse ADR-135 has anything to say about.
        plain = {k: v for k, v in self.symbol(line=1, end_line=6).items() if k != "name_col"}
        symbols, facts, counts = self.run(
            tmp_path,
            [plain],
            facts=[self.fact(line=5)],
            resolutions=[self.site(line=1)],
            definitions=[
                row("m.h", 3, "macro", "cxx . . $ FMT_API!"),
                row("a.cc", 5, "method", "cxx . . $ ns/next_one(2b)."),
            ],
            source="void f() {\n    g();\n}\n\nvoid next_one() {\n}\n",
        )
        assert symbols == [plain] and [f.scope for f in facts] == ["a.f"]
        assert not minted.contradicted_fired(counts)

    # ------------------------------------------------------------ R2

    #: A parse that ran on: `f` closes at line 3, and the index has a
    #: file-scope definition of its own at line 5.
    SWALLOWED = "void f() {\n    g();\n}\n\nvoid next_one() {\n    g();\n}\n"

    def test_an_extent_holding_a_file_scope_definition_is_read_from_the_braces(
        self, tmp_path
    ):
        symbols, facts, counts = self.run(
            tmp_path,
            [self.symbol(line=1, end_line=7)],
            facts=[self.fact(line=2), self.fact(line=6)],
            definitions=[row("a.cc", 5, "method", "cxx . . $ ns/next_one(2b).")],
            source=self.SWALLOWED,
        )
        assert [(s["id"], s["end_line"]) for s in symbols] == [("a.f", 3)]
        assert counts["extents"]["read"] == 1 and counts["extents"]["kept"] == 0
        # The call inside the real body keeps its caller; the one past it —
        # written in the definition the parse swallowed — takes the module.
        assert [f.scope for f in facts] == ["a.f", "a"]
        assert counts["facts_rescoped"] == 1
        # Nothing says `braces` on a lane A symbol: that field says *minted*.
        assert "extent" not in symbols[0]

    def test_a_definition_local_to_a_function_is_inside_by_right(self, tmp_path):
        # A lambda's or a local class's method (C-9, the mint's
        # `local-to-function`): its moniker's chain holds a method before
        # the last, and it contradicts no extent at all.
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol(line=1, end_line=7)],
            definitions=[row("a.cc", 5, "method", "cxx . . $ ns/f(1a).local#run(2b).")],
            source=self.SWALLOWED,
        )
        assert [(s["id"], s["end_line"]) for s in symbols] == [("a.f", 7)]
        assert not minted.contradicted_fired(counts)

    def test_braces_that_agree_with_the_parse_leave_the_symbol_alone(self, tmp_path):
        # The held row is something this rule does not understand, and an
        # end at or past the parse's is no evidence against it.
        symbols, _, counts = self.run(
            tmp_path,
            [self.symbol(line=1, end_line=3)],
            definitions=[row("a.cc", 2, "method", "cxx . . $ ns/inner(2b).")],
            source=self.SWALLOWED,
        )
        assert [(s["id"], s["end_line"]) for s in symbols] == [("a.f", 3)]
        assert counts["extents"]["kept"] == 1 and counts["extents"]["read"] == 0

    def test_a_conditional_in_the_body_refuses_and_leaves_a_line(self, tmp_path):
        # ADR-134's refusal, kept: either branch may hold the brace the
        # compiler saw, so the symbol keeps its own line and nothing else.
        symbols, facts, counts = self.run(
            tmp_path,
            [self.symbol(line=1, end_line=6)],
            facts=[self.fact(line=3)],
            definitions=[row("a.cc", 6, "method", "cxx . . $ ns/next_one(2b).")],
            source="void f() {\n#if GUARD\n    g();\n#endif\n}\nvoid next_one() {}\n",
        )
        assert [(s["id"], s["end_line"]) for s in symbols] == [("a.f", 1)]
        assert counts["extents"]["refused"] == {
            **dict.fromkeys(minted.READ_REFUSALS, 0),
            "conditional-inside": 1,
        }
        assert [f.scope for f in facts] == ["a"] and counts["facts_rescoped"] == 1

    def test_nothing_fired_says_so_and_the_caller_writes_no_block(self, tmp_path):
        symbols, facts, counts = self.run(
            tmp_path, [self.symbol()], facts=[self.fact()]
        )
        assert [s["id"] for s in symbols] == ["a.f"] and [f.scope for f in facts] == ["a.f"]
        assert counts == {
            "refused": dict.fromkeys(minted.CONTRADICTIONS, 0),
            "extents": {
                "read": 0,
                "kept": 0,
                "refused": dict.fromkeys(minted.READ_REFUSALS, 0),
            },
            "facts_rescoped": 0,
        }
        assert not minted.contradicted_fired(counts)


class TestTheParameterRead:
    """ADR-130's other end on a minted symbol: the same token read, one
    question over. A minted definition is one lane A's parse lost, so the
    count comes from the file's own tokens or from nothing — and nothing,
    here as everywhere, draws the edge."""

    def only(self, tmp_path, source: str, moniker: str = "cxx . . $ ns/f(1a)."):
        symbols, _ = mint(tmp_path, {"a.h": source}, [row("a.h", 1, "method", moniker)])
        assert len(symbols) == 1, symbols
        return symbols[0]["max_params"]

    @pytest.mark.parametrize(
        "source,expected",
        [
            ("void f() {\n}\n", 0),
            ("void f(void) {\n}\n", 0),
            ("void f(int a, int b = 2) {\n}\n", 2),
            # A C ellipsis and a parameter pack: any number at all.
            ("void f(int a, ...) {\n}\n", None),
            ("template <typename... A> void f(A&&... args) {\n}\n", None),
            # A comma inside a nested list belongs to that list.
            ("void f(map<int, int> m, int b) {\n}\n", 2),
            ("void f(const char* s = \"a, b\", int n = 1) {\n}\n", 2),
            # The list broken over three lines is one list.
            ("void f(int a,\n       int b,\n       int c) {\n}\n", 3),
            # A default argument holding a call with commas of its own.
            ("void f(int a = g(1, 2), int b = 3) {\n}\n", 2),
            # A macro: what it expands to is not in this file's tokens.
            ("void f(int a, FMT_API(x) b) {\n}\n", None),
            # A bracket the read cannot balance: a `>` written as a
            # comparison closes no template list, and no count follows.
            ("void f(int a = b > c) {\n}\n", None),
            ("void f(vector<int a) {\n}\n", None),
        ],
    )
    def test_the_token_read_counts_a_list_or_says_nothing(self, tmp_path, source, expected):
        assert self.only(tmp_path, source) == expected

    def test_a_method_defined_out_of_line_is_read_at_its_own_line(self, tmp_path):
        symbols, _ = mint(
            tmp_path,
            {"a.h": "struct A {\n    A(int n, int m);\n    int v;\n};\n"
                    "A::A(int n, int m)\n    : v(n)\n{\n}\n"},
            [row("a.h", 5, "method", "cxx . . $ A#A(2b).")],
        )
        assert [(s["id"], s["max_params"]) for s in symbols] == [("a.h.A::A", 2)]

    def test_a_minted_type_carries_no_count(self, tmp_path):
        # A type takes no arguments in this sense: a construction's target
        # is its constructor, and the rule never reads a type anyway.
        symbols, _ = mint(
            tmp_path,
            {"a.h": "struct FilePath { int n; };\n"},
            [row("a.h", 1, "type", "cxx . . $ testing/internal/FilePath#")],
        )
        assert [s["kind"] for s in symbols] == ["type"]
        assert "max_params" not in symbols[0]


class TestTheIds:
    def test_a_collision_with_a_lane_a_symbol_takes_b2_and_lane_a_does_not_move(
        self, tmp_path
    ):
        taken = lane_a("a.h", "ns::f", 1, 1)
        symbols, _ = mint(
            tmp_path,
            {"a.h": "int f() { return 1; }\n\n\n\n\nint f(int x) { return x; }\n"},
            [row("a.h", 6, "method", "cxx . . $ ns/f(2b).")],
            symbols=[taken],
        )
        assert [s["id"] for s in symbols] == ["a.h.ns::f~b2"]
        # The qualname stays the compiler's spelling; only the id moves.
        assert symbols[0]["qualname"] == "ns::f"
        assert taken["id"] == "a.h.ns::f"

    def test_two_mints_of_one_qualname_take_the_bare_id_and_b2_in_line_order(
        self, tmp_path
    ):
        symbols, counts = mint(
            tmp_path,
            {
                "a.h": "int f() { return 1; }\n\n\n\n\nint f(int x) { return x; }\n",
                "b.h": "int f() { return 1; }\n",
            },
            [
                row("a.h", 6, "method", "cxx . . $ ns/f(2b)."),
                row("a.h", 1, "method", "cxx . . $ ns/f(1a)."),
                row("b.h", 1, "method", "cxx . . $ ns/f(3c)."),
            ],
        )
        assert [(s["id"], s["line"]) for s in symbols] == [
            ("a.h.ns::f", 1),
            ("a.h.ns::f~b2", 6),
            # Another module, so no collision at all.
            ("b.h.ns::f", 1),
        ]
        assert (counts["symbols"], counts["files"]) == (3, 2)


class TestThroughTheIngest:
    """The whole extraction over a repo whose header really loses its
    definitions to a macro. Lane B is hand-fed — the real one needs
    scip-clang and a container (that case is `lane_b`-marked in
    ``test_scipsource_c.py``) — so what is under test is the wiring."""

    @staticmethod
    def repo(tmp_path: Path) -> Path:
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "lost.h").write_text(LOST_HEADER)
        (tmp_path / "src" / "main.cpp").write_text(LOST_MAIN)
        return tmp_path

    @staticmethod
    def facts(definitions, references=()):
        from hobbes.extract import evidence as ev

        return {
            "language": "cpp",
            "definitions": list(definitions),
            "references": [
                ev.Site(provider=ev.SCIP, kind=ev.RESOLUTION, **ref) for ref in references
            ],
            "external_refs": [],
            "degraded": [],
        }

    @staticmethod
    def graph(monkeypatch, repo: Path, facts):
        import hobbes.extract as extract
        from hobbes.extract import extract_repo

        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(repo).graph

    #: The call scip-clang resolved into the lost definition: `lib::lost`
    #: at main.cpp:5, answered with lost.h:9.
    LOST_CALL = {
        "file": "src/main.cpp", "line": 5, "col": 16, "name": "lost",
        "def_file": "src/lost.h", "def_line": 9,
    }
    #: `lib::Lost made(1)` at main.cpp:4, answered with the class.
    CONSTRUCT = {
        "file": "src/main.cpp", "line": 4, "col": 9, "name": "Lost",
        "def_file": "src/lost.h", "def_line": 11,
    }
    DEFINITIONS = [
        row("src/lost.h", 9, "method", LOST_MONIKER),
        row("src/lost.h", 11, "type", LOST_TYPE_MONIKER),
        row("src/lost.h", 13, "method", DECLARED_ONLY_MONIKER),
    ]

    def test_the_header_really_loses_its_definitions_to_the_macro(self, tmp_path):
        """The premise, checked with the parser rather than assumed: if a
        grammar release starts reading ``BEGIN_NS``, this file stops
        testing what it is here to test and says so."""
        from hobbes.extract.cppsource import extract_cpp

        layer = extract_cpp(self.repo(tmp_path))
        assert layer["lossy_files"] == frozenset({"src/lost.h"})
        assert [s["id"] for s in layer["symbols"]] == ["src/main.main"]

    def test_a_call_onto_the_lost_line_draws_to_the_minted_symbol(
        self, tmp_path, monkeypatch
    ):
        graph = self.graph(
            monkeypatch,
            self.repo(tmp_path),
            self.facts(self.DEFINITIONS, [self.LOST_CALL]),
        )
        assert graph["minted"]["symbols"] == 2
        assert graph["minted"]["files"] == 1
        # The prototype at line 13 is the one refusal this repo exercises.
        assert graph["minted"]["refused"]["declaration"] == 1
        edge = next(
            e for e in graph["symbol_edges"]
            if (e["from"], e["type"]) == ("src/main.main", "calls")
            and e["to"].startswith("src/lost.h.")
        )
        assert edge["to"] == "src/lost.h.lib::v1::lost"
        assert edge["tier"] == "semantic"
        assert [(s["path"], s["line"]) for s in edge["evidence"]] == [("src/main.cpp", 5)]
        # The site is no longer in the below-floor tail.
        row_ = next(r for r in graph["resolution_coverage"] if r["file"] == "src/main.cpp")
        assert "floored" not in row_

    def test_without_the_definitions_row_the_same_fact_is_below_floor(
        self, tmp_path, monkeypatch
    ):
        graph = self.graph(
            monkeypatch, self.repo(tmp_path), self.facts([], [self.LOST_CALL])
        )
        assert graph["minted"] == {
            "symbols": 0,
            "files": 0,
            "refused": dict.fromkeys(minted.REFUSALS, 0),
            # ADR-134: nothing minted is nothing to read an extent from,
            # and no fact to re-home.
            "extents": {
                "read": 0,
                "refused": dict.fromkeys(minted.EXTENT_REFUSALS, 0),
                "rehomed": 0,
            },
        }
        assert not [s for s in graph["symbols"] if s.get("declared_by")]
        row_ = next(r for r in graph["resolution_coverage"] if r["file"] == "src/main.cpp")
        assert row_["floored"] == 1
        assert row_["tail"]["below-floor"] == 1

    def test_a_call_onto_a_minted_type_draws_uses_and_never_calls(
        self, tmp_path, monkeypatch
    ):
        # `_CALLS_TO_TYPE_GUARDED` needs no change for a minted target:
        # the guard reads the projection's own symbol kinds (ADR-113 §2).
        graph = self.graph(
            monkeypatch,
            self.repo(tmp_path),
            self.facts(self.DEFINITIONS, [self.CONSTRUCT]),
        )
        onto = [
            (e["type"], e["tier"]) for e in graph["symbol_edges"]
            if e["to"] == "src/lost.h.lib::v1::Lost"
        ]
        assert onto == [("uses", "semantic")]

    #: ADR-134's own repo: `caller`'s body writes a call to `helper`, and
    #: `guarded`'s — inside an `#if` — writes the same one.
    @staticmethod
    def repo_with_a_caller(tmp_path: Path) -> Path:
        repo = TestThroughTheIngest.repo(tmp_path)
        (repo / "src" / "lost2.h").write_text(LOST_CALLER_HEADER)
        return repo

    DEFINITIONS_2 = [
        *DEFINITIONS,
        row("src/lost2.h", 9, "method", HELPER_MONIKER),
        row("src/lost2.h", 11, "method", CALLER_MONIKER),
        row("src/lost2.h", 16, "method", GUARDED_MONIKER),
    ]
    #: `helper(x)` at lost2.h:12, inside `caller`'s lost body.
    INNER_CALL = {
        "file": "src/lost2.h", "line": 12, "col": 12, "name": "helper",
        "def_file": "src/lost2.h", "def_line": 9,
    }
    #: The same call at lost2.h:18, inside `guarded`'s refused body.
    GUARDED_CALL = {
        "file": "src/lost2.h", "line": 18, "col": 12, "name": "helper",
        "def_file": "src/lost2.h", "def_line": 9,
    }

    def test_a_call_written_inside_a_lost_body_is_drawn_from_it(
        self, tmp_path, monkeypatch
    ):
        graph = self.graph(
            monkeypatch,
            self.repo_with_a_caller(tmp_path),
            self.facts(self.DEFINITIONS_2, [self.INNER_CALL, self.GUARDED_CALL]),
        )
        assert graph["minted"]["extents"] == {
            # `lost` and `helper` a line each, `caller` three; the type is
            # counted nowhere, and the prototype never reached the read.
            "read": 3,
            "refused": {
                **dict.fromkeys(minted.EXTENT_REFUSALS, 0),
                "conditional-inside": 1,
            },
            "rehomed": 1,
        }
        caller = next(
            s for s in graph["symbols"] if s["id"] == "src/lost2.h.lib::v1::caller"
        )
        assert (caller["line"], caller["end_line"]) == (11, 13)
        # A `uses` rather than a `calls`: lane A read no call site in a file
        # it lost whole, so the reference is lane B's alone. The re-homing
        # reads both kinds, and what is under test is the edge's `from`.
        onto = [
            (e["from"], e["type"]) for e in graph["symbol_edges"]
            if e["to"] == "src/lost2.h.lib::v1::helper"
        ]
        assert ("src/lost2.h.lib::v1::caller", "uses") in onto

    def test_a_call_inside_a_refused_body_is_still_the_modules(
        self, tmp_path, monkeypatch
    ):
        """The `#if` refusal, end to end: `guarded` stays a target, so the
        call written in it keeps the caller it had — the module."""
        graph = self.graph(
            monkeypatch,
            self.repo_with_a_caller(tmp_path),
            self.facts(self.DEFINITIONS_2, [self.GUARDED_CALL]),
        )
        guarded = next(
            s for s in graph["symbols"] if s["id"] == "src/lost2.h.lib::v1::guarded"
        )
        assert guarded["end_line"] == guarded["line"] == 16
        onto = [
            (e["from"], e["type"]) for e in graph["symbol_edges"]
            if e["to"] == "src/lost2.h.lib::v1::helper"
        ]
        assert onto == [("src/lost2.h", "uses")]
        assert graph["minted"]["extents"]["rehomed"] == 0

    #: ADR-135's own repo, C-164's shape end to end.
    @staticmethod
    def repo_with_an_annotation(tmp_path: Path) -> Path:
        repo = TestThroughTheIngest.repo(tmp_path)
        (repo / "src" / "lost3.h").write_text(LOST_ANNOTATED_HEADER)
        return repo

    DEFINITIONS_3 = [
        row("src/lost3.h", 4, "macro", LOCKED_MONIKER),
        row("src/lost3.h", 8, "method", INNER_MONIKER),
        row("src/lost3.h", 11, "method", ANNOTATED_MONIKER),
    ]
    #: The index's reference at exactly the token lane A took as the
    #: method's name — R1's whole evidence.
    MACRO_REFERENCE = {
        "file": "src/lost3.h", "line": 12, "col": 8, "name": "LOCKED_",
        "def_file": "src/lost3.h", "def_line": 4,
    }
    #: `inner(x)` at lost3.h:13, written inside the annotated body.
    ANNOTATED_CALL = {
        "file": "src/lost3.h", "line": 13, "col": 15, "name": "inner",
        "def_file": "src/lost3.h", "def_line": 8,
    }

    def test_the_header_really_names_the_method_after_the_macro(self, tmp_path):
        """The premise, checked with the parser rather than assumed: if a
        grammar release starts reading the annotation, this file stops
        testing C-164's shape and says so."""
        from hobbes.extract.cppsource import extract_cpp

        layer = extract_cpp(self.repo_with_an_annotation(tmp_path))
        misnamed = next(
            s for s in layer["symbols"] if s["id"] == "src/lost3.h.Holder3::LOCKED_"
        )
        assert (misnamed["kind"], misnamed["line"], misnamed["name_col"]) == ("method", 12, 8)
        assert not [s for s in layer["symbols"] if s["name"] == "annotated"]

    def test_a_symbol_the_index_reads_as_a_macro_reference_gives_up_its_calls(
        self, tmp_path, monkeypatch
    ):
        """R1 end to end: the misnamed symbol is gone, the definition the
        index names is minted with its own extent, and the call written
        inside the body is drawn from that definition instead."""
        graph = self.graph(
            monkeypatch,
            self.repo_with_an_annotation(tmp_path),
            self.facts(
                [*self.DEFINITIONS, *self.DEFINITIONS_3],
                [self.MACRO_REFERENCE, self.ANNOTATED_CALL],
            ),
        )
        assert graph["lane_a_contradicted"] == {
            "refused": {"macro": 1, "term": 0},
            "extents": {
                "read": 0,
                "kept": 0,
                "refused": dict.fromkeys(minted.READ_REFUSALS, 0),
            },
            # The call the misnamed symbol was drawing.
            "facts_rescoped": 1,
        }
        assert not [s for s in graph["symbols"] if s["name"] == "LOCKED_" and s["line"] == 12]
        annotated = next(
            s for s in graph["symbols"]
            if s["id"] == "src/lost3.h.lib::v1::Holder3::annotated"
        )
        assert (annotated["line"], annotated["end_line"]) == (11, 14)
        assert annotated["extent"] == "braces" and annotated["declared_by"] == "scip"
        edge = next(
            e for e in graph["symbol_edges"]
            if e["to"] == "src/lost3.h.inner" and e["type"] == "calls"
        )
        assert edge["from"] == "src/lost3.h.lib::v1::Holder3::annotated"

    def test_without_the_macro_reference_the_misnamed_symbol_keeps_its_call(
        self, tmp_path, monkeypatch
    ):
        """The other side of the same repo: nothing but the reference at
        the token removes a lane A symbol, and with no reference there the
        graph is what it was — the wrong caller included (C-164)."""
        graph = self.graph(
            monkeypatch,
            self.repo_with_an_annotation(tmp_path),
            self.facts([*self.DEFINITIONS, *self.DEFINITIONS_3], [self.ANNOTATED_CALL]),
        )
        assert "lane_a_contradicted" not in graph
        edge = next(
            e for e in graph["symbol_edges"]
            if e["to"] == "src/lost3.h.inner" and e["type"] == "calls"
        )
        assert edge["from"] == "src/lost3.h.Holder3::LOCKED_"

    def test_no_lane_b_facts_mint_nothing_and_write_no_block(self, tmp_path, monkeypatch):
        """P6: with no indexer the floor is exactly what it was."""
        import hobbes.extract as extract
        from hobbes.extract import extract_repo

        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([]))
        graph = extract_repo(self.repo(tmp_path)).graph
        assert "minted" not in graph
        assert not [s for s in graph["symbols"] if s.get("declared_by")]

    def test_nothing_lane_a_decided_moves(self, tmp_path, monkeypatch):
        """ADR-129 §4: the only consumer that moves is ``project``."""
        repo = self.repo(tmp_path)
        with_mint = self.graph(
            monkeypatch, repo, self.facts(self.DEFINITIONS, [self.LOST_CALL])
        )
        without = self.graph(monkeypatch, repo, self.facts([], [self.LOST_CALL]))

        def lane_a_symbols(graph):
            return [s for s in graph["symbols"] if not s.get("declared_by")]

        def syntactic(graph):
            return [e for e in graph["symbol_edges"] if e["tier"] == "syntactic"]

        assert lane_a_symbols(with_mint) == lane_a_symbols(without)
        assert syntactic(with_mint) == syntactic(without)
        assert with_mint["lane_agreement"] == without["lane_agreement"]
        assert with_mint["nodes"] == without["nodes"]
        assert with_mint["module_edges"] == without["module_edges"]
        # The one difference, and all of it: the minted nodes and the
        # edges onto them.
        assert [
            e for e in with_mint["symbol_edges"] if e not in without["symbol_edges"]
        ] == [
            e for e in with_mint["symbol_edges"] if e["to"].startswith("src/lost.h.")
        ]


def test_the_refusal_block_names_every_reason_whether_or_not_it_fired(tmp_path):
    """A reason that never fired reads ``0`` rather than being absent: the
    block a reader meets has the same shape on every repo."""
    _, counts = mint(tmp_path, {"a.h": "\n"}, [])
    assert list(counts["refused"]) == list(minted.REFUSALS)
    assert counts == {
        "symbols": 0,
        "files": 0,
        "refused": dict.fromkeys(minted.REFUSALS, 0),
        # `rehomed` is the caller's, counted where the facts are.
        "extents": {"read": 0, "refused": dict.fromkeys(minted.EXTENT_REFUSALS, 0)},
    }


class TestTheConstructorLines:
    """ADR-132's second half: which definition rows are a constructor's, so
    the join can tell a construction's reference from a type's at the same
    declared name. It mints nothing — it reads the mint's own rows."""

    CTOR = "cxx . . $ ns/T#T(1a2b)."

    def lines(self, *rows):
        return minted.constructor_lines(rows)

    def test_a_type_then_a_method_of_the_same_name_is_a_constructor(self):
        assert self.lines(row("a.cc", 7, "method", self.CTOR)) == frozenset(
            {("a.cc", 7)}
        )

    @pytest.mark.parametrize(
        "moniker",
        [
            # A destructor is the class's name with a `~`, and it is not
            # the class's name.
            "cxx . . $ ns/T#`~T`(1a2b).",
            # An operator is spelled as written, never as the type.
            "cxx . . $ ns/T#`operator=`(1a2b).",
            # A free function has no type in front of it at all.
            "cxx . . $ ns/make(1a2b).",
            # A local is a moniker the reader refuses outright.
            "local 12",
        ],
    )
    def test_what_is_not_a_constructor(self, moniker):
        assert self.lines(row("a.cc", 7, "method", moniker)) == frozenset()

    def test_a_line_with_two_distinct_monikers_is_left_out(self):
        # The mint's `several-monikers` reason, for its reason: which
        # definition the reference lands on would be a guess, and a wrong
        # one here draws a call that is not there.
        assert self.lines(
            row("a.cc", 7, "method", self.CTOR),
            row("a.cc", 7, "method", "cxx . . $ ns/T#other(3c4d)."),
        ) == frozenset()

    def test_the_same_moniker_twice_at_one_line_is_still_one(self):
        assert self.lines(
            row("a.cc", 7, "method", self.CTOR),
            row("a.cc", 7, "method", self.CTOR),
        ) == frozenset({("a.cc", 7)})


@pytest.mark.parametrize(
    "moniker, expected",
    [
        ("cxx . . $ fmt/v12/detail/write(9f11).", ["fmt", "v12", "detail", "write"]),
        ("cxx . . $ testing/internal/FilePath#", ["testing", "internal", "FilePath"]),
        ("cxx . . $ `src.a`/Engine#run(1a).", ["src.a", "Engine", "run"]),
        ("local 12", None),
        ("cxx . . $", None),
        ("cxx . . $ ns/(x)", None),
        ("cxx . . $ ns/f(", None),
        ("cxx . . $ ns/f(1a)", None),
    ],
)
def test_the_moniker_reader_agrees_with_the_helpers_descriptor_grammar(moniker, expected):
    """``scip/index.mjs``'s grammar, read from Python: anything the helper
    would call ``local``, ``malformed`` or a parameter descriptor is
    refused here rather than named by a guess."""
    chain = minted.read_moniker(moniker)
    assert (None if chain is None else [name for name, _ in chain]) == expected
