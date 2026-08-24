"""Pytest inventory with static test→symbol reach (ADR-006/007).

Collection mirrors pytest's defaults: files ``test_*.py`` / ``*_test.py``,
top-level ``Test*`` classes without ``__init__``, functions and methods
named ``test*``. A test's ``reaches`` list is the transitive closure over
``calls`` edges from the test symbol — fixtures are dynamic injection and
statically invisible (a documented M1 gap, ADR-007).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile


def is_test_file(path: str) -> bool:
    """Pytest's default file conventions."""
    name = PurePosixPath(path).name
    return name.startswith("test_") or name.endswith("_test.py")


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
