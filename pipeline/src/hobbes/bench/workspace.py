"""Instance checkouts and candidate patches (ADR-055).

A run needs the instance's repo at its base commit, once per arm, in
a directory nothing else touches. Repos are mirrored once into
``~/.hobbes/cache/bench/<owner>__<name>.git`` (bare) and every
checkout is a local clone of the mirror — the same cache discipline
lane B's staging uses, and the only network the harness itself does
(``HOBBES_BENCH_GIT_BASE`` overrides the ``https://github.com/``
prefix, which is also how the tests point it at a local repo).

The **candidate patch** is ``git diff <base_commit>`` over the
checkout with everything staged, ``.hobbes/`` excluded — so it covers
what an arm committed and what it left in the tree alike, and never
carries Hobbes's own files into a prediction.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from hobbes.bench.instances import Instance

GIT_BASE_ENV = "HOBBES_BENCH_GIT_BASE"
CACHE_ENV = "HOBBES_BENCH_CACHE"


class WorkspaceError(RuntimeError):
    """The repo could not be mirrored or checked out at the base commit."""


def _git(cwd: Path | None, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *(["-C", str(cwd)] if cwd else []), *args],
        capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)}: {(proc.stderr or proc.stdout).strip()[-400:]}")
    return proc.stdout


def cache_root() -> Path:
    return Path(os.environ.get(CACHE_ENV) or Path.home() / ".hobbes" / "cache" / "bench")


def repo_url(repo: str) -> str:
    base = os.environ.get(GIT_BASE_ENV, "https://github.com/")
    return base + repo if base.endswith("/") else f"{base}/{repo}"


def mirror(repo: str) -> Path:
    """The bare mirror for *repo* (``owner/name``), created on first use
    and fetched when a later checkout needs a commit it lacks."""
    path = cache_root() / (re.sub(r"[^A-Za-z0-9_.-]", "__", repo) + ".git")
    if not path.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        _git(None, "clone", "--quiet", "--mirror", repo_url(repo), str(path))
    return path


def _has_commit(mirror_path: Path, sha: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(mirror_path), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
    ).returncode == 0


def checkout(instance: Instance, dest: Path) -> Path:
    """A fresh clone of *instance*'s repo at its base commit in *dest*
    (replaced if present), on a branch so sessions and commits have a
    ref to start from. Returns *dest*."""
    dest = Path(dest)
    src = mirror(instance.repo)
    if not _has_commit(src, instance.base_commit):
        _git(src, "fetch", "--quiet", "--all")
        if not _has_commit(src, instance.base_commit):
            raise WorkspaceError(
                f"{instance.repo} has no commit {instance.base_commit[:12]} "
                f"(mirror {src})"
            )
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(None, "clone", "--quiet", "--no-hardlinks", str(src), str(dest))
    _git(dest, "checkout", "--quiet", "-B", "bench/base", instance.base_commit)
    # A benchmark checkout has no identity; sessions and the pure arm
    # commit under this one.
    _git(dest, "config", "user.name", "hobbes-bench")
    _git(dest, "config", "user.email", "bench@hobbes.local")
    return dest


def candidate_patch(workspace: Path, base_commit: str, ref: str | None = None) -> str:
    """The unified diff an arm produced: ``base_commit..ref`` when *ref*
    names a branch (the harness arm's integration branch), else the
    working tree with everything staged (the pure arm). ``.hobbes/``
    and ``.gitignore`` edits Hobbes made are excluded."""
    workspace = Path(workspace)
    excludes = [":(exclude).hobbes", ":(exclude).hobbes/**", ":(exclude).gitignore"]
    if ref:
        return _git(workspace, "diff", "--no-color", base_commit, ref, "--", ".", *excludes)
    _git(workspace, "add", "-A", "--", ".", ":(exclude).hobbes")
    return _git(workspace, "diff", "--no-color", "--cached", base_commit, "--", ".", *excludes)
