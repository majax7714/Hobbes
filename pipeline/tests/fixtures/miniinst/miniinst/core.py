"""Each form ADR-171 reads, and each it leaves alone."""

from miniinst.highlighter import Interned, Plain, ReprHighlighter, make_highlighter

BANNER = ReprHighlighter()("miniinst")


def render(line):
    """rich's `Traceback._render_syntax_error` shape: bound once, called."""
    highlighter = ReprHighlighter()
    return highlighter(line)


def direct(line):
    return ReprHighlighter()(line)


def interned(line):
    one = Interned()
    return one(line)


def factory(line):
    made = make_highlighter()
    return made(line)


def plain(line):
    return Plain()(line)


def twice(line, loud):
    chosen = ReprHighlighter()
    if loud:
        chosen = Interned()
    return chosen(line)


class Console:
    def __init__(self):
        self.highlighter = ReprHighlighter()

    def render_str(self, text):
        return self.highlighter(text)
