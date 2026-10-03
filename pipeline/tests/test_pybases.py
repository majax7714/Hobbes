"""A Python class base the index states no relationship for is named
(ADR-169, C-185).

scip-python 0.6.6 writes no SymbolInformation for some classes (flask's
``Flask``, icalendar's ``Component``), so no class-level ``implements`` edge
is drawn while the header's base name is resolved as an ordinary reference.
The record names each such pair; nothing is drawn.
"""

from pathlib import Path

import hobbes.extract as extract
from hobbes.extract import evidence as ev
from hobbes.extract import extract_repo, pybases
from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import parse_source

SOURCE = (
    "class Scaffold:\n"  # 1
    "    pass\n"  # 2
    "\n"  # 3
    "class App(Scaffold):\n"  # 4
    "    pass\n"  # 5
    "\n"  # 6
    "class Flask(App, metaclass=Meta):\n"  # 7
    "    pass\n"  # 8
    "\n"  # 9
    "class Lines(list[App]):\n"  # 10
    "    pass\n"  # 11
)


def test_the_heads_are_the_bases_not_their_arguments_or_keywords():
    heads = parse_source(SOURCE.encode()).type_facts.heads
    assert heads == ((4, 4, ("Scaffold",)), (7, 7, ("App",)), (10, 10, ("list",)))


def _layer(edges):
    modules = [ModuleInfo(id="app", import_name="app", path="app.py", root=".", kind="module")]
    parsed = {"app": parse_source(SOURCE.encode())}
    symbols = [
        {"id": f"app.{n}", "module": "app", "name": n, "kind": "class", "line": line}
        for n, line in (("Scaffold", 1), ("App", 4), ("Flask", 7), ("Lines", 10))
    ]
    return pybases.unstated_bases(modules, parsed, symbols, edges)


def _uses(src, dst, line):
    return {"from": src, "to": dst, "type": "uses", "evidence": [{"path": "app.py", "line": line, "lane": "scip"}]}


def test_a_resolved_base_with_no_implements_edge_is_named():
    edges = [
        _uses("app.App", "app.Scaffold", 4),
        {"from": "app.App", "to": "app.Scaffold", "type": "implements", "evidence": []},
        _uses("app.Flask", "app.App", 7),
    ]
    assert _layer(edges) == [("app.Flask", "app.App")]


def test_a_type_argument_is_not_a_base():
    assert _layer([_uses("app.Lines", "app.App", 10)]) == []


def test_a_lane_a_row_is_not_the_index():
    edge = _uses("app.Flask", "app.App", 7)
    edge["evidence"][0]["lane"] = "tree-sitter"
    assert _layer([edge]) == []


FIXTURE = Path(__file__).parent / "fixtures" / "minipyunion"


def test_the_record_names_the_pair(monkeypatch):
    # minipyunion's `class Calendar(Component)`: lane B resolves the base,
    # and (as scip-python does for flask's `Flask`) states no relationship.
    path = "miniunion/component.py"
    lines = (FIXTURE / path).read_text().splitlines()
    line = next(i + 1 for i, t in enumerate(lines) if t.startswith("class Calendar(Component)"))
    component = next(i + 1 for i, t in enumerate(lines) if t.startswith("class Component(dict)"))
    facts = {
        "language": "python",
        "definitions": [],
        "references": [
            ev.Site(provider=ev.SCIP, kind=ev.RESOLUTION, file=path, line=line,
                    col=lines[line - 1].index("Component"), name="Component",
                    def_file=path, def_line=component),
        ],
        "external_refs": [],
        "degraded": [],
        "python_reading": {"version": [3, 12]},
    }
    monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
    graph = extract_repo(FIXTURE).graph
    records = [e for e in graph.get("extraction_errors", []) if e["stage"] == "python-bases"]
    assert len(records) == 1, [e["stage"] for e in graph["extraction_errors"]]
    assert "C-185" in records[0]["message"]
    assert "miniunion.component.Calendar -> miniunion.component.Component" in records[0]["message"]
