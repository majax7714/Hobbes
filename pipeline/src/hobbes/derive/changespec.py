"""The change-spec: assembly, the plan-review gate, serialization
(ADR-051; agent-mapping §2).

The change-spec is the plan phase's artifact and the unit of review:
impact, partition, contracts, per-agent context and policy manifests,
each with its stated complement, plus the gate's verdicts. It is what
a human approves at concept level — not a transcript, not a prompt.

**The gate checks code that does not exist yet.** Proposed edges
(``--adds "a -> b"``) are judged against the confirmed
forbidden-import invariants before implementation: a plan that adds
``billing -> auth.token`` fails here, at planning cost instead of PR
cost. The gate can only check what is declared and what the graph can
answer — it says so in its output rather than passing silently on the
rest (never a false pass).

Change-specs live in ``.hobbes/plans/<task-id>/change-spec.yaml`` —
beside ``policies/`` and ``invariants/``, not under ``derived/``,
because an approved plan is not regenerable from a SHA (ADR-051). The
task id is a content hash of the proposal text, the ADR-026 keying
discipline: rerunning the same proposal against the same graph writes
byte-identical output. Serialization refuses a context manifest
without its complement (ADR-047) — the contract is enforced here, not
remembered in review.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from hobbes import artifacts
from hobbes.derive import cochange, contracts as contracts_mod, impact, manifests, partition
from hobbes.derive.manifests import ComplementError
from hobbes.invariants.schema import Invariant, load_all, scope_matches
from hobbes.invariants.verdict import _any_match

#: The C-35 statement every plan run surfaces: the register's rule that
#: an unvalidated number says so where it is met.
VALIDATION = (
    "partition quality is unvalidated (C-35): every weight and threshold "
    "in this plan is a declared guess; nothing has measured rework, "
    "contract failures, or context faults against it yet"
)

#: Where change-specs live, relative to the repo root.
PLANS_DIR = ".hobbes/plans"


class DeriveError(RuntimeError):
    """A plan input that cannot be used (malformed --adds, no seeds)."""


@dataclass
class ProposedEdge:
    """One declared future edge and the gate's judgement of it."""

    edge: str
    verdict: str  # pass | fail
    invariant: str = ""
    reason: str = ""


@dataclass
class Gate:
    """The plan-review gate's output."""

    proposed_edges: list[ProposedEdge]
    human_first_units: list[str]
    result: str  # pass | fail
    #: What this gate can and cannot check, stated (never a false pass).
    checked: str = (
        "declared proposed edges against confirmed forbidden-import "
        "invariants; undeclared behavior and non-graph rule kinds are "
        "not checkable at plan time and are not passed silently"
    )


@dataclass
class ChangeSpec:
    """The whole plan, one artifact."""

    task: str
    proposal: str
    graph_sha: str
    graph_dirty: bool
    budget: int
    seeds: dict[str, str]
    unresolved_terms: list[str]
    units: list[partition.Unit]
    contracts: list[contracts_mod.Contract]
    contexts: list[manifests.ContextManifest]
    policies: list[manifests.PolicyManifest]
    gate: Gate
    warnings: list[str] = field(default_factory=list)
    validation: str = VALIDATION
    #: The unit cap the partition ran under (ADR-058), None when uncapped.
    max_units: int | None = None
    #: Resolved seeds set aside by :func:`impact.filter_seeds`, with the
    #: reason each — visible, so a rejected seed can be named back in.
    seeds_rejected: dict[str, str] = field(default_factory=dict)
    #: Lexical seeds the change-grain rule kept out of the partitionable
    #: set (a hub the proposal's text alone hit — ADR-093, D6):
    #: still seeds for expansion, context for every unit, never an interior.
    seeds_context: dict[str, str] = field(default_factory=dict)
    #: Units the cap set aside (``deferred``): in the impact set, no seed,
    #: lowest-ranked — recorded so the selection is visible, never spawned.
    units_deferred: list[partition.Unit] = field(default_factory=list)


def task_id(proposal: str) -> str:
    """Content-hash keying (ADR-026's discipline): the id follows the
    text, so an approval can never bless different words."""
    return hashlib.sha256(proposal.encode()).hexdigest()[:12]


def _parse_adds(adds: list[str]) -> list[tuple[str, str]]:
    edges = []
    for raw in adds:
        head, sep, tail = raw.partition("->")
        if not sep or not head.strip() or not tail.strip():
            raise DeriveError(
                f"--adds {raw!r}: expected a declared edge as 'from -> to'"
            )
        edges.append((head.strip(), tail.strip()))
    return edges


def run_gate(
    graph: dict,
    invariants: list[Invariant],
    adds: list[tuple[str, str]],
    contexts: list[manifests.ContextManifest],
) -> Gate:
    """Judge declared edges against confirmed forbidden-import rules.

    An importer the graph does not know is a module the plan will
    create; it has no path, so a scope cannot exclude it — the same
    no-path rule the checker applies (verdict.py), because a rule
    dodged by being new is not a rule.
    """
    paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    rules = [
        inv for inv in invariants
        if inv.confirmed and inv.kind == "forbidden-import"
    ]

    judged: list[ProposedEdge] = []
    for source, target in adds:
        verdict = ProposedEdge(edge=f"{source} -> {target}", verdict="pass")
        for inv in rules:
            rule = inv.rule
            if target not in set(rule.get("imported") or []):
                continue
            if source in set(rule.get("except") or []):
                continue
            if not _any_match(rule.get("importers") or [], source):
                continue
            source_path = paths.get(source)
            if source_path is not None and not scope_matches(inv.scope, source_path):
                continue
            verdict = ProposedEdge(
                edge=f"{source} -> {target}",
                verdict="fail",
                invariant=inv.id,
                reason=f"{inv.id}: {inv.statement}",
            )
            break
        judged.append(verdict)

    human_first = [c.unit for c in contexts if c.human_first]
    result = "fail" if any(e.verdict == "fail" for e in judged) else "pass"
    return Gate(proposed_edges=judged, human_first_units=human_first,
                result=result)


def derive_plan(
    repo_root: Path,
    proposal: str,
    seeds: list[str] | None = None,
    adds: list[str] | None = None,
    budget: int = partition.DEFAULT_BUDGET,
    max_units: int | None = None,
    lexical: bool = True,
) -> ChangeSpec:
    """The whole derivation: proposal to change-spec. Deterministic.
    *lexical* off seeds from *seeds* alone (the staged run's planner
    path, ADR-059)."""
    repo_root = Path(repo_root)
    graph = artifacts.load_graph(repo_root, accepts=artifacts.V4_ONLY)
    tests = artifacts.load_tests(repo_root)
    known = {t["id"] for t in tests.get("tests", [])}
    invariants = load_all(repo_root, known_tests=known)
    declared = _parse_adds(adds or [])

    impact_set = impact.build_impact(graph, proposal, list(seeds or []), lexical=lexical)
    seeds_context = partition.context_seeds(graph, impact_set.scores, impact_set.seeds_lexical)
    modules = partition.unit_modules(graph, impact_set.scores, impact_set.seeds_lexical)
    if seeds_context and not (set(impact_set.seeds) - set(seeds_context)):
        # Every seed was a lexical hit on a hub (ADR-093): what is left is
        # the hub's neighborhood, units with no seed in them — a plan
        # built from context. Refuse with the fix named, as an empty seed
        # set is refused (never a silently empty or a seedless spec).
        named = ", ".join(f"{n} ({impact_set.seeds[n]!r})" for n in sorted(seeds_context))
        raise impact.SeedError(
            "every seed is a lexical hit on a hub — context, not work "
            f"({named}); name the change with --seed")
    history = cochange.observe(repo_root)
    warnings = [history.warning] if history.warning else []

    weights = partition.node_weights(repo_root, graph, tests)
    coupling = partition.module_coupling(graph, modules, history)
    all_units = partition.build_units(modules, weights, coupling, budget, max_units=max_units,
                                      scores=impact_set.scores)
    units = [u for u in all_units if not partition.is_deferred(u)]
    deferred = [u for u in all_units if partition.is_deferred(u)]

    guards = partition.guarding_tests(graph, tests)
    pinned = contracts_mod.build_contracts(graph, units, invariants)
    contexts = manifests.build_context_manifests(
        repo_root, graph, units, pinned, guards, invariants, warnings
    )
    policies = manifests.build_policy_manifests(graph, contexts, tests)
    gate = run_gate(graph, invariants, declared, contexts)

    return ChangeSpec(
        task=task_id(proposal),
        proposal=proposal,
        graph_sha=graph.get("sha", ""),
        graph_dirty=bool(graph.get("dirty")),
        budget=budget,
        seeds=dict(sorted(impact_set.seeds.items())),
        unresolved_terms=impact_set.unresolved_terms,
        units=units,
        contracts=pinned,
        contexts=contexts,
        policies=policies,
        gate=gate,
        warnings=warnings,
        max_units=max_units,
        seeds_rejected=dict(sorted(impact_set.seeds_rejected.items())),
        seeds_context=dict(sorted(seeds_context.items())),
        units_deferred=deferred,
    )


def spec_to_dict(spec: ChangeSpec) -> dict:
    """The serializable form. Refuses a manifest without its complement
    (ADR-047) — the enforcement point, not a convention."""
    for context in spec.contexts:
        if context.complement is None:
            raise ComplementError(
                f"unit {context.unit}: context manifest has no stated "
                "complement — a derivation that hands an agent only the "
                "captured half is not done (ADR-047)"
            )
    document = asdict(spec)
    if spec.unresolved_terms:
        document["unresolved_terms_note"] = (
            "code-shaped proposal terms that matched no node, symbol, or "
            "file — not guessed at (C-36); seed them explicitly if they matter"
        )
    return document


def write_spec(repo_root: Path, spec: ChangeSpec) -> Path:
    """Write ``.hobbes/plans/<task>/change-spec.yaml``; returns the path."""
    directory = Path(repo_root) / PLANS_DIR / spec.task
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "change-spec.yaml"
    path.write_text(yaml.safe_dump(spec_to_dict(spec), sort_keys=False,
                                   width=88, allow_unicode=True))
    return path


def format_spec(spec: ChangeSpec) -> str:
    """The CLI summary a human reads before opening the YAML."""
    lines: list[str] = []
    dirty = " (dirty)" if spec.graph_dirty else ""
    lines.append(f"plan {spec.task} @ {spec.graph_sha[:12]}{dirty}")
    lines.append(f"  proposal: {spec.proposal}")
    seeded = ", ".join(f"{node} (← {term})" for node, term in spec.seeds.items())
    lines.append(f"  seeds: {seeded}")
    if spec.seeds_rejected:
        for node, reason in spec.seeds_rejected.items():
            lines.append(f"  seed set aside: {node} — {reason}")
    if spec.seeds_context:
        for node, reason in spec.seeds_context.items():
            lines.append(f"  seed is context, not work: {node} — {reason}")
    if spec.unresolved_terms:
        lines.append(
            "  unmatched code-shaped terms (C-36, not guessed at): "
            + ", ".join(spec.unresolved_terms)
        )
    for warning in spec.warnings:
        lines.append(f"  warning: {warning}")

    capped = sum(1 for u in spec.units if any(f.startswith("capped") for f in u.flags))
    lines.append(
        f"\n{len(spec.units)} unit(s) under a {spec.budget:,}-token budget "
        + (f"and a {spec.max_units}-unit cap ({capped} capped, "
           f"{len(spec.units_deferred)} deferred, C-44) " if spec.max_units else "")
        + "— the partition's output, not a parameter:"
    )
    contexts = {c.unit: c for c in spec.contexts}
    for unit in spec.units:
        lines.append(
            f"  {unit.name}: {len(unit.modules)} module(s), "
            f"~{unit.weight:,} tokens — {', '.join(unit.modules[:6])}"
            + (" …" if len(unit.modules) > 6 else "")
        )
        for flag in unit.flags:
            lines.append(f"      flag: {flag}")
        context = contexts.get(unit.name)
        if context and context.complement:
            c = context.complement
            if c.sites:
                accounted = (c.sites - c.unresolved) / c.sites * 100
                lines.append(
                    f"      complement: {accounted:.1f}% of {c.sites} detected "
                    f"sites accounted; cannot resolve {c.cannot_resolve} "
                    "(the stated half rides the manifest — ADR-047)"
                )
            else:
                lines.append(
                    "      complement: no detected call sites in these files; "
                    "the denominator statement still applies (C-1/C-4/C-5)"
                )
        if context and context.human_first:
            lines.append(f"      HUMAN-FIRST: {context.human_first_reason}")

    if spec.contracts:
        lines.append(f"\n{len(spec.contracts)} pinned contract(s) — the only "
                     "interface between agents:")
        for contract in spec.contracts[:15]:
            lines.append(
                f"  {contract.id}: {contract.from_unit} → {contract.to_unit}  "
                f"{contract.caller} → {contract.target} "
                f"[{contract.edge_type}/{contract.tier}] "
                f"owner {contract.owner}, declared {contract.declared_at}"
            )
        if len(spec.contracts) > 15:
            lines.append(f"  … and {len(spec.contracts) - 15} more in the spec")
    else:
        lines.append("\nno cut edges: one agent, zero coordination")

    lines.append("\nplan-review gate:")
    lines.append(f"  checks: {spec.gate.checked}")
    for edge in spec.gate.proposed_edges:
        mark = "FAIL" if edge.verdict == "fail" else "pass"
        detail = f" — {edge.reason}" if edge.reason else ""
        lines.append(f"  {mark}: {edge.edge}{detail}")
    if spec.gate.human_first_units:
        lines.append(
            "  human-first unit(s): " + ", ".join(spec.gate.human_first_units)
        )
    lines.append(f"  result: {spec.gate.result}")
    lines.append(f"\n{VALIDATION}")
    return "\n".join(lines) + "\n"
