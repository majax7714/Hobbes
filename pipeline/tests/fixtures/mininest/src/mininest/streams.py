"""The three shapes ADR-150's abstention is read on.

``Streams`` is flask's ``TestStreaming`` shape: two methods, each nesting
an ``index`` that nests a ``generate`` it calls. scip-python names a def
nested in a *method* by the class and its own name, dropping every
function scope between, so both ``generate``s share one moniker and both
``index``es share another — one moniker, two lines of one file, and no
lane B answer for either.

``Plain`` is the control a single definition gives: ``go`` calls
``self.run()``, and ``run`` is defined once.

``outer`` is the other control: a def nested in a *module-level*
function keeps its path (``outer().inner().``), so nothing is shared and
the call is answered.
"""


class Streams:
    """Two methods whose nested defs collide under one moniker each."""

    def first(self):
        def index():
            def generate():
                return "first"

            return generate()

        return index()

    def second(self):
        def index():
            def generate():
                return "second"

            return generate()

        return index()


class Plain:
    """One definition per name: the method call still resolves."""

    def run(self):
        return "plain"

    def go(self):
        return self.run()


def outer():
    """A module-level function's nested def keeps its own path."""

    def inner():
        return "inner"

    return inner()
