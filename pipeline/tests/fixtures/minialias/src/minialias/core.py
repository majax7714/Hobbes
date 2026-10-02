"""Calls through local aliases (ADR-160): to a class, a method and a
function in the repo, to a list's method outside it, and through a name
bound twice."""

from minialias.segment import Segment, cell_len


def render(texts):
    _Segment = Segment
    first = _Segment(texts[0])
    return [first] + [_Segment(text) for text in texts[1:]]


class Console:
    def get_style(self, name):
        return name

    def render_str(self, text):
        get_style = self.get_style
        return get_style("x")


def measure(text):
    _len = cell_len
    return _len(text)


def collect(texts):
    parts = []
    append = parts.append
    append("".join(texts))
    return parts


def twice(text):
    size = cell_len
    size = len
    return size(text)
