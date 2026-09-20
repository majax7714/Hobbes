"""A decorator factory's application, read as a call of the def it
returns (ADR-147).

``@click.option("--count")`` is two calls. The first — ``option(…)`` — the
index names at the token and ADR-146 draws. The second is the application
of what it returned to the definition below it, and the source writes no
token for it at all: there is no name for any indexer to resolve, so the
join can never produce that edge. Where the factory's shape settles what
it returns, though, the second call is exact, and this module draws it —
a ``calls`` edge at the **``syntactic``** tier, evidenced at the callee's
line with ``via: decorator-factory``, from the decorator's caller to the
nested def.

The shape it reads, and nothing wider (:func:`factory_calls` asks the
five conditions in the ADR's order, and the first that fails is the one
counted):

1. the settled graph carries a ``semantic`` ``calls`` edge with evidence
   at the decorator's callee line whose target is a function or method
   **named as written** — the index naming ``f``, never lane A's reading
   — and exactly one such target. The edge's ``from`` is the caller, as
   ADR-146 scoped it: the decorator runs where it is written;
2. ``f`` has one body: of the definitions of its qualname, exactly one is
   not an ``@overload`` stub, and that one carries no decorator at all
   (the drawn symbol may *be* the first stub — H-19's grain — so the body
   is looked up rather than assumed);
3-4. that body's :attr:`~hobbes.extract.pysource.Symbol.returns_inner`
   names ``g``: every return in its own body is ``return g``, and ``g``
   is one plain undecorated nested ``def`` bound once;
5. ``<f's id>.<g>`` is exactly one symbol of kind ``function``.

**What it refuses**, each counted by reason: more than one answer at the
line (:data:`TWO_TARGETS`), no single body (:data:`NO_SINGLE_BODY`), a
decorated factory (:data:`DECORATED` — flask's ``Scaffold.route`` under
``@setupmethod``), a factory whose returns the strict wording does not
settle (:data:`NO_RETURNED_DEF`), no such inner symbol
(:data:`NO_SYMBOL`), and a ``(from, to)`` pair the graph already carries
a ``calls`` edge for (:data:`ALREADY_DRAWN` — the join's edge stands, and
this rule never restates it). :data:`NO_RETURNED_DEF` is one reason for
what the ADR lists as three — ``async``, a generator, and a return shape
the rule cannot settle — because the walk keeps one fact for all three
and a second walk here would be a second reading of the same body.

**Not counted, because nothing was asked**: a decorator with no
``semantic`` in-repo edge at its line (``@pytest.fixture()``, an untyped
``@app.route(…)``), a bare ``@f`` — which applies ``f`` itself, ADR-146's
edge, not this one — a callee that is not a name chain, and a callee
whose terminal identifier is not on the decorator's own line (a wrapped
chain is not asked). Without lane B the rule draws nothing at all:
condition 1 cannot hold.

The counts block is written where **some site was asked** — where the
index named a factory at a decorator's line — rather than only where one
reached condition 2 as the ADR words it: the one site those two readings
differ over is a line with more than one answer, which is a refusal, and
a refusal a reader cannot see is worse than a block that says one thing
was asked and refused.

**Not claimed:** what ``g`` returns, or what a later call of the
decorated name reaches. C-58 keeps every other function value.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile, Symbol
from hobbes.extract.schema import SEMANTIC

#: What an edge drawn on a decorator factory's application is evidenced as
#: (ADR-147), on the row and on the evidence entry it becomes.
DECORATOR_FACTORY = "decorator-factory"

#: The decorator that makes a definition a typing stub rather than a body:
#: read by its dotted name's last component, so ``@overload`` and
#: ``@t.overload`` are one thing.
OVERLOAD = "overload"

#: Why a decorator-factory application drew nothing, in the order the
#: conditions are asked. Each is a place the rule chose to draw less
#: rather than guess, so each is counted at the site it was refused at.
TWO_TARGETS = "two-targets"
NO_SINGLE_BODY = "no-single-body"
DECORATED = "decorated"
NO_RETURNED_DEF = "no-returned-def"
NO_SYMBOL = "no-symbol"
ALREADY_DRAWN = "already-drawn"
FACTORY_REASONS = (
    TWO_TARGETS,
    NO_SINGLE_BODY,
    DECORATED,
    NO_RETURNED_DEF,
    NO_SYMBOL,
    ALREADY_DRAWN,
)


def factory_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every call-form decorator whose factory's shape settles what it
    returns (ADR-147).

    *symbols* and *symbol_edges* are the graph's, **settled**: condition 1
    is an edge the index put there, and this rule only reads it.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line", "via", "factory"}`` — the decorator's caller, the nested def,
    the decorating file and the callee's line, :data:`DECORATOR_FACTORY`,
    and the factory whose return the chain went through — sorted by
    ``(from, to, path, line)``, one row per decorator site. *counts* is
    ``{"drawn", "refused"}`` with every one of :data:`FACTORY_REASONS`, or
    ``{}`` where no site was asked at all: a repo whose decorators the
    index resolved to nothing in-repo was never asked this question, and a
    block of zeroes would say otherwise.
    """
    by_id = {symbol["id"]: symbol for symbol in symbols}
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    resolved: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["type"] != "calls" or edge["tier"] != SEMANTIC:
            continue
        for row in edge["evidence"]:
            resolved[(row.get("path"), row.get("line"))].append(edge)

    drawn: list[dict] = []
    refused: Counter = Counter()
    asked = 0
    for module in modules:
        for symbol in parsed[module.id].symbols:
            for decorator in symbol.decorators:
                if not decorator.called or decorator.callee_line is None:
                    continue
                if decorator.callee_line != decorator.line:
                    # A chain wrapped across lines: the ADR does not ask
                    # about a site whose callee is not where the `@` is.
                    continue
                written = (decorator.dotted or "").rpartition(".")[2]
                answers = [
                    edge
                    for edge in resolved.get((module.path, decorator.callee_line), ())
                    if _named_as_written(by_id.get(edge["to"]), written)
                ]
                if not answers:
                    # The index resolved the factory to nothing in this
                    # repo — a plugin's, a dependency's, or nothing at all.
                    continue
                asked += 1
                targets = {edge["to"] for edge in answers}
                callers = {edge["from"] for edge in answers}
                if len(targets) != 1 or len(callers) != 1:
                    # One line, one enclosing scope and one factory, or the
                    # rule cannot name which call it is drawing the second
                    # half of.
                    refused[TWO_TARGETS] += 1
                    continue
                target = by_id[next(iter(targets))]
                caller = next(iter(callers))
                reason, inner_id = _returned_def(target, parsed, by_id)
                if reason is not None:
                    refused[reason] += 1
                    continue
                if (caller, inner_id) in already:
                    refused[ALREADY_DRAWN] += 1
                    continue
                drawn.append(
                    {
                        "from": caller,
                        "to": inner_id,
                        "path": module.path,
                        "line": decorator.callee_line,
                        "via": DECORATOR_FACTORY,
                        "factory": target["id"],
                    }
                )

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not asked:
        return drawn, {}
    return drawn, {
        "drawn": len(drawn),
        "refused": {reason: refused[reason] for reason in FACTORY_REASONS},
    }


def _returned_def(
    target: dict, parsed: dict[str, ParsedFile], by_id: dict
) -> tuple[str | None, str | None]:
    """Conditions 2 to 5 of ADR-147: the factory has one undecorated body,
    that body returns one nested ``def``, and the graph carries it.

    Returns ``(reason, symbol id)`` — a reason and no id, or no reason and
    the id to draw to. The definitions are counted in the target's module
    record rather than in the graph's symbols, because duplicate qualnames
    collapse to one record there (:func:`hobbes.extract.graph._symbol_records`)
    and a factory written twice would read as one clean answer.
    """
    facts = parsed.get(target["module"])
    if facts is None:
        return NO_SINGLE_BODY, None
    bodies = [
        definition
        for definition in _definitions(facts, target["qualname"])
        if not _is_overload(definition)
    ]
    if len(bodies) != 1:
        return NO_SINGLE_BODY, None
    body = bodies[0]
    if body.decorators:
        # A decorated factory hands back what its own decorator returned,
        # which is not the def written inside it.
        return DECORATED, None
    if body.returns_inner is None:
        return NO_RETURNED_DEF, None
    qualname = f"{target['qualname']}.{body.returns_inner}"
    inner_id = f"{target['module']}.{qualname}"
    found = [
        definition
        for definition in _definitions(facts, qualname)
        if definition.kind == "function"
    ]
    if len(found) != 1 or inner_id not in by_id:
        return NO_SYMBOL, None
    return None, inner_id


def _definitions(facts: ParsedFile, qualname: str) -> list[Symbol]:
    """Every definition of one qualname in a module's record — more than
    one where it is written twice (an ``@overload`` set, an ``if``/``else``
    pair)."""
    return [symbol for symbol in facts.symbols if symbol.qualname == qualname]


def _is_overload(definition: Symbol) -> bool:
    """Whether a definition is a typing stub rather than a body."""
    return any(
        (decorator.dotted or "").rpartition(".")[2] == OVERLOAD
        for decorator in definition.decorators
    )


def _named_as_written(record: dict | None, written: str) -> bool:
    """Whether a graph symbol is a function or method the decorator named.

    The written chain's last component against the symbol's own name: the
    index resolving ``f`` is the claim, and an edge at the line onto
    anything else — the class of a receiver, an argument's function — is
    not the factory this decorator applied.
    """
    return (
        record is not None
        and record["kind"] in ("function", "method")
        and record["name"] == written
    )
