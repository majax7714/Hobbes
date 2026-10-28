"""Run one worker in a role on its own worktree, test it, and merge it (DEC-022).

``dispatch(repo, mapping, role, brief)`` is slice 1 of DEC-022, called from
``hobbes dispatch``; the coordinator's ``dispatch`` MCP tool (slice 2) will
wrap it. One run:

1. a linked worktree under ``$HOBBES_CACHE_DIR/dispatch/<repo>-<hash>/<id>``
   on a new branch ``hobbes/<role>-<id>`` from the mapping's branch;
2. the worker: an ACP session there in the role's agent and route
   (DEC-007; Claude sessions carry DEC-010's hooks), with the knowledge
   tools when the role has them (DEC-008; they answer from the repo's own
   graph, not the worktree's) and the ``hobbes-worker`` MCP server
   (``hobbes.watterson.lead_mcp``, allowed once without asking), sent the role's
   standing prompt, how to report and the brief; its ``report(outcome,
   report)`` tool says done, blocked or review and hands back its own
   account of the work (DEC-022 slice 3a);
3. whatever the worker left uncommitted is committed by the driver, so a
   worker needs no git permissions;
4. no merge if the worker reported blocked, or the branch changed a path
   outside the role's ``writes``;
5. if the mapping's branch moved meanwhile, it is merged into the worker's
   branch in the worktree, so a conflict shows there and never in the
   user's checkout, and the test runs on what the branch would become;
6. the mapping's test command, in the worktree; no merge unless it passes;
7. a pause for review, tested and not merged, when the worker reported
   review or its role sets ``review = true``;
8. the merge into the mapping's branch (``--no-ff``), only when the
   user's checkout is on that branch with no tracked changes; the merged
   branch is deleted.

The ``outcome`` is ``merged``, ``review`` or ``stopped`` (``reason`` says
why). Anything short of a merge keeps the branch; nothing guesses a fix.
The worktree is always removed. The worker's report is its own word; the
rest of the ``Handoff`` (commits, files, test, merge) is the driver's, so a
report of done never skips a check, and a worker that never reports is
taken as done. It is saved as ``<id>.json`` beside the worktrees.

Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hobbes.watterson.roles import Mapping
from hobbes.watterson.session_graph import cache_dir
from hobbes.watterson.snapshot import repo_root

TEST_TAIL_LINES = 40
_GIT_TIMEOUT = 120
MCP_SCRIPT = Path(__file__).with_name("lead_mcp.py")
WORKER_SERVER = "hobbes-worker"
WORKER_TOOLS = ("report",)
OUTCOMES = ("done", "blocked", "review")

REPORT_RULES = """\
When you are done, or cannot go on, call the report tool of the hobbes-worker server once, as your
last step: outcome done (ready to merge), blocked (you could not finish) or review (ready, but the
user should look before a merge), and a report of your work: what you changed and why, what you
checked, and anything left or failing. Do not run git; the driver commits, tests and merges."""


class DispatchError(Exception):
    """The run could not start or its git steps failed; the message says which."""


@dataclass
class Handoff:
    id: str
    role: str
    brief: str
    branch: str
    base: str
    outcome: str = "stopped"
    stop_reason: str | None = None
    asked: str | None = None
    report: str = ""
    summary: str = ""
    commits: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    outside_writes: list[str] = field(default_factory=list)
    target_moved: bool = False
    test: dict[str, Any] | None = None
    merged: bool = False
    reason: str = ""
    record: str = ""


def run_dir(repo: Path) -> Path:
    digest = hashlib.sha256(str(repo).encode()).hexdigest()[:12]
    return cache_dir() / "dispatch" / f"{repo.name}-{digest}"


def worker_prompt(role: str, standing: str, brief: str) -> str:
    return f"[hobbes role: {role}]\n{standing.rstrip()}\n\n[hobbes report]\n{REPORT_RULES}\n\n[hobbes brief]\n{brief}"


def server_titles(server: str, tools: tuple[str, ...]) -> frozenset[str]:
    """The titles harnesses give calls to *tools* on MCP server *server* (Claude's, Codex's)."""
    return frozenset({f"mcp__{server}__{t}" for t in tools} | {f"mcp.{server}.{t}" for t in tools})


def is_server_tool(request, server: str, tools: tuple[str, ...]) -> bool:
    """True when *request* is for one of *tools* on our MCP server *server*."""
    if request.title not in server_titles(server, tools):
        return False
    meta = request.meta if isinstance(request.meta, dict) else {}
    claude = meta.get("claudeCode")
    found = claude.get("mcpServer") if isinstance(claude, dict) else None
    if found is not None and (
        not isinstance(found, dict) or (found.get("name"), found.get("source")) != (server, "dynamic")
    ):
        return False
    raw = request.raw_input
    if isinstance(raw, dict) and "server" in raw:
        return raw.get("server") == server and raw.get("tool") in tools
    return True


def is_worker_tool(request) -> bool:
    return is_server_tool(request, WORKER_SERVER, WORKER_TOOLS)


@contextlib.asynccontextmanager
async def tool_relay(handle: Callable[[str, dict], Awaitable[tuple[str, bool]]]) -> AsyncIterator[str]:
    """A Unix socket in a private temp dir answering ``lead_mcp``'s relayed
    calls with ``handle(tool, arguments) -> (text, is_error)``; yields its path.
    Calls still running when it closes (a dispatch, when the job is
    cancelled) are cancelled: nothing else would end them."""
    running: set[asyncio.Task] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        running.add(task)
        try:
            try:
                request = json.loads(await reader.read() or b"{}")
                text, error = await handle(str(request.get("tool")), request.get("arguments") or {})
            except Exception as exc:  # a bad request must not end the run
                text, error = f"the driver failed: {exc}", True
            except asyncio.CancelledError:
                writer.write(json.dumps({"text": "Interrupted by the user. End your turn.", "error": True}).encode())
                raise
            writer.write(json.dumps({"text": text, "error": error}).encode())
            await writer.drain()
        finally:
            running.discard(task)
            writer.close()

    private = tempfile.mkdtemp(prefix="hobbes-relay-")
    path = str(Path(private) / "s")
    server = await asyncio.start_unix_server(serve, path)
    try:
        yield path
    finally:
        server.close()
        for task in list(running):
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        await server.wait_closed()
        shutil.rmtree(private, ignore_errors=True)


def relay_server(server: str, socket_path: str):
    from hobbes.watterson.providers import StdioMcpServer

    return StdioMcpServer(server, sys.executable, ("-I", "-S", str(MCP_SCRIPT), socket_path, server))


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=_GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchError(f"cannot run git in {root}: {exc}") from exc
    if check and out.returncode != 0:
        raise DispatchError(f"git {args[0]} failed in {root}: {out.stderr.strip() or out.stdout.strip()}")
    return out


def _out(root: Path, *args: str) -> str:
    return _git(root, *args).stdout.strip()


async def dispatch(
    repo: str | Path,
    mapping: Mapping,
    role_name: str,
    brief: str,
    *,
    registry: dict | None = None,
    ask=None,
    allow_unasked: bool = False,
    on_event: Callable[[Any, Any], None] | None = None,
    merge_lock: asyncio.Lock | None = None,
) -> Handoff:
    """One worker run; see the module doc. ``ask`` and ``allow_unasked`` are
    ``RoutePolicy``'s; ``on_event(event, policy)`` sees each session event.
    Runs sharing a ``merge_lock`` take turns at steps 3 to 8 (a merge queue),
    so each is tested on top of what the one before it merged."""
    from hobbes.watterson.providers import ProviderError, get_agent

    root = repo_root(repo)
    role = mapping.role(role_name)
    try:
        spec = get_agent(role.agent, registry)
    except ProviderError as exc:
        raise DispatchError(f"role {role.name}: {exc}") from exc
    prompt = worker_prompt(role.name, role.prompt_text(), brief)
    base = _out(root, "rev-parse", "--verify", f"{mapping.branch}^{{commit}}")
    run_id = uuid.uuid4().hex[:8]
    out_dir = run_dir(root)
    worktree = out_dir / run_id
    handoff = Handoff(run_id, role.name, brief, f"hobbes/{role.name}-{run_id}", base)
    out_dir.mkdir(parents=True, exist_ok=True)
    async def report(tool: str, arguments: dict) -> tuple[str, bool]:
        outcome = str(arguments.get("outcome", ""))
        if tool != "report" or outcome not in OUTCOMES:
            return f"outcome must be one of {', '.join(OUTCOMES)}", True
        handoff.asked, handoff.report = outcome, str(arguments.get("report", ""))
        return "Reported. End your turn now.", False

    _git(root, "worktree", "add", "-q", "-b", handoff.branch, str(worktree), base)
    try:
        async with tool_relay(report) as socket_path:
            handoff.stop_reason, handoff.summary = await run_role_session(
                root, worktree, role, spec, prompt, ask=ask, allow_unasked=allow_unasked, on_event=on_event,
                servers=[relay_server(WORKER_SERVER, socket_path)], allowed=is_worker_tool)
        # Off the event loop (the test may run for minutes; the TUI's server
        # keeps answering), and finished even when cancelled, before the
        # worktree goes.
        async with merge_lock or contextlib.nullcontext():
            steps = asyncio.ensure_future(asyncio.to_thread(_finish, root, worktree, mapping, role, handoff))
            try:
                await asyncio.shield(steps)
            except asyncio.CancelledError:
                await steps
                raise
    finally:
        _git(root, "worktree", "remove", "--force", str(worktree), check=False)
        if handoff.merged:
            _git(root, "branch", "-q", "-d", handoff.branch, check=False)
        record = out_dir / f"{run_id}.json"
        handoff.record = str(record)
        record.write_text(json.dumps(asdict(handoff), indent=2) + "\n")
    return handoff


async def run_role_session(root: Path, cwd: Path, role, spec, prompt: str, *, ask=None,
                           allow_unasked: bool = False, on_event=None, servers=(),
                           allowed: Callable[[Any], bool] | None = None) -> tuple[str | None, str]:
    """One turn of a session in *role* at *cwd*: its stop reason and everything
    it said. *servers* are more MCP servers; *allowed* picks more requests to
    allow once without asking (as DEC-008's knowledge tools are)."""
    from hobbes.watterson import knowledge
    from hobbes.watterson.hooks import SessionHooks
    from hobbes.watterson.permissions import Route, RoutePolicy, load_test_files, modes_for
    from hobbes.watterson.providers import AgentSession, TextChunk, TurnEnded

    route = Route(role.route)
    proxy = knowledge.find_proxy() if role.knowledge else None
    servers = [knowledge.server(root, proxy)] * bool(proxy) + list(servers)
    test_files = load_test_files(root / ".hobbes" / "derived")

    def own_tool(request) -> bool:
        return bool(proxy) and knowledge.is_own_tool(request) or allowed is not None and allowed(request)

    policy = RoutePolicy(route, cwd, ask=ask, allow_unasked=allow_unasked, test_files=test_files,
                         allowed=own_tool if servers else None)
    text: list[str] = []
    stop_reason = None
    async with contextlib.AsyncExitStack() as stack:
        on_permission, meta = policy, None
        if spec.name == "claude":
            hooks = await stack.enter_async_context(
                SessionHooks(route, cwd, agent=spec.name, test_files=test_files))
            on_permission, meta = hooks.observe(policy), hooks.meta()
        session = await stack.enter_async_context(AgentSession(
            spec, cwd=cwd, on_permission=on_permission, modes=modes_for(route, spec.name),
            mcp_servers=servers, meta=meta))
        async with contextlib.aclosing(session.prompt(prompt)) as events:
            async for event in events:
                if on_event is not None:
                    on_event(event, policy)
                if isinstance(event, TextChunk):
                    text.append(event.text)
                elif isinstance(event, TurnEnded):
                    stop_reason = event.stop_reason
    return stop_reason, "".join(text)


def _finish(root: Path, worktree: Path, mapping: Mapping, role, handoff: Handoff) -> None:
    """Steps 3 to 8 of the module doc; sets ``outcome`` and ``merged`` or ``reason``."""
    _git(worktree, "add", "-A")
    if _git(worktree, "diff", "--cached", "--quiet", check=False).returncode != 0:
        subject = handoff.brief.strip().splitlines()[0][:72] if handoff.brief.strip() else "work"
        _git(worktree, "commit", "-q", "-m", f"{role.name}: {subject}",
             "-m", f"Hobbes-Dispatch: {handoff.id}")
    handoff.commits = _out(worktree, "rev-list", "--reverse", f"{handoff.base}..HEAD").split()
    handoff.files = _out(worktree, "diff", "--name-only", handoff.base, "HEAD").split("\n")
    handoff.files = [f for f in handoff.files if f]
    if handoff.stop_reason != "end_turn":
        handoff.reason = f"the worker stopped: {handoff.stop_reason}"
        return
    if handoff.asked == "blocked":
        handoff.reason = "the worker reported it is blocked"
        return
    if not handoff.commits:
        handoff.reason = "the worker changed nothing"
        return
    handoff.outside_writes = [f for f in handoff.files if not role.may_write(f)]
    if handoff.outside_writes:
        handoff.reason = f"changed paths outside role {role.name}'s writes: {', '.join(handoff.outside_writes)}"
        return

    target = _out(root, "rev-parse", "--verify", f"{mapping.branch}^{{commit}}")
    if target != handoff.base:
        handoff.target_moved = True
        merged = _git(worktree, "merge", "--no-edit", "-q", target, check=False)
        if merged.returncode != 0:
            _git(worktree, "merge", "--abort", check=False)
            handoff.reason = f"{mapping.branch} moved and conflicts with the worker's branch"
            return

    handoff.test = _run_test(worktree, mapping.test)
    if handoff.test["exit"] != 0:
        handoff.reason = f"the test command failed (exit {handoff.test['exit']})"
        return
    if handoff.asked == "review" or role.review:
        handoff.outcome = "review"
        handoff.reason = "paused for review: " + (
            "the worker asked" if handoff.asked == "review" else f"role {role.name} sets review")
        return

    current = _git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if current != mapping.branch:
        handoff.reason = f"your checkout is on {current or 'a detached HEAD'}, not {mapping.branch}"
        return
    if _out(root, "status", "--porcelain", "--untracked-files=no"):
        handoff.reason = f"your checkout of {mapping.branch} has uncommitted changes"
        return
    merged = _git(root, "merge", "--no-ff", "-q", "-m",
                  f"Merge {handoff.branch} ({role.name}, dispatch {handoff.id})", handoff.branch, check=False)
    if merged.returncode != 0:
        _git(root, "merge", "--abort", check=False)
        handoff.reason = f"the merge into {mapping.branch} failed: {merged.stderr.strip() or merged.stdout.strip()}"
        return
    handoff.outcome, handoff.merged = "merged", True


def _run_test(worktree: Path, command: tuple[str, ...]) -> dict[str, Any]:
    try:
        out = subprocess.run(command, cwd=worktree, capture_output=True, text=True)
    except OSError as exc:
        return {"command": list(command), "exit": 127, "tail": str(exc)}
    lines = (out.stdout + out.stderr).splitlines()
    return {"command": list(command), "exit": out.returncode, "tail": "\n".join(lines[-TEST_TAIL_LINES:])}
