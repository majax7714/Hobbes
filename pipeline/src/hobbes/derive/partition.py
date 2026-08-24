"""Impact set → work units (ADR-051; agent-mapping §3.2).

Minimize cut coupling subject to a per-unit context budget:

- **node weight** — representation cost: the module's file, its
  guarding test files, and its module doc, estimated in tokens
  (bytes/4). What an agent must *hold* to own the module.
- **edge weight** — coupling: tier × edge-type weight × reference
  count × co-change factor. What separating two modules would *cost*.
- **constraint** — a unit's total weight fits the budget, held well
  below the window ceiling because accuracy degrades before capacity.

**Agent count is the partition's output, not a parameter.** A contained
change yields one unit; a cross-cutting one yields several; the
codebase decides. The merge is agglomerative and greedy — strongest
coupling first, deterministic tie-breaks — because the weights are
declared guesses (C-35) and a solver's optimality would be precision
painted onto numbers that have never been validated.

Two explicit failure rules from the design's §7: a unit whose contract
overhead reaches its interior weight merges into its strongest
neighbor (over-decomposition — coordination that costs more than the
code it coordinates), and a single module larger than the budget is
flagged ``oversize`` rather than split — the partition's grain is the
module, a stated D1 limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hobbes.derive.cochange import CoChange
from hobbes.derive.impact import edge_factor, module_adjacency

#: Estimated tokens per unit (ADR-051, C-35). Overridable per plan.
DEFAULT_BUDGET = 60_000

#: Estimated cost of holding one pinned contract (ADR-051, C-35) —
#: the over-decomposition rule's currency.
CONTRACT_OVERHEAD = 300

#: Partitionable node kinds: things that are files someone edits.
#: env/ext/tf nodes are impact facts, not work.
_UNIT_KINDS = {"module", "package"}


@dataclass
class Unit:
    """One work unit: a single-use agent's whole responsibility."""

    name: str
    modules: list[str]
    weight: int
    flags: list[str] = field(default_factory=list)


#: A module the planner did not name is *work* only if it is change-grain.
#: A **hub** (fan-in at or above this many modules) or a **package root**
#: (`__init__` / dotless id) that a seed merely imports is *context*, not a
#: unit an implementer is spawned to edit: putting it in an interior is what
#: made django U4's interior hold `django.contrib.admin` (200+ importers) and
#: dragged the repo onto the unit's boundary, neighborhood, and guards (P12
#: inspection, 2026-08-23). Non-seed hubs/roots are dropped from the
#: partition here; they still appear as neighborhood/contracts, bounded by
#: the render caps. A **seed** (score 1.0 — the planner named it) is always
#: work, hub or not. A declared guess (C-35), overridable.
HUB_FANIN = 30


def module_fanin(graph: dict) -> dict[str, int]:
    """module id -> how many distinct modules import or use it (fan-in)."""
    from hobbes.derive.impact import module_adjacency

    importers: dict[str, set[str]] = {}
    for a, nbrs in module_adjacency(graph).items():
        for b in nbrs:
            importers.setdefault(b, set()).add(a)
    return {m: len(s) for m, s in importers.items()}


def unit_modules(graph: dict, scores: dict[str, float]) -> list[str]:
    """The impact nodes that are partitionable *work*, sorted.

    Change-grain (P12): a seed is always work; a non-seed that is a hub
    (:data:`HUB_FANIN`) or a package root is context, not a spawned unit's
    interior, and is dropped here — it reaches the agent as neighborhood
    and contracts instead."""
    from hobbes.run.agents import _is_package_root

    kinds = {n["id"]: n.get("kind") for n in graph.get("nodes", [])}
    fanin = module_fanin(graph)
    out = []
    for m in scores:
        if kinds.get(m) not in _UNIT_KINDS:
            continue
        is_seed = scores.get(m, 0.0) >= SEED_SCORE
        if not is_seed and (_is_package_root(m) or fanin.get(m, 0) >= HUB_FANIN):
            continue
        out.append(m)
    return sorted(out)


def guarding_tests(graph: dict, tests: dict) -> dict[str, list[str]]:
    """module id -> ids of tests whose reach includes one of its symbols."""
    owners: dict[str, str] = {}
    for symbol in graph.get("symbols", []):
        owners[symbol["id"]] = symbol.get("module", "")
    guards: dict[str, list[str]] = {}
    for test in tests.get("tests", []):
        for reached in test.get("reaches", []):
            module = owners.get(reached)
            if module:
                bucket = guards.setdefault(module, [])
                if test["id"] not in bucket:
                    bucket.append(test["id"])
    return guards


def node_weights(
    repo_root: Path, graph: dict, tests: dict
) -> dict[str, int]:
    """module id -> representation cost in estimated tokens (bytes/4).

    Counts the module's own file, each guarding test's file (once per
    module), and its module doc when narrate has produced one. A file
    the tree no longer holds counts zero — the graph is stamped at a
    SHA and the tree may have moved; the plan reflects what is there.
    """
    paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    test_files = {t["id"]: t.get("file", "") for t in tests.get("tests", [])}
    guards = guarding_tests(graph, tests)

    def size(rel: str | None) -> int:
        if not rel:
            return 0
        target = Path(repo_root) / rel
        return target.stat().st_size if target.is_file() else 0

    weights: dict[str, int] = {}
    for module, path in paths.items():
        if path is None:
            continue
        total = size(path)
        for file in sorted({test_files.get(t, "") for t in guards.get(module, [])}):
            total += size(file)
        doc = Path(repo_root) / ".hobbes/derived/docs/modules" / f"{module}.json"
        if doc.is_file():
            total += doc.stat().st_size
        weights[module] = total // 4
    return weights


def module_coupling(
    graph: dict, modules: list[str], cochange: CoChange
) -> dict[tuple[str, str], float]:
    """Pairwise coupling among *modules*: tier × type × refs × co-change."""
    paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    adjacency = module_adjacency(graph)
    wanted = set(modules)
    coupling: dict[tuple[str, str], float] = {}
    for a in modules:
        for b, edges in adjacency.get(a, {}).items():
            if b not in wanted or b <= a:
                continue
            # adjacency[a][b] holds each crossing edge once; the b <= a
            # guard above means every pair is visited once too.
            strength = sum(
                edge_factor(e) * max(len(e.get("evidence") or []), 1)
                for e in edges
            )
            coupling[(a, b)] = strength * cochange.factor(paths.get(a), paths.get(b))
    return coupling


#: A seed scores 1.0 in the impact set; a unit holding one is never
#: deferred by the cap — it is what the proposal named.
SEED_SCORE = 1.0


def is_deferred(unit: Unit) -> bool:
    """Whether the cap set this unit aside (``deferred`` flag)."""
    return any(f.startswith("deferred") for f in unit.flags)


def build_units(
    modules: list[str],
    weights: dict[str, int],
    coupling: dict[tuple[str, str], float],
    budget: int = DEFAULT_BUDGET,
    max_units: int | None = None,
    scores: dict[str, float] | None = None,
) -> list[Unit]:
    """Agglomerative merge under *budget*; returns named, ordered units.

    *max_units* is the unit cap (ADR-058, restated by the harness
    restructure): when the budgeted partition leaves more units than
    this, the cap **selects** rather than merges — units are ranked by
    the best impact *score* in their interior (*scores*, the impact
    set's), then weight, and the lowest-ranked are **deferred**: kept
    in the result, named ``D1..``, flagged ``deferred`` with their
    score, never spawned. A unit holding a seed (score 1.0) is never
    deferred; when seed-bearing units alone exceed the cap, they merge
    past the budget — strongest coupling first, then lightest — and
    are flagged ``capped`` (C-44). The first live run had merged 300
    modules into one 17M-token unit to meet a cap of 10; a cap is a
    ceiling on sessions, not a reason to fuse the repository.
    ``None`` means no cap.
    """
    members: dict[int, list[str]] = {i: [m] for i, m in enumerate(modules)}
    home = {m: i for i, m in enumerate(modules)}

    def unit_weight(i: int) -> int:
        return sum(weights.get(m, 0) for m in members[i])

    def pair_coupling(i: int, j: int) -> float:
        total = 0.0
        for a in members[i]:
            for b in members[j]:
                key = (a, b) if a < b else (b, a)
                total += coupling.get(key, 0.0)
        return total

    def strongest_mergeable() -> tuple[int, int] | None:
        best: tuple[float, str, int, int] | None = None
        ids = sorted(members)
        for x, i in enumerate(ids):
            for j in ids[x + 1:]:
                strength = pair_coupling(i, j)
                if strength <= 0.0:
                    continue
                if unit_weight(i) + unit_weight(j) > budget:
                    continue
                # Ties break on the smallest member id, so runs repeat.
                first = min(members[i][0], members[j][0])
                if best is None or (-strength, first) < (best[0], best[1]):
                    best = (-strength, first, i, j)
        return (best[2], best[3]) if best else None

    while (pair := strongest_mergeable()) is not None:
        i, j = pair
        absorbed = members.pop(j)
        for m in absorbed:
            home[m] = i
        members[i] = sorted(members[i] + absorbed)

    # Over-decomposition (design §7): a unit whose contract overhead
    # reaches its interior merges into its strongest neighbor if that
    # still fits; otherwise it stays, flagged — never silently.
    def neighbor_contracts(i: int) -> dict[int, float]:
        out: dict[int, float] = {}
        for j in members:
            if j != i and (c := pair_coupling(i, j)) > 0:
                out[j] = c
        return out

    for i in sorted(members):
        if i not in members:
            continue
        neighbors = neighbor_contracts(i)
        overhead = CONTRACT_OVERHEAD * _cut_degree(members[i], coupling)
        if not neighbors or unit_weight(i) > overhead:
            continue
        j = max(sorted(neighbors), key=lambda n: (neighbors[n], -n))
        if unit_weight(i) + unit_weight(j) <= budget:
            for m in members.pop(i):
                home[m] = j
            members[j] = sorted({m for m, h in home.items() if h == j})

    # The unit cap: select first — defer the lowest-impact units until
    # the count fits, never a seed-bearing one — then merge only among
    # seed-bearing units if those alone exceed the cap.
    scores = scores or {}

    def unit_score(i: int) -> float:
        return max((scores.get(m, 0.0) for m in members[i]), default=0.0)

    deferred: dict[int, list[str]] = {}
    capped: set[int] = set()
    if max_units is not None and max_units >= 1:
        ranked = sorted(members, key=lambda i: (-unit_score(i), -unit_weight(i), members[i][0]))
        while len(members) > max_units:
            candidates = [i for i in reversed(ranked) if i in members and unit_score(i) < SEED_SCORE]
            if not candidates:
                break
            deferred[candidates[0]] = members.pop(candidates[0])
        while len(members) > max_units:
            ids = sorted(members)
            best: tuple[float, int, str, int, int] | None = None
            for x, i in enumerate(ids):
                for j in ids[x + 1:]:
                    strength = pair_coupling(i, j)
                    combined = unit_weight(i) + unit_weight(j)
                    first = min(members[i][0], members[j][0])
                    key = (-strength, combined, first, i, j)
                    if best is None or key < best:
                        best = key
            assert best is not None
            _, _, _, i, j = best
            absorbed = members.pop(j)
            for m in absorbed:
                home[m] = i
            members[i] = sorted(members[i] + absorbed)
            capped.discard(j)
            capped.add(i)

    units: list[Unit] = []
    ordered = sorted(members.items(), key=lambda kv: (-sum(
        weights.get(m, 0) for m in kv[1]), kv[1][0]))
    for index, (uid, ms) in enumerate(ordered, start=1):
        weight = sum(weights.get(m, 0) for m in ms)
        flags: list[str] = []
        if uid in capped:
            flags.append(
                f"capped: merged to meet the unit cap (max_units={max_units}); "
                "the merge was for session count, not coupling (C-44)"
            )
        if len(ms) == 1 and weight > budget:
            flags.append(
                "oversize: one module exceeds the budget alone; the "
                "partition's grain is the module (D1 limit)"
            )
        interior = weight
        overhead = CONTRACT_OVERHEAD * _cut_degree(ms, coupling)
        if overhead and interior <= overhead:
            flags.append(
                "coordination-heavy: contract overhead rivals the interior "
                "and no neighbor had room to absorb it"
            )
        units.append(Unit(name=f"U{index}", modules=ms, weight=weight,
                          flags=flags))
    for index, (uid, ms) in enumerate(sorted(
            deferred.items(), key=lambda kv: (-max((scores.get(m, 0.0) for m in kv[1]), default=0.0),
                                              -sum(weights.get(m, 0) for m in kv[1]), kv[1][0])), start=1):
        best = max((scores.get(m, 0.0) for m in ms), default=0.0)
        units.append(Unit(name=f"D{index}", modules=ms,
                          weight=sum(weights.get(m, 0) for m in ms),
                          flags=[f"deferred: set aside by the unit cap (max_units={max_units}); "
                                 f"best impact score {best:.3f}, no seed — not spawned (C-44)"]))
    return units


def _cut_degree(modules: list[str], coupling: dict[tuple[str, str], float]) -> int:
    """How many coupled pairs cross this member set's boundary."""
    inside = set(modules)
    return sum(
        1 for (a, b) in coupling
        if (a in inside) != (b in inside)
    )
