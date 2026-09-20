"""The decorators ``minideco.app`` applies (ADR-146, ADR-147).

``plain`` is applied by name. ``factory`` and ``Registry.register`` are
called first and the ``decorator`` they return is applied to the
definition — the second hop, which ADR-147 draws: every return in each
body is that one nested ``def``.

``either`` and ``wrapped`` are the refusals beside them. ``either``
returns ``decorator`` on one path and ``decorator(label)`` on another, so
on that path the decorator site does not call ``decorator`` — ``either``
does. ``wrapped`` is itself decorated, so what it hands back is what
``passthrough`` returned, which is not the ``def`` written inside it.
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


def either(label):
    def decorator(fn):
        return fn

    if label:
        return decorator(label)
    return decorator


def passthrough(fn):
    return fn


@passthrough
def wrapped(label):
    def decorator(fn):
        return fn

    return decorator
