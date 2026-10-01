"""Tests for ``hobbes.extract._later_defs`` — a qualname's later live defs (ADR-155).

Each case parses a small source with :func:`parse_source`, as the ingest
does, builds lane A's records the way the graph does, and reads the spans
the projection is given, under Linux at Python 3.12. A twin case runs
ADR-154's step first, as the ingest does, so its record has moved.
"""

from types import SimpleNamespace

from hobbes.extract import _later_defs, _read_static_tests
from hobbes.extract.graph import _symbol_records
from hobbes.extract.pysource import parse_source

AT_312 = {"platform": "linux", "version": [3, 12]}


def later_defs(source: str) -> dict[str, list[tuple[int, int]]]:
    """The spans `_later_defs` gives one module ``m`` holding *source*."""
    module = SimpleNamespace(id="m", path="m.py")
    parsed = {"m": parse_source(source.encode())}
    graph = {"symbols": _symbol_records([module], parsed)}
    _read_static_tests(graph, [module], parsed, {}, AT_312)
    return _later_defs(graph, [module], parsed, AT_312)


def line_of(source: str, text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *source* that starts with *text*."""
    return [i for i, line in enumerate(source.splitlines(), 1) if line.startswith(text)][nth]


OVERLOADS = """\
import typing

@typing.overload
def f(x: int) -> int: ...
@typing.overload
def f(x: str) -> str: ...
def f(x):
    return x
"""


def test_overload_stubs_and_the_implementation_are_later_defs():
    second = line_of(OVERLOADS, "def f", 1)
    impl = line_of(OVERLOADS, "def f", 2)
    assert later_defs(OVERLOADS) == {"m.f": [(second, second), (impl, impl + 1)]}


PROPERTY = """\
class C:
    @property
    def x(self):
        return 1

    @x.setter
    def x(self, value):
        self._x = value
"""


def test_a_setter_is_a_later_def_of_its_property():
    setter = line_of(PROPERTY, "    def x", 1)
    assert later_defs(PROPERTY) == {"m.C.x": [(setter, setter + 1)]}


NOT_STATIC = """\
FLAG = True
if FLAG:
    def f():
        return 1
else:
    def f():
        return 2
"""


def test_a_branch_that_is_not_static_gives_its_else_def():
    other = line_of(NOT_STATIC, "    def f", 1)
    assert later_defs(NOT_STATIC) == {"m.f": [(other, other + 1)]}


TWIN = """\
import sys

if sys.platform == "win32":
    def f():
        return 1
else:
    def f():
        return 2
"""


def test_a_twins_dead_def_is_left_out_and_its_live_def_is_the_record():
    assert later_defs(TWIN) == {}


def test_a_qualname_defined_once_gives_nothing():
    assert later_defs("def f():\n    return 1\n\nclass C:\n    def g(self):\n        pass\n") == {}


# click 8.x `src/click/types.py`, `convert_type` (lines 1331–1358 at 36baa15),
# verbatim, under three definitions of the excerpt's own so it parses alone.
CLICK = '''\
import typing as t


class ParamType:
    pass


def _guess_type(ty, default):
    return ty


@t.overload
def convert_type(ty: None, default: None = None) -> StringParamType: ...
@t.overload
def convert_type(
    ty: type | ParamType[t.Any], default: t.Any | None = None
) -> ParamType[t.Any]: ...
@t.overload
def convert_type(
    ty: t.Any | None, default: t.Any | None = None
) -> ParamType[t.Any]: ...
def convert_type(
    ty: t.Any | None = None, default: t.Any | None = None
) -> ParamType[t.Any]:
    """Find the most appropriate :class:`ParamType` for the given Python
    type. If the type isn't provided, it can be inferred from a default
    value.
    """
    guessed = _guess_type(ty, default)
    is_guessed = guessed is not ty

    if isinstance(guessed, tuple):
        return Tuple(guessed)

    if isinstance(guessed, ParamType):
        return guessed

    if guessed is str or guessed is None:
        return STRING
'''

CLICK_SECOND_STUB = line_of(CLICK, "def convert_type", 1)
CLICK_SECOND_STUB_END = line_of(CLICK, ") -> ParamType[t.Any]: ...", 0)
CLICK_THIRD_STUB = line_of(CLICK, "def convert_type", 2)
CLICK_THIRD_STUB_END = line_of(CLICK, ") -> ParamType[t.Any]: ...", 1)
CLICK_IMPL = line_of(CLICK, "def convert_type", 3)
CLICK_IMPL_END = line_of(CLICK, "        return STRING")


def test_clicks_convert_type_gives_its_later_stubs_and_its_implementation():
    assert later_defs(CLICK) == {
        "m.convert_type": [
            (CLICK_SECOND_STUB, CLICK_SECOND_STUB_END),
            (CLICK_THIRD_STUB, CLICK_THIRD_STUB_END),
            (CLICK_IMPL, CLICK_IMPL_END),
        ]
    }
    # The record keeps the first stub's line, which is none of the spans.
    first = line_of(CLICK, "def convert_type")
    assert first not in {line for line, _ in later_defs(CLICK)["m.convert_type"]}
