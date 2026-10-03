"""rich's `rich/highlighter.py` shape (ADR-171): `__call__` written on an ABC,
two single named bases below it, and near misses beside them."""

from abc import ABC


class Highlighter(ABC):
    def __call__(self, text):
        return self.highlight(text)

    def highlight(self, text):
        return text


class RegexHighlighter(Highlighter):
    pass


class ReprHighlighter(RegexHighlighter):
    pass


class Interned:
    """Writes `__new__`: the construction may hand back another object."""

    _one = None

    def __new__(cls):
        if cls._one is None:
            cls._one = super().__new__(cls)
        return cls._one

    def __call__(self, text):
        return text


class Plain:
    """No `__call__` on its chain."""


def make_highlighter() -> Highlighter:
    return ReprHighlighter()
