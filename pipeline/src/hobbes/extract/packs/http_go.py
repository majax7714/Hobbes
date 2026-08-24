"""Pack: ``net/http`` route registrations (ADR-035 interface, ADR-037).

The V2.M5 pack, and the test of whether V2.M4's interface was actually a
plug: a new language's framework knowledge should be a new module and a
registry line, with nothing else touched.

Go's stdlib router is the one worth reading, because it is what a Go repo
has before it has a framework: ``http.HandleFunc("/path", handler)`` and
``mux.Handle("/path", h)``. Both name the path as a literal, which is the
same rule the Python and TS HTTP packs follow — a route is only reported
when the path is statically visible, never when it is computed (C-5).

**Method is not in the registration.** `net/http` routes match on path
alone and dispatch on method *inside* the handler (before Go 1.22's
``"GET /path"`` pattern syntax, which is also handled here when present).
So a route row's ``method`` is ``ANY`` unless the pattern says otherwise —
stated rather than guessed, because reporting ``GET`` for a handler that
also serves ``POST`` would be a confident wrong answer.
"""

from __future__ import annotations

import re

from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.schema import SYNTACTIC

#: ``http.HandleFunc(...)`` / ``mux.Handle(...)`` — the registration verbs.
_HANDLERS = {"HandleFunc", "Handle"}

#: Go 1.22 patterns may lead with a method: ``"GET /items/{id}"``.
_METHOD_PATTERN = re.compile(
    r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/.*)$"
)


def _applies(ctx: PackContext) -> bool:
    """True when a Go file imports ``net/http``.

    Keyed on the import rather than on finding a registration, so "no
    routes" and "pack never ran" stay distinguishable — the same rule the
    Python HTTP pack follows.
    """
    if not ctx.go:
        return False
    return any(
        imp["path"] == "net/http"
        for parsed in ctx.go["files"]
        for imp in parsed.imports
    )


def _run(ctx: PackContext) -> PackResult:
    from hobbes.extract.gosource import module_id

    routes = []
    errors = []
    for parsed in ctx.go["files"]:
        for call in parsed.calls:
            if call["name"] not in _HANDLERS:
                continue
            route = _route_from(call)
            if route is None:
                # A registration verb whose pattern argument is computed:
                # declined, and said so (C-5). Only when no string argument
                # exists at all — a string that is not a path (a host
                # pattern, a middleware name) was seen and judged, not
                # missed.
                if call["args"] and not any(
                    arg["kind"] == "string" for arg in call["args"]
                ):
                    errors.append(
                        {
                            "path": parsed.path,
                            "stage": "http-go",
                            "message": (
                                f"{parsed.path}:{call['call_line']}: a net/http "
                                "route registration whose pattern is computed "
                                "rather than literal; the route is absent from "
                                "interfaces.json, not guessed at (C-5)."
                            ),
                        }
                    )
                continue
            handler = route["handler"]
            routes.append(
                {
                    "framework": "net/http",
                    "method": route["method"],
                    "path": route["path"],
                    "handler": (
                        f"{module_id(parsed.path)}.{handler}" if handler else ""
                    ),
                    "file": parsed.path,
                    "line": call["call_line"],
                }
            )
    return PackResult(
        routes=sorted(routes, key=lambda r: (r["file"], r["line"], r["path"])),
        errors=sorted(errors, key=lambda e: (e["path"], e["message"])),
    )


def _route_from(call: dict) -> dict | None:
    """A route from a registration's statically visible arguments.

    Reads the lane's own facts (``call["args"]``) rather than re-parsing:
    the first string argument is the pattern, the first identifier is the
    handler. A computed pattern records no string, so it is simply absent
    — never guessed at (C-5).
    """
    pattern = next(
        (arg["value"] for arg in call["args"] if arg["kind"] == "string"), None
    )
    if not pattern:
        return None
    handler = next(
        (arg["value"] for arg in call["args"] if arg["kind"] == "ident"), None
    )

    method = "ANY"
    matched = _METHOD_PATTERN.match(pattern)
    if matched:
        method, pattern = matched.group(1), matched.group(2)
    if not pattern.startswith("/"):
        return None  # not a path: a middleware name, a host pattern, anything
    return {"method": method, "path": pattern, "handler": handler}


PACK = Pack(name="http-go", tier=SYNTACTIC, applies=_applies, run=_run)
