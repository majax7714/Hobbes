"""Invariant verdicts from the graph — the unified checker (ADR-025/039).

``hobbes review`` answers "does this rule hold?" in-process, reading
``graph.json`` — not by shelling out to import-linter or semgrep. The
graph already knows who imports whom, so a forbidden-import rule is a
question it can answer; and a review that needs no toolchain runs
anywhere the extractor does, deterministically and without quota. Since
V2.M6 this is one checker for every language and every ``check: graph``
record — and it still judges ``check: emit`` records where the graph
can see their rule, because the two answers must agree (the M6 exit).

**Verdicts are tier-aware** (architecture §3.4/§5): a violation whose
evidence is a ``semantic`` edge is proven; one resting on a
``syntactic`` edge is a *suspicion* — unless the edge is one only lane A
can produce at all (``ext:``/``env:``/``tf:`` targets, §3.1), where the
syntactic form is the authoritative one and counts as proof. A verdict
whose violations are all suspicions is ``suspect``, not ``fail`` — still
red, still exit 1, but the reviewer knows which kind of red.

What the graph cannot see, this refuses to guess. A semgrep rule matches
source patterns and a Rego rule reads a Terraform plan; neither is in
the graph, so those verdicts are ``unknown`` with the reason attached.
**Never a false pass** — an invariant reported green because nothing
checked it is worse than one reported unchecked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hobbes.invariants.schema import Invariant, scope_matches

#: Verdict values, worst first — the order a review sorts by.
FAIL = "fail"
SUSPECT = "suspect"
UNKNOWN = "unknown"
SOFT = "soft"
PASS = "pass"
SKIPPED = "skipped"

_SEVERITY = {FAIL: 0, SUSPECT: 1, UNKNOWN: 2, SOFT: 3, PASS: 4, SKIPPED: 5}

#: Node-id prefixes only lane A can see (§3.1) — for edges into these,
#: `syntactic` is not a downgrade, it is the only tier that exists, and
#: an import statement lane A read is a fact rather than a guess.
_LANE_A_ONLY = ("ext:", "env:", "tf:")


@dataclass
class Violation:
    """One concrete breach, cited where the extractor saw it."""

    importer: str
    imported: str
    path: str = ""
    line: int = 0
    #: The evidence edge's tier (schema v4); "" on pre-v4 graphs.
    tier: str = ""

    @property
    def proven(self) -> bool:
        """Proof or suspicion (§3.4): semantic evidence proves; syntactic
        evidence proves only where no semantic form could exist."""
        return self.tier == "semantic" or self.imported.startswith(_LANE_A_ONLY)

    def cite(self) -> str:
        where = f" [{self.path}:{self.line}]" if self.path else ""
        mark = "" if self.proven else " (syntactic — suspected)"
        return f"{self.importer} -> {self.imported}{where}{mark}"


@dataclass
class Verdict:
    """The judgement on one invariant."""

    invariant: Invariant
    result: str
    #: Why, in one line — always set for unknown and fail.
    reason: str = ""
    violations: list[Violation] = field(default_factory=list)
    #: Guards from ``guarded_by`` that no longer exist in tests.json.
    missing_guards: list[str] = field(default_factory=list)

    @property
    def severity(self) -> int:
        return _SEVERITY[self.result]


def judge_all(
    invariants: list[Invariant],
    graph: dict,
    test_ids: set[str] | None = None,
) -> list[Verdict]:
    """Judge every invariant against *graph*, worst verdict first."""
    verdicts = [judge(inv, graph, test_ids) for inv in invariants]
    return sorted(verdicts, key=lambda v: (v.severity, v.invariant.id))


def judge(
    invariant: Invariant, graph: dict, test_ids: set[str] | None = None
) -> Verdict:
    """Judge one invariant."""
    missing = sorted(
        g for g in invariant.guarded_by if test_ids is not None and g not in test_ids
    )

    if not invariant.confirmed:
        return Verdict(
            invariant,
            SKIPPED,
            reason=f"status is {invariant.status}; only confirmed records are judged",
            missing_guards=missing,
        )

    if invariant.soft:
        return Verdict(
            invariant,
            SOFT,
            reason="not mechanically checkable — a reviewer session must judge it "
            "and cite evidence",
            missing_guards=missing,
        )

    kind = invariant.kind
    if kind == "forbidden-import":
        # check: graph records land here by construction; check: emit
        # records land here too when the graph can see their rule, so the
        # emitted tool always has an in-process answer to agree with.
        return _judge_forbidden_import(invariant, graph, missing)

    # Compiled for CI, unanswerable here — and said so rather than passed.
    where = {
        "pattern-absent": "source patterns, which live in the AST rather than the graph",
        "resource-attribute": "a terraform plan, which the graph does not carry",
    }.get(kind, "something the graph does not record")
    return Verdict(
        invariant,
        UNKNOWN,
        reason=f"{invariant.target} checks {where}; compiled for CI, not judged here",
        missing_guards=missing,
    )


def _judge_forbidden_import(
    invariant: Invariant, graph: dict, missing: list[str]
) -> Verdict:
    """Evaluate a forbidden-import rule against the module graph."""
    rule = invariant.rule
    importers = rule.get("importers") or []
    allowed = set(rule.get("except") or [])
    forbidden = set(rule.get("imported") or [])

    # Scope bounds who the rule is about: `*` means everything under it,
    # not everything in the repo.
    paths = {node["id"]: node.get("path") for node in graph.get("nodes", [])}
    in_scope = {
        node_id
        for node_id, path in paths.items()
        if scope_matches(invariant.scope, path)
    }

    violations: list[Violation] = []
    for edge in graph.get("module_edges", []):
        if edge.get("type") != "imports" or edge.get("to") not in forbidden:
            continue
        source = edge.get("from", "")
        if source in allowed:
            continue
        if not _any_match(importers, source):
            continue
        # An importer with no path (an external or synthetic node) cannot
        # be placed in a scope, so the scope does not bind it.
        if paths.get(source) is not None and source not in in_scope:
            continue
        evidence = (edge.get("evidence") or [{}])[0]
        violations.append(
            Violation(
                importer=source,
                imported=edge.get("to", ""),
                path=evidence.get("path", ""),
                line=evidence.get("line", 0),
                tier=edge.get("tier", ""),
            )
        )

    violations.sort(key=lambda v: (v.importer, v.imported, v.line))
    if violations:
        proven = sum(1 for v in violations if v.proven)
        if proven:
            reason = f"{len(violations)} forbidden import(s)"
            if proven < len(violations):
                reason += f" ({len(violations) - proven} suspected on syntactic evidence)"
            return Verdict(
                invariant, FAIL, reason=reason,
                violations=violations, missing_guards=missing,
            )
        # Every violation rests on syntactic evidence lane B could have
        # confirmed and did not: red, but the reviewer should know which
        # kind of red (§3.4).
        return Verdict(
            invariant,
            SUSPECT,
            reason=f"{len(violations)} suspected forbidden import(s), all on "
            "syntactic evidence",
            violations=violations,
            missing_guards=missing,
        )
    return Verdict(
        invariant,
        PASS,
        reason=f"no module in {invariant.scope} imports "
        f"{', '.join(sorted(forbidden))} outside the exceptions",
        missing_guards=missing,
    )


def _any_match(patterns: list[str], node_id: str) -> bool:
    """Whether *node_id* matches any importer pattern.

    ``*`` is everything; ``prefix.*`` and ``prefix/*`` match a package or
    directory (both id shapes exist — dotted for Python, path for TS/JS,
    ADR-021); anything else is an exact id.
    """
    for pattern in patterns:
        if pattern == "*":
            return True
        for separator in (".", "/"):
            if pattern.endswith(separator + "*"):
                if node_id.startswith(pattern[:-1]):
                    return True
                break
        else:
            if pattern == node_id:
                return True
    return False
