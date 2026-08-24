"""Per-unit context and policy manifests (ADR-051; agent-mapping §4–§5).

**Context: resolution decays with distance.** Interior at full
resolution (code, guarding tests, module docs, in-scope invariants);
boundary as pinned contracts with the far side's declaration only;
neighborhood one hop out as signatures; nothing beyond. Detail falls
with graph distance, so information hiding is a computed property
rather than a discipline.

**The stated complement is mandatory** (ADR-047). Every context
manifest carries what Hobbes cannot see in the unit's scope — the
capture rollup over its files, each present tail class with the
register entry it points to, environment gaps, degradations, and the
standing denominator statement — so the agent knows which context it
must gather and verify itself. A manifest without its complement is
refused at serialization (:class:`ComplementError`), because a
derivation that hands an agent only the known half has recreated the
confident-surface-over-quiet-gap failure at the layer built to
prevent it.

**Policy: evidence widens, gaps narrow.** The floor is read-only and
escalate-by-default; write mounts widen only over the unit's interior;
and the specific guarantees P10 names are emitted first and are
impossible for this generator to widen past — it names them and raises
(:class:`GuaranteeError`) rather than absorbing them (ADR-036's
lesson). A blind-spot-heavy unit is flagged **human-first**: no write
mounts and a faster path to a human, never a wider sandbox and a
warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hobbes.derive.contracts import Contract
from hobbes.derive.partition import Unit
from hobbes.extract.tail import FALLBACK, NOT_MODELLED
from hobbes.invariants.schema import Invariant, scope_matches

#: The always-on denominator statement (ADR-045/047): what is in no
#: count below, because it is not detected at all.
DENOMINATOR = (
    "never in any count here, because it is not detected at all: dynamic "
    "dispatch and calls through values (C-1), fixture-injected test reach "
    "(C-4), computed route paths (C-5); every figure is over DETECTED "
    "call sites, not over the repo"
)

#: What each tail class means, with the register entry it points to.
#: Mirrors go/internal/knowledge's tailMeanings — the class vocabulary
#: is shared (ADR-045), and each meaning is an observation, never a
#: probability about a hypothetical edge.
TAIL_MEANINGS = {
    "fallback-resolved": "syntactic-tier edge from lane A's fallback; semantics could not confirm it (C-7) — trust it less",
    "local-binding": "bound below the modelled vocabulary in its own file (C-9) — seen and deliberately not modelled",
    "nested-decl": "declared in another repo file below the modelled vocabulary (C-9)",
    "external-origin": "every declaration lives outside the repo — often an environment gap (C-23/C-27/C-30)",
    "import-binding": "bound by a same-file import; the landing site is unresolved — usually a missing environment (C-23/C-27/C-30)",
    "builtin-name": "matches the language's pinned builtin list — language machinery, not architecture",
    "attr-call": "receiver no static provider could type — the genuine limit (C-2); verify these targets yourself where they matter",
    "path-call": "a ::-qualified call the index left dark",
    "unclassified": "no observation applies — genuinely unknown; read this code yourself",
}

#: Human-first thresholds (ADR-051, C-35): the unit's files must show a
#: real sample before the flag fires, and past it the honest default is
#: a narrower sandbox and a human, not a warning.
HUMAN_FIRST_MIN_SITES = 10
HUMAN_FIRST_FRACTION = 0.5

#: The specific guarantees (P10) every derived policy states first and
#: this generator refuses to widen past, by name.
GUARANTEES = (
    "deny read *.tfstate (I-1)",
    "deny git push (repo policy; sessions commit, the human publishes)",
    "deny writes under .hobbes/derived/ (P1: derived is regenerable, never authored)",
)

#: Path shapes the guarantees cover; a widening that touches one raises.
_FORBIDDEN_MOUNT_MARKS = (".tfstate", ".hobbes/derived")


class ComplementError(RuntimeError):
    """A context manifest without its stated complement (ADR-047)."""


class GuaranteeError(RuntimeError):
    """A derived widening would cross a specific guarantee (P10)."""


@dataclass
class Complement:
    """What Hobbes cannot see in a unit's scope — the mandatory half."""

    denominator: str
    #: Detected call sites in the unit's files, and the unresolved count.
    sites: int
    unresolved: int
    #: tail class -> count, over the unit's files.
    tail: dict[str, int]
    #: class -> meaning line (only classes present).
    meanings: dict[str, str]
    #: dependency gaps: "resolved/declared missing: a, b" lines.
    environment_gaps: list[str] = field(default_factory=list)
    #: extraction degradations touching the unit's paths.
    degradations: list[str] = field(default_factory=list)
    #: non-empty when co-change history was unavailable for this plan.
    warnings: list[str] = field(default_factory=list)

    @property
    def cannot_resolve(self) -> int:
        """The concentrated remainder: not by-design, not fallback."""
        return sum(
            n for cls, n in self.tail.items()
            if cls not in NOT_MODELLED and cls != FALLBACK
        )


@dataclass
class ContextManifest:
    """One agent's whole context, computed rather than assembled."""

    unit: str
    #: Interior, full resolution: [{id, path}].
    modules: list[dict]
    guarding_tests: list[str]
    #: Module-doc artifact paths that exist (narrate output).
    docs: list[str]
    #: Confirmed invariant ids whose scope covers the interior.
    invariants: list[str]
    #: Contract ids where this unit is a party — the boundary.
    boundary: list[str]
    #: One hop out, signatures only: [{id, symbols: [names]}].
    neighborhood: list[dict]
    complement: Complement | None
    human_first: bool = False
    human_first_reason: str = ""


@dataclass
class PolicyManifest:
    """One agent's derived policy: floor, guarantees, evidence-widened."""

    unit: str
    guarantees: list[str]
    floor: str
    write_mounts: list[str]
    #: Read-visible one-hop paths (signature-level context).
    read_signatures: list[str]
    flags: list[str] = field(default_factory=list)


def build_complement(
    graph: dict, interior_paths: list[str], warnings: list[str]
) -> Complement:
    """The unit-scoped blind-spot statement, from the ingest artifacts."""
    wanted = set(interior_paths)
    sites = unresolved = 0
    tail: dict[str, int] = {}
    for row in graph.get("resolution_coverage", []) or []:
        if row.get("file") not in wanted:
            continue
        sites += row.get("sites", 0)
        unresolved += row.get("unresolved", 0)
        for cls, n in (row.get("tail") or {}).items():
            tail[cls] = tail.get(cls, 0) + n

    gaps = []
    for dc in graph.get("dependency_coverage", []) or []:
        missing = dc.get("missing") or []
        if missing:
            gaps.append(
                f"{dc.get('resolved', 0)}/{dc.get('declared', 0)} declared "
                f"packages resolved; missing: {', '.join(missing)} — calls "
                "into these are invisible, not absent (C-23/C-27/C-30)"
            )

    dirs = {str(Path(p).parent) for p in wanted}
    degradations = []
    for error in graph.get("extraction_errors", []) or []:
        where = error.get("path", "")
        if where in (".", "") or any(
            where == d or d.startswith(where.rstrip("/") + "/") or
            where.startswith(d + "/") for d in dirs
        ):
            degradations.append(
                f"{where}: {error.get('stage', '')}: {error.get('message', '')}"
            )

    return Complement(
        denominator=DENOMINATOR,
        sites=sites,
        unresolved=unresolved,
        tail=dict(sorted(tail.items())),
        meanings={cls: TAIL_MEANINGS[cls] for cls in sorted(tail)
                  if cls in TAIL_MEANINGS},
        environment_gaps=gaps,
        degradations=degradations[:10],
        warnings=list(warnings),
    )


def build_context_manifests(
    repo_root: Path,
    graph: dict,
    units: list[Unit],
    contracts: list[Contract],
    guards: dict[str, list[str]],
    invariants: list[Invariant],
    warnings: list[str],
) -> list[ContextManifest]:
    """One context manifest per unit, complement always attached."""
    paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    symbol_names: dict[str, list[str]] = {}
    for symbol in graph.get("symbols", []):
        symbol_names.setdefault(symbol.get("module", ""), []).append(
            symbol.get("name", "")
        )
    from hobbes.derive.impact import module_adjacency

    adjacency = module_adjacency(graph)
    confirmed = [i for i in invariants if i.confirmed]

    manifests: list[ContextManifest] = []
    for unit in units:
        interior = set(unit.modules)
        interior_paths = sorted(p for m in interior if (p := paths.get(m)))

        docs = []
        for module in unit.modules:
            doc = Path(repo_root) / ".hobbes/derived/docs/modules" / f"{module}.json"
            if doc.is_file():
                docs.append(str(doc.relative_to(repo_root)))

        in_scope = sorted({
            inv.id for inv in confirmed
            for p in interior_paths if scope_matches(inv.scope, p)
        })

        boundary = [c.id for c in contracts
                    if unit.name in (c.from_unit, c.to_unit)]

        hop = sorted({
            n for m in interior for n in adjacency.get(m, {})
            if n not in interior and paths.get(n)
        })
        neighborhood = [
            {"id": n, "symbols": sorted(symbol_names.get(n, []))} for n in hop
        ]

        complement = build_complement(graph, interior_paths, warnings)
        human_first = (
            complement.sites >= max(HUMAN_FIRST_MIN_SITES, 1)
            and complement.cannot_resolve / complement.sites > HUMAN_FIRST_FRACTION
        )
        reason = ""
        if human_first:
            reason = (
                f"{complement.cannot_resolve} of {complement.sites} detected "
                "sites in this unit cannot be resolved — the stated complement "
                "rivals the captured fraction, so the honest shape is a human "
                "first, not a confident agent on a quietly unseen scope"
            )

        tests = sorted({t for m in unit.modules for t in guards.get(m, [])})
        manifests.append(ContextManifest(
            unit=unit.name,
            modules=[{"id": m, "path": paths.get(m)} for m in unit.modules],
            guarding_tests=tests,
            docs=docs,
            invariants=in_scope,
            boundary=boundary,
            neighborhood=neighborhood,
            complement=complement,
            human_first=human_first,
            human_first_reason=reason,
        ))
    return manifests


def build_policy_manifests(
    graph: dict,
    contexts: list[ContextManifest],
    tests: dict,
) -> list[PolicyManifest]:
    """One derived policy per unit. Raises GuaranteeError before it
    would emit a widening that crosses a specific guarantee (P10)."""
    test_files = {t["id"]: t.get("file", "") for t in tests.get("tests", [])}
    node_paths = {n["id"]: n.get("path") for n in graph.get("nodes", [])}

    manifests: list[PolicyManifest] = []
    for context in contexts:
        interior_paths = sorted(p for m in context.modules if (p := m["path"]))
        guard_paths = sorted({
            f for t in context.guarding_tests if (f := test_files.get(t))
        })
        mounts = sorted(set(interior_paths) | set(guard_paths))
        for mount in mounts:
            lowered = mount.lower()
            if any(mark in lowered for mark in _FORBIDDEN_MOUNT_MARKS):
                raise GuaranteeError(
                    f"derived write mount {mount!r} would cross a specific "
                    "guarantee; the generator refuses rather than widening "
                    "past it (P10)"
                )

        flags: list[str] = []
        if context.human_first:
            mounts = []
            flags.append(
                "human-first: sandbox stays read-only; pair with a human "
                "(blind-spot-heavy scope)"
            )

        manifests.append(PolicyManifest(
            unit=context.unit,
            guarantees=list(GUARANTEES),
            floor=(
                "read-only worktree; escalate by default; box and repo "
                "policy chain unchanged beneath this profile"
            ),
            write_mounts=mounts,
            read_signatures=sorted({
                p for n in context.neighborhood
                if (p := node_paths.get(n["id"]))
            }),
            flags=flags,
        ))
    return manifests
