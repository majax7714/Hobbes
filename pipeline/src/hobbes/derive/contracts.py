"""Cut edges → pinned contracts (ADR-051; agent-mapping §3.3).

The edges the partition severs are the interfaces between agents, and
each one is pinned *before implementation*: what is called, where it is
declared, which invariants constrain it, and which side owns a
migration (the definition side — the callee's unit — because the
declaration is theirs to move).

**A pin is a declaration site, not a type signature** (C-37): the graph
carries a symbol's kind, file, and line range, and does not carry
parameter or return types. Every contract entry says so in its ``pin``
field, so the concession is met where the contract is read, not in a
document about it.

Contracts are the *only* interface between agents — no shared chat, no
peeking at the far side's internals. The far side of every contract is
therefore exactly what a unit's boundary context contains (§4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hobbes.derive.impact import module_of_symbols
from hobbes.derive.partition import Unit
from hobbes.invariants.schema import Invariant, scope_matches

#: The C-37 statement every contract carries.
PIN_KIND = "declaration-site, not a type signature (C-37)"


@dataclass
class Contract:
    """One pinned cross-unit interface."""

    id: str
    from_unit: str
    to_unit: str
    #: The calling module and the target (symbol id, or module id when
    #: the crossing edge is module-level).
    caller: str
    target: str
    edge_type: str
    tier: str
    #: kind + declaration site of the target, as far as the graph knows.
    target_kind: str
    declared_at: str
    #: The migration owner: the unit holding the declaration.
    owner: str
    #: Confirmed invariants whose scope covers either side.
    invariants: list[str] = field(default_factory=list)
    pin: str = PIN_KIND


def build_contracts(
    graph: dict, units: list[Unit], invariants: list[Invariant]
) -> list[Contract]:
    """Pin every edge that crosses a unit boundary.

    One contract per (caller module, target, edge type): several call
    sites into the same symbol are one interface, not several.
    """
    home: dict[str, str] = {}
    for unit in units:
        for module in unit.modules:
            home[module] = unit.name

    owners = module_of_symbols(graph)
    paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    symbols = {s["id"]: s for s in graph.get("symbols", [])}

    crossing: dict[tuple[str, str, str], dict] = {}

    def note(caller: str, target: str, target_module: str, edge: dict) -> None:
        from_unit = home.get(caller)
        to_unit = home.get(target_module)
        if not from_unit or not to_unit or from_unit == to_unit:
            return
        crossing.setdefault(
            (caller, target, edge.get("type", "")),
            {"edge": edge, "target_module": target_module},
        )

    for edge in graph.get("module_edges", []):
        note(edge.get("from", ""), edge.get("to", ""), edge.get("to", ""), edge)
    for edge in graph.get("symbol_edges", []):
        target = edge.get("to", "")
        note(edge.get("from", ""), target, owners.get(target, ""), edge)

    confirmed = [i for i in invariants if i.confirmed]

    contracts: list[Contract] = []
    for index, key in enumerate(sorted(crossing), start=1):
        caller, target, edge_type = key
        edge = crossing[key]["edge"]
        target_module = crossing[key]["target_module"]
        symbol = symbols.get(target)
        if symbol is not None:
            kind = symbol.get("kind", "")
            declared = (
                f"{paths.get(target_module, '')}:"
                f"{symbol.get('line', 0)}-{symbol.get('end_line', 0)}"
            )
        else:
            kind = "module"
            declared = paths.get(target, "") or target
        in_scope = sorted(
            inv.id for inv in confirmed
            if scope_matches(inv.scope, paths.get(caller))
            or scope_matches(inv.scope, paths.get(target_module))
        )
        contracts.append(Contract(
            id=f"K{index}",
            from_unit=home[caller],
            to_unit=home[target_module],
            caller=caller,
            target=target,
            edge_type=edge_type,
            tier=edge.get("tier", ""),
            target_kind=kind,
            declared_at=declared,
            owner=home[target_module],
            invariants=in_scope,
        ))
    return contracts
