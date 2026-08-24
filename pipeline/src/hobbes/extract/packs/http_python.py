"""Pack: FastAPI and Flask routes (ADR-035, ported from ADR-006/007).

Routes are read **only from decorator sites**, which is why
``requests.get(...)`` in a function body can never become a route. That
rule is older than the pack and survives the port unchanged — the
implementation still lives in :mod:`hobbes.extract.interfaces`, and this
module is the only path by which its output reaches ``interfaces.json``.
"""

from __future__ import annotations

from hobbes.extract.interfaces import declined_route_sites, extract_routes
from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.pysource import FromImport, PlainImport
from hobbes.extract.schema import SYNTACTIC

#: Top-level imports that mean a module might register routes.
_FRAMEWORKS = ("fastapi", "flask")


def _applies(ctx: PackContext) -> bool:
    """True when any discovered module imports a framework we can read.

    Detection is the import, not the decorator: a repo that imports FastAPI
    and registers nothing statically still has this pack run and contribute
    zero routes, which is the honest answer. Deciding on decorators would
    make "no routes found" and "pack never ran" the same observation.
    """
    for facts in ctx.parsed.values():
        for imp in facts.imports:
            if isinstance(imp, PlainImport):
                top = imp.module.split(".")[0]
            elif isinstance(imp, FromImport) and imp.level == 0 and imp.module:
                top = imp.module.split(".")[0]
            else:
                continue
            if top in _FRAMEWORKS:
                return True
    return False


def _run(ctx: PackContext) -> PackResult:
    errors = [
        {
            "path": d["file"],
            "stage": "http-python",
            "message": (
                f"{d['file']}:{d['line']}: a {d['framework']} route registration "
                "whose path is computed rather than literal; the route is absent "
                "from interfaces.json, not guessed at (C-5)."
            ),
        }
        for d in declined_route_sites(ctx.modules, ctx.parsed)
    ]
    return PackResult(
        routes=extract_routes(ctx.modules, ctx.parsed), errors=errors
    )


PACK = Pack(name="http-python", tier=SYNTACTIC, applies=_applies, run=_run)
