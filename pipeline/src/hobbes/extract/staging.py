"""Staging trees for lane B (ADR-027's safety contract).

The SCIP indexers only index what is under their ``--cwd``, and they need
a config file next to it. Rather than write that config into the repo and
delete it afterwards — a transient write into a tree Hobbes otherwise only
reads, which has to be crash-safe, interrupt-safe, and careful never to
remove a file it did not create — lane B indexes a **staging tree Hobbes
owns outright**, holding copies of the sources and the generated config.

Measured equivalent: python-only recall against lane A is 1.000 either way
(ADR-027), and staging private-repo-A costs 9ms for 421KB against ~5.5s to index
it. There is no trade.

The contract this module exists to keep, clause by clause:

1. **Nothing is ever written to the target repo.** Every write lands under
   :func:`cache_root`.
2. **Authored source is copied, never linked.** A hardlink is a live handle
   into the user's tree — ``chmod`` through one changes the *original*
   file's mode. Refined by ADR-032: a *regenerable dependency tree*
   (``node_modules``) may be **symlinked**, because it is not authored, is
   reproducible from a lockfile, and is only ever read. TypeScript has no
   equivalent of Pyright's absolute ``venvPath``, and the measured
   alternative lost 6.4% of the semantic references the lane exists to
   produce. Two properties are asserted in the tests rather than assumed:
   indexing writes nothing through the link, and removing a stage unlinks
   it instead of recursing into the target (C-22).
3. **The staging path is derived**, not random, so removal is idempotent
   and a later run can find what an earlier one left.
4. **Removal refuses any path outside the cache root**, and takes no path
   that came from the repo or from a caller's string.
5. **The staged file set is lane A's discovered set**, not ``git
   ls-files`` — ``discover_modules`` never consults git, so it sees
   untracked files, and a mismatch would hand the two lanes different
   inputs and manufacture false disagreements in §3.4's report.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

#: Where staging trees and cached indexes live. Beside ``sessions/``,
#: which is the other thing Hobbes owns under ``$HOME`` (ADR-018).
#: ``HOBBES_CACHE_DIR`` overrides it, for tests and for boxes where
#: ``$HOME`` is small.
_CACHE_ENV = "HOBBES_CACHE_DIR"


class StagingError(RuntimeError):
    """A staging tree could not be built, or a removal was refused."""


def cache_root() -> Path:
    """The one directory lane B is allowed to write to."""
    override = os.environ.get(_CACHE_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".hobbes" / "cache"


def stage_key(repo_root: Path, sha: str, files: list[str]) -> str:
    """A deterministic key for one (repo, commit, file-set) state.

    Derived rather than random (clause 3), so the same tree always maps to
    the same directory and removal is idempotent. The file set's sizes and
    mtimes are folded in because a *dirty* tree's SHA does not identify its
    content — without that, an edit would silently reuse a stale index.
    Stat-based rather than content-based so the key costs no reads; the
    SHA remains the authority for a clean tree.
    """
    repo_root = Path(repo_root).resolve()
    digest = hashlib.sha256()
    digest.update(str(repo_root).encode())
    digest.update(b"\0")
    digest.update(sha.encode())
    for rel in sorted(files):
        digest.update(b"\0")
        digest.update(rel.encode())
        try:
            stat = (repo_root / rel).stat()
            digest.update(f":{stat.st_size}:{stat.st_mtime_ns}".encode())
        except OSError:
            digest.update(b":missing")
    return digest.hexdigest()[:16]


def stage_path(repo_root: Path, sha: str, files: list[str]) -> Path:
    """Where this (repo, commit, file-set) stages to."""
    return cache_root() / "stage" / stage_key(repo_root, sha, files)


def build_stage(
    repo_root: Path,
    files: list[str],
    config: dict | None = None,
    config_name: str = "pyrightconfig.json",
    sha: str = "",
    configs: dict[str, dict] | None = None,
    links: dict[str, str] | None = None,
) -> Path:
    """Copy *files* out of *repo_root* into a staging tree and return it.

    *files* are repo-relative POSIX paths — lane A's discovered set
    (clause 5). *config* is written into the staging root as JSON, which
    is the whole reason the tree exists: the indexer needs it beside the
    sources, and the repo is not ours to put it in. *configs* writes
    additional JSON at arbitrary repo-relative paths, for languages whose
    config is per zone rather than per repo (TypeScript).

    *links* maps a repo-relative path in the stage to an **absolute**
    directory to symlink there — only ever a regenerable dependency tree
    (ADR-032, clause 2 as refined). Sources are still copied.

    Builds into a sibling ``.partial`` directory and renames on success,
    so an interrupted run never leaves a half-built tree that a later run
    would mistake for a complete one.
    """
    repo_root = Path(repo_root).resolve()
    final = stage_path(repo_root, sha, files)
    partial = final.with_name(final.name + ".partial")

    _remove_within_cache(partial)
    _remove_within_cache(final)
    partial.mkdir(parents=True, exist_ok=True)

    for rel in files:
        source = repo_root / rel
        target = partial / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # copyfile, not link and not copy2: a hardlink would be a live
        # handle into the user's tree (clause 2), and metadata is not
        # something the indexer reads.
        try:
            shutil.copyfile(source, target)
        except OSError as exc:
            _remove_within_cache(partial)
            raise StagingError(f"cannot stage {rel}: {exc}") from exc

    if config is not None:
        (partial / config_name).write_text(json.dumps(config, indent=1) + "\n")
    for rel, document in (configs or {}).items():
        target = partial / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=1) + "\n")

    for rel, absolute in (links or {}).items():
        target = partial / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # symlink_to, never copytree: node_modules runs to hundreds of
        # megabytes, and the indexer only reads it (ADR-032).
        try:
            target.symlink_to(absolute, target_is_directory=True)
        except OSError as exc:
            _remove_within_cache(partial)
            raise StagingError(f"cannot link {rel}: {exc}") from exc

    partial.rename(final)
    return final


def remove_stage(path: Path) -> None:
    """Remove a staging tree, refusing anything outside the cache root.

    The guard is the point (clause 4). Nothing here ever removes a path
    that came from the repo, from a glob, or from a caller's arbitrary
    string — only one this module computed.
    """
    _remove_within_cache(Path(path))


def sweep_stale(keep: Path | None = None) -> int:
    """Remove leftover staging trees, returning how many went.

    A crashed run leaves a ``.partial``; a superseded one leaves a
    complete tree nobody will ask for again. Neither is load-bearing, so
    garbage-collecting them on the next run is safe — and it is the reason
    an interrupted Hobbes needs no cleanup step of its own.
    """
    root = cache_root() / "stage"
    if not root.is_dir():
        return 0
    removed = 0
    for child in sorted(root.iterdir()):
        if keep is not None and child == keep:
            continue
        _remove_within_cache(child)
        removed += 1
    return removed


def _remove_within_cache(path: Path) -> None:
    """``rm -rf`` bounded to the cache root; a refusal is an error."""
    if not path.exists() and not path.is_symlink():
        return  # idempotent: removing what is not there is not a failure
    root = cache_root()
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError) as exc:
        raise StagingError(
            f"refusing to remove {path}: outside the Hobbes cache at {root}. "
            "Lane B only ever deletes trees it created."
        ) from exc
    if resolved == root.resolve():
        raise StagingError(f"refusing to remove the cache root itself ({root})")
    shutil.rmtree(resolved)
