"""The ``watterson`` command-line interface: the dev environment's CLI (ADR-181).

``ingest`` and ``render`` are ``hobbes.cli``'s own handlers: one ingest,
whichever command runs it. This CLI differs from ``hobbes`` only in its cache
default, ``~/.watterson/cache`` (DEC-003, kept by ADR-181).
``levels`` prints the tiered folder views of DEC-014; ``review`` writes them
as a stamped HTML page and opens it (``hobbes.watterson.review``, DEC-018),
which is not ``hobbes review``'s concept-level PR review (ADR-025).

``freshness`` compares the graph's stamped commit with the repo's HEAD
(``hobbes.watterson.freshness``, DEC-005); ``ask`` runs the same check as its
session starts.

``agents``, ``ask`` and ``complete`` reach model providers through
``hobbes.watterson.providers`` (DEC-004): list the ACP agent registry, stream one
prompt to an agent harness, or stream one raw API completion. Their
handlers import ``hobbes.watterson.providers`` lazily, so ``ingest`` never loads the
ACP SDK or any-llm.

``tui``, ``chat``, ``roles``, ``dispatch`` and ``job`` are the app, the live
chat and the agent roles (DEC-013, DEC-009, DEC-022); ``dispatch`` here runs
one role's worker, not Shanks (``hobbes dispatch``, ADR-107).

Moved from watterson-environment@a65b6b1 ``pipeline/src/hobbes/cli.py``
(ADR-181). At import it loads ``hobbes.cli`` (for the shared handlers);
each command imports its own modules when it runs.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from hobbes import __version__

# The repo-root detection, the ingest summary and both handlers are
# hobbes.cli's own: one ingest, whichever command runs it.
from hobbes.cli import (
    _cmd_ingest,
    _cmd_render,
    _detect_repo_root,
    _repo_root_from,
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the watterson argument parser (exposed for tests)."""
    parser = argparse.ArgumentParser(
        prog="watterson",
        description="Hobbes: deterministic code-graph extraction. "
                    "With no command, opens the app (`hobbes tui`) on the repo here.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    ingest_parser = sub.add_parser(
        "ingest",
        help="run the deterministic extractors, write .hobbes/derived/",
        description=(
            "Extract the repo's knowledge skeleton (module graph, symbols, "
            "routes, test map) into SHA-stamped JSON artifacts under "
            ".hobbes/derived/."
        ),
    )
    ingest_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    ingest_parser.add_argument(
        "--uncontained", action="store_true",
        help="run lane B on this host instead of the sandbox image — repo code "
             "executes here; disclosed at ingest and stamped into graph.json (ADR-092)",
    )
    ingest_parser.add_argument(
        "--tf-plan",
        help="a `terraform show -json` file to enrich the infra graph "
        "(never .tfstate); only its root module's resources are read, and "
        "its edges cite the plan at line 1 (C-193)",
    )

    render_parser = sub.add_parser(
        "render",
        help="print the ingested module graph as Mermaid",
        description=(
            "Reads .hobbes/derived/graph.json (run `hobbes ingest` first) and "
            "prints a module-level Mermaid flowchart to stdout."
        ),
    )
    render_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )

    levels_parser = sub.add_parser(
        "levels",
        help="tiered views of the ingested graph, grouped by folder (DEC-014)",
        description=(
            "Reads .hobbes/derived/ (run `hobbes ingest` first) and prints one "
            "view of the level model: a folder's boxes (at most 12) and the "
            "edges between them. Start at the repo view and open a box with "
            "--view <its id>."
        ),
    )
    levels_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    levels_parser.add_argument("--view", help="the view to print (default: the repo view)")
    levels_parser.add_argument("--format", choices=("text", "mermaid", "json"), default="text",
                               help="json prints the whole document")
    levels_parser.add_argument("--list", action="store_true", help="list the view ids")

    review_parser = sub.add_parser(
        "review",
        help="the level views as a stamped HTML page, opened in the browser (DEC-018)",
        description=(
            "Reads .hobbes/derived/ (run `hobbes ingest` first) and writes one "
            "self-contained page of the level views, stamped with the commit, to "
            "~/.watterson/review/<repo>@<sha7>.html ($HOBBES_REVIEW_DIR), then opens it."
        ),
    )
    review_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    review_parser.add_argument("--no-open", action="store_true", help="write the page and print its path only")

    freshness_parser = sub.add_parser(
        "freshness",
        help="is the Hobbes graph current? compare its stamped commit with HEAD",
        description=(
            "Compare the commit stamped into .hobbes/derived/ by the last ingest "
            "with the repo's HEAD, and tag an uncommitted tree as dirty "
            "(informational only). Exit 0 fresh, 1 stale/missing/unreadable, "
            "2 not a git repo or no commits (DEC-005)."
        ),
    )
    freshness_parser.add_argument("--repo", help="repo path (default: here)")

    agents_parser = sub.add_parser(
        "agents",
        help="list the known ACP agents and whether each command is available",
        description=(
            "List the ACP agent registry: the built-ins plus entries from "
            "$HOBBES_AGENTS_FILE (default ~/.watterson/agents.toml)."
        ),
    )
    agents_parser.add_argument(
        "--check", action="store_true",
        help="compare the adapters locked in adapters/ against npm and report "
             "the gap (never updates); exit 0 current, 1 action suggested, "
             "2 npm unreachable",
    )

    ask_parser = sub.add_parser(
        "ask",
        help="send one prompt to an ACP agent and stream its reply",
        description=(
            "Start an agent harness over ACP, send one prompt, and stream the "
            "reply to stdout (tool calls and permission requests go to "
            "stderr). The harness uses its own login and runs its own tools. "
            "As the session starts, the repo's Hobbes graph is checked against "
            "HEAD (DEC-005): a stale or missing graph is offered for "
            "re-extraction on a terminal, and warned about otherwise. "
            "Permission requests are decided by --route (DEC-007): never "
            "allowed by Hobbes itself; asked on a terminal, with what each "
            "touches, and denied otherwise unless --allow-permissions. "
            "With --repo, Hobbes's knowledge tools are attached (DEC-008): "
            "hobbes-proxy --knowledge-only from $HOBBES_PROXY or PATH, its "
            "tools allowed once without asking."
        ),
    )
    _add_session_options(ask_parser)
    ask_parser.add_argument("prompt", help="the prompt text")

    chat_parser = sub.add_parser(
        "chat",
        help="a multi-turn session with an ACP agent, one prompt per line",
        description=(
            "Like ask, but the session stays open: each line is a turn. "
            "Ctrl-C cancels the running turn; Ctrl-D, or Ctrl-C at the "
            "prompt, ends the session. With --repo and the knowledge tools "
            "on, the graph is re-extracted from a snapshot between turns "
            "(lane A only), and each prompt is prefixed with which graph the "
            "tools answer from and which files changed since it (DEC-009)."
        ),
    )
    _add_session_options(chat_parser)

    tui_parser = sub.add_parser(
        "tui",
        help="the opencode TUI on a Hobbes server (DEC-013)",
        description=(
            "Start the Hobbes server on loopback and the pinned opencode v2 TUI "
            "(tui/) against it. The TUI's agents are Hobbes's permission routes "
            "(guarded, manual) and its models are the ACP agents in the registry. "
            "Server log: $HOBBES_CACHE_DIR/tui/server.log."
        ),
    )
    tui_parser.add_argument("--repo", help="repo root (default: auto-detected via .git, else this folder)")
    tui_parser.add_argument("--serve-only", action="store_true",
                            help="run only the server and print how to attach a TUI")
    tui_parser.add_argument("--port", type=int, default=0, help="server port (default: any free one)")

    roles_parser = sub.add_parser(
        "roles",
        help="list and check the repo's agent roles (DEC-022)",
        description=(
            "Read <repo>/.hobbes/roles.toml, the repo's agent roles and their "
            "mapping, and report each role and its prompt file. Keeps .hobbes/ "
            "out of git (.git/info/exclude) first. With --edit, a model writes or "
            "changes the mapping as asked (DEC-023), through a checked save, then "
            "the result is listed. Exit 0 saved (or listed), 1 not, 2 could not run."
        ),
    )
    roles_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    roles_parser.add_argument("--edit", metavar="REQUEST",
                              help="have a model write or change the mapping, e.g. \"a coordinator and an implementer for src/\"")
    roles_parser.add_argument("--agent", default="claude", help="the mapper's agent with --edit (default: claude)")
    roles_parser.add_argument(
        "--allow-permissions", action="store_true",
        help="with --edit: allow, once each and without asking, what would be asked; default: "
             "ask on a terminal, deny otherwise",
    )

    dispatch_parser = sub.add_parser(
        "dispatch",
        help="run one worker in a role on its own worktree, test it, merge it (DEC-022)",
        description=(
            "Start a worktree on a new branch from the mapping's branch, run the "
            "role's agent there on the brief, commit what it left, refuse paths "
            "outside the role's writes, run the mapping's test command, and merge "
            "into the branch when it passes and your checkout is on it and clean. "
            "The worker reports done, blocked or review; review (or a role with "
            "review = true) keeps the tested branch unmerged. Otherwise the branch is "
            "kept and the reason printed. Exit 0 merged or paused for review, 1 "
            "stopped, 2 could not run."
        ),
    )
    dispatch_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    dispatch_parser.add_argument("--role", required=True, help="a role from .hobbes/roles.toml")
    dispatch_parser.add_argument(
        "--allow-permissions", action="store_true",
        help="allow, once each and without asking, what would be asked "
             "(guarded still denies agent permission-config edits); default: "
             "ask on a terminal, deny otherwise",
    )
    dispatch_parser.add_argument("brief", help="what the worker is to do")

    job_parser = sub.add_parser(
        "job",
        help="run a job through the coordinator role: plan, approval, workers, docs (DEC-022)",
        description=(
            "Start a session in the mapping's coordinator role at your checkout, "
            "with tools to propose a plan (you approve it here), dispatch workers "
            "(each tested and merged as with `hobbes dispatch`) and finish. What the "
            "coordinator changed is committed as docs when it is within its role's "
            "writes. Each job gets a fresh session; with no job given, one job per "
            "line. Needs a terminal to approve plans. Exit 0 finished with no "
            "dispatch stopped, 1 otherwise, 2 could not start."
        ),
    )
    job_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    job_parser.add_argument(
        "--allow-permissions", action="store_true",
        help="allow, once each and without asking, what the sessions would ask "
             "(guarded still denies agent permission-config edits)",
    )
    job_parser.add_argument("job", nargs="?", help="the job; default: read one per line")

    complete_parser = sub.add_parser(
        "complete",
        help="stream one raw model API completion (keys from env)",
        description=(
            "Send one prompt straight to a model API through any-llm and "
            "stream the reply. Keys come from the provider's environment "
            "variable (ANTHROPIC_API_KEY, OPENAI_API_KEY)."
        ),
    )
    complete_parser.add_argument(
        "--model", required=True, help="provider:model, e.g. anthropic:<model-id>"
    )
    complete_parser.add_argument("--system", help="a system prompt")
    complete_parser.add_argument("--max-tokens", type=int, help="cap on reply tokens")
    complete_parser.add_argument("prompt", help="the prompt text")

    return parser


def _add_session_options(parser: argparse.ArgumentParser) -> None:
    """The options ``ask`` and ``chat`` share."""
    parser.add_argument("--agent", required=True, help="agent name (see `hobbes agents`)")
    parser.add_argument(
        "--route", choices=("guarded", "manual"), default="guarded",
        help="how permission requests are decided (DEC-007): guarded (default) "
             "turns the harness's own judge on and denies edits of an agent's "
             "permission config; manual uses the most-asking modes. Both ask "
             "on a terminal for the rest",
    )
    parser.add_argument(
        "--allow-permissions", action="store_true",
        help="allow, once each and without asking, what would be asked "
             "(guarded still denies agent permission-config edits); default: "
             "ask on a terminal, deny otherwise",
    )
    parser.add_argument(
        "--repo", "--cwd", dest="repo",
        help="the repo the session works in; the agent starts there (default: here)",
    )
    refresh = parser.add_mutually_exclusive_group()
    refresh.add_argument(
        "--refresh", action="store_true",
        help="re-extract a stale or missing Hobbes graph without asking",
    )
    refresh.add_argument(
        "--no-refresh", action="store_true",
        help="skip the Hobbes graph freshness check",
    )
    parser.add_argument(
        "--no-knowledge", action="store_true",
        help="do not attach Hobbes's knowledge tools (DEC-008)",
    )


def _level_document(repo_root: Path) -> dict:
    """The level model of an ingested repo (DEC-014); raises ArtifactError with no graph."""
    from hobbes import artifacts
    from hobbes.watterson import levels

    graph = artifacts.load_graph(repo_root)
    extras = {}
    for name in ("tests", "interfaces"):
        try:
            extras[name] = artifacts.load(repo_root, f"{name}.json")
        except artifacts.ArtifactError:
            extras[name] = None
    return levels.build(graph, repo_root, extras["tests"], extras["interfaces"])


def _cmd_review(args: argparse.Namespace) -> int:
    """Write the review page (DEC-018) and open it."""
    import webbrowser

    from hobbes import artifacts
    from hobbes.watterson import review

    repo_root = _repo_root_from(args)
    try:
        doc = _level_document(repo_root)
    except artifacts.ArtifactError as exc:
        print(f"hobbes review: {exc}", file=sys.stderr)
        return 1
    try:
        path = review.write(doc, repo_root)
    except review.AppMissing as exc:
        print(f"hobbes review: {exc}", file=sys.stderr)
        return 1
    print(path)
    if not args.no_open and not webbrowser.open(path.as_uri()):
        print("hobbes review: no browser found; open the file above", file=sys.stderr)
    return 0


def _cmd_levels(args: argparse.Namespace) -> int:
    """Print a view of the level model (DEC-014)."""
    from hobbes import artifacts
    from hobbes.watterson import levels

    repo_root = _repo_root_from(args)
    try:
        doc = _level_document(repo_root)
    except artifacts.ArtifactError as exc:
        print(f"hobbes levels: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(doc, indent=2))
        return 0
    if args.list:
        for view in doc["views"].values():
            print(f"{'  ' * view['level']}{view['id'] or '(repo)'}  ({len(view['boxes'])} boxes)")
        return 0
    view = doc["root_view"] if args.view is None else args.view.rstrip("/")
    if view not in doc["views"]:
        print(f"hobbes levels: no view {args.view!r}; see --list", file=sys.stderr)
        return 1
    render = levels.to_mermaid if args.format == "mermaid" else levels.to_text
    print(render(doc, view), end="")
    return 0


def _cmd_freshness(args: argparse.Namespace) -> int:
    """Report whether the repo's Hobbes graph matches its HEAD."""
    from hobbes.watterson.freshness import check_freshness, exit_code

    check = check_freshness(args.repo or Path.cwd())
    code = exit_code(check)
    if code == 2:
        print(f"hobbes: {check.summary()}", file=sys.stderr)
        return code
    print(check.summary())
    for note in check.freshness.notes:
        print(f"  {note}")
    return code


def _cmd_agents(args: argparse.Namespace) -> int:
    """List the agent registry with each command's availability."""
    if args.check:
        return _cmd_agents_check()
    from hobbes.watterson.providers import ProviderError, agents_file, load_registry

    try:
        registry = load_registry()
    except ProviderError as exc:
        print(f"hobbes: {exc}", file=sys.stderr)
        return 1
    width = max(len(name) for name in registry)
    for name, spec in sorted(registry.items()):
        found = spec.executable()
        if found:
            state = "available" if found == spec.command[0] else f"available ({found})"
        else:
            where = "not found" if os.sep in spec.command[0] else "not on PATH"
            state = f"missing: {spec.command[0]} {where}"
            if spec.install_hint:
                state += f"; {spec.install_hint}"
        print(f"{name:<{width}}  {' '.join(spec.command)}")
        print(f"{'':<{width}}    {state}; {spec.source}")
    print(f"overrides: {agents_file()}")
    return 0


def _cmd_agents_check() -> int:
    """Report how far each locked adapter's pin is behind npm."""
    from hobbes.watterson.providers.staleness import COOLDOWN, check_adapters, exit_code

    checks = check_adapters()
    for check in checks:
        f, h = check.freshness, check.harness
        print(f"{check.adapter.agent}  {f.subject}")
        print(f"    pinned {f.pinned or '-'}, installed {f.current or '-'}: {f.status}")
        if f.latest:
            when = f" (published {f.latest_at:%Y-%m-%d})" if f.latest_at else ""
            behind = f"; pin behind by {f.behind_by}" if f.behind_by else ""
            print(f"    latest stable {f.latest}{when}{behind}")
        if f.suggested:
            print(f"    suggested bump: {f.suggested} (newest stable past the "
                  f"{COOLDOWN.days}-day cooldown)")
        for note in f.notes:
            print(f"    {note}")
        if f.error:
            print(f"    {f.error}")
        bundled = h.bundled or "not installed"
        if h.bundled_note:
            bundled += f" ({h.bundled_note})"
        yours = h.cli_version or f"{h.cli} not on PATH"
        print(f"    harness {h.package} {bundled}; your {h.cli}: {yours}")
    code = exit_code(c.freshness for c in checks)
    if code == 2:
        print("hobbes: npm registry unreachable; local pins checked only", file=sys.stderr)
    elif code == 1:
        print("hobbes: action suggested (see above). Bumps are manual: edit adapters/package.json, "
              "then `npm install` (see DEC-004)", file=sys.stderr)
    return code


def _find_proxy(args: argparse.Namespace) -> str | None:
    """The hobbes-proxy to attach (DEC-008), or None: no --repo,
    --no-knowledge, or not found (warned)."""
    from hobbes.watterson import knowledge

    if not args.repo or args.no_knowledge:
        return None
    proxy = knowledge.find_proxy()
    if proxy is None:
        print(f"hobbes: knowledge tools off: {knowledge.NOT_FOUND}", file=sys.stderr, flush=True)
    return proxy


def _route_policy(args: argparse.Namespace, spec, knowledge_on: bool):
    """The session's permission policy (DEC-007, DEC-008), its route, and the
    modes to ask the agent for."""
    from hobbes.watterson import knowledge
    from hobbes.watterson.permissions import Route, RoutePolicy, load_test_files, modes_for, terminal_ask

    route = Route(args.route)
    ask = None if args.allow_permissions or not args.interactive else terminal_ask(spec.name)
    policy = RoutePolicy(
        route, args.root, ask=ask, allow_unasked=args.allow_permissions,
        test_files=load_test_files(args.root / ".hobbes" / "derived"),
        allowed=knowledge.is_own_tool if knowledge_on else None,
    )
    return policy, route, modes_for(route, spec.name)


def _session_started(session, spec, route, wanted, servers) -> None:
    print(f"hobbes: {_route_line(route, spec.name, wanted, session)}", file=sys.stderr, flush=True)
    if servers:
        print(f"hobbes: knowledge tools on ({servers[0].command})", file=sys.stderr, flush=True)


@contextlib.asynccontextmanager
async def _agent_session(args: argparse.Namespace, spec, policy, route, wanted, servers):
    """Open the ACP session; a claude session carries Hobbes hooks and
    prints their permission count when it ends (DEC-010)."""
    from hobbes.watterson.hooks import SessionHooks
    from hobbes.watterson.providers import AgentSession

    hooks = None
    if spec.name == "claude":
        hooks = SessionHooks(route, args.root, agent=spec.name, test_files=policy.test_files)
    try:
        async with contextlib.AsyncExitStack() as stack:
            on_permission, meta = policy, None
            if hooks is not None:
                await stack.enter_async_context(hooks)
                on_permission, meta = hooks.observe(policy), hooks.meta()
            session = await stack.enter_async_context(AgentSession(
                spec, cwd=args.repo, on_permission=on_permission, modes=wanted,
                mcp_servers=servers, meta=meta,
            ))
            _session_started(session, spec, route, wanted, servers)
            yield session
    finally:
        if hooks is not None and hooks.socket_path:
            print(f"hobbes: {hooks.summary()}", file=sys.stderr, flush=True)


def _show_event(event, policy, args: argparse.Namespace) -> None:
    """Print one session event: text to stdout, tools and permissions to stderr."""
    from hobbes.watterson.providers import PermissionDecision, TextChunk, ToolCall

    if isinstance(event, TextChunk):
        print(event.text, end="", flush=True)
    elif isinstance(event, ToolCall):
        print(f"[tool] {event.title}", file=sys.stderr, flush=True)
    elif isinstance(event, PermissionDecision):
        verdict = "allowed" if event.allowed else "denied"
        reason = policy.reasons.get(event.request.tool_call_id, "")
        if reason.startswith("denied without asking"):
            hint = f" ({reason.removeprefix('denied ')})"
        elif reason.startswith("allowed once: "):
            hint = f" ({reason.removeprefix('allowed once: ')})"
        elif event.allowed or args.allow_permissions or policy.ask is not None:
            hint = ""
        else:
            hint = " (--allow-permissions to allow)"
        title = event.request.title or event.request.tool_call_id
        print(f"[permission] {title}: {verdict}{hint}", file=sys.stderr, flush=True)


async def _run_turn(session, prompt: str, policy, args: argparse.Namespace) -> str | None:
    """Send one prompt, print its events, and return the turn's stop reason."""
    from hobbes.watterson.providers import TurnEnded

    stop_reason = None
    async with contextlib.aclosing(session.prompt(prompt)) as events:
        async for event in events:
            _show_event(event, policy, args)
            if isinstance(event, TurnEnded):
                stop_reason = event.stop_reason
    print()
    if stop_reason != "end_turn":
        print(f"hobbes: {session.spec.name} stopped: {stop_reason}", file=sys.stderr)
    return stop_reason


async def _ask(args: argparse.Namespace, spec) -> int:
    from hobbes.watterson import knowledge

    proxy = _find_proxy(args)
    servers = [knowledge.server(args.root, proxy)] if proxy else []
    policy, route, wanted = _route_policy(args, spec, bool(servers))
    async with _agent_session(args, spec, policy, route, wanted, servers) as session:
        await _run_turn(session, args.prompt, policy, args)
    return 0


class _LineReader:
    """Reads stdin lines on a daemon thread, one per ``read()``, so Ctrl-C at
    the prompt never leaves the event loop waiting on a blocked worker."""

    def __init__(self) -> None:
        import queue
        import threading

        self._requests: queue.SimpleQueue = queue.SimpleQueue()
        threading.Thread(target=self._serve, daemon=True).start()

    async def read(self, prompt: str | None) -> str | None:
        """The next line without its newline, or None at EOF."""
        import asyncio

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._requests.put((loop, future, prompt))
        return await future

    def _serve(self) -> None:
        while True:
            loop, future, prompt = self._requests.get()
            if prompt:
                sys.stderr.write(prompt)
                sys.stderr.flush()
            line = sys.stdin.readline()
            loop.call_soon_threadsafe(_settle, future, line.rstrip("\n") if line else None)


def _settle(future, value) -> None:
    if not future.done():
        future.set_result(value)


async def _chat(args: argparse.Namespace, spec) -> int:
    import asyncio
    import signal
    import uuid

    from hobbes.watterson import knowledge
    from hobbes.watterson.live_session import GraphView, turn_label
    from hobbes.watterson.session_graph import GraphStore, Refresher

    proxy = _find_proxy(args)
    view = refresher = None
    servers = []
    if proxy:
        session_id = uuid.uuid4().hex[:12]
        store = GraphStore(args.root)
        view = GraphView(store, session_id)
        refresher = Refresher(args.root, store=store, session=session_id)
        servers.append(knowledge.server(view.dir, proxy, env=view.env))
    policy, route, wanted = _route_policy(args, spec, bool(servers))
    reader = _LineReader()
    reported = 0

    def report_errors() -> None:
        nonlocal reported
        if refresher is not None:
            for error in refresher.errors[reported:]:
                print(f"hobbes: graph refresh failed: {error}", file=sys.stderr, flush=True)
            reported = len(refresher.errors)

    loop = asyncio.get_running_loop()
    try:
        async with _agent_session(args, spec, policy, route, wanted, servers) as session:
            if view is not None:
                print("hobbes: graph refreshes between turns (lane A only)", file=sys.stderr, flush=True)
            while (line := await reader.read("> " if args.interactive else None)) is not None:
                if not line.strip():
                    continue
                prompt = line
                if view is not None:
                    report_errors()
                    view.turn_start()
                    label = await turn_label(view, refreshing=refresher.busy)
                    print(f"hobbes: {label}", file=sys.stderr, flush=True)
                    prompt = f"{label}\n\n{line}"
                loop.add_signal_handler(signal.SIGINT, lambda: asyncio.ensure_future(session.cancel()))
                try:
                    await _run_turn(session, prompt, policy, args)
                finally:
                    loop.remove_signal_handler(signal.SIGINT)
                if refresher is not None:
                    await refresher.turn_ended()
                    report_errors()
    finally:
        if refresher is not None:
            await refresher.aclose()
        if view is not None:
            view.close()
    return 0


def _route_line(route, agent: str, wanted: tuple[str, ...], session) -> str:
    """``route guarded; claude mode auto``, or why the mode was left alone."""
    if not wanted:
        return f"route {route}; mode left to {agent} (Hobbes knows no modes for it)"
    if session.mode in wanted:
        return f"route {route}; {agent} mode {session.mode}"
    offered = ", ".join(session.available_modes) or "none"
    return (f"route {route}; {agent} offers none of {', '.join(wanted)} "
            f"(offers: {offered}); mode left at {session.mode or 'its default'}")


def _cmd_ask(args: argparse.Namespace) -> int:
    """Stream one prompt's reply from an ACP agent harness."""
    return _cmd_session(args, _ask)


def _cmd_tui(args: argparse.Namespace) -> int:
    """The opencode TUI against a Hobbes server (DEC-013)."""
    import asyncio

    from hobbes.watterson.providers import ProviderError, load_registry
    from hobbes.watterson.serve import launch

    try:
        registry = load_registry()
    except ProviderError as exc:
        print(f"hobbes: {exc}", file=sys.stderr)
        return 2
    # Outside a git repo the app still opens, on this folder (DEC-016).
    repo = Path(args.repo).resolve() if args.repo else _detect_repo_root(Path.cwd()) or Path.cwd().resolve()
    try:
        return asyncio.run(launch.run(repo, registry,
                                      serve_only=args.serve_only, port=args.port))
    except KeyboardInterrupt:
        return 130


def _cmd_chat(args: argparse.Namespace) -> int:
    """A multi-turn session with an ACP agent harness (DEC-009)."""
    return _cmd_session(args, _chat)


def _cmd_session(args: argparse.Namespace, run) -> int:
    """Check the graph as the session starts (DEC-005), then *run* it."""
    import asyncio

    from hobbes.watterson.freshness import RefreshPolicy, on_session_start
    from hobbes.watterson.providers import ProviderError, get_agent

    if args.repo:
        args.repo = str(Path(args.repo).expanduser().resolve())
    policy = (
        RefreshPolicy.SKIP if args.no_refresh
        else RefreshPolicy.REFRESH if args.refresh
        else RefreshPolicy.ASK
    )
    interactive = sys.stdin.isatty() and sys.stderr.isatty()
    try:
        spec = get_agent(args.agent)  # an unknown agent fails before any prompt or ingest
        start = on_session_start(args.repo or Path.cwd(), interactive=interactive, policy=policy)
        args.interactive = interactive
        args.root = start.check.root if start.check else Path(args.repo or Path.cwd()).resolve()
        return asyncio.run(run(args, spec))
    except ProviderError as exc:
        print(f"hobbes: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nhobbes: cancelled", file=sys.stderr)
        return 130


def _cmd_roles(args: argparse.Namespace) -> int:
    """List the repo's roles and check their files (DEC-022); with --edit, have a model write them first (DEC-023)."""
    from hobbes.watterson import roles

    repo_root = _repo_root_from(args)
    if change := roles.ensure_ignored(repo_root):
        print(f"hobbes: {change}", file=sys.stderr)
    if args.edit is not None:
        saved = _edit_roles(args, repo_root)
        if saved is not True:
            return saved
        print(file=sys.stderr)
    try:
        mapping = roles.load(repo_root)
    except roles.RolesError as exc:
        print(f"hobbes roles: {exc}", file=sys.stderr)
        if not roles.roles_file(repo_root).exists():
            print(f"for example:\n\n{roles.EXAMPLE}", file=sys.stderr)
        return 1
    print(f"{mapping.path}")
    print(f"  test: {' '.join(mapping.test)}")
    print(f"  merges into: {mapping.branch}")
    print(f"  workers: {mapping.workers} at a time in a job, the rest queued")
    if mapping.coordinator:
        print(f"  coordinator: {mapping.coordinator}")
    code = 0
    for role in mapping.roles.values():
        found = "" if role.prompt.is_file() else "  (missing)"
        if found:
            code = 1
        writes = ", ".join(role.writes) or "nothing"
        print(f"{role.name}: {role.agent}, route {role.route}, knowledge {'on' if role.knowledge else 'off'}"
              f"{', review' if role.review else ''}")
        print(f"    prompt {role.prompt}{found}")
        print(f"    writes {writes}")
    return code


def _edit_roles(args: argparse.Namespace, repo_root: Path) -> int | bool:
    """Run the mapper on ``--edit``: True when it saved, else the exit code."""
    import asyncio

    from hobbes.watterson.dispatch import DispatchError
    from hobbes.watterson.mapper import run_mapper
    from hobbes.watterson.permissions import terminal_ask

    args.interactive = sys.stdin.isatty() and sys.stderr.isatty()
    ask = None if args.allow_permissions or not args.interactive else terminal_ask(args.agent)
    try:
        result = asyncio.run(run_mapper(
            repo_root, args.edit, agent=args.agent, ask=ask, allow_unasked=args.allow_permissions,
            on_event=lambda event, policy: _show_event(event, policy, args)))
    except DispatchError as exc:
        print(f"hobbes roles: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nhobbes: cancelled", file=sys.stderr)
        return 130
    print()
    print(f"hobbes: {result.summary(Path(repo_root))}", file=sys.stderr)
    print(f"hobbes: mapper record {result.record}", file=sys.stderr)
    return True if result.saved else 1


def _cmd_dispatch(args: argparse.Namespace) -> int:
    """One worker run in a role (DEC-022)."""
    import asyncio

    from hobbes.watterson import roles
    from hobbes.watterson.dispatch import DispatchError, dispatch
    from hobbes.watterson.permissions import terminal_ask

    repo_root = _repo_root_from(args)
    roles.ensure_ignored(repo_root)
    args.interactive = sys.stdin.isatty() and sys.stderr.isatty()
    try:
        mapping = roles.load(repo_root)
        role = mapping.role(args.role)
        ask = None if args.allow_permissions or not args.interactive else terminal_ask(role.agent)
        handoff = asyncio.run(dispatch(
            repo_root, mapping, args.role, args.brief, ask=ask,
            allow_unasked=args.allow_permissions,
            on_event=lambda event, policy: _show_event(event, policy, args),
        ))
    except (roles.RolesError, DispatchError) as exc:
        print(f"hobbes dispatch: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nhobbes: cancelled", file=sys.stderr)
        return 130
    print()
    if handoff.report:
        print(f"hobbes: the worker reports {handoff.asked}:\n{handoff.report}", file=sys.stderr)
    files = ", ".join(handoff.files) or "none"
    print(f"hobbes: {handoff.branch}: {len(handoff.commits)} commit(s); files: {files}", file=sys.stderr)
    if handoff.test is not None:
        print(f"hobbes: test {' '.join(handoff.test['command'])}: exit {handoff.test['exit']}", file=sys.stderr)
        if handoff.test["exit"] != 0 and handoff.test["tail"]:
            print(handoff.test["tail"], file=sys.stderr)
    if handoff.merged:
        print(f"hobbes: merged into {mapping.branch}", file=sys.stderr)
    elif handoff.outcome == "review":
        print(f"hobbes: {handoff.reason}; branch {handoff.branch} kept, tested, not merged", file=sys.stderr)
    else:
        kept = f"; branch {handoff.branch} kept" if handoff.commits else ""
        print(f"hobbes: not merged: {handoff.reason}{kept}", file=sys.stderr)
    print(f"hobbes: handoff {handoff.record}", file=sys.stderr)
    return 1 if handoff.outcome == "stopped" else 0


def _plan_approver(reader: _LineReader):
    """Ask the user about a plan on the terminal: ``y``, ``y <comment>``, or a comment that says no."""
    from hobbes.watterson.lead import APPROVAL_HINT, parse_approval

    async def approve(plan: str) -> tuple[bool, str]:
        print(f"\n--- plan ---\n{plan.rstrip()}\n------------", file=sys.stderr, flush=True)
        return parse_approval(await reader.read(f"hobbes: approve? [{APPROVAL_HINT}] ") or "")
    return approve


async def _jobs(args: argparse.Namespace, repo_root: Path, mapping) -> int:
    from hobbes.watterson.lead import run_job
    from hobbes.watterson.permissions import terminal_ask

    reader = _LineReader()
    role = mapping.role(mapping.coordinator) if mapping.coordinator else None
    ask = None if args.allow_permissions or not args.interactive or role is None else terminal_ask(role.agent)
    approve = _plan_approver(reader) if args.interactive else None
    code = 0
    while True:
        job = args.job if args.job is not None else await reader.read("job> " if args.interactive else None)
        if job is None:
            return code
        if not job.strip():
            continue
        result = await run_job(
            repo_root, mapping, job, approve=approve, ask=ask, allow_unasked=args.allow_permissions,
            on_event=lambda event, policy: _show_event(event, policy, args),
            on_dispatch=lambda role, brief: print(
                f"\nhobbes: dispatch {role}: {brief.strip().splitlines()[0][:100]}", file=sys.stderr, flush=True),
        )
        print()
        for record in result.dispatches:
            state = "merged" if record["merged"] else (
                f"kept for review: {record['reason']}" if record["outcome"] == "review"
                else f"not merged: {record['reason']}")
            print(f"hobbes: #{record['ticket']} {record['role']} {record['branch'] or '(no branch)'}: {state}",
                  file=sys.stderr)
        if result.docs_commit:
            print(f"hobbes: docs committed {result.docs_commit[:7]}: {', '.join(result.docs_files)}", file=sys.stderr)
        elif result.reason:
            print(f"hobbes: docs {result.reason}", file=sys.stderr)
        finished = result.summary is not None
        print(f"hobbes: {'finished' if finished else 'not finished'}"
              f"{': ' + result.summary if result.summary else ''}", file=sys.stderr)
        print(f"hobbes: job record {result.record}", file=sys.stderr)
        ok = finished and not result.reason and all(r["outcome"] != "stopped" for r in result.dispatches)
        code = code or (0 if ok else 1)
        if args.job is not None:
            return code


def _cmd_job(args: argparse.Namespace) -> int:
    """Jobs through the coordinator role (DEC-022 slice 2)."""
    import asyncio

    from hobbes.watterson import roles
    from hobbes.watterson.dispatch import DispatchError

    repo_root = _repo_root_from(args)
    roles.ensure_ignored(repo_root)
    args.interactive = sys.stdin.isatty() and sys.stderr.isatty()
    try:
        mapping = roles.load(repo_root)
        return asyncio.run(_jobs(args, repo_root, mapping))
    except (roles.RolesError, DispatchError) as exc:
        print(f"hobbes job: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nhobbes: cancelled", file=sys.stderr)
        return 130


def _cmd_complete(args: argparse.Namespace) -> int:
    """Stream one completion from a raw model API."""
    from hobbes.watterson.providers import ProviderError, stream

    try:
        for text in stream(args.model, args.prompt, system=args.system, max_tokens=args.max_tokens):
            print(text, end="", flush=True)
    except ProviderError as exc:
        print(f"hobbes: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nhobbes: cancelled", file=sys.stderr)
        return 130
    print()
    return 0


#: This repo's own cache, kept apart from hobbes-public's ``~/.hobbes/cache``
#: so the two checkouts never share lane-B staging, index or timing entries.
#: Set here rather than in ``hobbes.extract`` so the pipeline stays verbatim.
DEFAULT_CACHE_DIR = "~/.watterson/cache"


def _default_cache_dir() -> None:
    """Point ``HOBBES_CACHE_DIR`` at this repo's cache unless already set."""
    os.environ.setdefault("HOBBES_CACHE_DIR", DEFAULT_CACHE_DIR)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    _default_cache_dir()
    # Report progress as it happens, not at exit. Python block-buffers
    # stdout when it is not a tty, so a redirected or supervised run
    # (`hobbes ingest > ingest.log &`) would look silent for as long as it
    # works. A tty is line-buffered already, so this changes nothing about
    # interactive use.
    #
    # Guarded because a captured stdout (pytest's capsys, a StringIO) has no
    # reconfigure, and buffering is not its problem anyway.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args(argv)
    if args.command is None:  # bare `hobbes` opens the app (DEC-016)
        args = build_parser().parse_args(["tui"])
    handlers = {
        "ingest": _cmd_ingest,
        "render": _cmd_render,
        "levels": _cmd_levels,
        "review": _cmd_review,
        "freshness": _cmd_freshness,
        "agents": _cmd_agents,
        "ask": _cmd_ask,
        "chat": _cmd_chat,
        "complete": _cmd_complete,
        "roles": _cmd_roles,
        "dispatch": _cmd_dispatch,
        "job": _cmd_job,
        "tui": _cmd_tui,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
