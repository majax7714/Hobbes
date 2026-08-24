"""Interface inventory: HTTP routes and CLI entry points (ADR-006/007).

Routes are read only from decorator sites, so ``requests.get(...)`` in a
function body can never false-positive. CLI entry points come from
``[project.scripts]`` in every ``pyproject.toml`` in the repo.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from hobbes.extract.discover import ModuleInfo, SKIPPED_DIR_NAMES
from hobbes.extract.pysource import FromImport, ParsedFile, PlainImport

#: Decorator attribute names treated as FastAPI-style route registrations
#: (`@app.get("/x")`); also matches Flask 2's method shortcuts.
_HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "trace", "websocket"}


def extract_routes(modules: list[ModuleInfo], parsed: dict[str, ParsedFile]) -> list[dict]:
    """Statically visible route registrations, one entry per HTTP method."""
    routes = []
    for module in modules:
        facts = parsed[module.id]
        framework = _framework(facts)
        for symbol in facts.symbols:
            for decorator in symbol.decorators:
                routes.extend(
                    _route_entries(decorator, module, symbol, framework)
                )
    return sorted(routes, key=lambda r: (r["file"], r["line"], r["method"]))


def _route_entries(decorator, module: ModuleInfo, symbol, framework: str) -> list[dict]:
    if decorator.dotted is None or "." not in decorator.dotted or not decorator.args:
        return []
    attr = decorator.dotted.rsplit(".", 1)[1]
    if attr == "route":
        methods = decorator.kwargs.get("methods", ("GET",))
    elif attr in _HTTP_VERBS:
        methods = (attr.upper(),)
    else:
        return []
    if isinstance(methods, str):
        methods = (methods,)
    return [
        {
            "framework": framework,
            "method": method.upper(),
            "path": decorator.args[0],
            "handler": f"{module.id}.{symbol.qualname}",
            "file": module.path,
            "line": decorator.line,
        }
        for method in methods
    ]


def declined_route_sites(
    modules: list[ModuleInfo], parsed: dict[str, ParsedFile]
) -> list[dict]:
    """Route-shaped decorators whose path is not a string literal (C-5).

    The complement of :func:`extract_routes`: same decorator shapes, the
    sites where the path argument did not survive digestion —
    ``@app.get(f"/items/{v}")``, ``@app.route(PREFIX)``. The route stays
    out of the inventory (a guessed path is a false interface), but the
    sighting is reported so the absence is legible. Only modules that
    import a known framework are read, so ``@x.get``-shaped decorators on
    arbitrary objects never produce a record.
    """
    declined = []
    for module in modules:
        facts = parsed[module.id]
        framework = _framework(facts)
        if framework == "unknown":
            continue
        for symbol in facts.symbols:
            for decorator in symbol.decorators:
                if decorator.dotted is None or "." not in decorator.dotted:
                    continue
                attr = decorator.dotted.rsplit(".", 1)[1]
                if attr != "route" and attr not in _HTTP_VERBS:
                    continue
                if decorator.args:
                    continue
                declined.append(
                    {
                        "framework": framework,
                        "file": module.path,
                        "line": decorator.line,
                    }
                )
    return sorted(declined, key=lambda d: (d["file"], d["line"]))


def _framework(facts: ParsedFile) -> str:
    """Which web framework the module imports; tags its routes."""
    tops = set()
    for imp in facts.imports:
        if isinstance(imp, PlainImport):
            tops.add(imp.module.split(".")[0])
        elif isinstance(imp, FromImport) and imp.level == 0 and imp.module:
            tops.add(imp.module.split(".")[0])
    for candidate in ("fastapi", "flask"):
        if candidate in tops:
            return candidate
    return "unknown"


def extract_cli_entry_points(repo_root: Path) -> list[dict]:
    """``[project.scripts]`` entries from every pyproject.toml in the repo."""
    entries = []
    for pyproject in iter_pyprojects(Path(repo_root)):
        try:
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            continue  # a broken pyproject is not the extractor's problem
        scripts = data.get("project", {}).get("scripts", {})
        source = pyproject.relative_to(repo_root).as_posix()
        entries.extend(
            {"name": name, "target": target, "source": source}
            for name, target in scripts.items()
            if isinstance(target, str)
        )
    return sorted(entries, key=lambda e: (e["source"], e["name"]))


def iter_pyprojects(repo_root: Path):
    """Every ``pyproject.toml`` in the repo, pruned like Python discovery.

    Public because the CLI pack's detection needs the same pruned walk:
    ``rglob`` would descend into ``node_modules``, which is 222 MB on a real
    Vite app and holds nothing this cares about.
    """
    stack = [repo_root]
    while stack:
        directory = stack.pop()
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                if child.name not in SKIPPED_DIR_NAMES and not child.name.startswith("."):
                    stack.append(child)
            elif child.name == "pyproject.toml":
                yield child
