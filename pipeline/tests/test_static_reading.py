"""Lane B reads Python as Linux at one version, and the ingest says where (ADR-154).

The ``miniplat`` fixture writes click's shapes small: ``term.py`` defines
``raw_terminal`` and ``getchar`` once per arm of an ``if sys.platform ==
"win32":`` (a twin each), and a module-level function with a ``darwin``
branch; ``front.py`` calls ``term``'s names through function-local
imports, one of them under the module's own def of the same name (step
6); ``wincon.py`` asserts ``win32`` at the top, so the rest is dead.

Three readings: lane A alone (the graph is what it was, but step 6 holds);
lane A with a Python reading handed in, which is what the ingest applies
where lane B ran (steps 3–5, the records); and the whole ingest with lane B,
which this sandbox cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes import extract as extract_pkg
from hobbes.extract import extract_repo
from hobbes.extract.schema import SEMANTIC

MINIPLAT = Path(__file__).parent / "fixtures" / "miniplat"
SRC = MINIPLAT / "src" / "miniplat"


def _line_of(file: str, text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *file* that starts (stripped)
    with *text*, so no case pins a literal line number."""
    hits = [
        i + 1
        for i, line in enumerate((SRC / file).read_text().splitlines())
        if line.strip().startswith(text)
    ]
    return hits[nth]


TERM = "miniplat.term"
FRONT = "miniplat.front"
WINCON = "miniplat.wincon"

#: The win32 arm's defs and the `else` arm's, in term.py.
WIN_RAW = _line_of("term.py", "def raw_terminal")
LIVE_RAW = _line_of("term.py", "def raw_terminal", 1)
WIN_GETCHAR = _line_of("term.py", "def getchar")
LIVE_GETCHAR = _line_of("term.py", "def getchar", 1)
#: The win32 arm runs from its first statement (the decorator) to the
#: win32 `getchar`'s last line, the one before the blank above `else:`.
WIN_ARM = (_line_of("term.py", "@contextlib.contextmanager"), _line_of("term.py", "else:") - 2)
DARWIN_BODY = _line_of("term.py", 'return _translate("mac")')
#: wincon.py: everything after the assert.
WINCON_DEAD = (
    _line_of("wincon.py", "def _write"),
    len((SRC / "wincon.py").read_text().splitlines()),
)


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


def adr154_records(graph):
    return {
        e["path"]: e["message"]
        for e in graph.get("extraction_errors", [])
        if e["message"].endswith("(ADR-154, C-173)")
    }


def symbol(graph, symbol_id):
    return next(s for s in graph["symbols"] if s["id"] == symbol_id)


def test_the_fixtures_lines_are_what_the_constants_say():
    assert WIN_RAW < WIN_GETCHAR < WIN_ARM[1] < LIVE_RAW < LIVE_GETCHAR < DARWIN_BODY


def test_lane_a_alone_is_what_it_was_but_a_local_import_shadows():
    """No lane B, no reading: nothing is evaluated, no record is written
    and each twin keeps its first record (P6). Step 6 is lane A's own rule,
    so it holds here too: `front.get_pager_file()` is not bound to the
    module's own def its import shadows."""
    graph = extract_repo(MINIPLAT).graph
    assert adr154_records(graph) == {}
    assert symbol(graph, f"{TERM}.raw_terminal")["line"] == WIN_RAW
    assert symbol(graph, f"{TERM}.getchar")["line"] == WIN_GETCHAR
    drawn = calls(graph)
    assert (f"{FRONT}.get_pager_file", f"{FRONT}.get_pager_file") not in drawn
    # The twin's first record is what lane A names without the reading.
    assert (f"{TERM}.getchar", f"{TERM}.raw_terminal") in drawn


class TestTheReadingAppliedToLaneA:
    """The ingest's step between lane B and the join, driven with a lane B
    that resolves nothing and reports Linux at 3.12 — so every edge here is
    lane A's, and what moves is ADR-154's doing alone."""

    @pytest.fixture
    def graph(self, monkeypatch):
        def facts(*args, **kwargs):
            yield {"python_reading": {"platform": "linux", "version": [3, 12]}}

        monkeypatch.setattr(extract_pkg, "_lane_b_facts", facts)
        return extract_repo(MINIPLAT).graph

    def test_each_twin_is_recorded_at_its_live_def(self, graph):
        raw = symbol(graph, f"{TERM}.raw_terminal")
        assert raw["line"] == LIVE_RAW and raw["id"] == f"{TERM}.raw_terminal"
        assert symbol(graph, f"{TERM}.getchar")["line"] == LIVE_GETCHAR

    def test_lane_a_names_no_twin_and_files_nothing_from_a_dead_def(self, graph):
        drawn = calls(graph)
        # A twin's name is lane B's to answer; lane A proposes nothing.
        assert (f"{TERM}.getchar", f"{TERM}.raw_terminal") not in drawn
        assert (f"{FRONT}.raw_terminal", f"{TERM}.raw_terminal") not in drawn
        # The live getchar's own call is drawn; the win32 one's is not.
        edge = drawn[(f"{TERM}.getchar", f"{TERM}._translate")]
        assert [row["line"] for row in edge["evidence"]] == [LIVE_GETCHAR + 2]
        for edge in graph["symbol_edges"]:
            for row in edge["evidence"]:
                assert not (
                    row["path"].endswith("term.py") and WIN_GETCHAR <= row["line"] <= WIN_ARM[1]
                ), edge

    def test_one_record_per_file_with_a_dead_region(self, graph):
        records = adr154_records(graph)
        assert sorted(records) == ["src/miniplat/term.py", "src/miniplat/wincon.py"]
        term = records["src/miniplat/term.py"]
        assert term.startswith(f"lines {WIN_ARM[0]}–{WIN_ARM[1]}, {DARWIN_BODY} read as never run")
        assert "Linux / Python 3.12 (sys.platform)" in term
        assert (
            f"twins recorded at their live def: getchar (line {LIVE_GETCHAR}), "
            f"raw_terminal (line {LIVE_RAW})"
        ) in term
        # The darwin branch's `_translate` call is lane A's, syntactic.
        assert "(1 symbol edge with evidence in them)" in term
        assert "1 call site in a dead twin def withheld" in term
        wincon = records["src/miniplat/wincon.py"]
        assert wincon.startswith(f"lines {WINCON_DEAD[0]}–{WINCON_DEAD[1]} read as never run")
        assert "no twin" in wincon and "(1 symbol edge with evidence in them)" in wincon
        assert all(
            e["stage"] == "scip-python"
            for e in graph["extraction_errors"]
            if e["message"].endswith("(ADR-154, C-173)")
        )


@pytest.mark.lane_b
def test_with_the_index_the_twins_land_and_lane_a_stops_guessing():
    """The whole ingest, lane B running (the developer's host): the twins'
    nodes sit at the live defs, so the index's references to them land
    `semantic`; the function-local import is the index's answer; the lanes
    no longer disagree; and the two files with dead code say so."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIPLAT).graph
    drawn = calls(graph)
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]

    assert symbol(graph, f"{TERM}.raw_terminal")["line"] == LIVE_RAW, err
    assert symbol(graph, f"{TERM}.getchar")["line"] == LIVE_GETCHAR, err
    edge = drawn.get((f"{TERM}.getchar", f"{TERM}.raw_terminal"))
    assert edge is not None and edge["tier"] == SEMANTIC, (edge, err)
    assert (f"{FRONT}.raw_terminal", f"{TERM}.raw_terminal") in drawn, err
    assert (f"{FRONT}.get_pager_file", f"{TERM}.get_pager_file") in drawn, err
    assert (f"{FRONT}.get_pager_file", f"{FRONT}.get_pager_file") not in drawn, err
    assert graph["lane_agreement"]["site_disagreements"] == [], graph["lane_agreement"]

    records = adr154_records(graph)
    assert sorted(records) == ["src/miniplat/term.py", "src/miniplat/wincon.py"], err
    assert "getchar" in records["src/miniplat/term.py"]
    assert "raw_terminal" in records["src/miniplat/term.py"]

    for edge in graph["symbol_edges"]:
        for row in edge["evidence"]:
            assert not (
                row["path"].endswith("term.py") and WIN_GETCHAR <= row["line"] <= WIN_ARM[1]
            ), edge
