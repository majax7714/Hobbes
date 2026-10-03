"""A Rust id two differently written impl blocks share draws nothing at its
later defs (ADR-163, C-180).

``rustsource._impl_type`` names an impl block after its first type
identifier, so ``impl Pointer for *const T`` and ``impl Pointer for *mut
T`` both hang ``distance`` off ``T``, and a trait impl and the inherent
impl of one type share every method name they both declare. The node is
the first def. Before ADR-163 a call written in a later def was filed
under it — memchr's ``ext.rs:33`` drew ``T.distance calls T.distance``,
a recursion that does not exist, at ``semantic`` — and a call resolved
onto a later def's line fell ``below-floor``.

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


class TestTheCollisionSet:
    """Lane A's own read: which ids two impl headers share."""

    def _shared(self):
        files = [
            rustsource._parse_file(f"src/{name}", (SRC / name).read_bytes())
            for name in ("ext.rs", "client.rs", "cow.rs", "lib.rs")
        ]
        return rustsource.shared_qualnames(files)

    def test_each_differently_headed_pair_is_listed_with_every_def(self):
        shared = self._shared()
        assert set(shared) == {
            f"{EXT}.T.distance",
            f"{EXT}.T.as_usize",
            f"{CLIENT}.Id.from",
            f"{CLIENT}.Client.describe",
        }
        assert [line for line, _ in shared[f"{EXT}.T.distance"]] == [DISTANCE_CONST, DISTANCE_MUT]
        assert [line for line, _ in shared[f"{CLIENT}.Id.from"]] == [FROM_STR, FROM_STRING]

    def test_two_kinds_under_one_name_are_listed_and_a_bare_repeat_is_not(self):
        # C-182's residual, memchr's `haystacks` shape: `struct B` and
        # `const B` are two items; two ungated `fn render` share a header
        # and a kind, and are named, not refused.
        parsed = [rustsource._parse_file("haystacks/std.rs", (FIXTURE / "haystacks" / "std.rs").read_bytes())]
        assert set(rustsource.shared_qualnames(parsed)) == {"haystacks/std.B"}
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

    def test_cfg_twins_share_a_header_and_are_not_listed(self):
        shared = self._shared()
        assert "src/cow.Imp" not in shared
        assert "src/cow.width" not in shared

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
        headers = [header for _, _, header in parsed.defs["T.distance"]]
        assert headers == ["impl<T> Pointer for *const T", "impl<T> Pointer for *mut T"]
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
    """The suite default (lane B off): the fallback's facts at a later def
    are refused, and each such site moves from `fallback-resolved` to
    `shared-qualname`, so the per-file sum still holds."""

    def test_nothing_written_in_a_later_def_is_drawn(self, graph):
        drawn = lines_in(graph, "src/client.rs")
        assert NORMALISE_IN_FROM_STRING not in drawn
        assert LABEL_CALL not in drawn
        edge = calls(graph)[(f"{CLIENT}.Id.from", f"{CLIENT}.normalise")]
        assert [row["line"] for row in edge["evidence"]] == [FROM_STR + 1]

    def test_the_refused_sites_are_relabelled_and_the_sum_holds(self, graph):
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/client.rs"]
        assert row["tail"][tail.SHARED_QUALNAME] == 3  # `Id(` and `normalise(` at one line, `label(`
        assert sum(row["tail"].values()) == row["unresolved"] + row.get("floored", 0)
        for row in graph["resolution_coverage"]:
            expected = row["unresolved"] + row.get("floored", 0)
            assert sum(row.get("tail", {}).values()) == expected, row

    def test_cfg_twins_still_draw(self, graph):
        edge = calls(graph)[("src/cow.width", "src/cow.count")]
        assert [row["line"] for row in edge["evidence"]] == [COUNT_CALL]

    def test_one_record_names_the_ids_and_the_register_entry(self, graph):
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-qualnames"]
        # The four impl-header ids and haystacks' two-kinds `B` (C-182's
        # residual); the fourth call is `helper()` inside `const B`.
        assert record["message"].startswith("5 Rust symbol id(s)")
        assert "C-180" in record["message"] and "ADR-163" in record["message"]
        assert "4 call(s)" in record["message"]

    def test_one_record_names_the_cfg_twins_and_the_register_entry(self, graph):
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-cfg-twins"]
        assert record["message"].startswith("2 Rust symbol id(s) are cfg twins")
        assert "C-182" in record["message"] and "ADR-165" in record["message"]
        assert f"src/cow.width (defs at line {WIDTH_ALLOC}, {WIDTH_NO_ALLOC})" in record["message"]

    def test_a_two_kinds_repeat_is_refused_at_its_later_def(self, graph):
        # `const B = helper();` at line 14, beside `struct B` at line 4.
        assert not [e for e in graph["symbol_edges"] if e["from"] == "haystacks/std.B"]
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "haystacks/std.rs"]
        assert row["tail"][tail.SHARED_QUALNAME] == 1

    def test_an_ungated_same_header_repeat_is_named_and_filed_as_before(self, graph):
        # `fn render` twice, no `cfg`: one node, both bodies' calls under it.
        edge = calls(graph)[("haystacks/std.render", "haystacks/std.helper")]
        assert [row["line"] for row in edge["evidence"]] == [HAYSTACK_RENDER_CALLS[0], HAYSTACK_RENDER_CALLS[1]]
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-repeats"]
        assert record["message"].startswith("1 Rust symbol id(s) in 1 file(s)")
        assert "C-182" in record["message"] and "haystacks/std.rs" in record["message"]
        assert f"haystacks/std.render (defs at line {HAYSTACK_RENDER[0]}, {HAYSTACK_RENDER[1]})" in record["message"]

    def test_the_class_is_available_to_rust(self, graph):
        assert tail.SHARED_QUALNAME in graph["tail_classes_available"]["rust"]

    def test_the_nodes_are_unchanged(self, graph):
        ids = {s["id"]: s["line"] for s in graph["symbols"]}
        assert ids[f"{EXT}.T.distance"] == DISTANCE_CONST
        assert ids[f"{CLIENT}.Client.describe"] == INHERENT_DESCRIBE
        assert ids[f"{CLIENT}.Id.from"] == FROM_STR


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

    def test_the_self_loop_is_not_drawn_and_is_counted(self, monkeypatch):
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/ext.rs", CALL_IN_MUT, "distance", "src/ext.rs", DISTANCE_CONST)],
        )
        assert (f"{EXT}.T.distance", f"{EXT}.T.distance") not in calls(graph)
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/ext.rs"]
        assert row["tail"][tail.SHARED_QUALNAME] == 1
        withheld = row["tail"][tail.SHARED_QUALNAME]
        assert sum(row["tail"].values()) == row["unresolved"] + row.get("floored", 0) + withheld

    def test_a_resolution_onto_a_later_def_is_counted_not_floored(self, monkeypatch):
        span = _line_of("lib.rs", "unsafe { end.distance(start) }")
        graph = self._graph(
            monkeypatch,
            [self._resolution("src/lib.rs", span, "distance", "src/ext.rs", DISTANCE_MUT)],
        )
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/lib.rs"]
        assert row["tail"].get(tail.SHARED_QUALNAME) == 1
        assert tail.BELOW_FLOOR not in row["tail"]

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
def test_with_the_index_no_later_def_is_the_nodes():
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
    assert NORMALISE_IN_FROM_STRING not in lines_in(graph, "src/client.rs"), err
    # What the first defs are owed is still drawn, at the index's tier.
    for pair in (
        ("src/lib.offset", f"{EXT}.T.distance"),
        ("src/lib.make", f"{CLIENT}.Client.describe"),
        ("src/lib.make", f"{CLIENT}.Id.from"),
        ("src/cow.width", "src/cow.count"),
    ):
        assert drawn[pair]["tier"] == SEMANTIC, (pair, err)
    [lib] = [r for r in graph["resolution_coverage"] if r["file"] == "src/lib.rs"]
    assert lib["tail"][tail.SHARED_QUALNAME] == 2, lib  # `span`'s and the trait call
    [record] = [e for e in graph["extraction_errors"] if e["stage"] == "rust-qualnames"]
    assert "C-180" in record["message"]
    # ADR-165: CI's `hobbes lanes` row, every disagreement shaped.
    rows = graph["lane_agreement"]["site_disagreements"]
    assert [r["shape"] for r in rows if r["name"] == "width"] == ["cfg-twin"], rows
    assert all(r["shape"] for r in rows), rows
