"""A Python moniker one file defines at several lines is no answer (ADR-150).

scip-python names a def nested in a *method* by the class and its own
name, dropping every function scope between them. Two sibling methods
that each nest an ``index`` holding a ``generate`` therefore share one
moniker per name, and the decode's old rule — keep the smallest line —
answered a call in the second method with the first method's def. That
is where flask's three wrong ``semantic`` edges came from
(``oracle-grading.md`` §10.35). Python now abstains as C++ does: no
definition for the shared moniker, no edge, and the count surfaced by
the ``scip-decode`` degradation record, worded for Python (C-170).

The ``mininest`` fixture writes the shape and its two controls — a
method defined once, and a def nested in a *module-level* function,
whose path scip-python keeps. The end-to-end case needs lane B; the twin
below states what lane A alone has, which is every def under its own id
and the call sites.

ADR-150's route c is now written (ADR-153): a bare call to the one
``def`` its own function's body binds is lane A's, at the ``syntactic``
tier. So the two *right* edges the abstention took with it come back —
each ``index`` to the ``generate`` written inside it — while the two
cross pairs, ADR-150's wrong edge among them, stay absent: no rule of
either lane names a def in another method's scope.
"""

from pathlib import Path

import pytest

from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import SEMANTIC, SYNTACTIC

MININEST = Path(__file__).parent / "fixtures" / "mininest"

STREAMS = "mininest.streams"
FIRST_GENERATE = f"{STREAMS}.Streams.first.index.generate"
SECOND_GENERATE = f"{STREAMS}.Streams.second.index.generate"
FIRST_INDEX = f"{STREAMS}.Streams.first.index"
SECOND_INDEX = f"{STREAMS}.Streams.second.index"


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_a_moniker_two_methods_share_draws_no_edge_and_says_so():
    """With the index running: the index still answers for neither
    ``generate``, and the edge its abstention removes is the wrong one —
    ``second``'s ``index`` calling ``first``'s ``generate``. What comes
    back is lane A's (ADR-153): each ``index`` calls the one ``def`` its
    own body writes, so the two straight pairs are drawn ``syntactic``
    and the two cross pairs stay absent. What the index does answer — a
    method defined once, and a def whose path it keeps — is
    unchanged."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MININEST).graph
    drawn = calls(graph)
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]

    for caller, callee in ((FIRST_INDEX, FIRST_GENERATE), (SECOND_INDEX, SECOND_GENERATE)):
        edge = drawn.get((caller, callee))
        assert edge is not None, (caller, callee, err)
        assert edge["tier"] == SYNTACTIC, (caller, callee, err)
    for caller, callee in ((FIRST_INDEX, SECOND_GENERATE), (SECOND_INDEX, FIRST_GENERATE)):
        assert (caller, callee) not in drawn, (caller, callee, err)
    # The method's own bare call to its ``index`` is this rule's site
    # too, so the edge is there whatever the index says about a name it
    # gives both ``index``es; only its tier turns on that, and this box
    # cannot ask.
    for pair in (
        (f"{STREAMS}.Streams.first", FIRST_INDEX),
        (f"{STREAMS}.Streams.second", SECOND_INDEX),
    ):
        assert drawn.get(pair) is not None, (pair, err)
    for pair in (
        (f"{STREAMS}.Plain.go", f"{STREAMS}.Plain.run"),
        (f"{STREAMS}.outer", f"{STREAMS}.outer.inner"),
    ):
        edge = drawn.get(pair)
        assert edge is not None, (pair, err)
        assert edge["tier"] == SEMANTIC, (pair, err)

    said = [e for e in err if "more than one line of one file" in e["message"]]
    assert len(said) == 1, err
    assert said[0]["stage"] == "scip-decode"
    assert "scip-python names a def nested in a method" in said[0]["message"]
    assert said[0]["message"].endswith("(ADR-150, C-170)")

    # Drawing less costs no node: every def the fixture writes is a graph
    # symbol under its own id, the six inside `Streams` with them.
    ids = {s["id"] for s in graph["symbols"]}
    assert {
        f"{STREAMS}.Streams.first",
        FIRST_INDEX,
        FIRST_GENERATE,
        f"{STREAMS}.Streams.second",
        SECOND_INDEX,
        SECOND_GENERATE,
        f"{STREAMS}.outer.inner",
    } <= ids


def test_lane_a_carries_every_nested_def_and_its_call_sites():
    """Without the index the defs are still distinct and the sites are
    still recorded — which is why the abstention loses no node, and what
    route c is written on: every one of these sites is a bare call to
    the one def its own function's body binds, and lane A now names the
    binding (ADR-153, the fact below)."""
    parsed = parse_source((MININEST / "src" / "mininest" / "streams.py").read_bytes())
    assert [(s.qualname, s.kind) for s in parsed.symbols] == [
        ("Streams", "class"),
        ("Streams.first", "method"),
        ("Streams.first.index", "function"),
        ("Streams.first.index.generate", "function"),
        ("Streams.second", "method"),
        ("Streams.second.index", "function"),
        ("Streams.second.index.generate", "function"),
        ("Plain", "class"),
        ("Plain.run", "method"),
        ("Plain.go", "method"),
        ("outer", "function"),
        ("outer.inner", "function"),
    ]
    assert [(c.scope, c.callee, c.line) for c in parsed.calls] == [
        ("Streams.first.index", "generate", 27),
        ("Streams.first", "index", 29),
        ("Streams.second.index", "generate", 36),
        ("Streams.second", "index", 38),
        ("Plain.go", "self.run", 48),
        ("outer", "inner", 57),
    ]
    # ADR-153 step 1 over the same file: each scope's own body binds one
    # name by one ``def``, and each call above is written in the scope
    # that binds the name it calls. ``Plain`` writes no nested def, and
    # ``self.run`` is not a bare name either way.
    assert {q: [names for _, _, names in ds] for q, ds in parsed.local_defs.items()} == {
        "Streams.first": [("index",)],
        "Streams.first.index": [("generate",)],
        "Streams.second": [("index",)],
        "Streams.second.index": [("generate",)],
        "outer": [("inner",)],
    }
