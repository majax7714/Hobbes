"""The mapper: a model writes or edits a repo's agent mapping on request (DEC-023).

``run_mapper(repo, request, agent=...)`` is what ``hobbes roles --edit`` and
the TUI's ``edit mapping`` mode run. One request, one fresh session:

1. the prompt: the mapper's rules, the mapping's format (``FORMAT``), the
   agents installed here, the repo's current mapping (``roles.toml`` and
   every prompt file under ``.hobbes/roles/``) or none, the requests made
   earlier in the same TUI session, and the request;
2. a harness session at the repo root in the given agent and route, with
   the knowledge tools (DEC-008) when the caller says the graph is there,
   and the ``hobbes-mapper`` MCP server (``hobbes.watterson.lead_mcp``) relaying its
   one tool here, allowed once without asking;
3. ``save_mapping(roles_toml, prompts)`` is checked (``check``): the TOML
   loads as ``hobbes.watterson.roles.load`` reads it, every role's agent is
   installed, and every role's prompt sits under ``.hobbes/`` and is given
   or already there. Only then is it written (``.hobbes/`` kept out of git
   first); otherwise the errors go back to the model. Prompt files no
   longer named are left;
4. after the turn, any change the session left in the checkout (the
   mapping's files are out of git, so not these) is reported, not
   reverted: the harness's own edits are not blocked (DEC-023).

The ``MapperResult`` is saved as ``mapper-<id>.json`` beside the dispatch
records. Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from hobbes.watterson import roles
from hobbes.watterson.dispatch import DispatchError, is_server_tool, relay_server, run_dir, run_role_session, tool_relay
from hobbes.watterson.lead import _changed
from hobbes.watterson.snapshot import repo_root

SERVER = "hobbes-mapper"
TOOLS = ("save_mapping",)

RULES = """\
You set up this repo's agent mapping for Hobbes: the roles that agents work in, which a
coordinator plans with and dispatches. Read the repo as you need to, but do not edit any file:
save the whole mapping with save_mapping on the hobbes-mapper server. roles_toml is the text of
.hobbes/roles.toml; prompts maps each role's prompt path (as its `prompt` key names it, such as
roles/implementer.md) to that role's standing prompt, in Markdown. If save_mapping returns
errors, fix them and save again. Once it is saved, say in a few lines what each role does.
Keep what the current mapping has unless the request changes it. A good mapping has: a
coordinator whose writes cover only the docs; workers whose writes are as narrow as their work;
the repo's real test command; review = true where a person should look before a merge; and
standing prompts that say what the role is for, what it must not touch, and how this repo is
built and tested."""

FORMAT = """\
Top-level keys:
- test (required): the repo's test command as a list of strings, run in a worker's worktree
  before its work merges; it must pass.
- branch (default "main"): where finished work merges.
- coordinator: the role that plans and dispatches a job; needed for jobs.
- workers (default 2): how many workers a job runs at once; the rest queue.
One [roles.<name>] table per role:
- agent (required): one of the installed agents listed below.
- route ("guarded", the default, or "manual": every permission request is asked).
- knowledge (default true): Hobbes's graph tools for the repo.
- prompt (required): the standing prompt's path under .hobbes/, such as "roles/<name>.md".
- writes (required): fnmatch patterns over repo paths the role may change ("*" crosses "/");
  [] for none.
- review (default false): true keeps the role's tested work on its branch for a person to
  review instead of merging it.
Unknown keys are errors."""


def is_mapper_tool(request) -> bool:
    return is_server_tool(request, SERVER, TOOLS)


def current_mapping(root: Path) -> str:
    """The repo's mapping files as text for the prompt, or a line saying there are none."""
    hobbes = root / ".hobbes"
    files = [hobbes / "roles.toml"] + sorted((hobbes / "roles").rglob("*")) if (hobbes / "roles").is_dir() \
        else [hobbes / "roles.toml"]
    shown = []
    for path in files:
        if path.is_file():
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            shown.append(f"--- .hobbes/{path.relative_to(hobbes).as_posix()} ---\n{text.rstrip()}")
    return "\n\n".join(shown) or "(none yet: this repo has no .hobbes/roles.toml)"


def mapper_prompt(request: str, *, current: str, agents: list[str], earlier: list[str] = (),
                  knowledge: bool = False) -> str:
    graph = ("Hobbes's knowledge tools are attached: use them to see how the repo is built."
             if knowledge else "Hobbes's knowledge tools are not attached here (Hobbes is off or the "
             "repo has no graph); read the files instead.")
    asked = "\n".join(f"- {line}" for line in earlier) or "(none)"
    return (f"[hobbes mapper]\n{RULES}\n{graph}\n\n[hobbes format]\n{FORMAT}\n\n"
            f"[hobbes agents]\n{', '.join(agents) or '(none)'}\n\n[hobbes current mapping]\n{current}\n\n"
            f"[hobbes earlier requests]\n{asked}\n\n[hobbes request]\n{request}")


def _prompt_path(hobbes: Path, key: str) -> Path | None:
    """Where prompt *key* goes under *hobbes*, or None when it would land outside."""
    pure = PurePosixPath(key)
    if not key or pure.is_absolute() or ".." in pure.parts or key == "roles.toml":
        return None
    return hobbes / pure


def check(root: Path, roles_toml: str, prompts: dict[str, str], registry: dict | None = None) -> list[str]:
    """What is wrong with a proposed mapping, or nothing."""
    from hobbes.watterson.providers import ProviderError, get_agent

    if not isinstance(roles_toml, str) or not roles_toml.strip():
        return ["roles_toml is empty"]
    if not isinstance(prompts, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in prompts.items()):
        return ["prompts must map each prompt path to its text"]
    errors = [f"prompt {key!r}: not a path under .hobbes/" for key in prompts if _prompt_path(Path("."), key) is None]
    if errors:
        return errors
    with tempfile.TemporaryDirectory(prefix="hobbes-mapper-") as scratch:
        hobbes = Path(scratch) / ".hobbes"
        hobbes.mkdir()
        (hobbes / "roles.toml").write_text(roles_toml)
        for key, text in prompts.items():
            target = _prompt_path(hobbes, key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        try:
            mapping = roles.load(scratch)
        except roles.RolesError as exc:
            return [str(exc).replace(str(hobbes), ".hobbes")]
        for role in mapping.roles.values():
            try:
                get_agent(role.agent, registry)
            except ProviderError as exc:
                errors.append(f"role {role.name}: agent {role.agent!r}: {exc}")
            try:
                key = role.prompt.resolve().relative_to(hobbes.resolve()).as_posix()
            except ValueError:
                errors.append(f"role {role.name}: prompt {role.prompt.name!r} is outside .hobbes/")
                continue
            if key not in prompts and not (root / ".hobbes" / key).is_file():
                errors.append(f"role {role.name}: prompt {key} is neither given in prompts nor already there")
    return errors


def save(root: Path, roles_toml: str, prompts: dict[str, str], registry: dict | None = None) -> list[str]:
    """Check, then write the mapping; the errors when it was not written."""
    errors = check(root, roles_toml, prompts, registry)
    if errors:
        return errors
    roles.ensure_ignored(root)
    hobbes = root / ".hobbes"
    hobbes.mkdir(exist_ok=True)
    (hobbes / "roles.toml").write_text(roles_toml if roles_toml.endswith("\n") else roles_toml + "\n")
    for key, text in prompts.items():
        target = _prompt_path(hobbes, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text if text.endswith("\n") else text + "\n")
    return []


@dataclass
class MapperResult:
    id: str
    request: str
    agent: str
    stop_reason: str | None = None
    said: str = ""
    #: each save_mapping call: its errors, [] when it was saved
    attempts: list[list[str]] = field(default_factory=list)
    saved: bool = False
    #: changes the session left in the checkout, outside the mapping
    other_changes: list[str] = field(default_factory=list)
    record: str = ""

    def summary(self, root: Path) -> str:
        """What the request came to, for a notice or the terminal."""
        if self.saved:
            try:
                mapping = roles.load(root)
                found = (f"{len(mapping.roles)} role(s): {', '.join(mapping.roles)}"
                         + (f"; coordinator {mapping.coordinator}" if mapping.coordinator else "; no coordinator"))
            except roles.RolesError as exc:
                found = f"but it does not load now: {exc}"
            line = f"Mapping saved to .hobbes/roles.toml, {found}."
        elif self.attempts:
            line = "Mapping not saved: " + "; ".join(self.attempts[-1])
        else:
            line = "Mapping not saved: the model did not call save_mapping."
        if self.other_changes:
            line += f"\nThe session also changed, outside the mapping: {', '.join(self.other_changes)}"
        return line


async def run_mapper(repo: str | Path, request: str, *, agent: str, route: str = "guarded",
                     registry: dict | None = None, ask=None, allow_unasked: bool = False, on_event=None,
                     earlier: list[str] = (), knowledge: bool | None = None) -> MapperResult:
    """One request; see the module doc. *knowledge* None attaches the
    knowledge tools when the repo has a graph. Raises DispatchError when the
    agent is unknown."""
    from hobbes.watterson.freshness import DERIVED_DIR
    from hobbes.watterson.providers import ProviderError, get_agent, load_registry

    root = repo_root(repo)
    try:
        spec = get_agent(agent, registry)
    except ProviderError as exc:
        raise DispatchError(f"mapper: {exc}") from exc
    if knowledge is None:
        knowledge = (root / DERIVED_DIR / "graph.json").is_file()
    agents = list(registry if registry is not None else load_registry())
    prompt = mapper_prompt(request, current=current_mapping(root), agents=agents, earlier=list(earlier),
                           knowledge=knowledge)
    role = roles.Role("mapper", agent, route, knowledge, Path(), ())
    result = MapperResult(uuid.uuid4().hex[:8], request, agent)

    async def handle(tool: str, arguments: dict) -> tuple[str, bool]:
        if tool != "save_mapping":
            return f"unknown tool {tool!r}", True
        errors = save(root, arguments.get("roles_toml"), arguments.get("prompts") or {}, registry)
        result.attempts.append(errors)
        result.saved = result.saved or not errors
        if errors:
            return "Not saved. Fix these and call save_mapping again:\n" + "\n".join(f"- {e}" for e in errors), True
        return "Saved. Now say in a few lines what each role does, and end your turn.", False

    before = set(_changed(root))
    try:
        async with tool_relay(handle) as socket_path:
            result.stop_reason, result.said = await run_role_session(
                root, root, role, spec, prompt, ask=ask, allow_unasked=allow_unasked, on_event=on_event,
                servers=[relay_server(SERVER, socket_path)], allowed=is_mapper_tool)
        result.other_changes = sorted(set(_changed(root)) - before)
    finally:
        out_dir = run_dir(root)
        out_dir.mkdir(parents=True, exist_ok=True)
        record = out_dir / f"mapper-{result.id}.json"
        result.record = str(record)
        record.write_text(json.dumps(asdict(result), indent=2) + "\n")
    return result


def describe(root: Path) -> dict[str, Any] | None:
    """The repo's mapping as data (the review page's Agents tab), None when it has none."""
    path = roles.roles_file(root)
    if not path.is_file():
        return None
    try:
        mapping = roles.load(root)
    except roles.RolesError as exc:
        return {"error": str(exc), "text": path.read_text(errors="replace")}
    found = []
    for role in mapping.roles.values():
        try:
            prompt = role.prompt.read_text(errors="replace")
        except OSError:
            prompt = None
        found.append({"name": role.name, "agent": role.agent, "route": role.route, "knowledge": role.knowledge,
                      "writes": list(role.writes), "review": role.review,
                      "prompt_path": role.prompt.relative_to(root).as_posix() if role.prompt.is_relative_to(root)
                      else str(role.prompt), "prompt": prompt,
                      "coordinator": role.name == mapping.coordinator})
    return {"test": list(mapping.test), "branch": mapping.branch, "coordinator": mapping.coordinator,
            "workers": mapping.workers, "roles": found}
