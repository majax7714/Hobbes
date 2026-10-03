"""rich's `rich/control.py` shape: classmethods that construct their own class."""
from enum import IntEnum


class ControlType(IntEnum):
    BELL = 1
    HOME = 2


class Control:
    def __init__(self, *codes):
        self.codes = codes

    @classmethod
    def bell(cls) -> "Control":
        """Ring the 'bell'."""
        return cls(ControlType.BELL)

    @classmethod
    def home(cls) -> "Control":
        """Move cursor to 'home' position."""
        return cls(ControlType.HOME)

    @classmethod
    def rebound(cls) -> "Control":
        # `cls` is rebound: not the class any more.
        cls = Other
        return cls()

    @classmethod
    def deferred(cls):
        # A closure: called later, perhaps with another `cls` (C-58).
        def make():
            return cls()

        return make

    @staticmethod
    def plain(cls):
        # Not a classmethod: `cls` is an ordinary parameter.
        return cls()


class Other:
    pass


def use() -> Control:
    return Control.bell()
