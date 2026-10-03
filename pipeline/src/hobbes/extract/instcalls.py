"""A call of a constructed instance, drawn to its class's ``__call__``
(ADR-171, narrowing C-174).

    TimeStamper(fmt="iso")(None, None, event_dict)      # direct
    highlighter = ReprHighlighter()                      # bound
    highlighter(text)

Calling an instance runs ``type(obj).__call__``, and the source writes no
name for it: lane A records the direct form as an ``<expr>`` site (C-63)
and the bound form as a call of a local (C-9), and the index names nothing
the join can draw at either. What the instance is, is written: lane A
records each ``C(…)(…)`` (:attr:`hobbes.extract.pysource.ParsedFile.instance_calls`)
and each name a definition's scope binds exactly once, by a plain
``N = C(…)``, that a bare call in that scope uses
(:attr:`~hobbes.extract.pysource.ParsedFile.local_instances`, under
ADR-160's refusals).

This module reads the class off the settled graph, as
:func:`hobbes.extract.withstmt.with_calls` reads a ``with`` item's: the
scope's ``semantic`` ``calls`` edge with an evidence row at the inner
callee's line whose target's last name is the callee's name — exactly one,
and a **class**. A construction gives the instance's exact class; a
factory's return annotation would give a declared one, and a subclass's
own ``__call__`` would make that edge wrong, so a def abstains. So does a
class that writes a ``def __new__`` on its chain of single named bases: the
construction may hand back something else. The method is ADR-145's
:func:`hobbes.extract.fixtures._class_method` walk for ``__call__``.

The edge is ``calls`` from the scope (the module at module level, for the
direct form) to the ``__call__``, ``syntactic`` — the class is the index's
answer at the construction, the instance's path to the call is read from
syntax — evidenced ``via: "__call__"`` at the outer call's line. A pair the
graph already carries a ``calls`` edge for is left alone. Without lane B
there is no ``semantic`` edge to read, so nothing is drawn (P6).
Resolution coverage is not moved: the join did not resolve the site.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.fixtures import (
    BASE_UNNAMED,
    CLASS_BINDS,
    MULTIPLE_BASES,
    NO_METHOD,
    PROPERTY,
    _class_method,
)
from hobbes.extract.pysource import ParsedFile
from hobbes.extract.schema import SEMANTIC

#: What an edge drawn by this rule is evidenced as (ADR-171): the name the
#: language calls, as the trace key's ``via`` spells it.
CALL = "__call__"

#: Why a site was not drawn (ADR-171 steps 2–4), each counted once per site.
NO_CALL_EDGE = "no-call-edge"
AMBIGUOUS_CALL = "ambiguous-call"
NOT_A_CLASS = "not-a-class"
DEFINES_NEW = "defines-new"
ALREADY_DRAWN = "already-drawn"

#: Every reason counted, in the order asked; the method walk's own reasons
#: sit between the class's and the pair's.
REASONS = (
    NO_CALL_EDGE,
    AMBIGUOUS_CALL,
    NOT_A_CLASS,
    DEFINES_NEW,
    NO_METHOD,
    PROPERTY,
    CLASS_BINDS,
    MULTIPLE_BASES,
    BASE_UNNAMED,
    ALREADY_DRAWN,
)


def instance_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every call of a constructed instance whose class the index named and
    whose ``__call__`` the class walk finds (ADR-171).

    *symbols* and *symbol_edges* are the graph's, settled: the class is an
    edge the index put there, and this rule only reads it.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line"}`` — the scope's id (the module's at module level), the
    ``__call__``'s id, the site's file and the outer call's line — sorted
    by ``(from, to, path, line)``, one row per site. *counts* is
    ``{"sites", "drawn", "abstained"}`` with every one of :data:`REASONS`,
    or ``{}`` where no file records a site: a block of zeroes would say
    something was asked.
    """
    by_id = {symbol["id"]: symbol for symbol in symbols}
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    semantic_from: dict[str, list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["tier"] == SEMANTIC:
            semantic_from[edge["from"]].append(edge)

    drawn: list[dict] = []
    abstained: Counter = Counter()
    sites = 0
    for module in modules:
        facts = parsed.get(module.id)
        if facts is None:
            continue
        for scope_name, line, name, site in _sites(facts):
            sites += 1
            scope = f"{module.id}.{scope_name}" if scope_name else module.id
            reason, method_id = _call_method(
                scope, name, module.path, line, parsed, by_id, semantic_from
            )
            if reason is None and (scope, method_id) in already:
                reason = ALREADY_DRAWN
            if reason is not None:
                abstained[reason] += 1
                continue
            drawn.append({"from": scope, "to": method_id, "path": module.path, "line": site})

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not sites:
        return drawn, {}
    return drawn, {
        "sites": sites,
        "drawn": len(drawn),
        "abstained": {reason: abstained[reason] for reason in REASONS},
    }


def _sites(facts: ParsedFile):
    """``(scope, the callee's line, its name, the site's line)`` for each
    site of ADR-171 step 1, in source order: the direct form, then each
    bare call of a recorded instance."""
    for call in facts.instance_calls:
        yield call.scope, call.line, call.name, call.site
    if not facts.local_instances:
        return
    for call in facts.calls:
        if call.scope is None or "." in call.callee:
            continue
        for start, end, names in facts.local_instances.get(call.scope, ()):
            if start <= call.line <= end:
                for bound, line, name in names:
                    if bound == call.callee:
                        yield call.scope, line, name, call.line


def _call_method(
    scope: str,
    name: str,
    path: str,
    line: int,
    parsed: dict[str, ParsedFile],
    by_id: dict,
    semantic_from: dict[str, list[dict]],
) -> tuple[str | None, str | None]:
    """ADR-171 steps 2–3: the ``__call__`` the constructed class answers
    with. Returns ``(None, method_id)`` or ``(reason, None)``."""
    targets = {
        edge["to"]
        for edge in semantic_from.get(scope, ())
        if edge["type"] == "calls"
        and edge["to"].rpartition(".")[2] == name
        and _at(edge, path, line)
    }
    if not targets:
        return NO_CALL_EDGE, None
    if len(targets) != 1:
        return AMBIGUOUS_CALL, None
    (class_id,) = targets
    record = by_id.get(class_id)
    if record is None:
        return NO_CALL_EDGE, None
    if record["kind"] != "class":
        return NOT_A_CLASS, None
    _reason, new = _class_method(class_id, "__new__", parsed, by_id, semantic_from)
    if new is not None:
        return DEFINES_NEW, None
    return _class_method(class_id, CALL, parsed, by_id, semantic_from)


def _at(edge: dict, path: str, line: int) -> bool:
    """Whether *edge* carries an evidence row at ``(path, line)``."""
    return any(
        row.get("path") == path and row.get("line") == line for row in edge["evidence"]
    )
