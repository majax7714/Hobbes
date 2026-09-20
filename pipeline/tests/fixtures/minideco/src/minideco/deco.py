"""The decorators ``minideco.app`` applies (ADR-146).

``plain`` is applied by name. ``factory`` and ``Registry.register`` are
called first and the ``decorator`` they return is applied to the
definition — the second hop, which this fixture asserts is *not* drawn:
what a decorator returns is ADR-147's question, not this one.
"""


def plain(fn):
    return fn


def factory(label):
    def decorator(fn):
        return fn

    return decorator


class Registry:
    def register(self, name):
        def decorator(fn):
            return fn

        return decorator
