"""Decide each permission request by route: ``guarded`` or ``manual`` (DEC-007).

Commands are never removed from a harness. Each permission request it
raises reaches ``RoutePolicy`` (the session's ``on_permission``), which:

- **guarded** (default): the harness's strongest built-in decider is on
  (``ROUTE_MODES``), so few requests get here. An edit, delete or move of
  an agent's own permission config is **denied without asking**.
  Everything else is **asked**, never allowed by itself.
- **manual**: the most-asking modes. Everything is asked; the agent-config
  case becomes a warning, since this user decides.

Requests that ``allowed`` accepts (Hobbes's own read-only knowledge tools,
DEC-008) are allowed once without asking, on both routes.

The policy never picks an ``*_always`` option by itself: that writes a rule
inside the harness, which then stops asking us. When no one can be asked
(no terminal), it rejects, or allows with ``allow_unasked``
(``--allow-permissions``); the hard deny still holds in guarded.

``annotate`` says what a request touches, from its paths, raw input and,
for a command, the path-like words in it: inside or outside the repo, an
agent's permission config, repo-controlled execution (git hooks and
config, ``.env``, CI workflows) and test files (from ``tests.json``). It
reads the command as text, so it can be fooled; since the policy allows
nothing by itself, a miss only turns a warned prompt into a plain one,
except for the agent-config deny, which looks at edits' paths, not at
command text.

Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import asyncio
import contextlib
import enum
import fnmatch
import json
import os
import re
import shlex
import sys
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from hobbes.watterson.providers.events import PermissionRequest, option_of_kind


class Route(enum.StrEnum):
    GUARDED = "guarded"
    MANUAL = "manual"


#: Session modes per route and built-in agent, in order of preference.
#: claude and codex ids are from the adapters locked in ``adapters/``
#: (claude offers ``auto`` only for models that support it); gemini's are
#: from its source (v0.64.0), not checked against an installed CLI.
ROUTE_MODES: dict[Route, dict[str, tuple[str, ...]]] = {
    Route.GUARDED: {"claude": ("auto", "default"), "codex": ("agent",), "gemini": ("default",)},
    Route.MANUAL: {"claude": ("default",), "codex": ("workspace-write",), "gemini": ("default",)},
}

#: Tool kinds that change files.
WRITE_KINDS = frozenset({"edit", "delete", "move"})
#: An agent's own permission settings, under the repo or the home directory.
#: A trailing ``/`` means the whole directory.
AGENT_CONFIG = (".claude/settings*.json", ".codex/", ".gemini/settings.json", ".gemini/policies/")
#: Files whose contents the repo's tooling executes or loads.
REPO_EXEC = (".git/hooks/", ".git/config", ".github/workflows/", ".gitlab-ci.yml", ".circleci/")
_RAW_PATH_KEYS = ("file_path", "path", "notebook_path", "filePath")
_REDIRECT = re.compile(r"^\d*[<>]+&?")


def modes_for(route: Route, agent: str) -> tuple[str, ...]:
    """The modes to ask *agent* for on *route*; empty for agents we don't know."""
    return ROUTE_MODES[route].get(agent, ())


def _matches(rel: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/") and (rel + "/").startswith(pattern):
            return True
        if fnmatch.fnmatchcase(rel, pattern):
            return True
    return False


@dataclass(frozen=True)
class PathFact:
    """One path a request names. ``shown`` is repo-relative when inside."""

    shown: str
    inside: bool
    agent_config: bool = False
    repo_exec: bool = False
    test: bool = False


def classify(path: str, repo: Path, test_files: frozenset[str] = frozenset()) -> PathFact:
    """What *path* (absolute, or relative to *repo*) is, as far as the rules see."""
    full = Path(os.path.normpath(Path(repo, os.path.expanduser(path))))
    try:
        rel = full.relative_to(repo).as_posix()
        inside = True
    except ValueError:
        rel, inside = str(full), False
    home_rel = None
    with contextlib.suppress(ValueError):
        home_rel = full.relative_to(Path.home()).as_posix()
    agent_config = (inside and _matches(rel, AGENT_CONFIG)) or (
        home_rel is not None and _matches(home_rel, AGENT_CONFIG)
    )
    name = full.name
    repo_exec = inside and (_matches(rel, REPO_EXEC) or name == ".env" or name.startswith(".env."))
    return PathFact(
        rel if inside else str(full), inside, agent_config, repo_exec,
        test=inside and rel in test_files,
    )


def _command(request: PermissionRequest) -> str | None:
    raw = request.raw_input
    command = raw.get("command") if isinstance(raw, dict) else None
    if isinstance(command, list) and all(isinstance(w, str) for w in command):
        return shlex.join(command)
    if isinstance(command, str) and command:
        return command
    if request.kind == "execute" and request.title:
        return request.title  # gemini sends no raw input; its title is the command
    return None


def command_paths(command: str) -> list[str]:
    """Path-like words in a shell command: anything with a ``/``, or starting
    with ``.`` or ``~``, after redirections and ``--opt=`` are stripped."""
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    found = []
    for word in words:
        word = _REDIRECT.sub("", word)
        if word.startswith("-"):
            word = word.partition("=")[2]
        if word and ("/" in word or word.startswith((".", "~"))) and "://" not in word:
            found.append(word)
    return found


@dataclass(frozen=True)
class Annotation:
    """What one request touches, in plain words, and what to warn about."""

    kind: str | None
    command: str | None = None
    paths: tuple[PathFact, ...] = ()
    url: str | None = None

    @property
    def agent_config_write(self) -> bool:
        """An edit, delete or move of an agent's own permission config."""
        return self.kind in WRITE_KINDS and any(p.agent_config for p in self.paths)

    def warnings(self) -> list[str]:
        out = []
        config = [p.shown for p in self.paths if p.agent_config]
        if config:
            verb = "changes" if self.agent_config_write else "names"
            out.append(f"{verb} an agent's own permission config: {', '.join(config)}")
        repo_exec = [p.shown for p in self.paths if p.repo_exec]
        if repo_exec:
            out.append(f"touches files the repo's tooling runs or loads: {', '.join(repo_exec)}")
        outside = [p.shown for p in self.paths if not p.inside and not p.agent_config]
        if outside:
            out.append(f"reaches outside the repo: {', '.join(outside)}")
        if self.url:
            out.append(f"reaches the network: {self.url}")
        return out

    def lines(self) -> list[str]:
        """What it does, then ``! `` warnings, one per line."""
        out = []
        if self.command:
            out.append(f"runs: {self.command}")
        elif self.paths:
            verb = {"edit": "edits", "delete": "deletes", "move": "moves", "read": "reads"}.get(
                self.kind or "", "touches"
            )
            shown = ", ".join(p.shown + (" (test)" if p.test else "") for p in self.paths)
            out.append(f"{verb}: {shown}")
        return out + [f"! {w}" for w in self.warnings()]


def annotate(request: PermissionRequest, repo: str | Path,
             test_files: frozenset[str] = frozenset()) -> Annotation:
    """Read *request* against *repo*; see the module doc."""
    root = Path(repo).resolve()
    command = _command(request)
    named: list[str] = list(request.paths)
    raw = request.raw_input
    if isinstance(raw, dict):
        named += [v for k in _RAW_PATH_KEYS if isinstance(v := raw.get(k), str) and v]
    if command:
        named += command_paths(command)
    url = raw.get("url") if isinstance(raw, dict) and isinstance(raw.get("url"), str) else None
    facts = {}
    for path in named:
        fact = classify(path, root, test_files)
        facts.setdefault(fact.shown, fact)
    return Annotation(request.kind, command, tuple(facts.values()), url)


def load_test_files(derived: str | Path) -> frozenset[str]:
    """Test files named in ``<derived>/tests.json``; empty when absent or unreadable."""
    try:
        doc = json.loads((Path(derived) / "tests.json").read_text())
        return frozenset(t["file"] for t in doc["tests"] if isinstance(t.get("file"), str))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return frozenset()


def once(request: PermissionRequest, prefix: str) -> str | None:
    """The ``<prefix>_once`` option, or None (cancel); never an ``_always`` one.
    A reject prefers one that lets the turn go on (Codex ``decline``)."""
    return option_of_kind(request, f"{prefix}_once")


#: ``ask(request, annotation) -> option id | None``: a human decides.
Ask = Callable[[PermissionRequest, Annotation], Awaitable["str | None"]]


@dataclass
class RoutePolicy:
    """The ``on_permission`` callback for a route; see the module doc.

    ``reasons`` maps a tool call id to why it was answered without a
    human (a hard deny, an ``allowed`` tool, or no one to ask), for the
    caller to show. ``allowed`` picks requests to allow once without asking
    (DEC-008).
    """

    route: Route
    repo: Path
    ask: Ask | None = None
    allow_unasked: bool = False
    test_files: frozenset[str] = frozenset()
    allowed: Callable[[PermissionRequest], bool] | None = None
    reasons: dict[str, str] = field(default_factory=dict)

    async def __call__(self, request: PermissionRequest) -> str | None:
        note = annotate(request, self.repo, self.test_files)
        if self.route is Route.GUARDED and note.agent_config_write:
            self.reasons[request.tool_call_id] = (
                "denied without asking: it changes an agent's own permission config (guarded route)"
            )
            return once(request, "reject")
        if self.allowed is not None and self.allowed(request):
            self.reasons[request.tool_call_id] = "allowed once: Hobbes's own knowledge tool (DEC-008)"
            return once(request, "allow")
        if self.ask is not None:
            return await self.ask(request, note)
        if self.allow_unasked:
            self.reasons[request.tool_call_id] = "allowed once without asking (--allow-permissions)"
            return once(request, "allow")
        self.reasons[request.tool_call_id] = "denied: no terminal to ask on"
        return once(request, "reject")


def terminal_ask(agent: str, *, read_line: Callable[[], str] | None = None,
                 out: TextIO | None = None) -> Ask:
    """An ``Ask`` that prompts on the terminal. Enter, EOF or anything that is
    not an option number rejects once."""

    async def ask(request: PermissionRequest, note: Annotation) -> str | None:
        stream = out or sys.stderr
        lines = [f"hobbes: {agent} asks: {request.title or request.tool_call_id}"]
        lines += [f"  {line}" for line in note.lines()]
        for i, option in enumerate(request.options, 1):
            hint = ""
            if option.kind.endswith("_always"):
                hint = f" ({agent} remembers this itself and will not ask Hobbes again for matching actions)"
            lines.append(f"  {i}) {option.name}{hint}")
        stream.write("\n".join(lines) + f"\nchoose 1-{len(request.options)} [Enter rejects]: ")
        stream.flush()
        answer = (await asyncio.to_thread(read_line or sys.stdin.readline)).strip()
        if answer.isdigit() and 1 <= int(answer) <= len(request.options):
            return request.options[int(answer) - 1].id
        return once(request, "reject")

    return ask
