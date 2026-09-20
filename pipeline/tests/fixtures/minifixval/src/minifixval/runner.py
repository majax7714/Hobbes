"""The subject a fixture constructs (ADR-145).

``Runner`` defines ``invoke`` in its own body and inherits ``close`` from
``Base``; ``name`` is a property. ``make_runner`` hands a ``Runner`` back
from a function, which is a value's type rather than a construction —
what the rule refuses is as much the point of this fixture as what it
draws.
"""


class Base:
    def close(self):
        return "closed"


class Runner(Base):
    def invoke(self, x):
        return x + 1

    @property
    def name(self):
        return "runner"


def make_runner():
    return Runner()
