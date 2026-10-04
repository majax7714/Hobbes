"""A Rust id two differently written impl blocks would share is told apart by
an ordinal, so each def is its own node (ADR-174, C-180 lifted); ADR-163's
refusal stays as the guard, tested on `project` directly.

``rustsource._impl_type`` names an impl block after its first type
identifier, so ``impl Pointer for *const T`` and ``impl Pointer for *mut
T`` both hang ``distance`` off ``T``, and a trait impl and the inherent
impl of one type share every method name they both declare. The node is
the first def. Before ADR-163 a call written in a later def was filed
under it — memchr's ``ext.rs:33`` drew ``T.distance calls T.distance``,
a recursion that does not exist, at ``semantic`` — and a call resolved
onto a later def's line fell ``below-floor``. ADR-163 refused both; since
ADR-174 the ``*mut T`` def is ``T.distance~2`` and its call of the
``*const T`` one is drawn.

The ``minirustimpl`` fixture is real source: ``src/ext.rs`` is memchr
2.8.3's ``ext.rs`` (lines 1–39, verbatim); ``src/client.rs`` writes
dagger's two shapes small (``From<&str>``/``From<String>`` for one type,
and an inherent ``describe`` beside a trait's); ``src/cow.rs`` keeps
memchr's cfg twins (``Imp`` as an enum and as a struct) and a function
defined once per ``cfg`` arm, which share a header and stay the node's.
"""

from pathlib import Path

import pytest

import hobbes.extract as extract
from hobbes.extract import evidence as ev
from hobbes.extract import extract_repo, rustsource, scipsource, tail
from hobbes.extract.schema import SEMANTIC

FIXTURE = Path(__file__).parent / "fixtures" / "minirustimpl"
SRC = FIXTURE / "src"


def _line_of(file: str, text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *file* that contains *text*."""
    hits = [
        i + 1 for i, line in enumerate((SRC / file).read_text().splitlines()) if text in line
    ]
    return hits[nth]


DISTANCE_CONST = _line_of("ext.rs", "unsafe fn distance(self, origin: *const T)")
DISTANCE_MUT = _line_of("ext.rs", "unsafe fn distance(self, origin: *mut T)")
CALL_IN_MUT = _line_of("ext.rs", "(self as *const T).distance(origin as *const T)")
FROM_STR = _line_of("client.rs", "fn from(value: &str)")
FROM_STRING = _line_of("client.rs", "fn from(value: String)")
INHERENT_DESCRIBE = _line_of("client.rs", "pub fn describe(&self)")
TRAIT_DESCRIBE = _line_of("client.rs", "fn describe(&self) -> String {", 1)
LABEL_CALL = _line_of("client.rs", "label(&self.name)")
NORMALISE_IN_FROM_STRING = _line_of("client.rs", "Id(normalise(&value))")
COUNT_CALL = _line_of("cow.rs", "count(bytes)")
WIDTH_ALLOC = _line_of("cow.rs", "pub fn width(bytes: &[u8]) -> usize {")
WIDTH_NO_ALLOC = _line_of("cow.rs", "pub fn width(bytes: &[u8]) -> usize {", 1)
WIDTH_CALL = _line_of("lib.rs", "cow::width(bytes)")

HAYSTACK = (FIXTURE / "haystacks" / "std.rs").read_text().splitlines()
HAYSTACK_RENDER = [i + 1 for i, line in enumerate(HAYSTACK) if line.startswith("pub fn render")]
HAYSTACK_RENDER_CALLS = [i + 1 for i, line in enumerate(HAYSTACK) if line.strip().startswith("helper()")]

EXT = "src/ext"
CLIENT = "src/client"


def calls(graph):
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


def lines_in(graph, path):
    """Every evidence line any symbol edge carries in *path*."""
    return {
        row["line"]
        for edge in graph["symbol_edges"]
        for row in edge["evidence"]
        if row["path"] == path
    }


def test_the_fixtures_lines_are_what_the_constants_say():
    assert DISTANCE_CONST < DISTANCE_MUT < CALL_IN_MUT
    assert FROM_STR < FROM_STRING == NORMALISE_IN_FROM_STRING - 1
    assert INHERENT_DESCRIBE < TRAIT_DESCRIBE == LABEL_CALL - 1


class TestTheOrdinals:
    """Lane A's own read: two impl headers, or two kinds, get two ids."""

    def _shared(self):
        files = [
            rustsource._parse_file(f"src/{name}", (SRC / name).read_bytes())
            for name in ("ext.rs", "client.rs", "cow.rs", "lib.rs")
        ]
        return rustsource.shared_qualnames(files)

    def test_each_differently_headed_def_gets_an_ordinal_and_none_is_shared(self):
        assert self._shared() == {}
        parsed = {
            name: rustsource._parse_file(f"src/{name}", (SRC / name).read_bytes())
            for name in ("ext.rs", "client.rs")
        }
        ids = {
            (s["qualname"], s["line"]) for p in parsed.values() for s in p.symbols
        }
        assert {
            ("T.distance", DISTANCE_CONST), ("T.distance~2", DISTANCE_MUT),
            ("Id.from", FROM_STR), ("Id.from~2", FROM_STRING),
            ("Client.describe", INHERENT_DESCRIBE), ("Client.describe~2", TRAIT_DESCRIBE),
        } <= ids
        assert "T.as_usize~2" in {s["qualname"] for s in parsed["ext.rs"].symbols}

    def test_two_kinds_get_an_ordinal_and_a_bare_repeat_does_not(self):
        # memchr's `haystacks` shape: `struct B` and `const B` are two items,
        # `B` and `B~2`; two ungated `fn render` share a header and a kind,
        # keep one id, and are named, not refused (C-182's residual).
        parsed = [rustsource._parse_file("haystacks/std.rs", (FIXTURE / "haystacks" / "std.rs").read_bytes())]
        assert rustsource.shared_qualnames(parsed) == {}
        assert [(s["qualname"], s["kind"]) for s in parsed[0].symbols if s["name"] == "B"] == [
            ("B", "type"), ("B~2", "const")
        ]
        assert rustsource.same_header_repeats(parsed) == {
            "haystacks/std.rs": {"haystacks/std.render": [(HAYSTACK_RENDER[0], HAYSTACK_RENDER[0] + 2),
                                                          (HAYSTACK_RENDER[1], HAYSTACK_RENDER[1] + 2)]}
        }
        assert rustsource.cfg_twins(parsed) == {}

    def test_cfg_twins_are_not_a_repeat(self):
        files = [
            rustsource._parse_file(f"src/{name}", (SRC / name).read_bytes())
            for name in ("ext.rs", "client.rs", "cow.rs", "lib.rs")
        ]
        assert rustsource.same_header_repeats(files) == {}

    def test_cfg_twins_share_a_header_and_keep_one_id(self):
        parsed = rustsource._parse_file("src/cow.rs", (SRC / "cow.rs").read_bytes())
        assert [s["qualname"] for s in parsed.symbols if s["name"] in ("Imp", "width")] == [
            "Imp", "Imp", "width", "width"
        ]

    def test_cfg_twins_are_listed_by_file_with_every_def(self):
        # ADR-165, C-182: the complement, read by `hobbes lanes`' shape.
        files = [
            rustsource._parse_file(f"src/{name}", (SRC / name).read_bytes())
            for name in ("ext.rs", "client.rs", "cow.rs", "lib.rs")
        ]
        twins = rustsource.cfg_twins(files)
        assert set(twins) == {"src/cow.rs"}
        assert set(twins["src/cow.rs"]) == {"src/cow.Imp", "src/cow.width"}
        assert [line for line, _ in twins["src/cow.rs"]["src/cow.width"]] == [
            WIDTH_ALLOC,
            WIDTH_NO_ALLOC,
        ]

    @pytest.mark.parametrize(
        "source, twins",
        [
            # The gate on an enclosing `mod` gates what it holds.
            (
                "#[cfg(unix)]\nmod imp { pub fn f() {} }\n"
                "#[cfg(not(unix))]\nmod imp { pub fn f() {} }\n",
                {"x.imp.f"},
            ),
            # Rust's type and value namespaces: two items, not one.
            ("struct B;\nconst B: usize = 6;\n", set()),
            ("#[cfg(a)]\nstruct B;\n#[cfg(a)]\nconst B: usize = 6;\n", set()),
            # No gate: a file no crate compiles repeats names freely.
            ("fn f() {}\nfn f() {}\n", set()),
            # One arm gated is not two arms.
            ("#[cfg(a)]\nfn f() {}\nfn f() {}\n", set()),
            # `cfg_attr` gates an attribute, never the item.
            ("#[cfg_attr(a, inline)]\nfn f() {}\n#[cfg_attr(b, inline)]\nfn f() {}\n", set()),
        ],
    )
    def test_a_twin_is_gated_and_of_one_kind(self, source, twins):
        parsed = rustsource._parse_file("x.rs", source.encode())
        assert set(rustsource.cfg_twins([parsed]).get("x.rs", {})) == twins
        # The gate rides beside the symbols, never in them.
        assert all("cfg" not in symbol for symbol in parsed.symbols)

    def test_the_header_is_the_text_up_to_the_body(self):
        parsed = rustsource._parse_file("src/ext.rs", (SRC / "ext.rs").read_bytes())
        assert [header for _, _, header in parsed.defs["T.distance"]] == ["impl<T> Pointer for *const T"]
        assert [header for _, _, header in parsed.defs["T.distance~2"]] == ["impl<T> Pointer for *mut T"]
        # The header rides beside the symbols, never in them.
        assert all("impl" not in symbol for symbol in parsed.symbols)


@pytest.fixture(scope="module")
def graph():
    """Lane A alone. Module-scoped fixtures run before the autouse
    lane-B-off monkeypatch, so the default is pinned here."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOBBES_SCIP", "0")
        return extract_repo(FIXTURE).graph


class TestLaneAAlone:
    """The suite default (lane B off): a later def is its own node, and the
    fallback's facts written in it are filed under it."""

    def test_what_a_later_def_writes_is_drawn_from_it(self, graph):
        drawn = calls(graph)
        assert [r["line"] for r in drawn[(f"{CLIENT}.Id.from~2", f"{CLIENT}.normalise")]["evidence"]] == [
            NORMALISE_IN_FROM_STRING
        ]
        assert [r["line"] for r in drawn[(f"{CLIENT}.Client.describe~2", f"{CLIENT}.label")]["evidence"]] == [
            LABEL_CALL
        ]
        assert [r["line"] for r in drawn[(f"{CLIENT}.Id.from", f"{CLIENT}.normalise")]["evidence"]] == [
            FROM_STR + 1
        ]

    def test_nothing_is_relabelled_and_the_sum_holds(self, graph):
        for row in graph["resolution_coverage"]:
            assert tail.SHARED_QUALNAME not in row.get("tail", {}), row
            expected = row["unresolved"] + row.get("floored", 0)
            assert sum(row.get("tail", {}).values()) == expected, row

    def test_the_fallback_still_abstains_on_an_overload_set(self, graph):
        # `Id::from(name)` in lib.rs: two impl blocks declare it (C-72).
        assert not [e for e in graph["symbol_edges"] if e["from"] == "src/lib.make" and "Id.from" in e["to"]]

    def test_cfg_twins_still_draw(self, graph):
        edge = calls(graph)[("src/cow.width", "src/cow.count")]
        assert [row["line"] for row in edge["evidence"]] == [COUNT_CALL]

    def test_no_shared_id_record_is_written(self, graph):
        assert not [e for e in graph["extraction_errors"] if e["stage"] == "rust-qualnames"]

    def test_one_record_names_the_cfg_twins_and_the_register_entry(self, graph):
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-cfg-twins"]
        assert record["message"].startswith("2 Rust symbol id(s) are cfg twins")
        assert "C-182" in record["message"] and "ADR-165" in record["message"]
        assert f"src/cow.width (defs at line {WIDTH_ALLOC}, {WIDTH_NO_ALLOC})" in record["message"]

    def test_the_second_kind_is_its_own_node(self, graph):
        # `const B = helper();` at line 14, beside `struct B` at line 4.
        edge = calls(graph)[("haystacks/std.B~2", "haystacks/std.helper")]
        assert [row["line"] for row in edge["evidence"]] == [14]

    def test_an_ungated_same_header_repeat_is_named_and_filed_as_before(self, graph):
        # `fn render` twice, no `cfg`: one node, both bodies' calls under it.
        edge = calls(graph)[("haystacks/std.render", "haystacks/std.helper")]
        assert [row["line"] for row in edge["evidence"]] == [HAYSTACK_RENDER_CALLS[0], HAYSTACK_RENDER_CALLS[1]]
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-repeats"]
        assert record["message"].startswith("1 Rust symbol id(s) in 1 file(s)")
        assert "C-182" in record["message"] and "haystacks/std.rs" in record["message"]
        assert f"haystacks/std.render (defs at line {HAYSTACK_RENDER[0]}, {HAYSTACK_RENDER[1]})" in record["message"]

    def test_the_guards_class_is_still_available_to_rust(self, graph):
        assert tail.SHARED_QUALNAME in graph["tail_classes_available"]["rust"]

    def test_first_defs_keep_their_ids_and_later_defs_have_their_own(self, graph):
        ids = {s["id"]: s["line"] for s in graph["symbols"]}
        assert ids[f"{EXT}.T.distance"] == DISTANCE_CONST
        assert ids[f"{EXT}.T.distance~2"] == DISTANCE_MUT
        assert ids[f"{CLIENT}.Client.describe"] == INHERENT_DESCRIBE
        assert ids[f"{CLIENT}.Client.describe~2"] == TRAIT_DESCRIBE
        assert ids[f"{CLIENT}.Id.from"] == FROM_STR
        assert ids[f"{CLIENT}.Id.from~2"] == FROM_STRING


def _site_col(file: str, line: int, name: str) -> int:
    return (SRC / file).read_text().splitlines()[line - 1].index(name)


class TestMemchrsResolutionByHand:
    """memchr's false edge, with lane B's own answer hand-built (the
    `test_tail` pattern): rust-analyzer resolves ``ext.rs:33``'s
    ``distance`` to the ``*const T`` impl's def at line 21. Before
    ADR-163 that drew ``T.distance calls T.distance``."""

    def _graph(self, monkeypatch, references):
        facts = {
            "language": "rust",
            "definitions": [],
            "references": references,
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(FIXTURE).graph

    def _resolution(self, file, line, name, def_file, def_line):
        return ev.Site(
            provider=ev.SCIP, kind=ev.RESOLUTION, file=file, line=line,
            col=_site_col(file.removeprefix("src/"), line, name), name=name,
            def_file=def_file, def_line=def_line,
        )

    def test_the_mut_impl_calls_the_const_one_and_no_self_loop(self, monkeypatch):
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/ext.rs", CALL_IN_MUT, "distance", "src/ext.rs", DISTANCE_CONST)],
        )
        drawn = calls(graph)
        assert (f"{EXT}.T.distance", f"{EXT}.T.distance") not in drawn
        assert drawn[(f"{EXT}.T.distance~2", f"{EXT}.T.distance")]["tier"] == SEMANTIC
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/ext.rs"]
        assert tail.SHARED_QUALNAME not in row.get("tail", {})

    def test_a_resolution_onto_a_later_def_draws_to_it(self, monkeypatch):
        span = _line_of("lib.rs", "unsafe { end.distance(start) }")
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/lib.rs", span, "distance", "src/ext.rs", DISTANCE_MUT)],
        )
        assert calls(graph)[("src/lib.span", f"{EXT}.T.distance~2")]["tier"] == SEMANTIC
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/lib.rs"]
        assert tail.SHARED_QUALNAME not in row.get("tail", {})
        assert tail.BELOW_FLOOR not in row.get("tail", {})

    def test_lane_b_naming_the_compiled_twin_is_a_cfg_twin_row(self, monkeypatch):
        # ADR-165, C-182: CI's row. Lane A's guess is the node's def, the
        # `alloc` arm; rust-analyzer, `alloc` off, names the other arm.
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/lib.rs", WIDTH_CALL, "width", "src/cow.rs", WIDTH_NO_ALLOC)],
        )
        [row] = [
            r for r in graph["lane_agreement"]["site_disagreements"] if r["name"] == "width"
        ]
        assert row["syntactic"] == f"src/cow.rs:{WIDTH_ALLOC}"
        assert row["semantic"] == f"src/cow.rs:{WIDTH_NO_ALLOC}"
        assert row["shape"] == "cfg-twin"
        # One node either way: the edge is the one lane A would draw.
        assert calls(graph)[("src/lib.measure", "src/cow.width")]["tier"] == SEMANTIC

    def test_a_resolution_onto_the_first_def_still_draws(self, monkeypatch):
        offset = _line_of("lib.rs", "unsafe { end.distance(start) }", 1)
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/lib.rs", offset, "distance", "src/ext.rs", DISTANCE_CONST)],
        )
        edge = calls(graph)[("src/lib.offset", f"{EXT}.T.distance")]
        assert edge["tier"] == SEMANTIC


LEAF_SHAPE = """\
pub trait Cipher {}
#[cfg(feature = "openssl-aead")]
pub mod aead {
    use super::*;
    pub struct AeadCipher;
    impl AeadCipher {
        pub fn new() -> Self {
            AeadCipher
        }
    }
}
#[cfg(not(feature = "openssl-aead"))]
pub mod aead {
    use super::*;
    pub struct AeadCipher;
    impl AeadCipher {
        pub fn new() -> Self {
            AeadCipher
        }
    }
}
"""


class TestTheCompiledArm:
    """ADR-165's second amendment (C-182): lane B's definitions say which arm
    the build compiled. leaf's `crypto.rs` in small: `mod aead` twice, the
    gate on the `mod`; rust-analyzer defines items only in the second."""

    def test_each_def_carries_its_gates_outermost_first(self):
        parsed = rustsource._parse_file("x.rs", LEAF_SHAPE.encode())
        # The gate is the `mod`, its attribute line included.
        assert parsed.cfg_gates[("aead.AeadCipher.new", 7)] == ((2, 11),)
        assert parsed.cfg_gates[("aead.AeadCipher.new", 17)] == ((12, 21),)
        assert ("Cipher", 1) not in parsed.cfg_gates

    def test_the_arm_lane_b_defined_is_compiled_and_the_other_mod_is_dead(self):
        parsed = rustsource._parse_file("x.rs", LEAF_SHAPE.encode())
        compiled, dead = rustsource.compiled_arms([parsed], {"x.rs": {1, 13, 15, 17}})
        assert compiled == {"x.aead.AeadCipher": (15, 15), "x.aead.AeadCipher.new": (17, 19)}
        # The whole first `mod`, not only the arms: its `impl` header is in it.
        assert dead == {"x.rs": [(2, 11)]}

    @pytest.mark.parametrize(
        "defined",
        [
            {},  # lane B silent on the file
            {"x.rs": {1}},  # neither arm defined
            {"x.rs": {1, 5, 7, 15, 17}},  # both arms defined: nothing to choose
        ],
    )
    def test_no_single_defined_arm_names_nothing(self, defined):
        parsed = rustsource._parse_file("x.rs", LEAF_SHAPE.encode())
        assert rustsource.compiled_arms([parsed], defined) == ({}, {})

    def test_a_gate_holding_a_definition_is_not_dead_the_arm_is(self):
        # The `mod` is live (lane B defines `g` in it); only `f`'s own gate died.
        source = (
            "mod m {\n    pub fn g() {}\n"
            "    #[cfg(a)]\n    pub fn f() {}\n"
            "    #[cfg(not(a))]\n    pub fn f() {}\n}\n"
        )
        parsed = rustsource._parse_file("x.rs", source.encode())
        compiled, dead = rustsource.compiled_arms([parsed], {"x.rs": {2, 6}})
        assert compiled == {"x.m.f": (6, 6)}
        assert dead == {"x.rs": [(3, 4)]}

    def _graph(self, monkeypatch, definitions, references):
        facts = {
            "language": "rust",
            "definitions": [{"file": "src/cow.rs", "line": line, "kind": "function"} for line in definitions],
            "references": references,
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(FIXTURE).graph

    def _resolution(self, file, line, name, def_file, def_line):
        return ev.Site(
            provider=ev.SCIP, kind=ev.RESOLUTION, file=file, line=line,
            col=_site_col(file.removeprefix("src/"), line, name), name=name,
            def_file=def_file, def_line=def_line,
        )

    def test_the_node_sits_at_the_compiled_arm_and_a_dead_arm_reference_is_refused(self, monkeypatch):
        count = _line_of("cow.rs", "fn count(bytes: &[u8]) -> usize {")
        imp_struct = _line_of("cow.rs", "pub struct Imp")
        graph = self._graph(
            monkeypatch,
            [imp_struct, WIDTH_NO_ALLOC, count],
            [
                # leaf's shape: a token in the arm the build left out,
                # resolved against the compiled arm's scope.
                self._resolution("src/cow.rs", WIDTH_ALLOC + 1, "bytes", "src/cow.rs", count),
                self._resolution("src/cow.rs", COUNT_CALL, "count", "src/cow.rs", count),
                self._resolution("src/lib.rs", WIDTH_CALL, "width", "src/cow.rs", WIDTH_NO_ALLOC),
            ],
        )
        lines = {s["id"]: (s["line"], s["end_line"]) for s in graph["symbols"]}
        assert lines["src/cow.width"] == (WIDTH_NO_ALLOC, WIDTH_NO_ALLOC + 2)
        assert lines["src/cow.Imp"][0] == imp_struct
        drawn = calls(graph)
        assert [r["line"] for r in drawn[("src/cow.width", "src/cow.count")]["evidence"]] == [COUNT_CALL]
        assert drawn[("src/lib.measure", "src/cow.width")]["tier"] == SEMANTIC
        assert WIDTH_ALLOC + 1 not in lines_in(graph, "src/cow.rs")
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-cfg-twins"]
        assert "2 sit at the one arm lane B defined" in record["message"]
        assert "1 lane B reference(s) written inside an arm the build did not compile were refused (1 file(s))" in record["message"]

    def test_without_lane_b_definitions_the_node_stays_at_its_first_arm(self, monkeypatch):
        graph = self._graph(
            monkeypatch,
            [],
            [self._resolution("src/lib.rs", WIDTH_CALL, "width", "src/cow.rs", WIDTH_NO_ALLOC)],
        )
        assert {s["id"]: s["line"] for s in graph["symbols"]}["src/cow.width"] == WIDTH_ALLOC
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-cfg-twins"]
        assert "0 sit at the one arm lane B defined" in record["message"]


class TestTheProjection:
    """`project` itself: the refusal is by line, for any lane, and the
    module edge the fact raises stays."""

    NODES = [
        {"id": "a", "kind": "module", "path": "a.rs"},
        {"id": "b", "kind": "module", "path": "b.rs"},
    ]
    SYMBOLS = [
        {"id": "a.T.f", "module": "a", "kind": "method", "line": 2, "end_line": 4},
        {"id": "b.g", "module": "b", "kind": "function", "line": 1, "end_line": 3},
    ]
    SHARED = {"a.T.f": [(6, 8)]}

    def _fact(self, line, def_file, def_line, source="a.rs"):
        return ev.Resolved(
            kind="calls", source_file=source, line=line, scope="", def_file=def_file,
            def_line=def_line, tier=SEMANTIC, lanes=(scipsource.SCIP_LANE,),
        )

    def test_inside_and_onto_a_later_def_are_refused_and_returned(self):
        out = scipsource.project(
            [self._fact(7, "b.rs", 1), self._fact(2, "a.rs", 6, source="b.rs")],
            self.NODES, self.SYMBOLS, shared=self.SHARED,
        )
        assert out["symbol_edges"] == []
        assert [(r["path"], r["line"], r["id"]) for r in out["shared_qualname"]] == [
            ("a.rs", 7, "a.T.f"),
            ("b.rs", 2, "a.T.f"),
        ]
        assert {(e["from"], e["to"]) for e in out["module_edges"]} == {("a", "b"), ("b", "a")}

    def test_the_first_def_draws_and_no_shared_map_is_what_it_was(self):
        fact = self._fact(3, "b.rs", 1)
        with_map = scipsource.project([fact], self.NODES, self.SYMBOLS, shared=self.SHARED)
        without = scipsource.project([fact], self.NODES, self.SYMBOLS)
        assert with_map["symbol_edges"] == without["symbol_edges"]
        assert [(e["from"], e["to"]) for e in without["symbol_edges"]] == [("a.T.f", "b.g")]
        assert with_map["shared_qualname"] == []

    def test_a_cfg_twins_other_arm_is_the_nodes_both_ways(self):
        # ADR-165: `a.T.f`'s second arm is lines 6-8. Onto it draws to the
        # node; inside it is filed under the node. Without the map, the
        # first falls below the floor, which is what CI's row hid.
        onto = self._fact(2, "a.rs", 6, source="b.rs")
        inside = self._fact(7, "b.rs", 1)
        out = scipsource.project(
            [onto, inside], self.NODES, self.SYMBOLS, twins={"a.T.f": [(6, 8)]}
        )
        assert sorted((e["from"], e["to"]) for e in out["symbol_edges"]) == [
            ("a.T.f", "b.g"),
            ("b.g", "a.T.f"),
        ]
        assert out["shared_qualname"] == []
        without = scipsource.project([onto], self.NODES, self.SYMBOLS)
        assert without["symbol_edges"] == []


@pytest.mark.lane_b
def test_with_the_index_every_def_is_its_own_node():
    """The whole ingest with rust-analyzer (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(FIXTURE).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    drawn = calls(graph)
    assert (f"{EXT}.T.distance", f"{EXT}.T.distance") not in drawn, err
    assert (f"{EXT}.T.as_usize", f"{EXT}.T.as_usize") not in drawn, err
    assert (f"{CLIENT}.Client.describe", f"{CLIENT}.label") not in drawn, err
    # ADR-174: every def its own node, each drawn at the index's tier — the
    # `*mut T` impl calling the `*const T` one, and the calls onto each.
    for pair in (
        (f"{EXT}.T.distance~2", f"{EXT}.T.distance"),
        (f"{EXT}.T.as_usize~2", f"{EXT}.T.as_usize"),
        (f"{CLIENT}.Client.describe~2", f"{CLIENT}.label"),
        (f"{CLIENT}.Id.from~2", f"{CLIENT}.normalise"),
        ("src/lib.span", f"{EXT}.T.distance~2"),
        ("src/lib.offset", f"{EXT}.T.distance"),
        ("src/lib.make", f"{CLIENT}.Client.describe"),
        ("src/lib.make", f"{CLIENT}.Id.from"),
        ("src/cow.width", "src/cow.count"),
    ):
        assert drawn[pair]["tier"] == SEMANTIC, (pair, err)
    for row in graph["resolution_coverage"]:
        assert tail.SHARED_QUALNAME not in row.get("tail", {}), row
    assert not [e for e in graph["extraction_errors"] if e["stage"] == "rust-qualnames"]
    # ADR-165: CI's `hobbes lanes` row, every disagreement shaped.
    rows = graph["lane_agreement"]["site_disagreements"]
    assert [r["shape"] for r in rows if r["name"] == "width"] == ["cfg-twin"], rows
    assert all(r["shape"] for r in rows), rows
    # ADR-165's second amendment: rust-analyzer, `alloc` off, defines only
    # the `not(alloc)` arm, so the node is there.
    lines = {s["id"]: s["line"] for s in graph["symbols"]}
    assert lines["src/cow.width"] == WIDTH_NO_ALLOC, err
