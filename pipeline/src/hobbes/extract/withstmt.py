"""A ``with`` statement's ``__enter__`` and ``__exit__``, where the item's
class is known (ADR-156, C-174).

A sync ``with`` runs its context manager's ``__enter__`` and ``__exit__``,
and the source writes a call to neither. Lane A records a call where one is
written and the index gives no reference at the ``with`` for them, so
neither is a site and the join draws nothing. What *is* written is the
item's own call — ``Live(…)``, ``console.capture()`` — and the index does
answer there. This module reads that answer off the settled graph, as
:func:`hobbes.extract.fixtures.value_calls` reads a fixture's
construction, and draws the two methods the class it names would run.

The item's class C comes from one of two shapes, both resolved by the
index and only pointed at by lane A:

- the item's scope has exactly one ``semantic`` ``calls`` edge with
  evidence at the item's line whose target's last name is the name the
  item's **own** call writes — never an inner call on the same line, which
  read ``FlaskClient.__exit__`` five times wrong for
  ``app.test_client().get(…)`` before the rule bound to the outermost
  call; a **class** target is C;
- a function or method target F whose written return annotation has head
  H on line L (:attr:`hobbes.extract.pysource.Symbol.returns`), where the
  graph carries exactly one ``semantic`` ``uses`` edge from F to a class
  named H with evidence at L: that class is C. Where a factory's
  annotation named an in-repo class, it was the class whose ``__exit__``
  ran in every case on rich, flask and click.

Each method is then ADR-145's :func:`~hobbes.extract.fixtures._class_method`
— one ``def``, not a property, on C or up its chain of single named bases,
stopping wherever Python's answer is not certain — and each one found is a
``calls`` edge from the item's scope at the ``syntactic`` tier, evidenced
at the item's line. A pair the graph already carries a ``calls`` edge for
is left alone: the join's answer stands.

It abstains, and counts the abstention, wherever the class is not known
exactly. What stays C-174: an item that is a bare name or attribute
(``with ctx:``), a ``@contextmanager`` factory (its methods are
``contextlib``'s), an annotation naming an outside type, an unannotated
factory, a class whose chain the walk stops on, and ``async with``, which
none of the graded cells holds. Without lane B there is no ``semantic``
edge to read, so nothing is drawn (P6).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.fixtures import (
    ALREADY_DRAWN,
    BASE_UNNAMED,
    CLASS_BINDS,
    MULTIPLE_BASES,
    NO_METHOD,
    PROPERTY,
    TWO_DEFINITIONS,
    _class_method,
    _is_class,
)
from hobbes.extract.pysource import ParsedFile
from hobbes.extract.schema import SEMANTIC

#: What an edge drawn for a ``with`` item is evidenced as (ADR-156), on the
#: evidence entry it becomes.
WITH = "with"

#: The two methods a sync ``with`` runs, in the order it runs them.
METHODS = ("__enter__", "__exit__")

#: Why an item named no class (ADR-156 step 2), in the order asked. Each
#: is counted once per item.
NO_CALL_EDGE = "no-call-edge"
AMBIGUOUS_CALL = "ambiguous-call"
NO_ANNOTATION = "no-annotation"
ANNOTATION_UNRESOLVED = "annotation-unresolved"

#: Every reason counted, the item's first and then each method's — ADR-145's
#: walk up the bases, and a pair the graph already carries — once per
#: method of an item whose class was known.
REASONS = (
    NO_CALL_EDGE,
    AMBIGUOUS_CALL,
    TWO_DEFINITIONS,
    NO_ANNOTATION,
    ANNOTATION_UNRESOLVED,
    NO_METHOD,
    PROPERTY,
    CLASS_BINDS,
    MULTIPLE_BASES,
    BASE_UNNAMED,
    ALREADY_DRAWN,
)


def with_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every ``__enter__`` / ``__exit__`` a sync ``with`` item's known class
    runs (ADR-156 steps 2–3).

    *symbols* and *symbol_edges* are the graph's, settled: the class is an
    edge the index put there, and this rule only reads it.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line"}`` — the item's scope (the module's id at module level), the
    method's id, the item's file and line — sorted by ``(from, to, path,
    line)``, one row per item and method. *counts* is ``{"items", "drawn",
    "abstained"}`` with every one of :data:`REASONS`, or ``{}`` where no
    file has a ``with`` item that is a call: nothing was asked there, and a
    block of zeroes would say otherwise.
    """
    by_id = {symbol["id"]: symbol for symbol in symbols}
    paths = {module.id: module.path for module in modules}
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    semantic_from: dict[str, list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["tier"] == SEMANTIC:
            semantic_from[edge["from"]].append(edge)

    drawn: list[dict] = []
    abstained: Counter = Counter()
    items = 0
    for module in modules:
        facts = parsed.get(module.id)
        if facts is None:
            continue
        for item in facts.with_items:
            items += 1
            scope = f"{module.id}.{item.scope}" if item.scope else module.id
            reason, class_id = _item_class(
                scope, item.name, module.path, item.line, parsed, by_id, paths, semantic_from
            )
            if reason is not None:
                abstained[reason] += 1
                continue
            for method in METHODS:
                method_reason, method_id = _class_method(
                    class_id, method, parsed, by_id, semantic_from
                )
                if method_reason is not None:
                    abstained[method_reason] += 1
                    continue
                if (scope, method_id) in already:
                    abstained[ALREADY_DRAWN] += 1
                    continue
                drawn.append(
                    {"from": scope, "to": method_id, "path": module.path, "line": item.line}
                )

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not items:
        return drawn, {}
    return drawn, {
        "items": items,
        "drawn": len(drawn),
        "abstained": {reason: abstained[reason] for reason in REASONS},
    }


def _item_class(
    scope: str,
    name: str,
    path: str,
    line: int,
    parsed: dict[str, ParsedFile],
    by_id: dict,
    paths: dict[str, str],
    semantic_from: dict[str, list[dict]],
) -> tuple[str | None, str | None]:
    """ADR-156 step 2: the class the item's own call constructs or returns.

    Returns ``(None, class_id)`` or ``(reason, None)``. A factory whose
    qualname is written twice in its file abstains: the graph keeps one
    record for both, so there is no single annotation to read.
    """
    calls = [
        edge
        for edge in semantic_from.get(scope, ())
        if edge["type"] == "calls"
        and edge["to"].rpartition(".")[2] == name
        and _at(edge, path, line)
    ]
    if not calls:
        return NO_CALL_EDGE, None
    if len(calls) != 1:
        return AMBIGUOUS_CALL, None
    target = by_id.get(calls[0]["to"])
    if target is None:
        return NO_CALL_EDGE, None
    if target["kind"] == "class":
        return None, target["id"]
    facts = parsed.get(target["module"])
    definitions = [
        symbol
        for symbol in (facts.symbols if facts is not None else ())
        if symbol.qualname == target["qualname"]
    ]
    if len(definitions) > 1:
        return TWO_DEFINITIONS, None
    if not definitions or definitions[0].returns is None:
        return NO_ANNOTATION, None
    head, annotation_line = definitions[0].returns
    classes = [
        edge
        for edge in semantic_from.get(target["id"], ())
        if edge["type"] == "uses"
        and _is_class(by_id.get(edge["to"]))
        and edge["to"].rpartition(".")[2] == head
        and _at(edge, paths.get(target["module"]), annotation_line)
    ]
    if len(classes) != 1:
        return ANNOTATION_UNRESOLVED, None
    return None, classes[0]["to"]


def _at(edge: dict, path: str | None, line: int) -> bool:
    """Whether *edge* carries an evidence row at ``(path, line)``."""
    return any(
        row.get("path") == path and row.get("line") == line for row in edge["evidence"]
    )
