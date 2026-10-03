"""A Go file's `func init()` defs are one node, and what is written inside a
later one is filed under it (ADR-166, C-183).

Go runs every package-level ``init`` a file declares, in order, and no code
can name one. Lane A mints one id per file, ``<module>.init``, at the first
def. Before ADR-166 a lane B ``uses`` fact written inside a later ``init``
carried no lane A scope and was filed under the module: dagger 89 rows in
22 files, ``internal/cmd/dagger/main.go`` among them, whose second ``init``
groups the commands (``agentCmd.GroupID = "daily"``).

The ``minigoinit`` fixture keeps that shape: ``main.go`` is dagger's first
``init`` verbatim, then a second that assigns to a command and calls one;
``cmds.go`` declares the commands and a *method* named ``init``, which has
its own qualname and is not one of the file's init functions.
"""

from pathlib import Path

import pytest

import hobbes.extract as extract
from hobbes.extract import extract_repo, gosource, scipsource
from hobbes.extract.evidence import Resolved
from hobbes.extract.schema import SEMANTIC

FIXTURE = Path(__file__).parent / "fixtures" / "minigoinit"


def _line_of(file: str, text: str, nth: int = 0) -> int:
    hits = [
        i + 1
        for i, line in enumerate((FIXTURE / file).read_text().splitlines())
        if text in line
    ]
    return hits[nth]


FIRST_INIT = _line_of("main.go", "func init() {")
SECOND_INIT = _line_of("main.go", "func init() {", 1)
GROUP_ASSIGN = _line_of("main.go", 'agentCmd.GroupID = "daily"')
REGISTER_CALL = _line_of("main.go", "register(callCoreCmd.Command())")


@pytest.fixture(scope="module")
def layer():
    return gosource.extract_go(FIXTURE)


@pytest.fixture(scope="module")
def graph():
    return extract_repo(FIXTURE).graph


class TestTheSpans:
    def test_a_file_with_two_inits_lists_every_def(self, layer):
        assert layer["init_spans"] == {
            "main.init": [(FIRST_INIT, FIRST_INIT + 6), (SECOND_INIT, SECOND_INIT + 3)]
        }

    def test_one_init_and_a_method_named_init_are_not_listed(self, layer):
        # cmds.go writes `func (c *Cmd) init()`: a method, `Cmd.init`.
        assert "cmds.init" not in layer["init_spans"]
        assert "cmds.Cmd.init" in {s["id"] for s in layer["symbols"]}


class TestTheProjection:
    """`project` with the later init as an ADR-155 later def: a use inside
    it is filed under the node, and nothing starts at its line."""

    NODES = [{"id": "main", "kind": "module", "path": "main.go"},
             {"id": "cmds", "kind": "module", "path": "cmds.go"}]
    SYMBOLS = [
        {"id": "main.init", "module": "main", "kind": "function", "line": 3, "end_line": 9},
        {"id": "cmds.agentCmd", "module": "cmds", "kind": "var", "line": 12, "end_line": 12},
    ]

    def _use(self, line):
        return Resolved(
            kind="uses", source_file="main.go", line=line, scope="", def_file="cmds.go",
            def_line=12, tier=SEMANTIC, lanes=(scipsource.SCIP_LANE,),
        )

    def test_a_use_inside_a_later_init_is_the_nodes(self):
        out = scipsource.project(
            [self._use(14)], self.NODES, self.SYMBOLS, later_defs={"main.init": [(13, 16)]}
        )
        assert [(e["from"], e["to"]) for e in out["symbol_edges"]] == [("main.init", "cmds.agentCmd")]

    def test_without_the_spans_it_is_the_modules(self):
        out = scipsource.project([self._use(14)], self.NODES, self.SYMBOLS)
        assert [(e["from"], e["to"]) for e in out["symbol_edges"]] == [("main", "cmds.agentCmd")]


class TestLaneAAlone:
    def test_the_node_is_the_first_def(self, graph):
        [node] = [s for s in graph["symbols"] if s["id"] == "main.init"]
        assert node["line"] == FIRST_INIT

    def test_a_call_in_the_later_init_is_the_nodes(self, graph):
        froms = {
            e["from"]
            for e in graph["symbol_edges"]
            for row in e["evidence"]
            if row["path"] == "main.go" and row["line"] == REGISTER_CALL
        }
        assert froms == {"main.init"}

    def test_one_record_names_the_files_and_the_register_entry(self, graph):
        [record] = [e for e in graph["extraction_errors"] if e["stage"] == "go-inits"]
        assert "C-183" in record["message"]
        assert f"main.init (later def at line {SECOND_INIT})" in record["message"]


class TestByHand:
    """dagger's 89 rows, with lane B's answer hand-built: a ``uses`` of a
    package var written inside the later ``init``."""

    def test_the_use_is_filed_under_init(self, monkeypatch):
        from hobbes.extract import evidence as ev

        facts = {
            "language": "go",
            "definitions": [],
            "references": [
                ev.Site(
                    provider=ev.SCIP, kind=ev.RESOLUTION, file="main.go", line=GROUP_ASSIGN,
                    col=2, name="agentCmd", def_file="cmds.go",
                    def_line=_line_of("cmds.go", "agentCmd    = &Cmd{}"),
                ),
            ],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        graph = extract_repo(FIXTURE).graph
        froms = {
            e["from"]
            for e in graph["symbol_edges"]
            if e["to"] == "cmds.agentCmd"
            for row in e["evidence"]
            if row["line"] == GROUP_ASSIGN
        }
        assert froms == {"main.init"}


@pytest.mark.lane_b
def test_with_the_index_a_use_in_the_later_init_is_the_nodes():
    """The whole ingest with scip-go (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(FIXTURE).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    at = {
        (e["from"], e["type"])
        for e in graph["symbol_edges"]
        if e["to"] == "cmds.agentCmd"
        for row in e["evidence"]
        if row["path"] == "main.go" and row["line"] == GROUP_ASSIGN
    }
    assert at == {("main.init", "uses")}, (at, err)
