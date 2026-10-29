"""ADR-187's fixture: calls the language makes with no call token.

Hand truth, read by the test from this file's text. In ``body``, each line
marked ``# implicit: <def>`` keys that def in the export's ``implicit``
list at the line, ``via: "implicit"``, and never in ``sites``:

- an operator (``__add__``, ``__eq__``, ``__getitem__``), a loop
  (``__iter__``), a builtin's hook (``__len__``), truth (``__bool__``),
  a format (``__str__`` from an f-string);
- a property's getter and setter, and a getter a base class defines.

Lines marked ``# not implicit`` key nothing implicit: construction (the
class is ``sites``' target; ``__init__`` is never keyed), an instance's
``__call__`` and an explicit dunder call (both ``CALL`` events, in
``sites``), and a ``with`` statement (H-37's, in ``sites``). The
``functools.cached_property`` line keys nothing either: its getter runs
from ``functools``' own frame, so no repo line is its caller (ADR-187's
stated limit).
"""
import functools


class Base:
    @property
    def size(self):
        return 1


class V(Base):
    def __init__(self, x):
        self.x = x

    def __add__(self, o):
        return self.x + o.x

    def __eq__(self, o):
        return self.x == o.x

    def __hash__(self):
        return self.x

    def __getitem__(self, i):
        return i

    def __iter__(self):
        return iter([1])

    def __len__(self):
        return 1

    def __bool__(self):
        return True

    def __str__(self):
        return "v"

    def __call__(self):
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def p(self):
        return self.x

    @p.setter
    def p(self, value):
        self.x = value

    @functools.cached_property
    def cached(self):
        return 3


def body():
    a, b = V(1), V(2)  # not implicit
    a + b  # implicit: __add__
    a == b  # implicit: __eq__
    a[0]  # implicit: __getitem__
    for _ in a:  # implicit: __iter__
        pass
    len(a)  # implicit: __len__
    if a:  # implicit: __bool__
        pass
    f"{a}"  # implicit: __str__
    a.p  # implicit: p
    a.p = 5  # implicit: p.setter
    a.size  # implicit: size
    a()  # not implicit
    a.__eq__(b)  # not implicit
    with a:  # not implicit
        pass
    a.cached  # not implicit
