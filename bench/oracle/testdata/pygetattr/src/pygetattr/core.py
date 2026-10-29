"""H-38's fixture: the tracer must never run a line the repo wrote.

``Anything.__getattr__`` answers every name, dunders too, with a value
that is not a code object, and records each name it is asked. Nothing in
the suite asks it, so under trace ``ASKED`` must stay empty: a tracer that
reads ``__code__``, ``__func__`` or ``__wrapped__`` with ``getattr`` on the
callable runs it, and then fails the test the untraced suite passes.

Hand truth (every pair in-repo, read by the test from this file's text):

- ``call_instance``'s ``a()`` → ``Anything.__call__``, via ``__call__``;
- ``call_wrapped``'s ``logged(1)`` → ``plain``, via ``wrapped``
  (``functools.wraps`` leaves ``__wrapped__`` in the wrapper's own dict);
- ``call_method``'s ``b.ping()`` → ``Bound.ping`` (a bound method's
  ``__func__``, a C slot).
"""
import functools

ASKED = []


class Anything:
    def __getattr__(self, name):
        ASKED.append(name)
        return 2

    def __call__(self):
        return "called"


class Bound(Anything):
    def ping(self):
        return "pong"


def plain(x):
    return x + 1


def wrap(f):
    @functools.wraps(f)
    def inner(*args):
        return f(*args)
    return inner


logged = wrap(plain)


def call_instance():
    a = Anything()
    return a()


def call_wrapped():
    return logged(1)


def call_method():
    b = Bound()
    return b.ping()
