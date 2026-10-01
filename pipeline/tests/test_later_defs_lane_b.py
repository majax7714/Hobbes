"""A later def of a Python qualname is its node's too, on a fixture (ADR-155).

The ``minisame`` fixture writes click's shapes small: ``core.py``'s
``Command.main`` is two ``@t.overload`` stubs and an implementation whose
body names ``Abort`` and ``Usage``; ``Command.name`` is a property whose
setter annotates ``Payload`` and raises ``Usage``; and ``encode`` is
defined once per arm of an ``if FAST:`` that is not static.

Two readings: lane A alone, where nothing is computed and the graph is
what it was (P6), and the whole ingest with lane B, which this sandbox
cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes import extract as extract_pkg
from hobbes.extract import extract_repo

MINISAME = Path(__file__).parent / "fixtures" / "minisame"
SRC = MINISAME / "src" / "minisame"

CORE = "minisame.core"
ERRORS = "minisame.errors"
CORE_PATH = "src/minisame/core.py"


def _line_of(file: str, text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *file* that starts (stripped)
    with *text*, so no case pins a literal line number."""
    hits = [
        i + 1
        for i, line in enumerate((SRC / file).read_text().splitlines())
        if line.strip().startswith(text)
    ]
    return hits[nth]


MAIN_STUB_1 = _line_of("core.py", "def main")
MAIN_STUB_2 = _line_of("core.py", "def main", 1)
MAIN_IMPL = _line_of("core.py", "def main", 2)
EXCEPT_ABORT = _line_of("core.py", "except Abort:")
NAME_GETTER = _line_of("core.py", "def name")
NAME_SETTER = _line_of("core.py", "def name", 1)
ENCODE_IF = _line_of("core.py", "def encode")
ENCODE_ELSE = _line_of("core.py", "def encode", 1)

#: Each later def's line, with the node its own name token belongs to.
LATER_DEF_LINES = {
    MAIN_STUB_2: f"{CORE}.Command.main",
    MAIN_IMPL: f"{CORE}.Command.main",
    NAME_SETTER: f"{CORE}.Command.name",
    ENCODE_ELSE: f"{CORE}.encode",
}


def uses(graph):
    """Every ``uses`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "uses"}


def test_the_fixtures_lines_are_what_the_constants_say():
    assert MAIN_STUB_1 < MAIN_STUB_2 < MAIN_IMPL < EXCEPT_ABORT < NAME_GETTER < NAME_SETTER
    assert NAME_SETTER < ENCODE_IF < ENCODE_ELSE


def test_lane_a_alone_computes_no_spans_and_is_what_it_was(monkeypatch):
    """No lane B for Python, no spans: `_later_defs` is never called and
    the projection is given none (P6)."""
    baseline = extract_repo(MINISAME).graph
    seen = []

    def later_defs(*args, **kwargs):
        seen.append(args)
        return {}

    monkeypatch.setattr(extract_pkg, "_later_defs", later_defs)
    assert extract_repo(MINISAME).graph["symbol_edges"] == baseline["symbol_edges"]
    assert seen == []


@pytest.mark.lane_b
def test_with_the_index_a_later_def_is_its_nodes():
    """The whole ingest, lane B running (the developer's host): scip-python
    references each later def's name token to the first def, and that is
    no use; a use written inside a later def is filed under its qualname."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINISAME).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]

    for edge in graph["symbol_edges"]:
        if edge["type"] != "uses":
            continue
        for row in edge["evidence"]:
            if row["path"] == CORE_PATH and row["line"] in LATER_DEF_LINES:
                assert edge["from"] == LATER_DEF_LINES[row["line"]], (edge, err)

    drawn = uses(graph)
    abort = drawn.get((f"{CORE}.Command.main", f"{ERRORS}.Abort"))
    assert abort is not None, err
    assert EXCEPT_ABORT in [row["line"] for row in abort["evidence"]]
    assert (f"{CORE}.Command", f"{ERRORS}.Abort") not in drawn

    payload = drawn.get((f"{CORE}.encode", f"{ERRORS}.Payload"))
    assert payload is not None, err
    assert {ENCODE_IF, ENCODE_ELSE} <= {row["line"] for row in payload["evidence"]}
    assert (CORE, f"{CORE}.encode") not in drawn

    setter = drawn.get((f"{CORE}.Command.name", f"{ERRORS}.Payload"))
    assert setter is not None, err
    assert NAME_SETTER in [row["line"] for row in setter["evidence"]]
