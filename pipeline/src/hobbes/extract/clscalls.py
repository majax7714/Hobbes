"""A bare ``cls(…)`` in a classmethod, drawn to the class the method is
written in (ADR-170, narrowing C-9).

    @classmethod
    def from_ical(cls, ical):
        return cls(parse(ical))

The index names the parameter ``cls`` at the call, a local below the
symbol floor, so the join has nothing to draw and the tail counts the site
``local-binding``. Where the ``def`` is written says which class ``cls``
is when the method is called on that class: lane A records each classmethod
written directly in a class body (and not one whose body rebinds ``cls``,
:attr:`hobbes.extract.pysource.ParsedFile.classmethods`), and a bare
``cls(…)`` in that method's own body calls the class. Called through a
subclass, it constructs the subclass; the class written is the declared
target, as for any call through a base (C-60).

The edge is ``syntactic`` (the class is read from syntax; lane B named a
parameter), ``via: "cls"``, from the classmethod to its class. A pair the
graph already carries a ``calls`` edge for is left alone, and a class the
graph keeps no symbol for draws nothing. Resolution coverage is not moved:
the join did not resolve the site, as ADR-160 leaves its own.
"""

from __future__ import annotations

from collections import Counter

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile

#: What an edge drawn by this rule is evidenced as (ADR-170).
CLS = "cls"

#: Why a site was not drawn, each counted once per site.
NO_CLASS_SYMBOL = "no-class-symbol"
ALREADY_DRAWN = "already-drawn"
REASONS = (NO_CLASS_SYMBOL, ALREADY_DRAWN)


def cls_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every ``cls(…)`` in a recorded classmethod's own body (ADR-170).

    Returns ``(calls, counts)``: a call is ``{"from", "to", "path",
    "line"}``, sorted; *counts* is ``{"classmethods", "sites", "drawn",
    "abstained"}``, or ``{}`` where no file records a classmethod.
    """
    ids = {symbol["id"] for symbol in symbols}
    already = {(e["from"], e["to"]) for e in symbol_edges if e["type"] == "calls"}
    drawn: list[dict] = []
    abstained: Counter = Counter()
    classmethods = sites = 0
    for module in modules:
        facts = parsed.get(module.id)
        if facts is None or not facts.classmethods:
            continue
        classmethods += len(facts.classmethods)
        spans: dict[str, list[tuple[int, int, str]]] = {}
        for qualname, first, last, owner in facts.classmethods:
            spans.setdefault(qualname, []).append((first, last, owner))
        for call in facts.calls:
            if call.callee != "cls" or call.scope not in spans:
                continue
            owner = next((o for first, last, o in spans[call.scope] if first <= call.line <= last), None)
            if owner is None:
                continue
            sites += 1
            source, target = f"{module.id}.{call.scope}", f"{module.id}.{owner}"
            if target not in ids or source not in ids:
                abstained[NO_CLASS_SYMBOL] += 1
                continue
            if (source, target) in already:
                abstained[ALREADY_DRAWN] += 1
                continue
            drawn.append({"from": source, "to": target, "path": module.path, "line": call.line})
    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not classmethods:
        return drawn, {}
    return drawn, {
        "classmethods": classmethods,
        "sites": sites,
        "drawn": len(drawn),
        "abstained": {reason: abstained[reason] for reason in REASONS},
    }
