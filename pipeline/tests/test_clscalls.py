"""`cls(…)` in a classmethod calls the class it is written in (ADR-170).

The index names the parameter `cls` at the call, below the symbol floor
(C-9), so the join draws nothing. The `minicls` fixture is rich's
`rich/control.py` shape (`Control.bell` returns `cls(ControlType.BELL)`),
with a rebound `cls`, a closure and a staticmethod as near misses.
"""

from pathlib import Path

import pytest

from hobbes.extract import clscalls, extract_repo
from hobbes.extract.schema import SYNTACTIC

FIXTURE = Path(__file__).parent / "fixtures" / "minicls"
SRC = (FIXTURE / "minicls" / "control.py").read_text().splitlines()


def _line(text: str, nth: int = 0) -> int:
    return [i + 1 for i, line in enumerate(SRC) if text in line][nth]


@pytest.fixture(scope="module")
def graph():
    return extract_repo(FIXTURE).graph


def _calls(graph):
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


def test_a_classmethod_constructing_cls_calls_its_class(graph):
    calls = _calls(graph)
    for method, text in (("bell", "return cls(ControlType.BELL)"), ("home", "return cls(ControlType.HOME)")):
        edge = calls[(f"minicls.control.Control.{method}", "minicls.control.Control")]
        assert edge["tier"] == SYNTACTIC
        assert [(r["line"], r.get("via")) for r in edge["evidence"]] == [(_line(text), clscalls.CLS)]


def test_the_near_misses_draw_nothing(graph):
    calls = _calls(graph)
    for source in ("rebound", "deferred", "deferred.make", "plain"):
        assert not [k for k in calls if k[0] == f"minicls.control.Control.{source}" and k[1].endswith(("Control", "Other"))], source


def test_the_counts(graph):
    assert graph["cls_calls"] == {
        "classmethods": 3, "sites": 2, "drawn": 2,
        "abstained": {"no-class-symbol": 0, "already-drawn": 0},
    }


def test_a_repo_with_no_classmethod_has_no_key():
    assert "cls_calls" not in extract_repo(Path(__file__).parent / "fixtures" / "minialias").graph
