"""``with`` statements, for the trace oracle's H-37 rule.

Hand truth, on CPython 3.12 (``__enter__`` runs from ``BEFORE_WITH`` and
an exception-path ``__exit__`` from ``WITH_EXCEPT_START``, neither a
``CALL``; a normal ``__exit__`` is a ``CALL``), every implicit call keyed
at its ``with`` line:

- ``plain`` — ``CM.__enter__`` and ``Base.__exit__`` (inherited), and the
  class call ``CM``;
- ``raising`` — ``Own.__enter__`` and ``Own.__exit__``, the exit on the
  exception path, and the class call ``Own``;
- ``two`` — all four (``CM.__enter__``, ``Base.__exit__``,
  ``Own.__enter__``, ``Own.__exit__``) on one line, and both class calls;
- ``nested_call`` — ``make`` (a ``CALL``), ``CM.__enter__`` and
  ``Base.__exit__``; ``make``'s own line calls the class ``CM``;
- ``through_contextlib`` — the call of ``gen`` (through ``__wrapped__``)
  and no in-repo ``__enter__``/``__exit__``: contextlib's are external.
"""

import contextlib


class Base:
    def __exit__(self, *exc):
        return False


class CM(Base):
    def __enter__(self):
        return self


class Own:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def plain():
    with CM():
        pass


def raising():
    try:
        with Own():
            raise ValueError("out through __exit__")
    except ValueError:
        pass


def two():
    with CM(), Own():
        pass


def make() -> CM: return CM()  # noqa: E704 — one line, so the class call is make's line


def nested_call():
    with make():
        pass


@contextlib.contextmanager
def gen():
    yield


def through_contextlib():
    with gen():
        pass
