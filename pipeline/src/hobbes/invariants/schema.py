"""Invariant record schema: loading and validation (ADR-024, ADR-039).

A record is one YAML file under ``.hobbes/invariants/`` describing a
structural rule the code is meant to obey: the prose a human reads
(``statement``), how it is checked (``check``), the spec a machine
consumes (``rule``), and the tests that already pin it down
(``guarded_by``).

``check`` is the V2.M6 field (architecture §5):

- ``graph`` — the unified checker judges the ``rule`` directly against
  the semantic graph, tier-aware. No CI config is emitted.
- ``emit`` — the ``rule`` compiles to the CI tool in ``compile.target``.
  The checker still gives its own answer where the graph can see the
  rule, and the two must agree (the M6 exit).
- ``soft`` — a reviewer session judges it and must cite evidence. No
  rule, no compile.

Validation is strict and runs before anything compiles or is judged: a
record that does not mean exactly one thing is worse than no record.
Only ``confirmed`` records participate — ``retired`` ones stay as
history, and an ``inferred`` one found here is a half-finished promotion
(ADR-019 keeps inferred output in ``derived/``), so it warns and stays
inert rather than failing the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

#: Where confirmed records live, relative to the repo root.
INVARIANTS_DIR = ".hobbes/invariants"

#: Where compiled CI configs are written (derived, regenerable).
COMPILED_DIR = ".hobbes/derived/compiled"

#: Lifecycle states (architecture §10).
STATUSES = ("inferred", "confirmed", "retired")

#: Checking modes (architecture §5, ADR-039).
CHECKS = ("graph", "emit", "soft")

#: Compile targets for ``check: emit`` (§5). A reviewer-judged record is
#: ``check: soft`` now, not a target.
TARGETS = ("import-linter", "dep-cruiser", "semgrep", "rego")

#: Structured rule kinds, one per shape a real record needed (ADR-024).
KINDS = ("forbidden-import", "pattern-absent", "resource-attribute")

#: Rule kinds the unified checker can answer from the graph. The others
#: live in the AST or a Terraform plan, which the graph does not carry —
#: a ``check: graph`` record with one of those would be permanently
#: ``unknown``, so validation refuses it up front (never a false pass,
#: and never a check that cannot check).
GRAPH_KINDS = ("forbidden-import",)

#: Which kind each emit target consumes.
TARGET_KIND = {
    "import-linter": "forbidden-import",
    "dep-cruiser": "forbidden-import",
    "semgrep": "pattern-absent",
    "rego": "resource-attribute",
}

_RECORD_FIELDS = {"id", "statement", "scope", "status", "check", "rule", "compile", "guarded_by"}
_COMPILE_FIELDS = {"target"}
_KIND_FIELDS = {
    "forbidden-import": ({"kind", "importers", "imported"}, {"except"}),
    "pattern-absent": ({"kind", "languages", "patterns"}, {"paths", "exclude"}),
    "resource-attribute": ({"kind", "resource_type"}, {"require", "forbid"}),
}


class ValidationError(ValueError):
    """A record violated the ADR-024 contract.

    Carries every problem found across every record, so one run tells
    you everything to fix.
    """

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass
class Invariant:
    """One loaded record."""

    id: str
    statement: str
    scope: str
    status: str
    #: How the record is checked: graph | emit | soft (ADR-039).
    check: str
    #: Emit target; empty for graph and soft records.
    target: str
    rule: dict
    guarded_by: list[str]
    #: Repo-relative path of the file this came from, for error messages.
    source: str
    warnings: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        """Only confirmed records compile and receive verdicts."""
        return self.status == "confirmed"

    @property
    def soft(self) -> bool:
        """Soft records are judged by a reviewer session, not a tool."""
        return self.check == "soft"

    @property
    def kind(self) -> str | None:
        """The rule kind, or None for soft records."""
        return self.rule.get("kind") if self.rule else None


def load_all(repo_root: Path, known_tests: set[str] | None = None) -> list[Invariant]:
    """Load and validate every record under ``.hobbes/invariants/``.

    *known_tests* is the set of test ids from ``tests.json``; when given,
    a ``guarded_by`` naming a test that does not exist is an error — a
    guard that points nowhere is a false reassurance.

    Raises ValidationError listing every problem across every file.
    Returns records sorted by id, including non-confirmed ones (callers
    filter; the review surface shows them).
    """
    directory = Path(repo_root) / INVARIANTS_DIR
    problems: list[str] = []
    records: list[Invariant] = []

    for path in sorted(directory.glob("*.yaml")):
        rel = str(path.relative_to(repo_root))
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            problems.append(f"{rel}: not valid YAML ({exc})")
            continue
        if not isinstance(raw, dict):
            problems.append(f"{rel}: expected a mapping, got {type(raw).__name__}")
            continue
        record = _validate(raw, rel, problems, known_tests)
        if record is not None:
            records.append(record)

    seen: dict[str, str] = {}
    for record in records:
        if record.id in seen:
            problems.append(
                f"{record.source}: duplicate id {record.id} "
                f"(already defined in {seen[record.id]})"
            )
        else:
            seen[record.id] = record.source

    if problems:
        raise ValidationError(problems)
    return sorted(records, key=lambda r: _id_key(r.id))


def _id_key(invariant_id: str) -> tuple:
    """Sort I-2 before I-10, unlike a plain string sort."""
    head, _, tail = invariant_id.partition("-")
    return (head, int(tail)) if tail.isdigit() else (head, 0, tail)


def _validate(
    raw: dict, rel: str, problems: list[str], known_tests: set[str] | None
) -> Invariant | None:
    """Validate one record, appending problems. None if unusable."""
    before = len(problems)

    unknown = set(raw) - _RECORD_FIELDS
    if unknown:
        problems.append(f"{rel}: unknown field(s) {', '.join(sorted(unknown))}")

    for required in ("id", "statement", "scope", "status", "check"):
        if required not in raw:
            hint = ""
            if required == "check":
                # The one migration everyone hits: a v1 record has no
                # check field, and telling them "missing field" without
                # the shape change would strand them (ADR-039).
                hint = (
                    " (v1 records migrate: check: soft for target soft, else "
                    "check: emit with the rule moved from compile.rule to a "
                    "top-level rule block — ADR-039)"
                )
            problems.append(f"{rel}: missing required field '{required}'{hint}")

    invariant_id = raw.get("id")
    if invariant_id is not None and not isinstance(invariant_id, str):
        problems.append(f"{rel}: id must be a string")
        invariant_id = None

    statement = raw.get("statement", "")
    if not isinstance(statement, str) or not statement.strip():
        problems.append(f"{rel}: statement must be a non-empty string")
        statement = ""

    scope = raw.get("scope", "")
    if not isinstance(scope, str) or not scope.strip():
        problems.append(f"{rel}: scope must be a non-empty path prefix")
        scope = ""

    status = raw.get("status")
    if status not in STATUSES:
        problems.append(f"{rel}: status must be one of {', '.join(STATUSES)}")
        status = "retired"

    guarded_by = raw.get("guarded_by") or []
    if not isinstance(guarded_by, list) or any(not isinstance(g, str) for g in guarded_by):
        problems.append(f"{rel}: guarded_by must be a list of test ids")
        guarded_by = []
    elif known_tests is not None:
        for guard in guarded_by:
            if guard not in known_tests:
                problems.append(
                    f"{rel}: guarded_by names a test not in tests.json: {guard}"
                )

    check, target, rule = _validate_check(raw, rel, problems)

    if len(problems) > before or invariant_id is None:
        return None

    warnings = []
    if status == "inferred":
        warnings.append(
            f"{rel}: status 'inferred' in the versioned directory — a promotion "
            "stopped halfway (ADR-019); the record is inert until confirmed"
        )

    return Invariant(
        id=invariant_id,
        statement=" ".join(statement.split()),
        scope=scope,
        status=status,
        check=check,
        target=target,
        rule=rule,
        guarded_by=guarded_by,
        source=rel,
        warnings=warnings,
    )


def _validate_check(raw: dict, rel: str, problems: list[str]) -> tuple[str, str, dict]:
    """Validate check/rule/compile together, returning (check, target, rule).

    The three fields are one contract: which of them may appear follows
    entirely from ``check``, and a combination that YAML would happily
    hold — a soft record with a rule, a graph record with a compile
    target — is a record whose author meant something else.
    """
    check = raw.get("check")
    if check is not None and check not in CHECKS:
        problems.append(f"{rel}: check must be one of {', '.join(CHECKS)}")
        return "soft", "", {}
    if check is None:
        return "soft", "", {}

    rule_block = raw.get("rule")
    compile_block = raw.get("compile")

    if check == "soft":
        # A soft record carrying a rule means someone wrote a spec and
        # then told every checker to ignore it.
        if rule_block is not None:
            problems.append(
                f"{rel}: check: soft takes no rule — either drop the rule or "
                "give the record check: graph or check: emit"
            )
        if compile_block is not None:
            problems.append(f"{rel}: check: soft takes no compile block")
        return check, "", {}

    if isinstance(compile_block, dict) and "rule" in compile_block:
        problems.append(
            f"{rel}: compile.rule moved to a top-level rule block (ADR-039)"
        )
        return check, "", {}

    if not isinstance(rule_block, dict):
        problems.append(f"{rel}: a rule block is required for check: {check}")
        return check, "", {}

    kind = rule_block.get("kind")
    if kind not in KINDS:
        problems.append(f"{rel}: rule.kind must be one of {', '.join(KINDS)}")
        return check, "", {}

    target = ""
    if check == "graph":
        if compile_block is not None:
            problems.append(
                f"{rel}: check: graph emits nothing — drop the compile block, "
                "or use check: emit if a CI tool should run it"
            )
        if kind not in GRAPH_KINDS:
            problems.append(
                f"{rel}: the graph cannot answer kind {kind} (it lives outside "
                f"the graph); use check: emit"
            )
            return check, "", {}
    else:  # emit
        if not isinstance(compile_block, dict):
            problems.append(f"{rel}: check: emit requires compile.target")
            return check, "", {}
        unknown = set(compile_block) - _COMPILE_FIELDS
        if unknown:
            problems.append(
                f"{rel}: unknown compile field(s) {', '.join(sorted(unknown))}"
            )
        target = compile_block.get("target")
        if target not in TARGETS:
            problems.append(
                f"{rel}: compile.target must be one of {', '.join(TARGETS)}"
            )
            return check, "", {}
        expected = TARGET_KIND[target]
        if kind != expected:
            problems.append(
                f"{rel}: target {target} takes kind {expected}, not {kind}"
            )
            return check, target, {}

    required, optional = _KIND_FIELDS[kind]
    unknown = set(rule_block) - required - optional
    if unknown:
        problems.append(
            f"{rel}: unknown rule field(s) {', '.join(sorted(unknown))}"
        )
    for name in sorted(required - set(rule_block)):
        problems.append(f"{rel}: rule missing '{name}'")

    for name in ("importers", "imported", "except", "languages", "patterns",
                 "paths", "exclude"):
        value = rule_block.get(name)
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(v, str) for v in value)
        ):
            problems.append(f"{rel}: rule.{name} must be a list of strings")

    return check, target, rule_block


def scope_matches(scope: str, path: str | None) -> bool:
    """Whether *path* falls inside *scope* (ADR-024: a path prefix).

    ``.`` is the whole repo. Matching is segment-wise, so scope ``src/a``
    does not swallow ``src/ab``.
    """
    if not path:
        return False
    if scope in (".", "", "./"):
        return True
    scope = scope.rstrip("/")
    return path == scope or path.startswith(scope + "/")
