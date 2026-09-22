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

``grouped``, ``flagged`` and ``relay`` hold no nested ``def`` at all, so
none of the rules above reads them: what each hands back is written in a
call of a **second** factory, which ADR-149 follows one level. ``grouped``
reaches ``optional``, whose guards are then folded over the arguments
``grouped`` forwards; ``flagged`` reaches ``factory``, which ADR-147
settles outright; and ``relay`` reaches ``plain``, which holds no
``decorator`` to reach — refused ``chain-inner``.
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


def grouped(name=None, cls=None, **attrs):
    if cls is None:
        cls = "g"
    if callable(name):
        return optional(**attrs)(name)
    return optional(name, **attrs)


def flagged(*decls, **kwargs):
    if not decls:
        decls = ("--x",)
    return factory(*decls, **kwargs)


def relay():
    return plain(relay)
