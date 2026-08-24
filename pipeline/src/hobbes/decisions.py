"""The decision ledger: what the human has already ruled on (ADR-026).

Exactly two things need a human — **intent** (the repo policy) and
**invariants**. Everything else is a natural part of the mechanism. This
module records those rulings so they hold until manually changed, and so
"what is new since I last looked" has a precise answer instead of a
heuristic.

Decisions key on a **content hash of the statement and scope**, never on
the invariant id. Inferred ids are positional — ``schema.py`` assigns
``INF-n`` by enumeration over whatever order the model returned — so
``INF-3`` names a different statement after the next narration. Keying by
id would let an old approval silently bless unrelated new text, which is
the exact failure the gate exists to prevent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

#: Where the ledger lives — human judgement, so it sits beside
#: policies/ and invariants/ rather than in derived/.
LEDGER_PATH = ".hobbes/decisions.yaml"

SCHEMA_VERSION = 1

#: Verdicts a human can return on an inferred invariant.
APPROVED = "approved"
DENIED = "denied"
EDITED = "edited"
VERDICTS = (APPROVED, DENIED, EDITED)


def content_key(statement: str, scope: str) -> str:
    """Stable identity for one proposed invariant.

    Whitespace is normalized so a reflowed line is the same decision;
    any change to the words or the scope is a different one, and gets
    asked again.
    """
    normalized = " ".join((statement or "").split()) + "\n" + (scope or "").strip()
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Decision:
    """One recorded ruling on one proposed invariant."""

    key: str
    verdict: str
    decided_at: str
    #: The record id written into .hobbes/invariants/, for approve/edit.
    record: str = ""
    #: What was originally proposed, so an edit stays inspectable.
    source_statement: str = ""
    source_scope: str = ""

    def to_dict(self) -> dict:
        out = {
            "key": self.key,
            "verdict": self.verdict,
            "decided_at": self.decided_at,
            "source_statement": self.source_statement,
            "source_scope": self.source_scope,
        }
        if self.record:
            out["record"] = self.record
        return out


@dataclass
class Ledger:
    """Every decision made in this repo, and whether intent was reviewed."""

    intent_confirmed_at: str = ""
    #: The policy file's blob hash when it was confirmed, so the UI can
    #: show that it has since been hand-edited.
    intent_policy_blob: str = ""
    decisions: dict[str, Decision] = field(default_factory=dict)

    @property
    def intent_confirmed(self) -> bool:
        return bool(self.intent_confirmed_at)

    def verdict_for(self, key: str) -> Decision | None:
        return self.decisions.get(key)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "intent": {
                "confirmed_at": self.intent_confirmed_at,
                "policy_blob": self.intent_policy_blob,
            },
            "invariants": [
                self.decisions[k].to_dict() for k in sorted(self.decisions)
            ],
        }


def load(repo_root: Path) -> Ledger:
    """Read the ledger, or an empty one when nothing has been decided."""
    path = Path(repo_root) / LEDGER_PATH
    if not path.is_file():
        return Ledger()
    raw = yaml.safe_load(path.read_text()) or {}
    intent = raw.get("intent") or {}
    ledger = Ledger(
        intent_confirmed_at=intent.get("confirmed_at", "") or "",
        intent_policy_blob=intent.get("policy_blob", "") or "",
    )
    for entry in raw.get("invariants") or []:
        key = entry.get("key")
        verdict = entry.get("verdict")
        if not key or verdict not in VERDICTS:
            # A torn or hand-mangled row is dropped rather than trusted:
            # an unreadable verdict must re-ask, never auto-approve.
            continue
        ledger.decisions[key] = Decision(
            key=key,
            verdict=verdict,
            decided_at=entry.get("decided_at", "") or "",
            record=entry.get("record", "") or "",
            source_statement=entry.get("source_statement", "") or "",
            source_scope=entry.get("source_scope", "") or "",
        )
    return ledger


def save(repo_root: Path, ledger: Ledger) -> Path:
    """Write the ledger atomically."""
    path = Path(repo_root) / LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Decisions Max has made about this repo (ADR-026). Approvals,\n"
        "# denials, and edits hold until changed here or in the UI; only\n"
        "# invariants whose text is new get asked again.\n"
        + yaml.safe_dump(ledger.to_dict(), sort_keys=False, allow_unicode=True)
    )
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(body)
    tmp.replace(path)
    return path


def record_verdict(
    repo_root: Path,
    statement: str,
    scope: str,
    verdict: str,
    record: str = "",
) -> Decision:
    """Record one ruling and persist it. Returns the stored Decision."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    ledger = load(repo_root)
    decision = Decision(
        key=content_key(statement, scope),
        verdict=verdict,
        decided_at=_now(),
        record=record,
        source_statement=" ".join((statement or "").split()),
        source_scope=(scope or "").strip(),
    )
    ledger.decisions[decision.key] = decision
    save(repo_root, ledger)
    return decision


def confirm_intent(repo_root: Path, policy_blob: str = "") -> Ledger:
    """Mark the policy as reviewed by a human."""
    ledger = load(repo_root)
    ledger.intent_confirmed_at = _now()
    ledger.intent_policy_blob = policy_blob
    save(repo_root, ledger)
    return ledger


# --- the pending queue -------------------------------------------------------


@dataclass
class Pending:
    """One inferred invariant still awaiting a verdict."""

    key: str
    id: str
    statement: str
    scope: str
    evidence: list = field(default_factory=list)
    guarded_by: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "id": self.id,
            "statement": self.statement,
            "scope": self.scope,
            "evidence": self.evidence,
            "guarded_by": self.guarded_by,
        }


def inferred_records(repo_root: Path) -> list[dict]:
    """The inferred invariants on disk, or [] when narration hasn't run."""
    path = (
        Path(repo_root)
        / ".hobbes"
        / "derived"
        / "docs"
        / "invariants.inferred.yaml"
    )
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text()) or {}
    return raw.get("invariants") or []


def pending_invariants(repo_root: Path, ledger: Ledger | None = None) -> list[Pending]:
    """Inferred invariants with no recorded verdict, in file order.

    A record whose text changed since it was decided reappears here —
    that is the point of hashing content rather than trusting the id.
    """
    ledger = ledger if ledger is not None else load(repo_root)
    pending = []
    for record in inferred_records(repo_root):
        statement = record.get("statement", "")
        scope = record.get("scope", "")
        key = content_key(statement, scope)
        if ledger.verdict_for(key) is not None:
            continue
        pending.append(
            Pending(
                key=key,
                id=record.get("id", ""),
                statement=" ".join(statement.split()),
                scope=scope,
                evidence=record.get("evidence") or [],
                guarded_by=record.get("guarded_by") or [],
            )
        )
    return pending


@dataclass
class Readiness:
    """Whether the repo is ready to develop in (ADR-026's blocking gate)."""

    intent_confirmed: bool
    pending: list[Pending]

    @property
    def ready(self) -> bool:
        return self.intent_confirmed and not self.pending

    def blockers(self) -> list[str]:
        """One line per thing still owed a human, for the CLI to print."""
        out = []
        if not self.intent_confirmed:
            out.append("intent: the repo policy has not been confirmed")
        if self.pending:
            out.append(
                f"invariants: {len(self.pending)} awaiting approve / deny / edit"
            )
        return out

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "intent_confirmed": self.intent_confirmed,
            "pending_invariants": [p.to_dict() for p in self.pending],
            "blockers": self.blockers(),
        }


def readiness(repo_root: Path) -> Readiness:
    """The blocking gate `hobbes up` polls."""
    ledger = load(repo_root)
    return Readiness(
        intent_confirmed=ledger.intent_confirmed,
        pending=pending_invariants(repo_root, ledger),
    )
