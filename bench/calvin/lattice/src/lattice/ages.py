"""Cell age: since when a kernel's **name** and its **body** have been what they are at a ref.

This is a contamination instrument (`calvin-experiments.md` §6, the E0 card). A base model's knowledge
cutoff is a date, so a cell whose body is newer than the cutoff cannot have been read, and a cell whose
body predates it might have been. C-39 is the standing lesson: a benchmark the base has read measures
recall. Every row this module writes is a fact about **W** — the target — and is read beside G-mem, never
instead of it.

Two dates per cell, and they are different questions:

- **`name_since`** — since when this file has defined this name. Walking the file's history back from
  *ref*, the oldest commit of the unbroken run whose version defines it.
- **`body_since`** — since when the body at *ref* has been byte-identical. The same walk, stopping at
  the first commit whose version's body differs, and taking the commit after it.

Both walks are **contiguous from the ref backwards**: a name or a body that existed, went away and came
back gets the date of the run that reaches *ref*, which is the only one a cutoff can be compared with.

Git is read through `subprocess` — `git log --format=%H %cI -- <file>` for the file's history and
`git show <sha>:<path>` for a version — and decoded with `errors="replace"`, because the target carries
a non-UTF-8 byte and a body is read for its text, not its bytes. **No rename following:** `git log`
without `--follow`, so a file's history begins where its path does, and that is what the row says.

Every version is found with `scan`, the package's own C scanner, and never with a regex over the name:
the body's span is where the scanner says the body is, so "identical" means the same braces-to-braces
text the graders would fill. The scan happens once per commit per file, not once per cell.

A date is the committer date truncated to the day (`2025-06-21`), which is the grain the quarter counts
in the design's record are read at.

**The cells come from git, not from a working tree** (part 4; session `189e`'s review found this). Given
no *lattice*, :func:`ages` reads `src/distance-*.c` **at the ref** with `git show`, so a bare clone — the
shape a contamination run actually has, a history fetched to be read and never checked out — answers
instead of reporting "ages of 0 native cell(s)". That was the choice between the two on offer: refuse a
tree it cannot read, or read the one git holds. Reading it is strictly more useful and no less honest,
and the refusal is kept for the case that is left — a ref whose tree holds no kernel file at all raises
:class:`NoKernelsAtRef`, its own type (P10, ADR-036), and the CLI exits 2 with the reason. A *lattice*
handed in is still used as given, which is how a caller asks about a working tree on purpose.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .cells import Cell, Lattice
from .cells import build as build_lattice
from .scan import ScanError, scan

__all__ = ["GitError", "NoKernelsAtRef", "ages", "cells_at", "identical_at"]


class GitError(RuntimeError):
    """A git command failed in a way that is not an answer: not "no such path", but a broken repo."""


class NoKernelsAtRef(Exception):
    """The ref's tree holds no `src/distance-*.c`, so there are no cells to date.

    Its own type, and raised rather than answered with an empty table: "ages of 0 native cell(s)" reads
    like a fact about the target when it is a fact about what was pointed at.
    """


def cells_at(git_dir: Path | str, ref: str, rename: dict[str, str] | None = None) -> Lattice:
    """The lattice of the tree *ref* points at, read out of git — a bare clone included.

    The ref's `src/distance-*.c` are written to a temporary directory and handed to `cells.build`, so
    the grid comes from this package's one reader and not from a second one written for git. Raises
    :class:`NoKernelsAtRef` when the ref's tree holds none.
    """
    root = Path(git_dir)
    files = [
        line
        for line in _git(root, "ls-tree", "-r", "--name-only", ref, "--", "src").splitlines()
        if line.startswith("src/distance-") and line.endswith(".c")
    ]
    if not files:
        raise NoKernelsAtRef(f"{root} holds no src/distance-*.c at {ref}: nothing to date")
    staged = Path(tempfile.mkdtemp(prefix="lattice-ages-"))
    (staged / "src").mkdir(parents=True, exist_ok=True)
    for file in sorted(files):
        text = _show(root, ref, file)
        if text is not None:
            (staged / file).write_text(text, encoding="utf-8")
    return build_lattice(staged, rename=rename)


def ages(git_dir: Path | str, ref: str, lattice: Lattice | None = None) -> dict[str, dict]:
    """One row per native cell: `{"cell", "name", "file", "name_since", "body_since", …}`, by cell id.

    *git_dir* is a clone of the target and *ref* the commit to read. *lattice* names the cells; without
    one it is :func:`cells_at`, the tree at the ref. Every body compared comes from git at *ref* or
    earlier, never from a working tree.
    """
    root = Path(git_dir)
    lattice = cells_at(root, ref) if lattice is None else lattice
    rows: dict[str, dict] = {}
    for file, cells in _by_file(lattice).items():
        history = _history(root, ref, file)
        versions = _Versions(root, file)
        at_ref = versions.of(ref)
        for cell in cells:
            rows[cell.id] = _row(cell, history, versions, at_ref)
    return rows


def identical_at(rows: dict[str, dict], date: str) -> int:
    """How many of *rows* had their ref-time body already, at the end of the day *date* (`YYYY-MM-DD`).

    The count the E0 card reads by quarter: a body whose `body_since` is on or before *date* is one the
    tree already held then.
    """
    return sum(1 for row in rows.values() if row["body_since"] and row["body_since"] <= date)


# MARK: - one cell -


def _row(cell: Cell, history: list[tuple[str, str]], versions: _Versions, at_ref: dict[str, str]) -> dict:
    body = at_ref.get(cell.name)
    row = {
        "cell": cell.id,
        "name": cell.name,
        "file": cell.file,
        "commits": len(history),
        "name_since": None,
        "name_sha": None,
        "body_since": None,
        "body_sha": None,
        "reason": None,
    }
    if body is None:
        row["reason"] = f"{cell.name} is not defined in {cell.file} at the ref"
        return row
    named = _run_back(history, versions, lambda bodies: cell.name in bodies)
    same = _run_back(history, versions, lambda bodies: bodies.get(cell.name) == body)
    row["name_sha"], row["name_since"] = named
    row["body_sha"], row["body_since"] = same
    if not history:
        row["reason"] = f"{cell.file} has no history at the ref"
    return row


def _run_back(history, versions: _Versions, holds) -> tuple[str | None, str | None]:
    """The oldest commit of the unbroken run from the newest for which *holds*, as `(sha, date)`."""
    chosen: tuple[str | None, str | None] = (None, None)
    for sha, date in history:
        if not holds(versions.of(sha)):
            break
        chosen = (sha, date[:10])
    return chosen


def _by_file(lattice: Lattice) -> dict[str, list[Cell]]:
    """The native cells grouped by their file, so each version of a file is scanned once."""
    grouped: dict[str, list[Cell]] = {}
    for cell in lattice.cells.values():
        if cell.native:
            grouped.setdefault(cell.file, []).append(cell)
    for cells in grouped.values():
        cells.sort(key=lambda cell: cell.signature_span.start)
    return grouped


class _Versions:
    """Every version of one file that the walk needs, scanned once each: name → body text."""

    def __init__(self, root: Path, file: str):
        self.root = root
        self.file = file
        self._by_sha: dict[str, dict[str, str]] = {}

    def of(self, sha: str) -> dict[str, str]:
        if sha not in self._by_sha:
            text = _show(self.root, sha, self.file)
            self._by_sha[sha] = {} if text is None else _bodies(text)
        return self._by_sha[sha]


def _bodies(text: str) -> dict[str, str]:
    """Each top-level definition's body, by name, as the scanner spans it.

    A version the scanner cannot read at all (`ScanError`: a stray brace at the top level) answers
    nothing, so the walk stops there — the age it reports is the shortest one the evidence supports,
    never a longer one guessed past a version that could not be read.
    """
    try:
        scanned = scan(text)
    except ScanError:
        return {}
    return {fn.name: text[fn.body_span.start : fn.body_span.end] for fn in scanned.functions}


# MARK: - git -


def _history(root: Path, ref: str, file: str) -> list[tuple[str, str]]:
    """The commits reachable from *ref* that touched *file*, newest first, as `(sha, committer date)`."""
    out = _git(root, "log", ref, "--format=%H %cI", "--", file)
    history = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            history.append((parts[0], parts[1]))
    return history


def _show(root: Path, sha: str, file: str) -> str | None:
    """The file's text at that commit, or `None` when the commit does not have that path."""
    done = subprocess.run(
        ["git", "-C", str(root), "show", f"{sha}:{file}"], capture_output=True, check=False
    )
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", errors="replace")


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if done.returncode != 0:
        raise GitError(f"git {' '.join(args)} in {root} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", errors="replace")
