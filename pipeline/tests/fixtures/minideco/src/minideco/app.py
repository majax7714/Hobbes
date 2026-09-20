"""Every decorator shape ADR-146 draws, and the hop it does not.

``plain`` is bare, ``factory("a")`` is a call, ``registry.register("b")``
is a call on a module-level construction, and ``outer`` holds a nested
def whose decorator is ``outer``'s own site — not the nested def's, which
is not running when the ``@`` is read.
"""

from minideco.deco import Registry, factory, plain

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
