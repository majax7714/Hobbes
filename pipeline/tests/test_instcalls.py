"""A call of a constructed instance, drawn to its class's `__call__`
(ADR-171, C-174).

The rule, :func:`hobbes.extract.instcalls.instance_calls`, is handed the
``miniinst`` fixture's symbols and ``semantic`` edges written out, because
those edges are exactly what it is allowed to believe; each abstention, and
each edge it must not read, has a case of its own. Lane A's records are
pinned here too. The whole ingest with lane B is
``test_instcalls_lane_b.py``.
"""

from pathlib import Path

import pytest

from hobbes.extract import _add_with_call_edges
from hobbes.extract.discover import discover_modules
from hobbes.extract.fixtures import NO_METHOD
from hobbes.extract.graph import build_graph
from hobbes.extract.instcalls import (
    ALREADY_DRAWN,
    AMBIGUOUS_CALL,
    CALL,
    DEFINES_NEW,
    NO_CALL_EDGE,
    NOT_A_CLASS,
    REASONS,
    instance_calls,
)
from hobbes.extract.pysource import InstanceCall, parse_source
from hobbes.extract.schema import LANE_SCIP, LANE_TREE_SITTER, SEMANTIC, SYNTACTIC, tiered_edge

FIXTURE = Path(__file__).parent / "fixtures" / "miniinst"
CORE_PATH = "miniinst/core.py"
HL_PATH = "miniinst/highlighter.py"
CORE_TEXT = (FIXTURE / CORE_PATH).read_text()
HL_TEXT = (FIXTURE / HL_PATH).read_text()

CORE = "miniinst.core"
HL = "miniinst.highlighter"
CALL_ID = f"{HL}.Highlighter.__call__"
REPR = f"{HL}.ReprHighlighter"


def line_of(text: str, needle: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *text* holding *needle*."""
    return [i + 1 for i, line in enumerate(text.splitlines()) if needle in line][nth]


BANNER = line_of(CORE_TEXT, "BANNER = ")
RENDER_BIND = line_of(CORE_TEXT, "highlighter = ReprHighlighter()")
RENDER_CALL = line_of(CORE_TEXT, "return highlighter(line)")
DIRECT = line_of(CORE_TEXT, "return ReprHighlighter()(line)")
INTERNED_BIND = line_of(CORE_TEXT, "one = Interned()")
INTERNED_CALL = line_of(CORE_TEXT, "return one(line)")
FACTORY_BIND = line_of(CORE_TEXT, "made = make_highlighter()")
FACTORY_CALL = line_of(CORE_TEXT, "return made(line)")
PLAIN = line_of(CORE_TEXT, "return Plain()(line)")


def semantic(source: str, target: str, line: int, edge_type: str = "calls", path: str = CORE_PATH) -> dict:
    return tiered_edge(source, target, edge_type, [{"path": path, "line": line}], tier=SEMANTIC, lane=LANE_SCIP)


#: The two single named bases under `Highlighter`, as the index names them
#: on each class's header line.
BASES = (
    semantic(REPR, f"{HL}.RegexHighlighter", line_of(HL_TEXT, "class ReprHighlighter("), "uses", HL_PATH),
    semantic(f"{HL}.RegexHighlighter", f"{HL}.Highlighter", line_of(HL_TEXT, "class RegexHighlighter("), "uses", HL_PATH),
)

#: The index's answer at every construction and call the fixture writes.
CONSTRUCTIONS = (
    semantic(CORE, REPR, BANNER),
    semantic(f"{CORE}.render", REPR, RENDER_BIND),
    semantic(f"{CORE}.direct", REPR, DIRECT),
    semantic(f"{CORE}.interned", f"{HL}.Interned", INTERNED_BIND),
    semantic(f"{CORE}.factory", f"{HL}.make_highlighter", FACTORY_BIND),
    semantic(f"{CORE}.plain", f"{HL}.Plain", PLAIN),
)


def run(edges: tuple = BASES + CONSTRUCTIONS):
    modules = [m for m in discover_modules(FIXTURE) if m.path.endswith(".py")]
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    return instance_calls(modules, parsed, graph["symbols"], list(edges))


def pairs(rows):
    return [(r["from"], r["to"], r["line"]) for r in rows]


class TestLaneARecords:
    def test_the_direct_form_at_function_and_module_level(self):
        parsed = parse_source(CORE_TEXT.encode())
        assert parsed.instance_calls == [
            InstanceCall(None, BANNER, "ReprHighlighter", BANNER),
            InstanceCall("direct", DIRECT, "ReprHighlighter", DIRECT),
            InstanceCall("plain", PLAIN, "Plain", PLAIN),
        ]

    def test_the_bound_form_once_bound_and_called(self):
        parsed = parse_source(CORE_TEXT.encode())
        recorded = {q: [n for _s, _e, names in defs for n in names] for q, defs in parsed.local_instances.items()}
        assert recorded == {
            "render": [("highlighter", RENDER_BIND, "ReprHighlighter")],
            "interned": [("one", INTERNED_BIND, "Interned")],
            "factory": [("made", FACTORY_BIND, "make_highlighter")],
        }

    @pytest.mark.parametrize(
        "body",
        [
            "    h = C()\n    h = C()\n    return h(1)\n",  # bound twice
            "    for h in xs:\n        pass\n    h = C()\n    return h(1)\n",  # a loop target too
            "    global h\n    h = C()\n    return h(1)\n",
            "    h = h.make()\n    return h(1)\n",  # reads h before binding it
            "    h = g = C()\n    return h(1)\n",  # chained
            "    h: C = C()\n    return h(1)\n",  # annotated: another binder
            "    h = C()[0]\n    return h(1)\n",  # not a call on a name
            "    h = C()\n    return h.m(1)\n",  # not a bare call
        ],
    )
    def test_the_bound_form_refusals(self, body):
        parsed = parse_source(f"def f(xs):\n{body}".encode())
        assert parsed.local_instances == {}

    def test_a_parameter_is_not_an_instance(self):
        parsed = parse_source(b"def f(h):\n    h = C()\n    return h(1)\n")
        assert parsed.local_instances == {}

    def test_a_module_level_binding_is_not_read(self):
        parsed = parse_source(b"h = C()\nh(1)\n")
        assert parsed.local_instances == {}

    def test_the_callee_line_is_the_inner_callees(self):
        parsed = parse_source(b"def f():\n    h = (\n        mod.C()\n    )\n    return h(1)\n")
        assert parsed.local_instances == {"f": ((1, 5, (("h", 3, "C"),)),)}


class TestTheRule:
    def test_each_form_is_drawn_to_the_inherited_call(self):
        rows, counts = run()
        assert pairs(rows) == [
            (CORE, CALL_ID, BANNER),
            (f"{CORE}.direct", CALL_ID, DIRECT),
            (f"{CORE}.render", CALL_ID, RENDER_CALL),
        ]
        assert counts == {
            "sites": 6,
            "drawn": 3,
            "abstained": {
                reason: {DEFINES_NEW: 1, NOT_A_CLASS: 1, NO_METHOD: 1}.get(reason, 0) for reason in REASONS
            },
        }

    def test_without_an_edge_at_the_construction_nothing_is_drawn(self):
        rows, counts = run(BASES)
        assert rows == []
        assert counts["abstained"][NO_CALL_EDGE] == 6

    def test_a_syntactic_edge_is_not_read(self):
        edge = tiered_edge(
            f"{CORE}.direct", REPR, "calls", [{"path": CORE_PATH, "line": DIRECT}], tier=SYNTACTIC, lane=LANE_TREE_SITTER
        )
        rows, _ = run(BASES + (edge,))
        assert rows == []

    def test_an_edge_at_another_line_is_not_read(self):
        rows, _ = run(BASES + (semantic(f"{CORE}.render", REPR, RENDER_CALL),))
        assert rows == []

    def test_a_uses_edge_is_not_a_construction(self):
        rows, _ = run(BASES + (semantic(f"{CORE}.direct", REPR, DIRECT, "uses"),))
        assert rows == []

    def test_two_targets_named_alike_are_ambiguous(self):
        other = semantic(f"{CORE}.direct", "miniinst.other.ReprHighlighter", DIRECT)
        rows, counts = run(BASES + (semantic(f"{CORE}.direct", REPR, DIRECT), other))
        assert rows == []
        assert counts["abstained"][AMBIGUOUS_CALL] == 1

    def test_an_unnamed_base_stops_the_walk(self):
        rows, counts = run(CONSTRUCTIONS)
        assert [r for r in rows if r["to"] == CALL_ID] == []
        assert counts["abstained"]["base-unnamed"] == 3

    def test_a_pair_already_drawn_is_left_alone(self):
        drawn = semantic(f"{CORE}.direct", CALL_ID, DIRECT)
        rows, counts = run(BASES + CONSTRUCTIONS + (drawn,))
        assert (f"{CORE}.direct", CALL_ID, DIRECT) not in pairs(rows)
        assert counts["abstained"][ALREADY_DRAWN] == 1

    def test_no_site_anywhere_is_an_empty_block(self, tmp_path):
        (tmp_path / "m.py").write_text("def f():\n    return g(1)\n")
        modules = discover_modules(tmp_path)
        parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
        graph = build_graph(modules, parsed)
        assert instance_calls(modules, parsed, graph["symbols"], []) == ([], {})

    def test_the_rows_are_deterministic_and_sorted(self):
        rows, _ = run()
        again, _ = run(tuple(reversed(BASES + CONSTRUCTIONS)))
        assert rows == again
        assert pairs(rows) == sorted(pairs(rows))


def test_the_edges_are_syntactic_with_their_own_via():
    graph = {"symbols": [{"id": CALL_ID}], "nodes": [{"id": CORE}], "symbol_edges": []}
    _add_with_call_edges(
        graph,
        [
            {"from": CORE, "to": CALL_ID, "path": CORE_PATH, "line": BANNER},
            {"from": CORE, "to": "miniinst.gone", "path": CORE_PATH, "line": BANNER},
        ],
        via=CALL,
    )
    (edge,) = graph["symbol_edges"]
    assert (edge["from"], edge["to"], edge["type"], edge["tier"]) == (CORE, CALL_ID, "calls", SYNTACTIC)
    assert edge["evidence"] == [{"path": CORE_PATH, "line": BANNER, "via": "__call__", "lane": LANE_TREE_SITTER}]
