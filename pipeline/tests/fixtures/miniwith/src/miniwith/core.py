from types import TracebackType
from typing import Optional, Type


class Capture:
    """Context manager to capture the result of printing to the console.
    See :meth:`~rich.console.Console.capture` for how to use.

    Args:
        console (Console): A console instance to capture output.
    """

    def __init__(self, console: "Console") -> None:
        self._console = console
        self._result: Optional[str] = None

    def __enter__(self) -> "Capture":
        self._console.begin_capture()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._result = self._console.end_capture()

    def get(self) -> str:
        """Get the result of the capture."""
        return self._result


class Console:
    def begin_capture(self) -> None:
        pass

    def end_capture(self) -> str:
        return ""

    def capture(self) -> Capture:
        """A context manager to *capture* the result of print() or log() in a string,
        rather than writing it to the console.
        """
        capture = Capture(self)
        return capture


def use(console: Console) -> str:
    with console.capture() as capture:
        pass
    return capture.get()


class Base:
    def __exit__(self, *exc) -> None:
        pass


class Sub(Base):
    def __enter__(self) -> "Sub":
        return self


def make() -> Sub:
    return Sub()


def unannotated():
    return Sub()


def each(c: Console) -> None:
    with Capture(c):
        pass
    with c.capture() as capture:
        pass
    with make():
        pass
    with unannotated():
        pass
    with Sub() as s:
        pass
