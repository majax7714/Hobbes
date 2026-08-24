"""Standing role policies (ADR-054).

The owner's structure gives every agent a policy made of the shared
repo policy plus a **per-role** policy. Roles here are the phases of
agent-mapping §2, not personas: ``planner`` (breaks the proposal down,
hands off, writes nothing), ``reviewer`` (judges a plan or a range),
``implementer`` (one per unit, writes inside its unit), ``verifier``
(reads the integrated result, writes nothing), ``orchestrator``
(sequences and arbitrates, owns no code).
The files live at ``.hobbes/policies/roles/<role>.policy`` with
``scope: role``; the Go engine loads the one matching the session's
role between the repo policy and any folder policy.

They are **standing** context: versioned with the repo and changed
only by commits. ``hobbes run`` scaffolds a missing one from the
templates below and never overwrites an existing one — a role policy
someone edited is intent, and intent is the human's (ADR-026).
"""

from __future__ import annotations

from pathlib import Path

ROLES_DIR = ".hobbes/policies/roles"

ROLE_POLICIES: dict[str, str] = {
    "implementer": """\
# Role policy: implementer (ADR-054). One per work unit; writes only
# inside its unit, commits on its session branch, never publishes.
# Loaded between the repo policy and the derived agent policy; deny
# overrides allow, so nothing here can widen past the repo's denies.
version: 1
scope: role
default: escalate

rules:
  - pattern: "git commit*"
    decision: allow
  - pattern: "git add *"
    decision: allow
  - pattern: "git checkout -b *"
    decision: deny
    reason: "a session works on the branch it was started on"
  - pattern: "git merge*"
    decision: deny
    reason: "integration is the orchestrator's, after harvest"
  - pattern: "git rebase*"
    decision: deny
    reason: "history on a session branch is the audit trail"
""",
    "planner": """\
# Role policy: planner (harness restructure, phase 1; ADR-085). Reads the
# repo and the derived context, decomposes the proposal into requirements
# with owning files, and hands off — its worktree is mounted read-only and
# its deliverable is a reflect handoff (requirements, files, symbols,
# approach, tests to run). Every write is denied here too, so a refusal
# carries a reason instead of an EROFS.
version: 1
scope: role
default: escalate

rules:
  - pattern: "git commit*"
    decision: deny
    reason: "a planner plans; it does not change the tree"
  - pattern: "git add *"
    decision: deny
    reason: "a planner plans; it does not change the tree"
""",
    "reviewer": """\
# Role policy: reviewer (M8 / harness restructure, phase 1). Reviews a
# plan or a range and reports; worktree read-only, writes denied with a
# reason.
version: 1
scope: role
default: escalate

rules:
  - pattern: "git commit*"
    decision: deny
    reason: "a reviewer reports; it does not change the tree"
  - pattern: "git add *"
    decision: deny
    reason: "a reviewer reports; it does not change the tree"
""",
    "verifier": """\
# Role policy: verifier (ADR-054). Reads the integrated result and
# reports; its worktree is mounted read-only, so every write is denied
# here too — a refusal with a reason beats a confusing EROFS.
version: 1
scope: role
default: escalate

rules:
  - pattern: "git commit*"
    decision: deny
    reason: "a verifier reports; it does not change the tree"
  - pattern: "git add *"
    decision: deny
    reason: "a verifier reports; it does not change the tree"
""",
    "orchestrator": """\
# Role policy: orchestrator (ADR-054). Sequences units and arbitrates
# contracts; owns no code. It is the most restricted session in a run:
# nothing but reading and the plan artifacts.
version: 1
scope: role
default: deny

rules:
  - pattern: "git status*"
    decision: allow
  - pattern: "git log*"
    decision: allow
  - pattern: "git diff*"
    decision: allow
""",
}


def ensure_role_policies(repo_root: Path) -> list[str]:
    """Write any missing role policy from the templates; return the
    roles written. Existing files are never touched."""
    root = Path(repo_root) / ROLES_DIR
    written = []
    for role, text in ROLE_POLICIES.items():
        path = root / f"{role}.policy"
        if path.exists():
            continue
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(role)
    return written
