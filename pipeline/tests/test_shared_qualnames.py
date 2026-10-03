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

    def test_cfg_twins_share_a_header_and_are_not_listed(self):
        shared = self._shared()
        assert "src/cow.Imp" not in shared
        assert "src/cow.width" not in shared

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
        assert record["message"].startswith("4 Rust symbol id(s)")
        assert "C-180" in record["message"] and "ADR-163" in record["message"]
        assert "3 call(s)" in record["message"]

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
