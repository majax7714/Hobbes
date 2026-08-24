"""`hobbes review <base>..<head>` — the concept-level PR review (ADR-025).

Assembles the four things architecture §7 asks a reviewer to look at,
in that order: the architecture delta, the invariant verdicts, the
behavioral-coverage delta, and — for invariants no tool can check — a
reviewer session's judgement.

Verdicts are computed at *both* ends of the range. An invariant that
already failed on base is inherited; one that fails only on head is this
change's regression. A review that cannot tell them apart trains people
to ignore it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from hobbes.graphdiff import diff_graphs, extract_all_at_ref, has_changes
from hobbes.invariants import Invariant, load_all, scope_matches
from hobbes.invariants.verdict import FAIL, PASS, SUSPECT, Verdict, judge_all

#: The red family: verdicts that demand attention. `suspect` is a
#: violation resting on syntactic evidence (V2.M6) — a different kind of
#: red, not a lesser one, so movement and exit codes treat them alike.
_RED = {FAIL, SUSPECT}

#: How an invariant's verdict moved across the range.
REGRESSED = "regressed"
FIXED = "fixed"
STILL_FAILING = "still-failing"
UNCHANGED = "unchanged"


@dataclass
class InvariantReview:
    """One invariant, judged at both ends of the range."""

    invariant: Invariant
    base: Verdict
    head: Verdict
    movement: str

    @property
    def needs_attention(self) -> bool:
        """Only a regression is *this change's* problem."""
        return self.movement == REGRESSED


@dataclass
class CoverageDelta:
    """The §4.2 behavioural-coverage delta."""

    #: Modules this change added that no test statically reaches.
    new_unguarded: list[str] = field(default_factory=list)
    #: Modules that had guarding tests on base and have none on head.
    lost_guards: list[str] = field(default_factory=list)
    #: Invariants whose guarded_by names a test that no longer exists.
    broken_guards: dict[str, list[str]] = field(default_factory=dict)
    base_tests: int = 0
    head_tests: int = 0

    @property
    def needs_attention(self) -> bool:
        return bool(self.new_unguarded or self.lost_guards or self.broken_guards)


@dataclass
class Review:
    """Everything a concept-level review asserts about one range."""

    base_ref: str
    head_ref: str
    delta: dict
    invariants: list[InvariantReview]
    coverage: CoverageDelta
    soft: list[dict] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)

    @property
    def regressions(self) -> list[InvariantReview]:
        return [i for i in self.invariants if i.movement == REGRESSED]

    @property
    def needs_attention(self) -> bool:
        """The exit-code question: does this change need a human's eye?"""
        return bool(self.regressions) or self.coverage.needs_attention


def changed_paths(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    """Repo-relative paths this range touches, via `git diff --name-only`."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{base_ref}...{head_ref}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return sorted(p for p in result.stdout.splitlines() if p)


def build_review(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    with_soft: bool = False,
    runner=None,
) -> Review:
    """Extract both trees and assemble the review (ADR-025).

    *with_soft* runs a sandboxed reviewer session (read-only checkout of
    the head ref + knowledge tools, V2.M6) for soft invariants whose
    scope this change touches; it is the only part that spends quota,
    and it is off by default.
    """
    repo_root = Path(repo_root)
    base = extract_all_at_ref(repo_root, base_ref)
    head = extract_all_at_ref(repo_root, head_ref)
    delta = diff_graphs(base.graph, head.graph)

    # Records are read from the working tree, not from either ref: they
    # are the rules being applied, not part of the change under review.
    base_tests = {t["id"] for t in base.tests.get("tests", [])}
    head_tests = {t["id"] for t in head.tests.get("tests", [])}
    records = load_all(repo_root)

    base_verdicts = {v.invariant.id: v for v in judge_all(records, base.graph, base_tests)}
    head_verdicts = {v.invariant.id: v for v in judge_all(records, head.graph, head_tests)}

    reviews = [
        InvariantReview(
            invariant=record,
            base=base_verdicts[record.id],
            head=head_verdicts[record.id],
            movement=_movement(base_verdicts[record.id], head_verdicts[record.id]),
        )
        for record in records
    ]
    reviews.sort(key=lambda r: (_MOVEMENT_ORDER[r.movement], r.invariant.id))

    coverage = _coverage_delta(base, head, records, head_tests)
    touched = changed_paths(repo_root, base_ref, head_ref)

    review = Review(
        base_ref=base_ref,
        head_ref=head_ref,
        delta=delta,
        invariants=reviews,
        coverage=coverage,
        changed_paths=touched,
    )
    if with_soft:
        review.soft = judge_soft(review, records, runner=runner, repo_root=repo_root)
    return review


_MOVEMENT_ORDER = {REGRESSED: 0, STILL_FAILING: 1, FIXED: 2, UNCHANGED: 3}


def _movement(base: Verdict, head: Verdict) -> str:
    """How a verdict moved. Only red/green transitions are movements —
    fail and suspect are one family, so a verdict shifting between them
    (evidence changed tier) is still-failing, not fixed-and-regressed."""
    base_red, head_red = base.result in _RED, head.result in _RED
    if base_red and head_red:
        return STILL_FAILING
    if head_red:
        return REGRESSED
    if base_red:
        return FIXED
    return UNCHANGED


def _guarded_modules(tests: dict) -> set[str]:
    """Modules at least one test statically reaches."""
    return {
        module
        for test in tests.get("tests", [])
        for module in test.get("reaches_modules") or []
    }


def _own_code(graph: dict, tests: dict) -> dict[str, str]:
    """Internal module ids to paths — the code a test could guard.

    Test modules are excluded: a test file is not behaviour needing a
    guard, and listing every new test as "unguarded new code" is the kind
    of noise that makes a coverage metric ignorable. The test inventory
    names its own files, so this is data rather than a filename heuristic.
    """
    test_files = {t.get("file") for t in tests.get("tests", []) if t.get("file")}
    return {
        node["id"]: node.get("path", "")
        for node in graph.get("nodes", [])
        if node.get("kind") in ("module", "package")
        and node.get("path") not in test_files
    }


def _coverage_delta(base, head, records: list[Invariant], head_tests: set[str]) -> CoverageDelta:
    """Which behaviour lost its guard, and which new behaviour never had one."""
    base_modules = _own_code(base.graph, base.tests)
    head_modules = _own_code(head.graph, head.tests)
    base_guarded = _guarded_modules(base.tests)
    head_guarded = _guarded_modules(head.tests)

    new_unguarded = sorted(
        module
        for module in head_modules
        if module not in base_modules and module not in head_guarded
    )
    lost_guards = sorted(
        module
        for module in head_modules
        if module in base_modules and module in base_guarded and module not in head_guarded
    )
    broken = {
        record.id: missing
        for record in records
        if record.confirmed
        and (missing := sorted(g for g in record.guarded_by if g not in head_tests))
    }
    return CoverageDelta(
        new_unguarded=new_unguarded,
        lost_guards=lost_guards,
        broken_guards=broken,
        base_tests=len(base.tests.get("tests", [])),
        head_tests=len(head.tests.get("tests", [])),
    )


#: Environment override for locating hobbes-session (mirrors policy.py).
SESSION_BIN_ENV = "HOBBES_SESSION_BIN"

#: Diff excerpt budget per soft invariant — enough to judge a change,
#: bounded so a mass rename cannot blow the prompt.
_DIFF_LIMIT = 400


class ReviewerSessionRunner:
    """Runs a soft-invariant prompt in the M4 reviewer sandbox (V2.M6).

    The M8 shape sent prompts through the tool-less ADR-020 runner, so a
    session judged from the architecture delta and a changed-file list —
    honest but shallow (C-18): "does this change violate the invariant"
    often needs the files. The reviewer role has what that needs — the
    worktree mounted read-only at the review's *head ref* (`--ref`), and
    the knowledge tools — so the session can open what it judges.

    Failure is loud, not silent: no binary, no podman, or a non-zero
    session raises, and `judge_soft` records the error on the answer.
    Falling back to the delta-based prompt would quietly recreate C-18.
    """

    def __init__(self, repo_root: Path, head_ref: str):
        self.repo_root = Path(repo_root)
        self.head_ref = head_ref

    def _binary(self) -> str:
        override = os.environ.get(SESSION_BIN_ENV)
        if override:
            return override
        found = shutil.which("hobbes-session")
        if not found:
            raise RuntimeError(
                "hobbes-session not found — build go/cmd/hobbes-session and put "
                f"it on PATH, or set ${SESSION_BIN_ENV}"
            )
        return found

    def __call__(self, prompt: str) -> str:
        proc = subprocess.run(
            [
                self._binary(), "start",
                "--repo", str(self.repo_root),
                "--role", "reviewer",
                "--ref", self.head_ref,
                "--task", prompt,
                "--claude-cred",
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()[-300:]
            raise RuntimeError(f"reviewer session exited {proc.returncode}: {detail}")
        return proc.stdout


def judge_soft(
    review: Review,
    records: list[Invariant],
    runner=None,
    repo_root: Path | None = None,
) -> list[dict]:
    """Ask a reviewer session about each in-scope soft invariant.

    Only records whose scope contains a changed path are asked: judging
    an invariant this change cannot have touched spends quota to say
    "unaffected". *runner* is any prompt → text callable, so tests drive
    this without a sandbox; the default is the real reviewer session
    (V2.M6 — source-based, not delta-based).
    """
    if runner is None:
        if repo_root is None:
            raise ValueError("judge_soft needs repo_root to start reviewer sessions")
        runner = ReviewerSessionRunner(repo_root, review.head_ref)

    answers = []
    for record in records:
        if not (record.confirmed and record.soft):
            continue
        touched = [p for p in review.changed_paths if scope_matches(record.scope, p)]
        if not touched:
            continue
        diff = _diff_excerpt(repo_root, review, touched) if repo_root else ""
        try:
            raw = runner(soft_prompt(record, review, touched, diff))
            answers.append({"id": record.id, "answer": raw.strip(), "scope_hits": touched})
        except Exception as exc:  # a failed session must not fail the review
            answers.append({"id": record.id, "error": str(exc), "scope_hits": touched})
    return answers


def _diff_excerpt(repo_root: Path, review: Review, touched: list[str]) -> str:
    """The range's diff hunks for *touched*, bounded to `_DIFF_LIMIT` lines."""
    result = subprocess.run(
        [
            "git", "-C", str(repo_root), "diff",
            f"{review.base_ref}...{review.head_ref}", "--", *touched,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    lines = result.stdout.splitlines()
    if len(lines) > _DIFF_LIMIT:
        omitted = len(lines) - _DIFF_LIMIT
        lines = lines[:_DIFF_LIMIT] + [f"… (+{omitted} diff lines omitted — read the files)"]
    return "\n".join(lines)


def soft_prompt(
    record: Invariant, review: Review, touched: list[str], diff: str = ""
) -> str:
    """The reviewer-session prompt for one soft invariant.

    Source-based since V2.M6: the session runs in a read-only checkout of
    the head ref with the knowledge tools, and the prompt carries the
    range's diff hunks — the delta plus a file list was honest but
    shallow (C-18, lifted).
    """
    from hobbes.graphdiff import format_delta

    sections = [
        "You are reviewing one change against one stated invariant.",
        "",
        f"INVARIANT {record.id} (scope {record.scope}):\n{record.statement}",
        "",
        "You are in a read-only checkout of the repo at the head of this "
        "change. Read any file you need before answering; the knowledge "
        "tools (graph_neighborhood, who_calls, tests_guarding, "
        "get_module_doc, list_invariants) answer structural questions.",
        "",
        "FILES THIS CHANGE TOUCHES INSIDE THAT SCOPE:",
        "\n".join(f"  {p}" for p in touched),
        "",
        "ARCHITECTURE DELTA:",
        format_delta(review.delta, review.base_ref, review.head_ref),
    ]
    if diff:
        sections += ["", "THE CHANGE (diff hunks inside the scope):", diff]
    sections += [
        "",
        "Answer in exactly this shape:",
        "VERDICT: holds | violated | unclear",
        "WHY: one sentence",
        "EVIDENCE: file:line, file:line",
        "",
        "Cite only lines you verified exist in the checkout. If the change "
        "does not bear on the invariant, answer 'holds' and say so.",
    ]
    return "\n".join(sections)


def format_review(review: Review) -> str:
    """The human-facing review, in §7's order."""
    lines: list[str] = []
    add = lines.append

    add(f"review {review.base_ref}..{review.head_ref}")
    add("")

    add("1. architecture delta")
    if has_changes(review.delta):
        from hobbes.graphdiff import format_delta

        body = format_delta(review.delta, review.base_ref, review.head_ref)
        add("\n".join(f"   {line}" for line in body.rstrip("\n").split("\n")))
    else:
        add("   no architectural change")
    add("")

    add("2. invariants")
    if not review.invariants:
        add("   no confirmed invariants — see .hobbes/invariants/")
    for item in review.invariants:
        marker = {
            REGRESSED: "REGRESSED",
            STILL_FAILING: "still failing",
            FIXED: "fixed",
            UNCHANGED: "",
        }[item.movement]
        head = item.head
        label = f"   {head.result.upper():<8} {item.invariant.id:<6}"
        suffix = f"  [{marker}]" if marker else ""
        add(f"{label} {item.invariant.statement[:64]}{suffix}")
        if head.result in _RED:
            for violation in head.violations[:5]:
                add(f"            {violation.cite()}")
            if len(head.violations) > 5:
                add(f"            +{len(head.violations) - 5} more")
        elif head.result != PASS:
            add(f"            {head.reason}")
    add("")

    add("3. behavioral coverage")
    coverage = review.coverage
    add(f"   tests: {coverage.base_tests} -> {coverage.head_tests}")
    if coverage.new_unguarded:
        add(f"   new code no test reaches ({len(coverage.new_unguarded)}):")
        for module in coverage.new_unguarded:
            add(f"      {module}")
    if coverage.lost_guards:
        add(f"   lost every guarding test ({len(coverage.lost_guards)}):")
        for module in coverage.lost_guards:
            add(f"      {module}")
    for invariant_id, guards in sorted(coverage.broken_guards.items()):
        add(f"   {invariant_id} names {len(guards)} test(s) that no longer exist:")
        for guard in guards:
            add(f"      {guard}")
    if not coverage.needs_attention:
        add("   no coverage regression")
    add("")

    if review.soft:
        add("4. soft invariants (reviewer session)")
        for answer in review.soft:
            if "error" in answer:
                add(f"   {answer['id']}: session failed — {answer['error']}")
                continue
            body = answer["answer"].strip().splitlines()
            add(f"   {answer['id']}:")
            for line in body:
                add(f"      {line}")
        add("")

    if review.needs_attention:
        reasons = []
        if review.regressions:
            reasons.append(f"{len(review.regressions)} invariant regression(s)")
        if coverage.new_unguarded:
            reasons.append(f"{len(coverage.new_unguarded)} unguarded new module(s)")
        if coverage.lost_guards:
            reasons.append(f"{len(coverage.lost_guards)} module(s) lost their guards")
        if coverage.broken_guards:
            reasons.append(f"{len(coverage.broken_guards)} invariant(s) with a dead guard")
        add("needs attention: " + ", ".join(reasons))
    else:
        add("nothing needs attention")
    return "\n".join(lines) + "\n"


def review_to_dict(review: Review) -> dict:
    """The `--json` payload (ADR-025): the whole review, not a summary."""
    return {
        "base": review.base_ref,
        "head": review.head_ref,
        "needs_attention": review.needs_attention,
        "delta": review.delta,
        "changed_paths": review.changed_paths,
        "invariants": [
            {
                "id": item.invariant.id,
                "statement": item.invariant.statement,
                "scope": item.invariant.scope,
                "target": item.invariant.target,
                "movement": item.movement,
                "base": _verdict_to_dict(item.base),
                "head": _verdict_to_dict(item.head),
            }
            for item in review.invariants
        ],
        "coverage": {
            "base_tests": review.coverage.base_tests,
            "head_tests": review.coverage.head_tests,
            "new_unguarded": review.coverage.new_unguarded,
            "lost_guards": review.coverage.lost_guards,
            "broken_guards": review.coverage.broken_guards,
        },
        "soft": review.soft,
    }


def _verdict_to_dict(verdict: Verdict) -> dict:
    return {
        "result": verdict.result,
        "reason": verdict.reason,
        "violations": [
            {
                "importer": v.importer,
                "imported": v.imported,
                "path": v.path,
                "line": v.line,
            }
            for v in verdict.violations
        ],
    }
