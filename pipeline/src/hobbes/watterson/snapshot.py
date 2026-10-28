"""Freeze a repo's working tree into a commit object, untouched (DEC-006).

``take_snapshot(repo)`` records the tree as it stands (tracked edits and
untracked, non-ignored files; ``.hobbes/`` left out) as a commit whose
parent is HEAD. Nothing the user sees moves: it stages into a temporary
copy of the index (``GIT_INDEX_FILE``), then ``write-tree`` and
``commit-tree``. No branch, index or working file changes; the only writes
are new objects in the repo's object store.

The commit is deterministic: a fixed identity, date and message, so the
same tree on the same HEAD always gives the same SHA. A turn that changed
nothing therefore snapshots to the SHA already extracted.

A snapshot is recognised by its subject (``hobbes snapshot``) and has
exactly one parent, the HEAD it was taken on (``snapshot_base``). Snapshots
are on no branch. One private ref per session
(``refs/hobbes/snapshot/<session>``, ``pin``/``unpin``) keeps the latest
reachable; older ones are left for ``git gc`` to prune.

Glue outside ``hobbes.extract``: plain git plumbing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

SUBJECT = "hobbes snapshot"
REF_PREFIX = "refs/hobbes/snapshot/"
_GIT_TIMEOUT = 60.0
#: Fixed identity and date, so a snapshot's SHA depends only on tree + parent.
_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "hobbes",
    "GIT_AUTHOR_EMAIL": "hobbes@localhost",
    "GIT_AUTHOR_DATE": "@0 +0000",
    "GIT_COMMITTER_NAME": "hobbes",
    "GIT_COMMITTER_EMAIL": "hobbes@localhost",
    "GIT_COMMITTER_DATE": "@0 +0000",
}


class SnapshotError(RuntimeError):
    """The tree could not be snapshotted (not a repo, no commits, git failed)."""


@dataclass(frozen=True)
class Snapshot:
    """A frozen working tree: commit ``sha`` with ``tree`` on parent ``base`` (HEAD)."""

    sha: str
    base: str
    tree: str


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, check=False, timeout=_GIT_TIMEOUT,
            env={**os.environ, **env} if env else None,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SnapshotError(f"cannot run git in {root}: {exc}") from exc
    if out.returncode != 0:
        raise SnapshotError(f"git {args[0]} failed in {root}: {out.stderr.strip()}")
    return out.stdout.strip()


#: ``add -A`` pathspecs, by whether ``.hobbes/`` is already ignored. Naming an
#: ignored path in an exclude pathspec makes ``git add`` fail ("paths are
#: ignored"), and ``hobbes ingest`` puts ``.hobbes/`` in ``info/exclude``.
_ADD_PATHS = {False: (".", ":(top,exclude).hobbes"), True: (".",)}


def _hobbes_ignored(root: Path) -> bool:
    """True when git already ignores ``.hobbes/`` in *root*."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", ".hobbes/"],
            capture_output=True, check=False, timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SnapshotError(f"cannot run git in {root}: {exc}") from exc
    return out.returncode == 0


def repo_root(repo: str | Path) -> Path:
    """The top level of the git repo containing *repo*."""
    return Path(_git(Path(repo).expanduser().resolve(), "rev-parse", "--show-toplevel"))


def take_snapshot(repo: str | Path) -> Snapshot:
    """Snapshot *repo*'s working tree as a commit on HEAD; see the module doc."""
    root = repo_root(repo)
    try:
        head = _git(root, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    except SnapshotError as exc:
        raise SnapshotError(f"{root} has no commits yet") from exc
    index = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    with tempfile.TemporaryDirectory(prefix="hobbes-snapshot-") as tmp:
        temp_index = Path(tmp) / "index"
        env = {"GIT_INDEX_FILE": str(temp_index)}
        if index.is_file():
            shutil.copyfile(index, temp_index)  # keeps the stat cache: add -A rehashes only changes
        else:
            _git(root, "read-tree", head, env=env)
        _git(root, "add", "-A", "--", *_ADD_PATHS[_hobbes_ignored(root)], env=env)
        tree = _git(root, "write-tree", env=env)
    sha = _git(
        root, "commit-tree", tree, "-p", head, "-m", SUBJECT,
        "-m", f"Hobbes-Snapshot-Of: {head}", env=_COMMIT_ENV,
    )
    return Snapshot(sha, head, tree)


def snapshot_base(repo: str | Path, sha: str) -> str | None:
    """The HEAD a snapshot was taken on, or None when *sha* is not a snapshot."""
    try:
        out = _git(Path(repo), "show", "-s", "--format=%P%n%s", f"{sha}^{{commit}}")
    except SnapshotError:
        return None
    parents, _, subject = out.partition("\n")
    parents_list = parents.split()
    if subject != SUBJECT or len(parents_list) != 1:
        return None
    return parents_list[0]


def changed_files(repo: str | Path, old: str, new: str) -> list[str]:
    """Paths that differ between two commits' trees (renames as delete + add)."""
    out = _git(Path(repo), "diff-tree", "-r", "-z", "--name-only", "--no-renames", old, new)
    return [p for p in out.split("\0") if p]


def pin(repo: str | Path, session: str, sha: str) -> None:
    """Point ``refs/hobbes/snapshot/<session>`` at *sha* so gc keeps it."""
    _git(Path(repo), "update-ref", f"{REF_PREFIX}{session}", sha)


def unpin(repo: str | Path, session: str) -> None:
    """Drop the session's ref; its snapshots become ordinary gc candidates."""
    _git(Path(repo), "update-ref", "-d", f"{REF_PREFIX}{session}")
