"""What Pyright reads as never run, from lane A's facts (ADR-154).

Once scip-python's Pyright 0.6.6 loads a config it evaluates a short list
of static tests — ``sys.platform``, ``os.name``, ``sys.version_info``,
``TYPE_CHECKING``, ``True`` / ``False``, and ``not`` / ``and`` / ``or``
over them — against one platform and one interpreter version, marks the
branch it reads as never taken unreachable, and emits **no occurrence**
there. The ingest pins the platform (``Linux``) and reads the version off
the index's own stdlib monikers (:func:`hobbes.extract.scipsource.python_reading`);
this module evaluates the tests :mod:`hobbes.extract.pysource` collected
under that reading and says which lines are dead and which qualnames are
*twins* — defined once outside the dead lines and again inside them.

No grammar here (I-4): the tests arrive as
:class:`~hobbes.extract.pysource.StaticTest` facts, their conditions
already encoded, and this module reads only those. It runs only where
lane B ran for Python; without it nothing is evaluated (P6).
"""

from __future__ import annotations

import operator
from dataclasses import dataclass

from hobbes.extract.pysource import ParsedFile, StaticTest, Symbol

#: ``os.name`` on each platform Pyright names; Hobbes pins ``linux``.
_OS_NAME = {"linux": "posix"}

_COMPARE = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}

#: The forms a record names, in the order it names them.
FORMS = ("sys.platform", "os.name", "sys.version_info", "TYPE_CHECKING", "constant")

_FORM_OF = {
    "sys.platform": "sys.platform",
    "os.name": "os.name",
    "sys.version_info": "sys.version_info",
    "sys.version_info[0]": "sys.version_info",
    "TYPE_CHECKING": "TYPE_CHECKING",
    "const": "constant",
}


@dataclass(frozen=True)
class Reading:
    """The platform and version Pyright indexed under: ``version`` is
    ``(major, minor)``, or None when no stdlib moniker named it — every
    version test is then not static."""

    platform: str = "linux"
    version: tuple[int, int] | None = None


@dataclass(frozen=True)
class FileReading:
    """One file's dead lines under a :class:`Reading`.

    ``regions`` are the merged ``(first line, last line)`` spans, ascending;
    ``forms`` the kinds of test that killed them, in :data:`FORMS` order;
    ``twins`` maps each twin's qualname to ``(live def, dead defs)``.
    """

    regions: tuple[tuple[int, int], ...]
    forms: tuple[str, ...]
    twins: dict[str, tuple[Symbol, tuple[Symbol, ...]]]

    def dead(self, line: int) -> bool:
        """Whether *line* lies in a dead region."""
        return any(first <= line <= last for first, last in self.regions)


def _bound_above(aliases: tuple[tuple[str, int], ...], name: str | None, line: int) -> bool:
    """Whether an import written above *line* binds *name*."""
    return any(bound == name and at < line for bound, at in aliases)


def evaluate(
    condition: tuple, line: int, facts: ParsedFile, reading: Reading, forms: set | None = None
) -> bool | None:
    """What *condition*, written at *line*, reads as under *reading*:
    True, False, or None when it is not static. *forms*, when given,
    collects the kind of each form that read as a value."""
    head = condition[0]
    value: bool | None = None
    if head == "const":
        value = condition[1]
    elif head == "TYPE_CHECKING":
        receiver = condition[1]
        if receiver is None or _bound_above(facts.typing_aliases, receiver, line):
            value = True
    elif head == "os.name":
        _, op, text = condition
        value = _COMPARE[op](_OS_NAME[reading.platform], text)
    elif head == "sys.platform":
        _, receiver, op, text = condition
        if _bound_above(facts.sys_aliases, receiver, line):
            value = _COMPARE[op](reading.platform, text)
    elif head == "sys.version_info":
        _, receiver, op, written = condition
        if reading.version is not None and _bound_above(facts.sys_aliases, receiver, line):
            major, minor = reading.version
            wanted = written[0] * 256 + (written[1] if len(written) > 1 else 0)
            value = _COMPARE[op](major * 256 + minor, wanted)
    elif head == "sys.version_info[0]":
        _, receiver, op, written = condition
        if reading.version is not None and _bound_above(facts.sys_aliases, receiver, line):
            value = _COMPARE[op](reading.version[0], written)
    elif head == "not":
        inner = evaluate(condition[1], line, facts, reading, forms)
        return None if inner is None else not inner
    elif head in ("and", "or"):
        # Code flow, as Pyright reads it: one deciding operand settles the
        # whole wherever it sits; otherwise every operand must be static.
        # Only the operands that decided it name their form.
        deciding = head == "or"
        read = []
        for c in condition[1]:
            own: set = set()
            read.append((evaluate(c, line, facts, reading, own), own))
        values = [v for v, _ in read]
        if deciding in values:
            chosen = [own for v, own in read if v is deciding]
            result: bool | None = deciding
        else:
            chosen = [own for _, own in read]
            result = None if None in values else not deciding
        if result is not None and forms is not None:
            for own in chosen:
                forms |= own
        return result
    if value is not None and forms is not None:
        forms.add(_FORM_OF[head])
    return value


def _merged(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """*spans* as a union: a span inside or overlapping another counts once."""
    out: list[list[int]] = []
    for first, last in sorted(spans):
        if out and first <= out[-1][1]:
            out[-1][1] = max(out[-1][1], last)
        else:
            out.append([first, last])
    return tuple((first, last) for first, last in out)


def _killed(test: StaticTest, facts: ParsedFile, reading: Reading, forms: set):
    """The spans *test* kills under *reading*, recording what decided it."""
    decided: set = set()
    value = evaluate(test.condition, test.line, facts, reading, decided)
    if value is None:
        return ()
    spans = test.on_true if value else test.on_false
    if spans:
        forms |= decided
    return spans


def read_file(facts: ParsedFile, reading: Reading) -> FileReading:
    """One file's dead regions and twins under *reading* (ADR-154 step 3).

    A twin is a qualname with exactly one def whose line lies outside the
    dead regions and one or more whose line lies inside: its node belongs
    at the live def (step 5). All live, or two live, is no twin.
    """
    forms: set = set()
    spans: list[tuple[int, int]] = []
    for test in facts.static_tests:
        spans.extend(_killed(test, facts, reading, forms))
    regions = _merged(spans)
    by_qualname: dict[str, list[Symbol]] = {}
    for symbol in facts.symbols:
        by_qualname.setdefault(symbol.qualname, []).append(symbol)
    twins: dict[str, tuple[Symbol, tuple[Symbol, ...]]] = {}
    for qualname in sorted(by_qualname):
        defs = by_qualname[qualname]
        dead = tuple(s for s in defs if any(a <= s.line <= b for a, b in regions))
        live = [s for s in defs if not any(s is d for d in dead)]
        if len(live) == 1 and dead:
            twins[qualname] = (live[0], dead)
    return FileReading(
        regions=regions,
        forms=tuple(f for f in FORMS if f in forms),
        twins=twins,
    )
