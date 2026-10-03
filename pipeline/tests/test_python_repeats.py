"""A Python name one scope defines more than once is one node at its first
def, whichever def runs, and one record names it (ADR-172, C-186).

The case is structlog's `dev._init_terminal`: two defs under `if
_IS_WINDOWS: … else:` on a variable, so both read live, and the node is the
Windows def while Linux runs the other. Beside it an `@overload` group, a
redefinition, and a property's accessors, which are one property and are
not named.
"""

from hobbes.extract import _python_repeats, _python_repeats_record, extract_repo
from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source

SOURCE = '''import sys
from typing import overload

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:

    def _init_terminal(who):
        return who

else:

    def _init_terminal(who):
        """Nothing to do off Windows."""


@overload
def get(key: int) -> int: ...
@overload
def get(key: str) -> str: ...
def get(key):
    return key


def helper():
    return 1


def helper():
    return 2


class Box:
    @property
    def size(self):
        return 1

    @size.setter
    def size(self, value):
        pass
'''


def _line(needle: str, nth: int = 0) -> int:
    return [i + 1 for i, line in enumerate(SOURCE.splitlines()) if needle in line][nth]


def _tree(tmp_path):
    (tmp_path / "dev.py").write_text(SOURCE)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    return modules, parsed, build_graph(modules, parsed)


def test_lane_a_names_every_repeat_but_the_accessors(tmp_path):
    modules, parsed, graph = _tree(tmp_path)
    assert _python_repeats(graph, modules, parsed, None) == {
        "dev._init_terminal": ("repeated", [_line("def _init_terminal"), _line("def _init_terminal", 1)]),
        "dev.get": ("overload", [_line("def get"), _line("def get", 1), _line("def get", 2)]),
        "dev.helper": ("repeated", [_line("def helper"), _line("def helper", 1)]),
    }


def test_with_lane_b_only_the_later_live_defs_are_named(tmp_path):
    """ADR-155's reading: a name with no later live def (ADR-154 found the
    other dead, or moved the node to the live one) is settled."""
    modules, parsed, graph = _tree(tmp_path)
    later = {"dev._init_terminal": [(_line("def _init_terminal", 1), _line("def _init_terminal", 1) + 1)]}
    assert _python_repeats(graph, modules, parsed, later) == {
        "dev._init_terminal": ("repeated", [_line("def _init_terminal"), _line("def _init_terminal", 1)]),
    }


def test_the_record(tmp_path):
    (tmp_path / "dev.py").write_text(SOURCE)
    graph = extract_repo(tmp_path).graph
    [record] = [e for e in graph["extraction_errors"] if e["stage"] == "python-repeats"]
    assert record["path"] == "."
    message = record["message"]
    assert message.startswith("3 Python name(s) are defined two or more times in one scope: 2 written again")
    assert "1 `@overload` stub group(s)" in message
    assert "(ADR-172, C-186)" in message
    assert f"dev._init_terminal (repeated, defs at line {_line('def _init_terminal')}, " in message
    assert "dev.size" not in message and "Box.size" not in message


def test_no_repeat_no_record(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    graph = extract_repo(tmp_path).graph
    assert not [e for e in graph.get("extraction_errors", []) if e["stage"] == "python-repeats"]


def test_the_record_lists_repeats_before_overloads():
    record = _python_repeats_record({"m.a": ("overload", [1, 3]), "m.z": ("repeated", [5, 9])})
    assert record["message"].index("m.z") < record["message"].index("m.a")
