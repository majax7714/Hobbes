"""A call rooted at a standard-library import, on a fixture (ADR-164,
C-181).

``ministdlib/use.py`` calls stdlib names in every form scip-python 0.6.6
leaves unplaced — a name from a dotted module (``urlsplit``), a member of
a submodule bound by ``from urllib import parse``, of a module alias
(``eu.formatdate``), of an ``import a.b`` path
(``importlib.metadata.version``), ``sys.exit`` and gettext's ``_`` — and
``helpers.py`` defines in-repo namesakes of four of them. Measured in the
image, the index names the first five with a document-local symbol and
writes no occurrence for ``_``.

Two readings: lane A alone, where every such site is ``stdlib-import`` and
lane A draws none of them to a namesake, and the whole ingest with lane
B, which this sandbox cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.schema import SEMANTIC, SYNTACTIC

MINISTDLIB = Path(__file__).parent / "fixtures" / "ministdlib"
USE_PATH = "src/ministdlib/use.py"
USE_LINES = (MINISTDLIB / USE_PATH).read_text().splitlines()

RUN = "ministdlib.use.run"
HELPERS = "ministdlib.helpers"


def _line_of(text: str) -> int:
    """The 1-based line of ``use.py`` holding *text*."""
    hits = [i + 1 for i, line in enumerate(USE_LINES) if text in line]
    assert len(hits) == 1, (text, hits)
    return hits[0]


QUOTE = _line_of("    quote(url)")
HELPER_CALL = _line_of("helpers.urlsplit(url)")


def use_row(graph) -> dict:
    rows = [r for r in graph["resolution_coverage"] if r["file"] == USE_PATH]
    assert len(rows) == 1
    return rows[0]


def calls_into_helpers(graph) -> list[tuple[str, str, int]]:
    """Every ``calls`` row from ``use.py`` into ``helpers.py``: (target,
    tier, line)."""
    return sorted(
        (e["to"], e["tier"], row["line"])
        for e in graph["symbol_edges"]
        if e["type"] == "calls" and e["to"].startswith(HELPERS)
        for row in e["evidence"]
        if row.get("path") == USE_PATH
    )


def test_lane_a_alone_counts_them_and_draws_none_to_a_namesake():
    graph = extract_repo(MINISTDLIB).graph
    row = use_row(graph)
    # urlsplit, parse.urlsplit, eu.formatdate, importlib.metadata.version,
    # sys.exit, _, reduce, json.dumps: lane A resolves nothing outside the
    # repo. sys.stdout.write's receiver is a value, and `shadowed`'s
    # parse.urlsplit reads a parameter: both stay attr-call.
    assert row["tail"] == {"stdlib-import": 8, "attr-call": 2, "fallback-resolved": 2}
    # Lane A abstains at every stdlib site: the only rows into helpers.py
    # are the explicit `helpers.urlsplit` and the `except ImportError`
    # rebinding of `quote` (C-181's residual).
    assert calls_into_helpers(graph) == [
        (f"{HELPERS}.urlsplit", SYNTACTIC, QUOTE),
        (f"{HELPERS}.urlsplit", SYNTACTIC, HELPER_CALL),
    ]


@pytest.mark.lane_b
def test_with_the_index_the_unplaced_stdlib_calls_are_stdlib_import():
    """The whole ingest, lane B running (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINISTDLIB).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    row = use_row(graph)
    # reduce, json.dumps and sys.stdout.write resolve outside the repo;
    # helpers.urlsplit resolves in it.
    assert (row["external"], row["resolved"]) == (3, 1), (row, err)
    # The six scip-python leaves unplaced; `shadowed`'s parameter is still
    # attr-call; `quote` keeps lane A's fallback.
    assert row["tail"] == {"stdlib-import": 6, "attr-call": 1, "fallback-resolved": 1}, (row, err)
    # No row into a namesake from a stdlib site. The `quote` row is the
    # residual C-181 registers: lane B's document-local answer cannot veto
    # lane A's in-repo rebinding the way an external answer would
    # (ADR-111).
    assert calls_into_helpers(graph) == [
        (f"{HELPERS}.urlsplit", SEMANTIC, HELPER_CALL),
        (f"{HELPERS}.urlsplit", SYNTACTIC, QUOTE),
    ]
