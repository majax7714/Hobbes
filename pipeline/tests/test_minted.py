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
LOST_MONIKER = "cxx . . $ lib/v1/lost(9ab1c0d2e3f40506)."
LOST_TYPE_MONIKER = "cxx . . $ lib/v1/Lost#"
DECLARED_ONLY_MONIKER = "cxx . . $ lib/v1/declared_only(77cc88dd99ee00ff)."


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
                # ADR-129 §3: a target, not a scope.
                "end_line": 2,
                "declared_by": "scip",
                # ADR-130: what the definition's own list can take.
                "max_params": 1,
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
    }


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
