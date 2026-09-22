"""Every decorator shape ADR-146 draws, and the hop ADR-147 adds.

``plain`` is bare, ``factory("a")`` is a call, ``registry.register("b")``
is a call on a module-level construction, and ``outer`` holds a nested
def whose decorator is ``outer``'s own site, not the nested def's.
``either("d")`` and ``wrapped("e")`` are the factories ADR-147 refuses.
"""

from minideco.deco import Registry, either, factory, plain, wrapped

registry = Registry()


@plain
def one():
    return 1


@factory("a")
def two():
    return 2


@registry.register("b")
def three():
    return 3


def outer():
    @factory("c")
    def nested():
        return 4

    return nested


@either("d")
def four():
    return 5


@wrapped("e")
def five():
    return 6


# ADR-148: the same two calls, where which return the factory reaches is
# decided by the arguments the site itself writes. `optional` is the
# optional-parentheses idiom: `@optional()` and `@optional(tag="x")`
# leave its `func` None, so `return decorator` is the only return they
# can reach, while `@optional(TAG)` passes a name — which the fold cannot
# read even where the name is a constant beside it — and a bare
# `@optional` asks nothing at all: it applies `optional` itself
# (ADR-146). `@registry.command()` is the method shape, whose unfilled
# `*args` is empty. `@either("")` is folded the same way: the guard
# `if label:` is false on the empty string, where `@either("d")` above
# takes the other path.
from minideco.deco import optional

TAG = "x"


@optional()
def six():
    return 7


@optional(tag="x")
def seven():
    return 8


@optional(TAG)
def eight():
    return 9


@optional
def nine():
    return 10


@registry.command()
def ten():
    return 11


@either("")
def eleven():
    return 12


def folding():
    @optional()
    def deeper():
        return 13

    return deeper


# ADR-149: a factory that holds no nested def at all, and hands back a
# second factory's call. `grouped` ends `return optional(name, **attrs)`,
# so `@grouped()` and `@grouped("n")` leave `name` where `optional`'s own
# fold can read it and the chain reaches `optional`'s `decorator`;
# `@grouped(TAG)` leaves the `callable(name)` guard unread, and the return
# it then reaches — `optional(**attrs)(name)`, a call on a call — names
# nothing the index resolved, so the site is refused `chain-guard-unknown`.
# A bare `@grouped` asks nothing at all (ADR-146). `@flagged()` chains to
# `factory`, which ADR-147 settles outright, and `@relay()` chains to
# `plain`, which holds no def to reach: `chain-inner`.
from minideco.deco import flagged, grouped, relay


@grouped()
def twelve():
    return 14


@grouped("n")
def thirteen():
    return 15


@grouped(TAG)
def fourteen():
    return 16


@grouped
def fifteen():
    return 17


@flagged()
def sixteen():
    return 18


@relay()
def seventeen():
    return 19


def chaining():
    @grouped()
    def deepest():
        return 20

    return deepest
