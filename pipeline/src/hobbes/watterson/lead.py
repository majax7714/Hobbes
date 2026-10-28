"""One job through the coordinator: plan, approval, workers, docs (DEC-022 slice 2; parallel workers).

``run_job(repo, mapping, job)`` is what ``hobbes job`` runs for each job.
It needs the user's checkout on the mapping's branch with no tracked
changes, since workers merge into it. Then:

1. a Unix socket in a private temp dir, and a session in the mapping's
   ``coordinator`` role at the user's checkout, with the ``hobbes-lead``
   MCP server (``hobbes.watterson.lead_mcp``) relaying its tools here; those tools
   are allowed once without asking, as DEC-008's knowledge tools are;
2. the prompt: the role's standing prompt, the loop's rules, the job;
3. the tools, answered here (``Lead.handle``):
   - ``propose_plan(plan)`` asks the user through ``approve``; with none
     (no terminal) it is refused;
   - ``dispatch(role, brief)`` queues one worker (``hobbes.watterson.dispatch``) and
     returns at once with its ticket. Up to the mapping's ``workers`` run
     at a time; the rest start in order as slots free. Their finish steps
     (main merged in, the test, the merge) take turns, so each branch is
     tested on top of the work merged before it. Refused before an
     approved plan, for the coordinator's own role or an unknown one, and
     once the checkout has tracked changes (a merge would be refused);
   - ``wait()`` returns once every dispatched worker is done, with the
     handoffs not returned before, as JSON (each: its outcome, merged,
     stopped or review, and the worker's report);
   - ``finish(summary)`` records the summary; refused while workers run;
4. when the turn ends, workers still running are waited for; then what
   the coordinator changed in the checkout is committed as
   ``docs: <job>`` if every path is within its role's ``writes``;
   otherwise it is left and the result says why. A cancelled job cancels
   its workers, queued and running;
5. the session closes. Nothing carries over to the next job: a fresh
   session reads the docs again.

The ``JobResult`` is saved as ``job-<id>.json`` beside the dispatch
records. Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hobbes.watterson.dispatch import (
    MCP_SCRIPT, DispatchError, _git, _out, dispatch, is_server_tool, relay_server, run_dir, run_role_session,
    tool_relay,
)
from hobbes.watterson.roles import Mapping, RolesError
from hobbes.watterson.snapshot import repo_root

SERVER = "hobbes-lead"
TOOLS = ("propose_plan", "dispatch", "wait", "finish")

#: Approve a plan: (approved, comment for the coordinator).
Approve = Callable[[str], Awaitable[tuple[bool, str]]]
#: What the user may answer to a plan, on the terminal or in the TUI.
APPROVAL_HINT = "y, y <comment>, or what to change"

LOOP_RULES = """\
You coordinate this job; you do not write the code. Through the hobbes-lead tools:
1. Read what you need, then call propose_plan with the units of work, each with a role.
2. Once approved, call dispatch for each unit that can start now, each with a self-contained
   brief. dispatch returns at once: up to {workers} workers run at a time and the rest wait in
   a queue. Their work merges one at a time, each tested on top of what merged before it, so
   give units that change the same files to one worker, or dispatch the later one after wait.
3. Call wait: it returns once every dispatched worker is done, with their handoffs. Each
   outcome is merged, stopped (with the reason) or review (kept on its branch for the user),
   with the worker's report. Dispatch a unit that needs another unit's work after wait.
4. Only after wait has returned every handoff, update the docs the work changed (your files only).
5. Call finish with a short summary. Do not run git; the driver commits your docs."""


def parse_approval(answer: str) -> tuple[bool, str]:
    """``y`` or ``yes`` approves, with what follows as a comment; empty,
    ``n`` or ``no`` declines; anything else declines with itself as the change."""
    answer = answer.strip()
    word, _, comment = answer.partition(" ")
    if word.lower() in ("y", "yes"):
        return True, comment.strip()
    return False, "" if word.lower() in ("", "n", "no") else answer


def lead_prompt(role: str, standing: str, job: str, workers: int = 1) -> str:
    rules = LOOP_RULES.format(workers=workers)
    return f"[hobbes role: {role}]\n{standing.rstrip()}\n\n[hobbes loop]\n{rules}\n\n[hobbes job]\n{job}"


def is_lead_tool(request) -> bool:
    """True when *request* is for one of our tools on our ``hobbes-lead`` server."""
    return is_server_tool(request, SERVER, TOOLS)


@dataclass
class JobResult:
    id: str
    job: str
    role: str
    stop_reason: str | None = None
    said: str = ""
    plans: list[dict[str, Any]] = field(default_factory=list)
    dispatches: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    docs_files: list[str] = field(default_factory=list)
    docs_commit: str | None = None
    reason: str = ""
    record: str = ""

    @property
    def approved(self) -> bool:
        return any(plan["approved"] for plan in self.plans)


@dataclass
class Worker:
    """What a caller gives one dispatched worker (``on_dispatch``'s answer):
    its own ``ask`` and ``on_event`` (else the job's), ``start()`` as it
    leaves the queue (in the worker's task), and ``done(record, error)``
    once it is done or failed (a record) or cancelled (an error), queued or
    running."""
    ask: Any = None
    on_event: Any = None
    start: Callable[[], None] | None = None
    done: Callable[[dict | None, BaseException | None], None] | None = None


def stopped(ticket: int, role: str, brief: str, reason: str) -> dict[str, Any]:
    """The handoff of a dispatch that could not run."""
    return {"ticket": ticket, "role": role, "brief": brief, "branch": "", "outcome": "stopped",
            "merged": False, "reason": reason, "report": "", "record": ""}


class Lead:
    """The driver's side of the coordinator's tools for one job."""

    def __init__(self, root: Path, mapping: Mapping, result: JobResult, *, approve: Approve | None,
                 registry: dict | None = None, ask=None, allow_unasked: bool = False,
                 on_event=None, on_dispatch: Callable[[str, str], Worker | None] | None = None) -> None:
        """*ask* and *on_event* are the workers' (``hobbes.watterson.dispatch``) unless
        ``on_dispatch(role, brief)``, called as each is queued, gives its own."""
        self.root, self.mapping, self.result = root, mapping, result
        self.approve, self.registry = approve, registry
        self.ask, self.allow_unasked, self.on_event, self.on_dispatch = ask, allow_unasked, on_event, on_dispatch
        self._slots = asyncio.Semaphore(mapping.workers)
        self._merges = asyncio.Lock()  # the merge queue: one finish at a time
        self._tickets = 0
        #: ticket -> the worker's task, queued or running
        self.running: dict[int, asyncio.Task] = {}
        self._unread: list[dict[str, Any]] = []

    async def handle(self, tool: str, arguments: dict) -> tuple[str, bool]:
        """Answer one tool call: (text for the coordinator, is it an error)."""
        if tool == "propose_plan":
            return await self._propose(str(arguments.get("plan", "")))
        if tool == "dispatch":
            return self._dispatch(str(arguments.get("role", "")), str(arguments.get("brief", "")))
        if tool == "wait":
            return await self._wait()
        if tool == "finish":
            if self.running:
                return f"{len(self.running)} worker(s) are still running; call wait first.", True
            self.result.summary = str(arguments.get("summary", ""))
            return "Finished. End your turn now.", False
        return f"unknown tool {tool!r}", True

    async def _propose(self, plan: str) -> tuple[str, bool]:
        if not plan.strip():
            return "The plan is empty.", True
        if self.approve is None:
            self.result.plans.append({"plan": plan, "approved": False, "comment": "no one to approve it"})
            return "No one can approve a plan here (not a terminal). End your turn.", True
        approved, comment = await self.approve(plan)
        self.result.plans.append({"plan": plan, "approved": approved, "comment": comment})
        if approved:
            return "Approved." + (f" The user adds: {comment}" if comment else ""), False
        return "Not approved." + (f" The user says: {comment}" if comment else " Revise the plan or end your turn."), False

    def _dispatch(self, role: str, brief: str) -> tuple[str, bool]:
        if not self.result.approved:
            return "Propose a plan and have it approved before dispatching.", True
        if role == self.mapping.coordinator:
            return f"{role} is the coordinator's own role; dispatch to a worker role.", True
        try:
            self.mapping.role(role)
        except RolesError as exc:
            return f"The dispatch could not run: {exc}", True
        if not brief.strip():
            return "The brief is empty.", True
        if _out(self.root, "status", "--porcelain", "--untracked-files=no"):
            return ("The checkout has uncommitted changes, so the work could not merge. "
                    "Dispatch before editing files."), True
        self._tickets += 1
        ticket = self._tickets
        hooks = (self.on_dispatch(role, brief) if self.on_dispatch is not None else None) or Worker()
        busy = len(self.running)
        task = asyncio.create_task(self._work(ticket, role, brief, hooks))
        self.running[ticket] = task
        task.add_done_callback(lambda done: self._settled(ticket, hooks, done))
        where = ("started" if busy < self.mapping.workers
                 else f"queued behind {busy} worker(s) (at most {self.mapping.workers} at a time)")
        return f"Dispatched #{ticket} to {role}: {where}. Call wait for the handoffs.", False

    async def _work(self, ticket: int, role: str, brief: str, hooks: Worker) -> dict[str, Any]:
        async with self._slots:
            if hooks.start is not None:
                hooks.start()
            try:
                handoff = await dispatch(
                    self.root, self.mapping, role, brief, registry=self.registry,
                    ask=self.ask if hooks.ask is None else hooks.ask, allow_unasked=self.allow_unasked,
                    on_event=self.on_event if hooks.on_event is None else hooks.on_event,
                    merge_lock=self._merges)
            except (RolesError, DispatchError) as exc:
                return stopped(ticket, role, brief, f"the dispatch could not run: {exc}")
            except Exception as exc:  # the harness failed: a handoff that says so, not a lost task
                return stopped(ticket, role, brief, f"the worker failed: {exc}")
        return {"ticket": ticket, **asdict(handoff)}

    def _settled(self, ticket: int, hooks: Worker, task: asyncio.Task) -> None:
        self.running.pop(ticket, None)
        record = None if task.cancelled() else task.result()
        if record is not None:
            self.result.dispatches.append(record)
            self._unread.append(record)
        if hooks.done is not None:
            hooks.done(record, asyncio.CancelledError() if record is None else None)

    async def _wait(self) -> tuple[str, bool]:
        while self.running:
            await asyncio.wait(list(self.running.values()))
        if not self._unread:
            return "Nothing to wait for: every handoff has been returned.", False
        records, self._unread = self._unread, []
        return json.dumps([{k: v for k, v in r.items() if k != "record"} for r in records], indent=2), False

    async def settle(self) -> None:
        """Wait for every worker still queued or running."""
        while self.running:
            await asyncio.wait(list(self.running.values()))

    async def stop(self) -> None:
        """Cancel every worker still queued or running, and wait for them to go."""
        tasks = list(self.running.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _changed(root: Path) -> list[str]:
    """Paths with tracked changes or untracked, not ignored, in the checkout."""
    lines = _git(root, "status", "--porcelain", "-z", "--untracked-files=all").stdout.split("\0")
    paths, skip = [], False
    for line in lines:
        if skip:  # the old path of a rename
            skip = False
            continue
        if line:
            paths.append(line[3:])
            skip = line[0] in "RC"
    return paths


def commit_docs(root: Path, role, before: set[str], job_id: str, job: str) -> tuple[list[str], str | None, str]:
    """Commit what the coordinator changed when it is all within its writes:
    (files, commit or None, reason when not committed)."""
    files = sorted(set(_changed(root)) - before)
    if not files:
        return [], None, ""
    outside = [f for f in files if not role.may_write(f)]
    if outside:
        return files, None, f"left uncommitted: outside role {role.name}'s writes: {', '.join(outside)}"
    subject = job.strip().splitlines()[0][:66] if job.strip() else "job"
    _git(root, "add", "--", *files)
    _git(root, "commit", "-q", "-m", f"docs: {subject}", "-m", f"Hobbes-Job: {job_id}", "--", *files)
    return files, _out(root, "rev-parse", "HEAD"), ""


async def run_job(repo: str | Path, mapping: Mapping, job: str, *, approve: Approve | None,
                  registry: dict | None = None, ask=None, allow_unasked: bool = False,
                  on_event=None, on_dispatch=None) -> JobResult:
    """One job; see the module doc. Raises RolesError or DispatchError when it
    cannot start. *ask* and *on_event* serve the coordinator's session and
    the workers' unless ``on_dispatch`` gives a worker its own (``Worker``)."""
    from hobbes.watterson.providers import ProviderError, get_agent

    root = repo_root(repo)
    if not mapping.coordinator:
        raise RolesError(f"{mapping.path}: no coordinator role named")
    role = mapping.role(mapping.coordinator)
    try:
        spec = get_agent(role.agent, registry)
    except ProviderError as exc:
        raise DispatchError(f"role {role.name}: {exc}") from exc
    current = _git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if current != mapping.branch:
        raise DispatchError(f"your checkout is on {current or 'a detached HEAD'}, not {mapping.branch}")
    if _out(root, "status", "--porcelain", "--untracked-files=no"):
        raise DispatchError(f"your checkout of {mapping.branch} has uncommitted changes")
    prompt = lead_prompt(role.name, role.prompt_text(), job, mapping.workers)
    result = JobResult(uuid.uuid4().hex[:8], job, role.name)
    lead = Lead(root, mapping, result, approve=approve, registry=registry, ask=ask,
                allow_unasked=allow_unasked, on_event=on_event, on_dispatch=on_dispatch)
    before = set(_changed(root))
    try:
        async with tool_relay(lead.handle) as socket_path:
            result.stop_reason, result.said = await run_role_session(
                root, root, role, spec, prompt, ask=ask, allow_unasked=allow_unasked,
                on_event=on_event, servers=[relay_server(SERVER, socket_path)], allowed=is_lead_tool)
        await lead.settle()  # workers the coordinator did not wait for land before its docs
        result.docs_files, result.docs_commit, result.reason = commit_docs(root, role, before, result.id, job)
    finally:
        await lead.stop()  # only when cancelled or failed: the queue and the running workers go
        out_dir = run_dir(root)
        out_dir.mkdir(parents=True, exist_ok=True)
        record = out_dir / f"job-{result.id}.json"
        result.record = str(record)
        record.write_text(json.dumps(asdict(result), indent=2) + "\n")
    return result
