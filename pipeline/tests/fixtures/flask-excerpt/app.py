# flask @ d73fa1c, src/flask/sansio/app.py (BSD-3-Clause) — see NOTICE.
# Signatures and decorators verbatim; the bodies are shortened.
from __future__ import annotations

import typing as t

from scaffold import F, Scaffold, setupmethod


class App(Scaffold):
    @setupmethod
    def add_url_rule(
        self,
        rule: str,
        endpoint: str | None = None,
        view_func: t.Callable[..., t.Any] | None = None,
        provide_automatic_options: bool | None = None,
        **options: t.Any,
    ) -> None:
        self.url_map.add(rule, endpoint, view_func, **options)

    @t.overload
    def template_filter(self, name: F) -> F: ...

    @t.overload
    def template_filter(self, name: str | None = None) -> t.Callable[[F], F]: ...

    @setupmethod
    def template_filter(self, name: F | str | None = None) -> t.Any:
        return self.jinja_env.filters.setdefault(name, name)
