"""Is the Hobbes graph current for this repo? Checked when a session starts (DEC-005).

``check_freshness(repo)`` compares the commit an ingest stamped into
``<repo>/.hobbes/derived/`` against the repo's HEAD. Each of ``graph.json``,
``tests.json`` and ``interfaces.json`` carries the stamp as its top-level
``sha`` (the full HEAD SHA at ingest, from ``hobbes.extract.emit.repo_stamp``)
next to a ``dirty`` flag. ``graph.json``'s ``built_by.sha`` is the Hobbes
checkout that ran the ingest, not the target, and is not read here.

Staleness means **only a different commit** (DEC-005): an uncommitted
working tree is reported as a separate, informational **dirty** tag (a
count of changed or untracked files, ``.hobbes/`` excluded) and never makes
the graph stale. The result reuses the generic ``hobbes.watterson.checks.Freshness``
(``pinned`` = stamp, ``current`` = HEAD) inside a ``GraphCheck``.

``on_session_start`` holds the session-start policy in one place: note a
fresh graph, offer to re-extract a stale or missing one (prompt on a TTY,
warn otherwise, or ``refresh``/``skip`` by flag), and show the dirty tag.
A graph extracted from a snapshot (DEC-006, ``hobbes.watterson.snapshot``) is
stamped with the snapshot's SHA, a commit on HEAD that is on no branch.
It is compared through the HEAD it was taken on, so a snapshot of HEAD is
fresh and a snapshot of an older commit is that many commits behind.
``check_freshness(repo, derived=…)`` reads such a graph from where it is
kept (``hobbes.watterson.session_graph``) instead of the repo's own
``.hobbes/derived/``.

Glue outside ``hobbes.extract``: it reads the artifacts and calls git, and
re-extraction goes through the ``hobbes ingest`` code path.
"""

from __future__ import annotations

import contextlib
import enum
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from hobbes.watterson.checks import Freshness
from hobbes.watterson.snapshot import snapshot_base

#: Where ingest writes, relative to the repo root (``hobbes.extract.emit``).
DERIVED_DIR = Path(".hobbes") / "derived"
#: ``graph.json`` first: its stamp is the one compared with HEAD.
DERIVED_FILES = ("graph.json", "tests.json", "interfaces.json")
_SHORT = 7
_GIT_TIMEOUT = 30.0


class GraphStatus(enum.StrEnum):
    """The graph's verdict against HEAD."""

    FRESH = "fresh"                 # every stamp == HEAD
    STALE = "stale"                 # a stamp != HEAD
    MISSING = "missing"             # no graph.json
    UNREADABLE = "unreadable"       # a derived file is corrupt, partial or absent
    NOT_A_REPO = "not a git repo"
    NO_COMMITS = "no commits"


#: Statuses a re-extract would fix.
NEEDS_INGEST = frozenset({GraphStatus.STALE, GraphStatus.MISSING, GraphStatus.UNREADABLE})
#: Statuses where there is nothing to compare against.
CANNOT_CHECK = frozenset({GraphStatus.NOT_A_REPO, GraphStatus.NO_COMMITS})


@dataclass(frozen=True)
class GraphCheck:
    """One repo's graph freshness plus the dirty tag.

    ``root`` is the repo's top level (or the path given, when it is not a
    repo). ``stamps`` maps each derived file to its stamped SHA (None when
    missing or unreadable). ``dirty_files`` counts changed or untracked
    files outside ``.hobbes/``; None when there is no repo to ask.
    """

    root: Path
    freshness: Freshness
    stamps: dict[str, str | None] = field(default_factory=dict)
    dirty_files: int | None = None

    @property
    def status(self) -> GraphStatus:
        return GraphStatus(self.freshness.status)

    @property
    def needs_ingest(self) -> bool:
        return self.status in NEEDS_INGEST

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_files)

    def describe(self) -> str:
        """The status with its reason, e.g. ``stale (3 commits behind)``."""
        f = self.freshness
        if self.status is GraphStatus.STALE and f.behind_by:
            return f"stale ({f.behind_by})"
        if self.status in (GraphStatus.MISSING, GraphStatus.UNREADABLE) and f.error:
            return f"{self.status} ({f.error})"
        return str(self.status)

    def summary(self) -> str:
        """One line: ``graph @ abc1234 · HEAD def5678 · stale (…) · dirty (2 files)``."""
        f = self.freshness
        if self.status in CANNOT_CHECK:
            return f.error or f"{self.root}: {self.status}"
        graph = f"graph @ {f.pinned[:_SHORT]}" if f.pinned else "no graph"
        parts = [graph, f"HEAD {f.current[:_SHORT]}" if f.current else "HEAD -", self.describe()]
        if self.dirty:
            parts.append(f"dirty ({_files(self.dirty_files)})")
        return " · ".join(parts)


def _files(n: int | None) -> str:
    return f"{n} file{'s' if n != 1 else ''}"


def exit_code(check: GraphCheck) -> int:
    """0 fresh, 1 stale/missing/unreadable (re-extract fixes it), 2 cannot check."""
    if check.status in CANNOT_CHECK:
        return 2
    return 1 if check.needs_ingest else 0


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=False, timeout=_GIT_TIMEOUT,
    )


def _read_stamp(path: Path) -> tuple[str | None, bool | None, str | None]:
    """``(sha, dirty, problem)`` for one derived file."""
    if not path.is_file():
        return None, None, f"{path.name} missing"
    try:
        doc = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, None, f"{path.name} unreadable: {type(exc).__name__}"
    sha = doc.get("sha") if isinstance(doc, dict) else None
    if not isinstance(sha, str) or not sha:
        return None, None, f"{path.name} has no stamp (top-level 'sha')"
    dirty = doc.get("dirty")
    return sha, dirty if isinstance(dirty, bool) else None, None


def dirty_count(root: Path) -> int:
    """Changed or untracked files under *root*, ``.hobbes/`` excluded.

    Untracked directories are counted file by file (``-uall``). Excluded
    both by pathspec and by filtering, so it does not rely on ingest's
    ``.git/info/exclude`` line.
    """
    out = _git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all",
        "--", ".", ":(top,exclude).hobbes",
    )
    if out.returncode != 0:
        return 0
    entries = out.stdout.split("\0")
    count, i = 0, 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        if entry[0] in "RC":
            i += 1  # the rename's or copy's source path follows
        path = entry[3:]
        if path == ".hobbes" or path.startswith(".hobbes/"):
            continue
        count += 1
    return count


def _behind(root: Path, stamp: str, head: str) -> str:
    """How the stamped commit relates to HEAD, e.g. ``3 commits behind``."""
    if _git(root, "cat-file", "-e", f"{stamp}^{{commit}}").returncode != 0:
        return "stamp not in history"
    if _git(root, "merge-base", "--is-ancestor", stamp, head).returncode == 0:
        out = _git(root, "rev-list", "--count", f"{stamp}..{head}")
        n = int(out.stdout.strip() or 0)
        return f"{n} commit{'s' if n != 1 else ''} behind"
    out = _git(root, "rev-list", "--left-right", "--count", f"{stamp}...{head}")
    try:
        ahead, behind = (int(x) for x in out.stdout.split())
    except ValueError:
        return "diverged"
    return f"diverged: {behind} behind, {ahead} not on HEAD"


def check_freshness(repo: str | Path, derived: str | Path | None = None) -> GraphCheck:
    """Compare *repo*'s Hobbes graph stamp with its HEAD. Never raises for
    an absent repo, graph or git; the status says what was found.

    *derived* is the directory holding the three artifacts; by default the
    repo's ``.hobbes/derived/``."""
    given = Path(repo).expanduser().resolve()
    subject = f"hobbes graph {given}"

    def cannot(status: GraphStatus, error: str, root: Path = given) -> GraphCheck:
        return GraphCheck(root, Freshness(subject, None, None, None, None, None, status, error=error))

    if not given.is_dir():
        return cannot(GraphStatus.NOT_A_REPO, f"{given} is not a directory")
    try:
        top = _git(given, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError) as exc:
        return cannot(GraphStatus.NOT_A_REPO, f"cannot run git: {exc}")
    if top.returncode != 0:
        return cannot(GraphStatus.NOT_A_REPO, f"{given} is not a git repo")
    root = Path(top.stdout.strip())
    subject = f"hobbes graph {root}"
    head_out = _git(root, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    if head_out.returncode != 0:
        return cannot(GraphStatus.NO_COMMITS, f"{root} has no commits yet", root)
    head = head_out.stdout.strip()
    dirty = dirty_count(root)

    shown = DERIVED_DIR if derived is None else Path(derived)
    derived = root / DERIVED_DIR if derived is None else Path(derived)
    stamps: dict[str, str | None] = {}
    problems: list[str] = []
    graph_dirty = None
    for name in DERIVED_FILES:
        sha, was_dirty, problem = _read_stamp(derived / name)
        stamps[name] = sha
        if name == "graph.json":
            graph_dirty = was_dirty
        if problem:
            problems.append(problem)
    graph = stamps["graph.json"]

    notes: list[str] = []
    stamped = {sha for sha in stamps.values() if sha}
    if len(stamped) > 1:
        notes.append(
            "stamps disagree: "
            + ", ".join(f"{n} @ {s[:_SHORT] if s else '-'}" for n, s in stamps.items())
        )
    if graph_dirty:
        notes.append("the graph was extracted from a dirty tree")
    # A snapshot graph is compared through the HEAD it was taken on (DEC-006).
    base = snapshot_base(root, graph) if graph and graph != head else None
    if base:
        notes.append(f"the graph is a snapshot of {base[:_SHORT]} with uncommitted changes")
    compared = base or graph

    def result(status: GraphStatus, behind_by: str | None = None, error: str | None = None) -> GraphCheck:
        suggested = head if status in NEEDS_INGEST else None
        freshness = Freshness(
            subject, graph, head, head, suggested, behind_by, status,
            notes=tuple(notes), error=error,
        )
        return GraphCheck(root, freshness, stamps, dirty)

    if not (derived / "graph.json").exists():
        return result(GraphStatus.MISSING, error=f"no {shown / 'graph.json'}")
    if problems:
        return result(GraphStatus.UNREADABLE, error="; ".join(problems))
    if compared != head:
        return result(GraphStatus.STALE, behind_by=_behind(root, compared, head))
    if len(stamped) > 1:
        return result(GraphStatus.STALE, behind_by="stamps disagree")
    return result(GraphStatus.FRESH)


# -- session start ---------------------------------------------------------


class RefreshPolicy(enum.StrEnum):
    """What a session start does about a stale or missing graph."""

    ASK = "ask"          # prompt on a TTY; warn and continue otherwise
    REFRESH = "refresh"  # re-extract without asking (--refresh)
    SKIP = "skip"        # do not check at all (--no-refresh)


#: ``ingest(root) -> exit code``; progress goes to the caller's stderr.
Ingest = Callable[[Path], int]
#: ``ask(question) -> answer line``; EOF answers "".
Ask = Callable[[str], str]


@dataclass(frozen=True)
class SessionStart:
    """What ``on_session_start`` found and did."""

    check: GraphCheck | None       # None when skipped; after a re-extract, the re-check
    before: GraphCheck | None = None
    ingested: bool = False
    ingest_exit: int | None = None


def run_ingest(root: Path) -> int:
    """``hobbes ingest --repo root`` in-process, its output sent to stderr
    so the session's stdout stays the agent's."""
    from hobbes.watterson import cli

    with contextlib.redirect_stdout(sys.stderr):
        return cli.main(["ingest", "--repo", str(root)])


def _ask_stdin(question: str) -> str:
    sys.stderr.write(question)
    sys.stderr.flush()
    return sys.stdin.readline()


def on_session_start(
    repo: str | Path,
    *,
    interactive: bool,
    policy: RefreshPolicy = RefreshPolicy.ASK,
    ingest: Ingest = run_ingest,
    ask: Ask = _ask_stdin,
    out: TextIO | None = None,
) -> SessionStart:
    """Check the graph as a session starts in *repo* and apply *policy*.

    Fresh: one note. Stale, missing or unreadable: re-extract when
    *policy* is REFRESH, or ASK on an *interactive* terminal and the answer
    is yes; otherwise warn and continue. The dirty tag is always shown when
    present and never prompts. Not a repo or no commits: one note. Never
    raises for the repo's state; the session goes ahead in every case.
    """
    out = out or sys.stderr
    if policy is RefreshPolicy.SKIP:
        return SessionStart(None)

    def say(line: str) -> None:
        print(f"hobbes: {line}", file=out, flush=True)

    check = before = check_freshness(repo)
    ingested, ingest_exit = False, None
    if check.status in CANNOT_CHECK:
        say(f"graph freshness not checked: {check.freshness.error or check.status}")
        return SessionStart(check)
    if check.status is GraphStatus.FRESH:
        say(f"graph fresh @ {check.freshness.pinned[:_SHORT]} (HEAD)")
    else:
        reason = check.describe()
        if policy is RefreshPolicy.REFRESH:
            go = True
            say(f"Hobbes graph is {reason}; re-extracting (--refresh)")
        elif interactive:
            answer = ask(f"Hobbes graph is {reason}. Re-extract now? [y/N] ")
            go = answer.strip().lower() in ("y", "yes")
        else:
            go = False
            say(f"warning: Hobbes graph is {reason}; continuing without re-extracting "
                "(run `hobbes ingest`, or pass --refresh)")
        if go:
            ingest_exit = ingest(check.root)
            ingested = ingest_exit == 0
            check = check_freshness(check.root)
            if ingested:
                say(f"re-extracted: {check.summary()}")
            else:
                say(f"warning: re-extract failed (exit {ingest_exit}); continuing with "
                    f"the graph as it is: {check.describe()}")
    if check.dirty:
        say(f"session started dirty ({_files(check.dirty_files)} changed)")
    return SessionStart(check, before, ingested, ingest_exit)
