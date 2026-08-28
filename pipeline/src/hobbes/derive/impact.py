"""Proposal → scored impact set (ADR-051; agent-mapping §3.1).

Seeds are resolved **lexically** — explicit ``--seed`` ids or paths,
plus proposal tokens matched exactly against node ids, node path stems,
and symbol names. Nothing is inferred from prose: a term that matches
nothing seeds nothing, and a *code-shaped* term that matches nothing is
reported in the change-spec rather than guessed at (C-36). A generative
planner may one day sit above this and emit seeds; it will never sit
inside it (P5).

Expansion is max-product score propagation over the module-projected
graph: a seed scores 1.0, and a neighbor's score is the best path
product of per-edge factors (tier weight × edge-type weight). Both
directions — a change's impact reaches the callers that depend on it
as much as the callees it depends on. Nodes at or above the pinned
threshold are the impact set. Every number here is a declared guess
(C-35); nothing claims the set is *right*, and the recorder milestone
is what will measure it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

#: Per-hop damping (ADR-051's pinned table, C-35). Without it a chain
#: of semantic calls would propagate at 1.0 forever and the impact set
#: would be the connected component — the dogfood exit check measured
#: exactly that (33 units from one seed). Decay must be real: with
#: 0.55, semantic calls reach two hops above the threshold, syntactic
#: ones reach one.
HOP_DECAY = 0.55

#: Edge-tier factors (C-35). Semantic evidence propagates impact
#: strongly; syntactic evidence is a weaker signal of coupling, not a
#: weaker fact — the tier vocabulary is schema v4's.
TIER_WEIGHT = {"semantic": 1.0, "syntactic": 0.6, "dynamic": 1.0}

#: Edge-type factors (C-35). Unknown types get a real, reduced weight
#: rather than zero — the ADR-023 rule that an unknown is drawn,
#: labelled, never invisible, applied to propagation.
TYPE_WEIGHT = {
    "calls": 1.0,
    "http-call": 0.9,
    "db-read": 0.9,
    "db-write": 0.9,
    "queue": 0.9,
    "imports": 0.8,
    "env-read": 0.8,
    "env-set": 0.8,
    "packages": 0.8,
    "uses": 0.7,
    "references": 0.6,
}
UNKNOWN_TYPE_WEIGHT = 0.5

#: A node enters the impact set at or above this score (C-35).
THRESHOLD = 0.2

#: Proposal tokens skipped for seeding: the prose that would otherwise
#: collide with short symbol names ("add", "the"). Pinned, not learned.
STOPWORDS = frozenset({
    "the", "and", "for", "with", "into", "onto", "from", "that", "this",
    "then", "when", "where", "which", "each", "every", "add", "adds",
    "make", "makes", "build", "builds", "new", "use", "uses", "using",
    "remove", "removes", "change", "changes", "changed", "move", "moves",
    "support", "supports", "should", "must", "can", "will", "one", "two",
    "all", "any", "not", "but", "its", "our", "their", "via", "per",
    "over", "under", "between", "existing", "current",
})

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_./:@-]{2,}")


class SeedError(ValueError):
    """An explicit seed matched nothing, or no seed resolved at all."""


@dataclass
class ImpactSet:
    """The scored result of seed resolution and expansion."""

    #: node id -> score in (0, 1]; seeds are 1.0.
    scores: dict[str, float]
    #: resolved seeds: node id -> the term or --seed value that hit it.
    seeds: dict[str, str]
    #: code-shaped proposal terms that matched nothing (C-36) — reported,
    #: never guessed at.
    unresolved_terms: list[str] = field(default_factory=list)
    #: node id -> why a resolved seed was set aside (:func:`filter_seeds`);
    #: recorded in the spec so the decision is visible, never silent.
    seeds_rejected: dict[str, str] = field(default_factory=dict)
    #: seeds that came from the proposal's text alone — no ``--seed``, no
    #: planner named them. The weakest evidence the mapping has (C-36):
    #: they expand like any seed, but they do not make a hub *work*
    #: (ADR-093; :func:`hobbes.derive.partition.unit_modules`).
    seeds_lexical: list[str] = field(default_factory=list)


def module_of_symbols(graph: dict) -> dict[str, str]:
    """symbol id -> owning module id, from the symbols table."""
    return {
        s["id"]: s.get("module", "")
        for s in graph.get("symbols", [])
        if s.get("id")
    }


def module_adjacency(graph: dict) -> dict[str, dict[str, list[dict]]]:
    """The module-projected graph: id -> neighbor id -> crossing edges.

    Module edges connect modules directly; symbol edges connect the
    calling module to the target symbol's module. Self-edges are
    dropped (a module's internal calls are interior, not coupling).
    Undirected: each crossing edge appears under both endpoints.
    """
    owners = module_of_symbols(graph)
    adjacency: dict[str, dict[str, list[dict]]] = {}

    def connect(a: str, b: str, edge: dict) -> None:
        if not a or not b or a == b:
            return
        adjacency.setdefault(a, {}).setdefault(b, []).append(edge)
        adjacency.setdefault(b, {}).setdefault(a, []).append(edge)

    for edge in graph.get("module_edges", []):
        connect(edge.get("from", ""), edge.get("to", ""), edge)
    for edge in graph.get("symbol_edges", []):
        connect(edge.get("from", ""), owners.get(edge.get("to", ""), ""), edge)
    return adjacency


def edge_factor(edge: dict) -> float:
    """One edge's coupling factor: tier weight × type weight.

    This is the *coupling* strength the partition uses. Propagation
    additionally applies :data:`HOP_DECAY` per hop (see :func:`expand`)
    so distance always attenuates, even along the strongest edges.
    """
    tier = TIER_WEIGHT.get(edge.get("tier", ""), TIER_WEIGHT["syntactic"])
    kind = TYPE_WEIGHT.get(edge.get("type", ""), UNKNOWN_TYPE_WEIGHT)
    return tier * kind


def _code_shaped(term: str) -> bool:
    """Whether a term looks like a code reference rather than prose.

    Separators or internal capitals mark intent to name something; the
    C-36 report lists only these, so prose never floods it.
    """
    if any(sep in term for sep in "./:_-"):
        return True
    return term != term.lower() and term != term.title()


def build_lookup(graph: dict, dotted_head: bool = False):
    """A ``term -> module id or None`` resolver over *graph*: exact node
    id, symbol id, symbol name, file path, or unambiguous path suffix /
    stem (names case-insensitive), plus a unique symbol-id suffix for a
    dotted name. Shared by seed resolution and the tolerant
    planner-handoff resolver (harness restructure). *dotted_head* lets a
    dotted name fall back to its leading segment (the class a planner
    named) — the planner's resolver only; the lexical seeds never guess
    a prose term by its head (C-36)."""
    by_id = {n["id"]: n for n in graph.get("nodes", [])}
    by_path: dict[str, str] = {}
    by_stem: dict[str, list[str]] = {}
    for node in graph.get("nodes", []):
        path = node.get("path")
        if path:
            by_path[path] = node["id"]
            by_stem.setdefault(PurePosixPath(path).stem.lower(), []).append(node["id"])
    by_symbol_name: dict[str, list[str]] = {}
    symbol_module: dict[str, str] = {}
    for symbol in graph.get("symbols", []):
        module = symbol.get("module", "")
        if not module:
            continue
        symbol_module[symbol["id"]] = module
        by_symbol_name.setdefault(symbol.get("name", "").lower(), []).append(module)

    def lookup(term: str) -> str | None:
        if term in by_id:
            return term
        if term in symbol_module:
            return symbol_module[term]
        if term in by_path:
            return by_path[term]
        suffix = [x for x in by_path if x.endswith("/" + term) or x == term]
        if len(suffix) == 1:
            return by_path[suffix[0]]
        lowered = term.lower()
        for index in (by_stem, by_symbol_name):
            hits = sorted(set(index.get(lowered, [])))
            if len(hits) == 1:
                return hits[0]
        # A dotted name ("SlicedLowLevelWCS.world_to_pixel", "pkg.mod.Cls"):
        # a unique symbol-id suffix first, then the leading segment (the
        # class, usually unique) — the first live planner named the gold
        # module exactly this way and the flat lookup missed it.
        if "." in term and "/" not in term:
            suffix_hits = sorted({m for sid, m in symbol_module.items() if sid.endswith("." + term)})
            if len(suffix_hits) == 1:
                return suffix_hits[0]
            head = term.split(".", 1)[0]
            if dotted_head and head and head != term:
                return lookup(head)
        return None

    return lookup


def resolve_terms(graph: dict, terms: list[str]) -> tuple[list[str], list[str]]:
    """Tolerantly resolve *terms* (a planner's named files/symbols) to
    module ids: returns (hits in order, unique; misses). A miss is
    reported, not raised (ADR-059) — the planner names things loosely
    and the caller records what did not resolve rather than failing."""
    lookup = build_lookup(graph, dotted_head=True)
    hits: list[str] = []
    misses: list[str] = []
    for term in terms:
        cleaned = term.strip() if term else ""
        node = lookup(cleaned) if cleaned else None
        if node is None:
            if cleaned:
                misses.append(cleaned)
        elif node not in hits:
            hits.append(node)
    return hits, misses


def resolve_seeds(
    graph: dict, proposal: str, explicit: list[str], lexical: bool = True
) -> tuple[dict[str, str], list[str]]:
    """Resolve seeds from *explicit* values and the proposal's terms.

    With *lexical* off the proposal's terms are not read at all — the
    staged run's planner seeds (ADR-059) *replace* the lexical layer
    rather than join it; the first live probe showed the join re-admits
    the prose seeds C-36 warns about (`input`, `frame`, `isinstance`…)
    and the plan was the capped repository again.

    Explicit values must match a node id, a symbol id or name, or a
    file path (exact, or unambiguous path suffix) — one that matches
    nothing raises :class:`SeedError`, because the human named it on
    purpose. Proposal terms are matched exactly (case-insensitive) and
    silently skipped when they miss, except code-shaped terms, which
    are returned as unresolved (C-36).
    """
    lookup = build_lookup(graph)
    seeds: dict[str, str] = {}
    for value in explicit:
        node = lookup(value)
        if node is None:
            raise SeedError(
                f"--seed {value!r} matches no node, symbol, or file in the graph"
            )
        seeds.setdefault(node, value)

    unresolved: list[str] = []
    for term in (_TOKEN.findall(proposal) if lexical else []):
        if term.lower() in STOPWORDS:
            continue
        node = lookup(term)
        if node is not None:
            seeds.setdefault(node, term)
        elif _code_shaped(term) and term not in unresolved:
            unresolved.append(term)
    return seeds, unresolved


def expand(graph: dict, seeds: dict[str, str]) -> dict[str, float]:
    """Max-product score propagation from the seeds (§3.1).

    Dijkstra over -log(score) in spirit; written as best-first over the
    product directly because every factor is in (0, 1]. Deterministic:
    ties break on node id.
    """
    adjacency = module_adjacency(graph)
    scores = {node: 1.0 for node in seeds}
    frontier = sorted(scores)
    while frontier:
        # Highest score first; id breaks ties so runs are reproducible.
        frontier.sort(key=lambda n: (-scores[n], n))
        node = frontier.pop(0)
        base = scores[node]
        for neighbor, edges in sorted(adjacency.get(node, {}).items()):
            best = base * HOP_DECAY * max(edge_factor(e) for e in edges)
            if best < THRESHOLD:
                continue
            if best > scores.get(neighbor, 0.0):
                scores[neighbor] = best
                if neighbor not in frontier:
                    frontier.append(neighbor)
    return scores


def _in_code_context(term: str, proposal: str) -> bool:
    """Whether the proposal names *term* as code somewhere: inside
    backticks, or called (``term(``). A prose word that is also a
    symbol name seeds only on this evidence once better seeds exist."""
    if re.search(r"`[^`\n]*\b" + re.escape(term) + r"\b[^`\n]*`", proposal):
        return True
    return re.search(r"\b" + re.escape(term) + r"\(", proposal) is not None


def filter_seeds(
    graph: dict, proposal: str, seeds: dict[str, str], explicit: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Seed hygiene (harness restructure, phase 0): returns (kept,
    rejected-with-reason). Two deterministic rules, both conditional on
    better evidence existing, so the filter can never empty the set:

    1. a **package** node is set aside when any module-level seed
       remains — the root package is the whole repo, never the change;
    2. a **prose-shaped** hit (a lowercase single word that equals a
       symbol or file stem — ``input``, ``open``, ``check``) is set
       aside when the proposal also seeded through a *code-shaped* term
       (``AltAz``, ``astropy.coordinates.baseframe``), unless the
       proposal names it as code (backticks, or a call).

    Explicit ``--seed`` values are never rejected: the human named them.
    The first live astropy run seeded the root package plus fourteen
    prose words and the impact set became the repository (C-36).
    """
    kinds = {n["id"]: n.get("kind") for n in graph.get("nodes", [])}
    explicit_set = set(explicit)
    kept, rejected = dict(seeds), {}
    # Rule 2 first: the more specific reason wins when both apply.
    if any(kinds.get(n) != "package" for n in kept):
        for node, term in list(kept.items()):
            if term in explicit_set or kinds.get(node) != "package":
                continue
            rejected[node] = (f"package node seeded by {term!r} while module seeds exist: "
                              "a package is the whole tree, not the change")
            del kept[node]
    code_evidence = any(
        term in explicit_set or _code_shaped(term) for term in kept.values()
    )
    if code_evidence:
        for node, term in list(kept.items()):
            if term in explicit_set or _code_shaped(term) or _in_code_context(term, proposal):
                continue
            rejected[node] = (f"prose-shaped term {term!r} while code-shaped seeds exist "
                              "(C-36); name it as code or with --seed if it matters")
            del kept[node]
    return kept, rejected


def build_impact(graph: dict, proposal: str, explicit: list[str], lexical: bool = True) -> ImpactSet:
    """Seeds plus expansion; raises :class:`SeedError` when nothing seeds.

    An empty impact set is not a plan — it is the mapping saying the
    proposal names nothing it can find, and the fix (name a node with
    --seed) belongs in the error, not in a silently empty change-spec.
    """
    seeds, unresolved = resolve_seeds(graph, proposal, explicit, lexical=lexical)
    if not seeds:
        hint = ""
        if unresolved:
            hint = f" (unmatched code-shaped terms: {', '.join(unresolved)})"
        raise SeedError(
            "no proposal term matches any node, symbol, or file in the "
            f"graph{hint} — name a starting point with --seed"
        )
    seeds, rejected = filter_seeds(graph, proposal, seeds, explicit)
    explicit_set = set(explicit)
    lexical_nodes = sorted(n for n, term in seeds.items() if term not in explicit_set)
    return ImpactSet(scores=expand(graph, seeds), seeds=seeds,
                     unresolved_terms=unresolved, seeds_rejected=rejected,
                     seeds_lexical=lexical_nodes)
