"""The decorators ``minideco.app`` applies (ADR-146, ADR-147, ADR-148).

``plain`` is applied by name. ``factory`` and ``Registry.register`` are
called first and the ``decorator`` they return is applied to the
definition — the second hop, which ADR-147 draws: every return in each
body is that one nested ``def``.

``wrapped`` is the refusal beside them: it is itself decorated, so what
it hands back is what ``passthrough`` returned, which is not the ``def``
written inside it.

``either``, ``optional`` and ``Registry.command`` each return
``decorator`` on one path and ``decorator(…)`` on another, so ADR-147
settles none of them. ADR-148 folds their guards over the arguments the
site itself writes: ``@either("")``, ``@optional()`` and
``@registry.command()`` can reach no return but ``return decorator``,
while ``@either("d")`` reaches the other one and ``@optional(TAG)``
passes a name the fold cannot read — both refused ``guard-unknown``.
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

    def command(self, *args, **kwargs):
        func = None
        if args and callable(args[0]):
            (func,) = args

        def decorator(fn):
            return fn

        if func is not None:
            return decorator(func)
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


def optional(name=None, **attrs):
    func = None
    if callable(name):
        func = name

    def decorator(fn):
        return fn

    if func is not None:
        return decorator(func)
    return decorator
