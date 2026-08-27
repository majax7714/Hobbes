"""The orchestrator loop — ``hobbes run <task>`` (ADR-054).

Agent-mapping §3.4: the only orchestrator there is, a scheduler and
contract arbiter that owns no code. Per unit, in contract order
(definition owners before their consumers — a consumer's pin should
exist before the consumer is started), it writes the brief from the
standing context plus the inbox as it stands, spawns one single-use
session through ``hobbes-session start --agent-dir``, and after the
session reads three things back: the **flight log** (knowledge calls,
context faults, exec decisions), the **mail** (reflections, folded
into the orchestrator's inbox), and the **harvested branch**
(``hobbes/<session>`` in the repo — commits, files, and the files
outside the manifest, which is *rework* in §6's loss).

Then integration: the unit branches merge onto ``hobbes/<task>`` in
contract order, a conflict recorded as an integration failure at the
cut rather than resolved by guessing; ``hobbes review`` runs over
``base..hobbes/<task>``; and the run says plainly that re-ingesting
the merged result is what moves standing context — it does not
re-ingest behind the human's back.

Everything lands in ``.hobbes/plans/<task>/partition-record.json`` —
the record agent-mapping §6 specified, with the loss computed under
ADR-051's declared weights and labelled a declared guess (C-35).
Tokens and wall time per unit are recorded where the session reports
them and ``null`` where it does not; a number the recorder did not
observe is never filled in.

A **human-first** unit is not spawned: the plan said a human goes
first, and the orchestrator posts that to its own inbox and moves on.
``--dry-run`` writes everything and spawns nothing; the test suite
drives the loop with a stand-in session binary.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from hobbes import artifacts
from hobbes.run import agents, mail
from hobbes.run.roles import ensure_role_policies
from hobbes.run.spec import load_spec, plan_dir

RECORD = "partition-record.json"

#: ADR-051's declared loss weights (agent-mapping §6) — guesses until the
#: record has enough runs to fit them (C-35).
LOSS_WEIGHTS = {"rework": 3.0, "contract_failures": 3.0, "fault_rate": 1.0,
                "tokens": 0.5, "wall_time": 0.5}


class RunError(RuntimeError):
    """The run could not proceed (no spec, no session binary, bad repo)."""


#: hobbes-session's commit-on-exit report line.
EXIT_COMMIT_RE = re.compile(r"hobbes-session: committed (\d+) uncommitted file\(s\) at exit")


@dataclass
class UnitRecord:
    """One unit's observations — §6's per-agent terms."""

    unit: str
    role: str
    session: str
    spawned: bool
    reason: str = ""
    exit: int | None = None
    knowledge_calls: int = 0
    context_faults: int = 0
    exec: dict[str, int] = field(default_factory=lambda: {"allow": 0, "deny": 0, "escalate": 0})
    reflections: list[str] = field(default_factory=list)
    #: What the session handed forward (ADR-091, D8): ``handoff`` when a
    #: reflection was sent with kind ``handoff``; ``reflection-only``
    #: when it reflected but never marked a handoff (the last reflection
    #: is forwarded in its place); ``missing`` when nothing was sent at
    #: all — a prose "reflection" in the transcript is not a handoff.
    handoff: str = ""
    commits: int = 0
    files_changed: list[str] = field(default_factory=list)
    rework_files: list[str] = field(default_factory=list)
    tokens: int | None = None
    wall_seconds: float | None = None
    #: The brief's size and what the brief limit cut from its standing
    #: context (C-45); 0 when nothing was cut.
    brief_chars: int = 0
    brief_cut: int = 0
    #: Files the wrapper committed at session end because the agent had
    #: not (``hobbes-session --commit-on-exit``, ADR-058); 0 when the
    #: agent committed its own work or left nothing.
    exit_commit_files: int = 0

    @property
    def fault_rate(self) -> float:
        return self.context_faults / self.knowledge_calls if self.knowledge_calls else 0.0



def handoff_status(reflected: list[dict]) -> str:
    """How a session's mail reads as a handoff (ADR-091, D8) — see
    :attr:`UnitRecord.handoff`."""
    if not reflected:
        return "missing"
    if any(m.get("kind") == mail.HANDOFF for m in reflected):
        return "handoff"
    return "reflection-only"

def order_units(spec: dict) -> list[str]:
    """Units in contract order: an owner before every unit that
    consumes its declaration; ties and cycles broken by name, and said
    so in the record (a cycle means the partition cut a mutual
    dependency — itself a §6 observation)."""
    names = [u["name"] for u in spec.get("units", [])]
    after: dict[str, set[str]] = {n: set() for n in names}
    for c in spec.get("contracts", []):
        owner = c["owner"]
        other = c["from_unit"] if c["to_unit"] == owner else c["to_unit"]
        if other != owner and other in after and owner in after:
            after[other].add(owner)
    ordered: list[str] = []
    remaining = set(names)
    while remaining:
        ready = sorted(n for n in remaining if not (after[n] & remaining))
        pick = ready[0] if ready else sorted(remaining)[0]  # cycle: by name
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


def _git(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "-q", branch)[0] == 0


def read_flight(session_dir: Path, record: UnitRecord) -> None:
    """Fold a session's flight log into its record."""
    path = Path(session_dir) / "flight.jsonl"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        tool = event.get("tool", "")
        if tool == "exec":
            decision = event.get("decision", "")
            if decision in record.exec:
                record.exec[decision] += 1
        elif tool == "reflect":
            continue
        elif tool:
            record.knowledge_calls += 1
            if event.get("context_fault"):
                record.context_faults += 1


def read_branch(repo: Path, base: str, session: str, manifest_paths: set[str], record: UnitRecord) -> None:
    """What the harvested branch changed, and what of it lies outside
    the unit's manifest (rework)."""
    branch = f"hobbes/{session}"
    if not _branch_exists(repo, branch):
        return
    code, count = _git(repo, "rev-list", "--count", f"{base}..{branch}")
    record.commits = int(count) if code == 0 and count.isdigit() else 0
    code, names = _git(repo, "diff", "--name-only", f"{base}..{branch}")
    if code != 0:
        return
    record.files_changed = sorted(n for n in names.splitlines() if n)
    record.rework_files = [f for f in record.files_changed if f not in manifest_paths]


def loss(records: list[UnitRecord], contract_failures: int) -> dict:
    """§6's loss under the declared weights. Terms the recorder did not
    observe (tokens, wall time) contribute zero and are listed as
    unobserved rather than imputed."""
    rework = sum(len(r.rework_files) for r in records)
    faults = sum(r.context_faults for r in records)
    calls = sum(r.knowledge_calls for r in records)
    fault_rate = faults / calls if calls else 0.0
    tokens = sum(r.tokens for r in records if r.tokens is not None)
    wall = sum(r.wall_seconds for r in records if r.wall_seconds is not None)
    unobserved = [t for t, present in (
        ("tokens", any(r.tokens is not None for r in records)),
        ("wall_time", any(r.wall_seconds is not None for r in records)),
    ) if not present]
    w = LOSS_WEIGHTS
    value = (w["rework"] * rework + w["contract_failures"] * contract_failures
             + w["fault_rate"] * fault_rate + w["tokens"] * tokens / 1000.0
             + w["wall_time"] * wall / 60.0)
    return {
        "value": round(value, 4),
        "terms": {"rework": rework, "contract_failures": contract_failures,
                  "fault_rate": round(fault_rate, 4), "tokens": tokens,
                  "wall_seconds": wall},
        "weights": w,
        "unobserved": unobserved,
        "note": "weights are ADR-051's declared guesses; the value ranks runs "
                "of the same task, it proves nothing about partition quality "
                "(C-35)",
    }


def integrate(repo: Path, base: str, task: str, order: list[str], sessions: dict[str, str]) -> dict:
    """Merge the harvested unit branches onto ``hobbes/<task>`` in
    contract order. A conflict is recorded, the merge aborted, and the
    unit left out — never resolved by guessing."""
    target = f"hobbes/{task}"
    merged, failed = [], []
    # A fresh integration branch at base; a re-run replaces the old one.
    code, out = _git(repo, "branch", "-f", target, base)
    if code != 0:
        return {"branch": target, "error": out, "merged": [], "failed": []}
    # Merge in a detached temporary worktree so the human's checkout is
    # never touched.
    tmp = repo / ".hobbes" / "plans" / task / ".integrate"
    shutil.rmtree(tmp, ignore_errors=True)
    code, out = _git(repo, "worktree", "add", "-q", "--detach", str(tmp), target)
    if code != 0:
        return {"branch": target, "error": out, "merged": [], "failed": []}
    try:
        for unit in order:
            session = sessions.get(unit)
            branch = f"hobbes/{session}" if session else ""
            if not branch or not _branch_exists(repo, branch):
                continue
            code, out = _git(tmp, "-c", "user.name=hobbes", "-c", "user.email=hobbes@local",
                             "merge", "--no-ff", "-q", "-m", f"integrate {unit} ({branch})", branch)
            if code == 0:
                merged.append(unit)
            else:
                _git(tmp, "merge", "--abort")
                failed.append({"unit": unit, "branch": branch, "error": out[-400:]})
        _git(tmp, "branch", "-f", target, "HEAD")
    finally:
        _git(repo, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(tmp, ignore_errors=True)
    return {"branch": target, "merged": merged, "failed": failed}


def review_integration(repo: Path, base: str, head: str) -> dict:
    """``hobbes review base..head`` over the integration branch, as a
    dict; an error is recorded, not raised — the record must exist
    even when the review cannot."""
    try:
        from hobbes.review import build_review, review_to_dict
        review = build_review(repo, base, head)
        out = review_to_dict(review)
        out["needs_attention"] = bool(review.needs_attention)
        return out
    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed silently
        return {"error": f"{type(exc).__name__}: {exc}", "needs_attention": True}


def run_task(
    repo_root: Path,
    task: str,
    dry_run: bool = False,
    only_units: list[str] | None = None,
    session_bin: str | None = None,
    sessions_root: Path | None = None,
    role: str = "implementer",
    extra_args: list[str] | None = None,
    brief_limit: int | None = None,
) -> dict:
    """Run a change-spec end to end; returns the partition record.
    *brief_limit* holds each unit's brief to that many characters (the
    model's context window is finite; a capped unit's context is not —
    C-44/C-45); ``None`` sends the whole standing context."""
    repo = Path(repo_root).resolve()
    spec = load_spec(repo, task)
    task = spec["task"]
    pdir = plan_dir(repo, task)
    tests = artifacts.load_tests(repo) if (repo / ".hobbes/derived/tests.json").is_file() else {"tests": []}
    session_bin = session_bin or os.environ.get("HOBBES_SESSION_BIN") or shutil.which("hobbes-session")
    if not session_bin and not dry_run:
        raise RunError("hobbes-session not found; build go/bin/hobbes-session or set HOBBES_SESSION_BIN")
    sessions_root = Path(sessions_root or os.environ.get("HOBBES_SESSIONS") or Path.home() / ".hobbes" / "sessions")

    roles_written = ensure_role_policies(repo)
    dirs = agents.materialize(pdir, spec, tests, role=role)
    orchestrator = agents.agent_dir(pdir, agents.ORCHESTRATOR)
    code, head = _git(repo, "rev-parse", "HEAD")
    base = head if code == 0 else spec.get("graph_sha", "")
    if spec.get("graph_sha") and base != spec.get("graph_sha"):
        mail.post(orchestrator, "hobbes", f"plan was derived at {spec['graph_sha'][:12]} but HEAD is "
                  f"{base[:12]}: the standing context is stale — re-ingest and re-plan to refresh it",
                  kind="warning")

    contexts = {c["unit"]: c for c in spec.get("contexts", [])}
    test_files = {t["id"]: t.get("file", "") for t in tests.get("tests", [])}
    order = order_units(spec)
    selected = [u for u in order if not only_units or u in only_units]
    records: list[UnitRecord] = []
    sessions: dict[str, str] = {}
    for unit in selected:
        session = f"{task}-{unit.lower()}"
        sessions[unit] = session
        record = UnitRecord(unit=unit, role=role, session=session, spawned=False)
        context = contexts[unit]
        inbox = mail.read(dirs[unit])
        full = agents.render_brief(spec, unit, role, inbox, session)
        brief = agents.render_brief(spec, unit, role, inbox, session, limit=brief_limit)
        brief_path = dirs[unit] / "brief.md"
        brief_path.write_text(brief)
        record.brief_chars = len(brief)
        record.brief_cut = max(0, len(full) - len(brief))
        if context.get("human_first"):
            record.reason = "human-first: not spawned — " + context.get("human_first_reason", "")
            mail.post(orchestrator, unit, record.reason, kind="human-first")
            records.append(record)
            continue
        cmd = [session_bin or "hobbes-session", "start", "--repo", str(repo), "--role", role,
               "--agent-dir", str(dirs[unit]), "--session", session,
               "--sessions", str(sessions_root), "--task-file", str(brief_path)]
        if dry_run:
            cmd.append("--dry-run")
        cmd += list(extra_args or [])
        (dirs[unit] / "spawn.txt").write_text(" ".join(cmd) + "\n")
        if dry_run and not session_bin:
            record.reason = "dry run: command written to spawn.txt, nothing spawned"
            records.append(record)
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True)
        record.spawned = not dry_run
        record.exit = proc.returncode
        (dirs[unit] / "session.log").write_text(proc.stdout + proc.stderr)
        if m := EXIT_COMMIT_RE.search(proc.stderr):
            record.exit_commit_files = int(m.group(1))
        if dry_run:
            record.reason = "dry run: session planned, nothing spawned"
        session_dir = sessions_root / session
        read_flight(session_dir, record)
        reflected = mail.reflections(session_dir)
        record.reflections = [m.get("text", "") for m in reflected]
        record.handoff = handoff_status(reflected)
        mail.fold_back(orchestrator, unit, reflected)
        manifest_paths = {m["path"] for m in context.get("modules", []) if m.get("path")}
        manifest_paths |= {test_files[t] for t in context.get("guarding_tests", []) if test_files.get(t)}
        read_branch(repo, base, session, manifest_paths, record)
        records.append(record)

    integration: dict = {"skipped": "dry run"} if dry_run else integrate(repo, base, task, selected, sessions)
    contract_failures = len(integration.get("failed", []))
    review: dict = {"skipped": "dry run"}
    if not dry_run and integration.get("merged"):
        review = review_integration(repo, base, integration["branch"])

    record_doc = {
        "task": task,
        "proposal": spec.get("proposal", ""),
        "base": base,
        "graph_sha": spec.get("graph_sha", ""),
        "order": order,
        "selected": selected,
        "roles_scaffolded": roles_written,
        "units": [{**r.__dict__, "fault_rate": round(r.fault_rate, 4)} for r in records],
        "contracts": len(spec.get("contracts", [])),
        "integration": integration,
        "review": review,
        "loss": loss(records, contract_failures),
        "standing_context": (
            "commits alter standing context: re-ingest the merged branch "
            f"({integration.get('branch', 'hobbes/' + task)}) to refresh every "
            "manifest; this run did not re-ingest"
        ),
        "c38": "write scope is advisory at path grain — measured as rework_files, not enforced at the mount (C-38)",
    }
    (pdir / RECORD).write_text(json.dumps(record_doc, indent=2, sort_keys=True) + "\n")
    return record_doc


def format_record(record: dict) -> str:
    """The run summary a human reads."""
    lines = [f"run {record['task']} @ {record['base'][:12]}"]
    lines.append(f"  order: {' → '.join(record['order'])}")
    for u in record["units"]:
        head = f"  {u['unit']} [{u['role']}] session {u['session']}: "
        if not u["spawned"]:
            lines.append(head + (u["reason"] or "not spawned"))
            continue
        lines.append(head + f"exit {u['exit']}; {u['commits']} commits, "
                     f"{len(u['files_changed'])} files ({len(u['rework_files'])} outside manifest); "
                     f"knowledge {u['knowledge_calls']} calls / {u['context_faults']} faults; "
                     f"exec allow {u['exec']['allow']} deny {u['exec']['deny']} escalate {u['exec']['escalate']}; "
                     f"{len(u['reflections'])} reflections")
        for text in u["reflections"]:
            lines.append(f"      ↩ {text}")
    integ = record["integration"]
    if "skipped" in integ:
        lines.append(f"  integration: {integ['skipped']}")
    else:
        lines.append(f"  integration: {integ.get('branch')} — merged {integ.get('merged')}"
                     + (f", failed {[f['unit'] for f in integ.get('failed', [])]}" if integ.get("failed") else "")
                     + (f" — {integ['error']}" if integ.get("error") else ""))
    rev = record["review"]
    if "skipped" in rev:
        lines.append(f"  review: {rev['skipped']}")
    elif "error" in rev:
        lines.append(f"  review: error — {rev['error']}")
    else:
        lines.append(f"  review: {'needs attention' if rev.get('needs_attention') else 'clean'}")
    l = record["loss"]
    lines.append(f"  loss (declared weights, C-35): {l['value']} — {l['terms']}"
                 + (f"; unobserved: {', '.join(l['unobserved'])}" if l["unobserved"] else ""))
    lines.append(f"  {record['standing_context']}")
    lines.append(f"  record: .hobbes/plans/{record['task']}/{RECORD}")
    return "\n".join(lines)
