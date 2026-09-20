"""A TS/JS construction is a call where the index names the constructor
at the ``new`` token (ADR-142, C-168 narrowed).

The ``minicnew`` fixture holds the three shapes the rule tells apart, in
the spellings the ADR measured: a class that declares its own
constructor (drawn, **to the class** — the constructor's own line starts
no symbol), a class that declares none (**not drawn** — there the index
names the written class while the base's constructor is what runs), and
an ES5 constructor function that is its module's whole export (drawn, to
the function).

The edge belongs to neither lane alone — lane A writes the token, lane B
names what was constructed — so it must be there with the index and gone
without it: one case each, as ADR-141's rule is tested.
"""
from pathlib import Path

import pytest

from hobbes.extract.schema import LANE_SCIP, SEMANTIC

MINICNEW = Path(__file__).parent / "fixtures" / "minicnew"

#: A class with its own constructor: the edge ends at the *class*.
CIRCLE = ("esm/main.round", "esm/shapes.Circle")
#: An ES5 constructor function: the edge ends at the function itself.
COUNTER = ("index.build", "lib/counter.Counter")
#: A class that declares none: nothing new is drawn, ever.
SQUARE = "esm/shapes.Square"


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


def test_lane_a_records_one_token_per_new_and_no_call_site():
    """What lane A states on this fixture, with no index anywhere near it:
    three tokens, positioned on the callee's terminal identifier, and not
    one call site among them."""
    from hobbes.extract.tssource import extract_ts

    layer = extract_ts(MINICNEW)
    assert layer["constructions"] == {
        "esm/main.mjs": frozenset({(4, 13), (8, 13)}),
        "index.js": frozenset({(4, 13)}),
    }
    assert [(s.file, s.line, s.name) for s in layer["call_sites"]] == [
        ("index.js", 1, "require")
    ]
    # The ends the rule draws to, and the line lane B's definition row
    # has to agree with: a class starts where it is written, and the
    # constructor inside it starts no symbol at all (C-58).
    lines = {s["id"]: s["line"] for s in layer["symbols"]}
    assert lines[CIRCLE[1]] == 3 and lines[CIRCLE[0]] == 3
    assert lines[COUNTER[1]] == 3 and lines[COUNTER[0]] == 3
    assert lines[SQUARE] == 13


#: scip-typescript's own spelling, over the fixture: a class and the
#: constructor it declares one descriptor below it, a class that declares
#: none, and an ES5 constructor function.
PREFIX = "scip-typescript npm minicnew 0.0.0 "
DEFINITIONS = [
    {"file": "esm/shapes.mjs", "line": 3, "end_line": 11, "kind": "type",
     "moniker": PREFIX + "`esm/shapes.mjs`/Circle#"},
    {"file": "esm/shapes.mjs", "line": 4, "end_line": 6, "kind": "method",
     "moniker": PREFIX + "`esm/shapes.mjs`/Circle#`<constructor>`()."},
    {"file": "esm/shapes.mjs", "line": 13, "end_line": 17, "kind": "type",
     "moniker": PREFIX + "`esm/shapes.mjs`/Square#"},
    {"file": "lib/counter.js", "line": 3, "end_line": 5, "kind": "method",
     "moniker": PREFIX + "`lib/counter.js`/Counter()."},
]

#: What the index puts at each of lane A's three tokens: the constructor,
#: the class that declares none, and the constructor function.
AT_THE_TOKENS = (
    ("esm/main.mjs", 4, 13, "esm/shapes.mjs", 4),
    ("esm/main.mjs", 8, 13, "esm/shapes.mjs", 13),
    ("index.js", 4, 13, "lib/counter.js", 3),
)


def test_the_rule_reads_the_index_s_own_rows(monkeypatch):
    """The whole wiring over the fixture, with scip-typescript's rows
    written out rather than indexed — what the ingest does between lane
    A's tokens and the graph's edges, on a box with no container."""
    from hobbes.extract import evidence as ev, extract_repo
    import hobbes.extract as extract

    references = [
        ev.Site(
            provider=ev.SCIP, kind=ev.RESOLUTION, file=file, line=line, col=col,
            name="<constructor>", def_file=def_file, def_line=def_line,
        )
        for file, line, col, def_file, def_line in AT_THE_TOKENS
    ]
    monkeypatch.setattr(
        extract,
        "_lane_b_facts",
        lambda *a, **k: iter([{
            "definitions": DEFINITIONS,
            "references": references,
            "external_refs": [],
            "degraded": [],
        }]),
    )
    graph = extract_repo(MINICNEW).graph
    edges = {(e["from"], e["type"], e["to"]) for e in graph["symbol_edges"]}
    assert (CIRCLE[0], "calls", CIRCLE[1]) in edges
    assert (COUNTER[0], "calls", COUNTER[1]) in edges
    # The class that declares none: the `uses` reference it has always
    # been, from the symbol that encloses the site — the fact the rule
    # refuses is not withheld, it is left exactly alone.
    assert ("esm/main.boxed", "calls", SQUARE) not in edges
    assert ("esm/main.boxed", "uses", SQUARE) in edges
    assert graph["constructions"] == {"ts_drawn": 2, "ts_named_class": 1}


@pytest.mark.lane_b
def test_the_construction_is_drawn_where_the_index_names_a_constructor():
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINICNEW).graph
    drawn = calls(graph)
    why = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    for pair, line in ((CIRCLE, 4), (COUNTER, 4)):
        edge = drawn.get(pair)
        assert edge is not None, (pair, why)
        # Semantic and both lanes: lane A proved a construction was
        # written here, lane B what it constructs.
        assert edge["tier"] == SEMANTIC, why
        assert [(s["line"], s["lane"]) for s in edge["evidence"]] == [(line, LANE_SCIP)]
    # The class that declares no constructor stays exactly as it was: the
    # index names it, the key names the base whose constructor runs, and
    # 55 of 58 such rows read contradicted when the shape was measured.
    assert [pair for pair in drawn if pair[1] == SQUARE] == []
    assert graph["constructions"]["ts_drawn"] == 2


def test_lane_a_draws_nothing_without_the_index():
    """P6: lane A records the token and no call site, so with lane B off
    there is nothing to meet it and the graph is what it was."""
    from hobbes.extract import extract_repo

    graph = extract_repo(MINICNEW).graph
    drawn = calls(graph)
    assert [pair for pair in drawn if pair in (CIRCLE, COUNTER) or pair[1] == SQUARE] == []
    # and no count to report either, so the block says nothing
    assert "ts_drawn" not in graph.get("constructions", {})
