"""An overload, a property setter and an if/else pair: one qualname, several defs."""

import typing as t

from .errors import Abort, Payload, Usage


class Command:
    """A command with an overloaded entry point and a named property."""

    @t.overload
    def main(self, args: None) -> None: ...
    @t.overload
    def main(self, args: list) -> int: ...
    def main(self, args=None):
        try:
            return len(args or ())
        except Abort:
            raise Usage("aborted")

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: Payload) -> None:
        if not value:
            raise Usage("empty")
        self._name = value


FAST = True

if FAST:
    def encode(v: Payload) -> str:
        return "fast"
else:
    def encode(v: Payload) -> str:
        return "slow"
