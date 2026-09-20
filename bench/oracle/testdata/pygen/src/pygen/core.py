"""Comprehensions and a lambda, for the trace oracle's H-36 rule.

Hand truth, on CPython 3.12+ (PEP 709 inlines the list comprehensions,
so only the two generator expressions make a compiler-written call):

- ``total`` — one dropped ``<genexpr>`` entry at line 21, and a real
  call of ``double`` on that same line, written in the genexpr's body;
- ``firsts`` — one dropped entry at line 25 and no in-repo target
  there: the line's only other callee is ``tuple``, external;
- ``squares`` — nothing dropped, a real call of ``double`` at line 29;
- ``apply`` — nothing dropped; the lambda (declared at 33) is called at
  line 34, and its own body calls ``double`` at line 33.
"""


def double(x):
    return x * 2


def total(xs):
    return sum(double(x) for x in xs)


def firsts(xs):
    return tuple(x for x in xs)


def squares(xs):
    return [double(x) for x in xs]


def apply(xs):
    pick = lambda v: double(v)  # noqa: E731 — a lambda is the point here
    return [pick(x) for x in xs]
