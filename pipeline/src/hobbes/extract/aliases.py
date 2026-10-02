"""A call through a local alias, drawn to what the alias's right-hand side
names (ADR-160, narrowing C-9).

A function that binds a local name to a global or an attribute and then
calls the local —

    _Segment = Segment
    …
    append(_Segment(bar, …))

— draws no edge at the call. The index names ``Segment`` at the
assignment and draws ``uses`` to the class; at the call it names the
local variable, which is below the symbol floor (C-9), so the join has
nothing to draw and the tail calls the site ``local-binding``. What the
local holds is written in syntax: lane A records, per definition, each
name its own scope binds exactly once by a plain ``N = R``
(:attr:`hobbes.extract.pysource.ParsedFile.local_aliases`), and a call of
the bare name in that scope calls what R named at that line.

This module reads R's target off the settled graph, as
:func:`hobbes.extract.withstmt.with_calls` reads a ``with`` item's class:
the calling definition's ``semantic`` ``uses`` or ``calls`` edges with an
evidence row at the assignment's line whose target's last name is R's last
name. Exactly one target, and it is drawn — a class, a function or a
method, whatever lane B named at R — as a ``calls`` edge from the
definition at the ``syntactic`` tier (the binding is read from syntax;
only R's answer is the index's), evidenced at each call site. A pair the
graph already carries a ``calls`` edge for is left alone: the join's
answer stands.

It abstains, and counts the abstention, where R names nothing the graph
holds (outside the repo, below the floor, or the index silent) and where R
names more than one thing. Nothing here infers a type. Without lane B
there is no ``semantic`` edge to read, so nothing is drawn (P6).
Resolution coverage is not moved (ADR-160 *Not taken*): the join did not
resolve the site, so the tail still counts it.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile
from hobbes.extract.schema import SEMANTIC

#: What an edge drawn through a local alias is evidenced as (ADR-160), on
#: the evidence entry it becomes.
ALIAS = "alias"

#: Why a site was not drawn (ADR-160 steps 3–4), each counted once per site.
NO_RHS_EDGE = "no-rhs-edge"
AMBIGUOUS_RHS = "ambiguous-rhs"
ALREADY_DRAWN = "already-drawn"

#: Every reason counted, in the order asked.
REASONS = (NO_RHS_EDGE, AMBIGUOUS_RHS, ALREADY_DRAWN)

#: The edge types the index draws at a right-hand side: ``uses`` for a
#: name read, ``calls`` where the line also calls it.
_RHS_TYPES = ("uses", "calls")


def alias_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every call through a local alias whose right-hand side the index
    named exactly (ADR-160 steps 2–4).

    *symbols* and *symbol_edges* are the graph's, settled: the target is an
    edge the index put there, and this rule only reads it. *symbols* is
    taken for the signature :mod:`hobbes.extract.withstmt` set; an end the
    graph does not carry is dropped where the edges are drawn.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line"}`` — the calling function's id, the target's id, the site's
    file and line — sorted by ``(from, to, path, line)``, one row per site.
    *counts* is ``{"aliases", "sites", "drawn", "abstained"}`` with every
    one of :data:`REASONS`, or ``{}`` where no file records an alias: a
    block of zeroes would say something was asked.
    """
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    semantic_from: dict[str, list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["tier"] == SEMANTIC and edge["type"] in _RHS_TYPES:
            semantic_from[edge["from"]].append(edge)

    drawn: list[dict] = []
    abstained: Counter = Counter()
    aliases = sites = 0
    for module in modules:
        facts = parsed.get(module.id)
        if facts is None or not facts.local_aliases:
            continue
        for definitions in facts.local_aliases.values():
            aliases += sum(len(names) for _start, _end, names in definitions)
        for call in facts.calls:
            if call.scope is None or "." in call.callee:
                continue
            alias = _alias_at(facts, call.scope, call.callee, call.line)
            if alias is None:
                continue
            sites += 1
            scope = f"{module.id}.{call.scope}"
            _name, assigned, last = alias
            targets = {
                edge["to"]
                for edge in semantic_from.get(scope, ())
                if edge["to"].rpartition(".")[2] == last
                and _at(edge, module.path, assigned)
            }
            if not targets:
                abstained[NO_RHS_EDGE] += 1
                continue
            if len(targets) != 1:
                abstained[AMBIGUOUS_RHS] += 1
                continue
            (target,) = targets
            if (scope, target) in already:
                abstained[ALREADY_DRAWN] += 1
                continue
            drawn.append({"from": scope, "to": target, "path": module.path, "line": call.line})

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not aliases:
        return drawn, {}
    return drawn, {
        "aliases": aliases,
        "sites": sites,
        "drawn": len(drawn),
        "abstained": {reason: abstained[reason] for reason in REASONS},
    }


def _alias_at(
    facts: ParsedFile, scope: str, name: str, line: int
) -> tuple[str, int, str] | None:
    """The alias *name* the definition of *scope* written around *line*
    records, or None (ADR-160 step 2: the call's line says which
    definition a qualname written more than once means)."""
    for start, end, names in facts.local_aliases.get(scope, ()):
        if start <= line <= end:
            for alias in names:
                if alias[0] == name:
                    return alias
    return None


def _at(edge: dict, path: str, line: int) -> bool:
    """Whether *edge* carries an evidence row at ``(path, line)``."""
    return any(
        row.get("path") == path and row.get("line") == line for row in edge["evidence"]
    )
