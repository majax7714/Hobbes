"""Pytest inventory with static test→symbol reach (ADR-006/007).

Collection mirrors pytest's defaults: files ``test_*.py`` / ``*_test.py``,
top-level ``Test*`` classes without ``__init__``, functions and methods
named ``test*``. A test's ``reaches`` list is the transitive closure over
``calls`` edges from the test symbol — fixtures are dynamic injection and
statically invisible (a documented M1 gap, ADR-007).
"""

from __future__ import annotations

import configparser
import tomllib
from collections import defaultdict
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile


def is_test_file(path: str) -> bool:
    """Pytest's default file conventions."""
    name = PurePosixPath(path).name
    return name.startswith("test_") or name.endswith("_test.py")


#: pytest's config files, each with the section its settings live in
#: (pyproject.toml's is the ``[tool.pytest.ini_options]`` table).
_PYTEST_CONFIGS = {
    "pyproject.toml": None,
    "pytest.ini": "pytest",
    "tox.ini": "pytest",
    "setup.cfg": "tool:pytest",
}


def _pytest_settings(config: Path) -> tuple[list[str], list[str]] | None:
    """``(testpaths, norecursedirs)`` as *config* states them, or None when
    it holds no pytest section or does not parse."""
    try:
        if config.name == "pyproject.toml":
            opts = tomllib.loads(config.read_text()).get("tool", {}).get("pytest", {}).get("ini_options")
            if not isinstance(opts, dict):
                return None

            def listed(key: str) -> list[str]:
                value = opts.get(key, [])
                return value.split() if isinstance(value, str) else [str(v) for v in value]

            return listed("testpaths"), listed("norecursedirs")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(config.read_text())
        section = _PYTEST_CONFIGS[config.name]
        if not parser.has_section(section):
            return None
        return (
            parser.get(section, "testpaths", fallback="").split(),
            parser.get(section, "norecursedirs", fallback="").split(),
        )
    except (OSError, ValueError, configparser.Error):
        return None


def runner_excluded_trees(repo_root: Path, module_paths: Iterable[str]) -> tuple[dict, ...]:
    """The directories the repo's own test runners exclude from collection,
    among those holding a module: fixture trees, which a test reads as
    input and never calls, so no test could guard them (ADR-114, C-154).

    Both rules are read from the tree, never guessed from a name:

    - **pytest** — a config that states ``norecursedirs`` excludes every
      directory whose basename matches one of its patterns under each of
      its ``testpaths`` (the config's own directory when it names none).
      pytest's built-in defaults (``build``, ``dist``, …) are not read: an
      exclusion the repo did not state is a guess.
    - **Go** — the go tool ignores a directory named ``testdata`` inside a
      module, so the first ``testdata`` with a ``go.mod`` at or above it is
      excluded.

    *module_paths* bounds the search to directories that hold code. Each
    record is ``{"path", "by"}``, sorted by path.
    """
    root = Path(repo_root)
    paths = sorted({p for p in module_paths if p})
    trees: dict[str, str] = {}

    dirs = {""}
    for path in paths:
        parts = PurePosixPath(path).parts[:-1]
        dirs.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    for cfg_dir in sorted(dirs):
        for name in _PYTEST_CONFIGS:
            config = root / cfg_dir / name
            settings = _pytest_settings(config) if config.is_file() else None
            if not settings or not settings[1]:
                continue
            testpaths, patterns = settings
            cfg_rel = f"{cfg_dir}/{name}" if cfg_dir else name
            prefix = f"{cfg_dir}/" if cfg_dir else ""
            for base in [f"{prefix}{t.strip('/')}" for t in testpaths] or [cfg_dir]:
                for path in paths:
                    if base and not path.startswith(base + "/"):
                        continue
                    below = PurePosixPath(path[len(base) + 1 if base else 0:]).parts[:-1]
                    for i, part in enumerate(below):
                        pattern = next((p for p in patterns if fnmatchcase(part, p)), None)
                        if pattern:
                            tree = "/".join(filter(None, [base, *below[: i + 1]]))
                            trees.setdefault(tree, f"pytest norecursedirs {pattern!r} in {cfg_rel}")
                            break

    for path in paths:
        parts = PurePosixPath(path).parts[:-1]
        if "testdata" not in parts:
            continue
        at = parts.index("testdata")
        for k in range(at, -1, -1):
            if (root.joinpath(*parts[:k]) / "go.mod").is_file():
                gomod = "/".join([*parts[:k], "go.mod"])
                trees.setdefault("/".join(parts[: at + 1]), f"go: testdata inside the module at {gomod}")
                break

    return tuple({"path": tree, "by": by} for tree, by in sorted(trees.items()))


def collect_tests(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbol_edges: list[dict],
) -> list[dict]:
    """The tests.json ``tests`` list: inventory plus static reach."""
    test_modules = [m for m in modules if is_test_file(m.path)]
    test_module_ids = {m.id for m in test_modules}

    inventory: list[tuple[str, dict]] = []  # (test symbol id, record)
    for module in test_modules:
        quals = {s.qualname: s for s in parsed[module.id].symbols}
        for symbol in parsed[module.id].symbols:
            if not _is_test_symbol(symbol, quals):
                continue
            node_id = f"{module.path}::{symbol.qualname.replace('.', '::')}"
            inventory.append(
                (
                    f"{module.id}.{symbol.qualname}",
                    {
                        "id": node_id,
                        "file": module.path,
                        "framework": "pytest",
                        "line": symbol.line,
                        "symbol": f"{module.id}.{symbol.qualname}",
                    },
                )
            )

    adjacency = defaultdict(set)
    for edge in symbol_edges:
        # `calls` only. Since V2.M2 the symbol layer also carries `uses`
        # edges — a resolution no call site claimed: a type annotation, an
        # `except` clause, a value passed by name (ADR-029). Following them
        # would widen reach to code a test merely *names*, and reach is the
        # basis of "which tests guard this" — a claim that must not inflate.
        # ADR-007 defines reaches as the closure over call edges; this
        # keeps that contract now that it is no longer the only edge type.
        if edge["type"] != "calls":
            continue
        adjacency[edge["from"]].add(edge["to"])
    test_symbol_ids = {sid for sid, _ in inventory}
    symbol_module = _symbol_module_map(modules, parsed)

    records = []
    for symbol_id, record in inventory:
        reached = _closure(symbol_id, adjacency) - {symbol_id} - test_symbol_ids
        record["reaches"] = sorted(reached)
        # Which source modules the test guards: test-file modules (helpers
        # in the test file itself) are excluded from the projection.
        record["reaches_modules"] = sorted(
            {
                symbol_module[s]
                for s in reached
                if symbol_module.get(s) not in test_module_ids
                and symbol_module.get(s) is not None
            }
        )
        records.append(record)
    return sorted(records, key=lambda r: r["id"])


def _is_test_symbol(symbol, quals: dict) -> bool:
    """Pytest defaults: test* functions, and test* methods on top-level
    Test* classes that lack an ``__init__``."""
    if symbol.kind == "function":
        return symbol.name.startswith("test") and symbol.qualname == symbol.name
    if symbol.kind == "method" and symbol.name.startswith("test"):
        class_name, _, _ = symbol.qualname.rpartition(".")
        return (
            "." not in class_name
            and class_name.startswith("Test")
            and f"{class_name}.__init__" not in quals
        )
    return False


def _closure(start: str, adjacency: dict) -> set:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for target in adjacency.get(current, ()):
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


def _symbol_module_map(modules: list[ModuleInfo], parsed: dict[str, ParsedFile]) -> dict:
    mapping = {}
    for module in modules:
        for symbol in parsed[module.id].symbols:
            mapping[f"{module.id}.{symbol.qualname}"] = module.id
    return mapping
