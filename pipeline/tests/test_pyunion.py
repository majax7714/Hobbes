"""A Python method call on a union-typed receiver is not drawn (ADR-168, C-184).

scip-python answers ``x.m()`` on a union receiver with the union's first
member that declares ``m``; on the held-out icalendar cell that drew 6
wrong ``semantic`` edges (``component['TZOFFSETFROM'].to_ical()`` →
``vAdr.to_ical``). Lane A reads the union from the annotations it can see
and marks the site ``union-member``; the join draws nothing there.

The ``minipyunion`` fixture writes icalendar 7.3.0's shapes small: a
``TypeAlias`` union, a ``__getitem__`` returning it, a parameter annotated
with it, a local bound from a method returning it, and a class attribute
annotated with a two-strategy union; ``vUTCOffset`` inherits ``to_ical``.
"""

from pathlib import Path

import pytest

import hobbes.extract as extract
from hobbes.extract import evidence as ev
from hobbes.extract import extract_repo, pyunion, tail
from hobbes.extract.discover import discover_modules
from hobbes.extract.pysource import UNREAD_TYPE, parse_source

FIXTURE = Path(__file__).parent / "fixtures" / "minipyunion"
COMPONENT = FIXTURE / "miniunion" / "component.py"
PATH = "miniunion/component.py"


def _line(text: str) -> int:
    return next(i + 1 for i, line in enumerate(COMPONENT.read_text().splitlines()) if text in line)


def _col(line: int, name: str) -> int:
    return COMPONENT.read_text().splitlines()[line - 1].index("." + name) + 1


SUBSCRIPT = _line('component["TZOFFSETFROM"].to_ical()')
PARAM = _line("return utc_prop.to_ical()")
LOCAL = _line("return factory.to_ical()")
ATTRIBUTE = _line("calendar._subcomponents.is_lazy()")
ONE_HOLDER = _line("utc_prop.only_text()")
PLAIN = _line("return value.to_ical()")


@pytest.fixture(scope="module")
def sites():
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    return pyunion.union_member_sites(modules, parsed)


class TestTheTypeFacts:
    def test_an_alias_an_optional_and_a_forward_reference(self):
        facts = parse_source(
            b"from typing import Optional, TypeAlias, Union\n"
            b"V: TypeAlias = A | B\n"
            b"W = Union[A, 'B']\n"
            b"type T = A | None\n"
            b"def f(x: Optional[A]) -> 'A | B': ...\n"
        ).type_facts
        assert dict(facts.aliases) == {
            "V": ("|", ("A", "B")),
            "W": ("|", ("A", "B")),
            "T": ("|", ("A", "None")),
        }
        assert dict(facts.returns) == {"f": ("|", ("A", "B"))}

    def test_an_unreadable_annotation_is_said_so(self):
        facts = parse_source(b"def f(x) -> list[A]: ...\n").type_facts
        assert dict(facts.returns) == {"f": UNREAD_TYPE}


class TestTheSites:
    def test_each_read_of_the_union_marks_its_call(self, sites):
        for line, name in (
            (SUBSCRIPT, "to_ical"),
            (PARAM, "to_ical"),
            (LOCAL, "to_ical"),
            (ATTRIBUTE, "is_lazy"),
        ):
            assert (PATH, line, _col(line, name)) in sites, (line, name)

    def test_one_holder_and_a_plain_annotation_are_not_marked(self, sites):
        lines = {line for path, line, _ in sites if path == PATH}
        assert ONE_HOLDER not in lines
        assert PLAIN not in lines

    def test_an_inherited_def_is_its_base_holder(self):
        # vUTCOffset runs vText's to_ical: one def, so a union of the two
        # has one holder and is not a union member.
        repo = pyunion._Repo([parse_source(
            b"class vText:\n    def to_ical(self): ...\n"
            b"class vUTCOffset(vText): ...\n"
            b"def f(x: vText | vUTCOffset):\n    return x.to_ical()\n"
        ).type_facts])
        assert {repo.holder(c, "to_ical") for c in ("vText", "vUTCOffset")} == {"vText"}

    def test_a_class_defined_twice_reads_as_nothing(self):
        repo = pyunion._Repo([
            parse_source(b"class A:\n    def m(self): ...\nclass B:\n    def m(self): ...\n").type_facts,
            parse_source(b"class A:\n    def m(self): ...\n").type_facts,
        ])
        assert repo.union([("|", ("A", "B"))]) is None

    def test_reads_that_disagree_read_as_nothing(self):
        repo = pyunion._Repo([parse_source(
            b"class A:\n    def m(self): ...\nclass B:\n    def m(self): ...\nclass C: ...\n"
            b"def get() -> A | B: ...\n"
            b"class K:\n    def get(self) -> C: ...\n"
        ).type_facts])
        assert repo.receiver_union("local", "get") is None


@pytest.fixture(scope="module")
def graph():
    return extract_repo(FIXTURE).graph


class TestLaneAAlone:
    """Lane A alone draws no method call through an attribute receiver, so
    nothing moves in its graph; the tail names the sites."""

    def test_the_sites_are_tailed_union_member(self, graph):
        [row] = [r for r in graph["resolution_coverage"] if r["file"] == PATH]
        assert row["tail"][tail.UNION_MEMBER] == 4

    def test_the_class_is_available_to_python(self, graph):
        assert tail.UNION_MEMBER in graph["tail_classes_available"]["python"]


class TestIcalendarsWrongEdgeByHand:
    """The held-out cell's row, with lane B's answer hand-built: scip-python
    names `vAdr.to_ical` at `component["TZOFFSETFROM"].to_ical()`."""

    def _graph(self, monkeypatch, line, name, def_line):
        facts = {
            "language": "python",
            "definitions": [],
            "references": [
                ev.Site(
                    provider=ev.SCIP, kind=ev.RESOLUTION, file=PATH, line=line,
                    col=_col(line, name), name=name, def_file="miniunion/prop.py", def_line=def_line,
                ),
            ],
            "external_refs": [],
            "degraded": [],
        }
        monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
        return extract_repo(FIXTURE).graph

    def test_the_first_members_method_is_not_drawn(self, monkeypatch):
        graph = self._graph(monkeypatch, SUBSCRIPT, "to_ical", 6)
        drawn = [
            e for e in graph["symbol_edges"]
            if e["to"] == "miniunion.prop.vAdr.to_ical"
            and any(r["line"] == SUBSCRIPT for r in e["evidence"])
        ]
        assert drawn == []

    def test_a_plain_receiver_still_draws(self, monkeypatch):
        graph = self._graph(monkeypatch, PLAIN, "to_ical", 11)
        drawn = [
            e for e in graph["symbol_edges"]
            if e["to"] == "miniunion.prop.vText.to_ical"
            and any(r["line"] == PLAIN for r in e["evidence"])
        ]
        assert [e["tier"] for e in drawn] == ["semantic"]


@pytest.mark.lane_b
def test_with_the_index_no_union_member_is_drawn():
    """The whole ingest with scip-python (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(FIXTURE).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    at = {
        (r["line"], e["to"])
        for e in graph["symbol_edges"]
        if e["type"] == "calls"
        for r in e["evidence"]
        if r["path"] == PATH
    }
    for line in (SUBSCRIPT, PARAM, LOCAL, ATTRIBUTE):
        assert not [to for ln, to in at if ln == line and to.rsplit(".", 1)[-1] in ("to_ical", "is_lazy")], (line, at, err)
    assert (PLAIN, "miniunion.prop.vText.to_ical") in at, (at, err)
