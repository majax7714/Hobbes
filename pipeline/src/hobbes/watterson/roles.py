"""A repo's agent roles and their mapping (DEC-022).

The mapping is ``<repo>/.hobbes/roles.toml``, kept out of git with the rest
of ``.hobbes/`` (DEC-022 note): ``ensure_ignored`` writes the clone's
``info/exclude`` line through the ingest's own helper, since an ingest may
not have run yet. A repo that tracks files under ``.hobbes/`` (as
hobbes-public does) gets only ``.hobbes/derived/`` from that helper, so the
role files get lines of their own. Linked worktrees share the exclude
file. The file::

    coordinator = "lead"                 # optional; the driver (slice 2) starts it
    branch = "main"                      # optional; where finished work merges
    workers = 2                          # optional; a job's workers at a time, the rest queue; default 2
    test = ["uv", "run", "pytest", "-q"] # run in the worker's worktree before a merge

    [roles.implementer]
    agent = "claude"                     # a name from `hobbes agents` (DEC-004)
    route = "guarded"                    # DEC-007; default guarded
    knowledge = true                     # attach the knowledge tools (DEC-008); default true
    prompt = "roles/implementer.md"      # the role's standing prompt, under .hobbes/
    writes = ["src/*", "tests/*"]        # paths it may change; [] for none
    review = false                       # true: its work pauses for review, never merges; default false

``writes`` patterns are ``fnmatch`` globs over repo-relative paths, so
``*`` crosses ``/``. A role names no model: the ACP sessions here cannot
choose one yet (DEC-022 note). Unknown keys are errors, so a typo is not
silently ignored.

Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

ROLES_FILE = Path(".hobbes") / "roles.toml"
ROUTES = ("guarded", "manual")
_TOP_KEYS = {"coordinator", "branch", "test", "roles", "workers"}
DEFAULT_WORKERS = 2
_ROLE_KEYS = {"agent", "route", "knowledge", "prompt", "writes", "review"}

EXAMPLE = """\
test = ["uv", "run", "pytest", "-q"]

[roles.implementer]
agent = "claude"
route = "guarded"
knowledge = true
prompt = "roles/implementer.md"
writes = ["src/*", "tests/*"]
"""


class RolesError(Exception):
    """The mapping is missing or malformed; the message says where."""


@dataclass(frozen=True)
class Role:
    name: str
    agent: str
    route: str
    knowledge: bool
    prompt: Path
    writes: tuple[str, ...]
    review: bool = False

    def may_write(self, path: str) -> bool:
        return any(fnmatchcase(path, pattern) for pattern in self.writes)

    def prompt_text(self) -> str:
        try:
            return self.prompt.read_text()
        except OSError as exc:
            raise RolesError(f"role {self.name}: prompt {self.prompt}: {exc.strerror}") from exc


@dataclass(frozen=True)
class Mapping:
    path: Path
    roles: dict[str, Role]
    test: tuple[str, ...]
    branch: str = "main"
    coordinator: str | None = None
    workers: int = DEFAULT_WORKERS

    def role(self, name: str) -> Role:
        try:
            return self.roles[name]
        except KeyError:
            known = ", ".join(sorted(self.roles)) or "none"
            raise RolesError(f"{self.path}: no role {name!r} (roles: {known})") from None


def roles_file(repo_root: str | Path) -> Path:
    return Path(repo_root) / ROLES_FILE


#: The role files, and a path under each that ``git check-ignore`` can test.
_ROLE_PATHS = ((".hobbes/roles.toml", ".hobbes/roles.toml"), (".hobbes/roles/", ".hobbes/roles/x.md"))


def ensure_ignored(repo_root: str | Path) -> str | None:
    """Keep the role files out of git before they land there; says what it changed."""
    from hobbes.extract.emit import ensure_hobbes_ignored

    root = Path(repo_root)
    changes = [change] if (change := ensure_hobbes_ignored(root)) else []

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

    found = git("rev-parse", "--git-path", "info/exclude")
    if found.returncode != 0:
        return "; ".join(changes) or None  # not a git repo: the helper wrote .gitignore
    lines = [line for line, probe in _ROLE_PATHS if git("check-ignore", "-q", probe).returncode != 0]
    if lines:
        exclude = Path(found.stdout.strip())
        exclude = exclude if exclude.is_absolute() else root / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text() if exclude.exists() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        exclude.write_text(text + "".join(f"{line}\n" for line in lines))
        changes.append(f"added {', '.join(lines)} to .git/info/exclude")
    return "; ".join(changes) or None


def load(repo_root: str | Path) -> Mapping:
    """The repo's mapping; raises RolesError naming the file and the problem."""
    path = roles_file(repo_root)
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise RolesError(f"{path}: not found") from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RolesError(f"{path}: {exc}") from exc

    def fail(message: str) -> RolesError:
        return RolesError(f"{path}: {message}")

    if unknown := set(data) - _TOP_KEYS:
        raise fail(f"unknown keys {sorted(unknown)} (known: {sorted(_TOP_KEYS)})")
    test = data.get("test")
    if not (isinstance(test, list) and test and all(isinstance(a, str) for a in test)):
        raise fail("test must be the repo's test command as a list of strings")
    branch = data.get("branch", "main")
    if not isinstance(branch, str) or not branch:
        raise fail("branch must be a branch name")
    workers = data.get("workers", DEFAULT_WORKERS)
    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise fail("workers must be a whole number, at least 1")
    tables = data.get("roles", {})
    if not isinstance(tables, dict):
        raise fail("roles must be tables, [roles.<name>]")

    roles = {}
    for name, table in tables.items():
        where = f"roles.{name}"
        if not isinstance(table, dict):
            raise fail(f"{where} must be a table")
        if unknown := set(table) - _ROLE_KEYS:
            raise fail(f"{where}: unknown keys {sorted(unknown)} (known: {sorted(_ROLE_KEYS)})")
        agent, prompt, writes = table.get("agent"), table.get("prompt"), table.get("writes")
        route, knowledge = table.get("route", "guarded"), table.get("knowledge", True)
        review = table.get("review", False)
        if not isinstance(agent, str) or not agent:
            raise fail(f"{where}: agent must name an agent (see `hobbes agents`)")
        if route not in ROUTES:
            raise fail(f"{where}: route must be one of {', '.join(ROUTES)}")
        if not isinstance(knowledge, bool):
            raise fail(f"{where}: knowledge must be true or false")
        if not isinstance(review, bool):
            raise fail(f"{where}: review must be true or false")
        if not isinstance(prompt, str) or not prompt:
            raise fail(f"{where}: prompt must be a file under .hobbes/")
        if not (isinstance(writes, list) and all(isinstance(w, str) for w in writes)):
            raise fail(f"{where}: writes must be a list of path patterns ([] for none)")
        roles[name] = Role(name, agent, route, knowledge, path.parent / prompt, tuple(writes), review)

    coordinator = data.get("coordinator")
    if coordinator is not None and coordinator not in roles:
        raise fail(f"coordinator {coordinator!r} is not a role")
    return Mapping(path, roles, tuple(test), branch, coordinator, workers)
