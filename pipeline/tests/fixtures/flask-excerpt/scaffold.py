# flask @ d73fa1c, src/flask/sansio/scaffold.py (BSD-3-Clause) — see NOTICE.
# Signatures and decorators verbatim; the bodies are shortened.
from __future__ import annotations

import typing as t
from functools import update_wrapper

F = t.TypeVar("F", bound=t.Callable[..., t.Any])
T_route = t.TypeVar("T_route", bound=t.Callable[..., t.Any])


def setupmethod(f: F) -> F:
    f_name = f.__name__

    def wrapper_func(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        self._check_setup_finished(f_name)
        return f(self, *args, **kwargs)

    return t.cast(F, update_wrapper(wrapper_func, f))


class Scaffold:
    def __init__(self, import_name: str, root_path: str | None = None) -> None:
        self.import_name = import_name
        self.root_path = root_path

    @setupmethod
    def route(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        def decorator(f: T_route) -> T_route:
            endpoint = options.pop("endpoint", None)
            self.add_url_rule(rule, endpoint, f, **options)
            return f

        return decorator

    @setupmethod
    def get(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        return self.route(rule, methods=["GET"], **options)

    @setupmethod
    def add_url_rule(
        self,
        rule: str,
        endpoint: str | None = None,
        view_func: t.Callable[..., t.Any] | None = None,
        provide_automatic_options: bool | None = None,
        **options: t.Any,
    ) -> None:
        raise NotImplementedError
