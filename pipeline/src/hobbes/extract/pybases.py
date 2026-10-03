"""Python classes whose base the index resolved but whose `implements` edge
the index never stated (ADR-169, C-185).

scip-python 0.6.6 writes no SymbolInformation for some classes — flask's
``Flask``, icalendar's ``Component``, click's ``Group`` — so the class-level
relationship to their base is absent and Hobbes draws no ``implements``
edge, while it resolves the base name in the header as an ordinary
reference. This module finds exactly those: a lane B ``uses`` of an in-repo
class, written in a class header as one of its bases, with no ``implements``
edge from the class to it. Nothing is drawn; the pairs are named in one
record. Grammar-free (I-4): the header spans come from :mod:`pysource`.
"""

from __future__ import annotations

from hobbes.extract.pysource import ParsedFile


def unstated_bases(modules, parsed: dict[str, ParsedFile], symbols: list[dict], edges: list[dict]) -> list[tuple[str, str]]:
    """``(class id, base id)`` pairs, sorted: the base lane B resolved in the
    class's header, and no ``implements`` edge between them."""
    by_line = {}
    path_of = {m.id: m.path for m in modules}
    for symbol in symbols:
        if symbol.get("kind") == "class" and symbol.get("module") in path_of:
            by_line[(path_of[symbol["module"]], symbol["line"])] = symbol
    heads: dict[str, list[tuple[int, int, frozenset[str], dict]]] = {}
    for module in modules:
        for line, last, names in parsed[module.id].type_facts.heads:
            symbol = by_line.get((module.path, line))
            if symbol is not None:
                heads.setdefault(module.path, []).append((line, last, frozenset(names), symbol))
    kinds = {s["id"]: s for s in symbols}
    stated = {(e["from"], e["to"]) for e in edges if e["type"] == "implements"}
    out: set[tuple[str, str]] = set()
    for edge in edges:
        target = kinds.get(edge["to"])
        if edge["type"] != "uses" or target is None or target.get("kind") != "class":
            continue
        for row in edge.get("evidence", ()):
            if row.get("lane") != "scip":
                continue
            for line, last, names, symbol in heads.get(row["path"], ()):
                if (
                    line <= row["line"] <= last
                    and target["name"] in names
                    and edge["to"] != symbol["id"]
                    and edge["from"] in (symbol["id"], symbol["module"])
                    and (symbol["id"], edge["to"]) not in stated
                ):
                    out.add((symbol["id"], edge["to"]))
    return sorted(out)
