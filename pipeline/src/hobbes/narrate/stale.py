"""Blob-level staleness for narrative artifacts (ADR-019).

An artifact stamps the git blob SHA of every file it cites (its
``sources``); it is stale iff any cited file's current working-tree
blob differs from the stamp, or the file is gone. Hashing the working
tree (``git hash-object``) — not HEAD — means an uncommitted edit flips
the badge immediately: staleness is visible, never silent (§3.3).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


def blob_shas(repo_root: Path, paths: Iterable[str]) -> dict[str, str | None]:
    """Working-tree blob SHA per repo-relative path; None for missing files.

    One ``git hash-object --stdin-paths`` call for all existing paths.
    """
    repo_root = Path(repo_root)
    unique = sorted(set(paths))
    existing = [p for p in unique if (repo_root / p).is_file()]
    result: dict[str, str | None] = {p: None for p in unique}
    if existing:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "hash-object", "--stdin-paths"],
            input="\n".join(existing) + "\n",
            capture_output=True,
            text=True,
            check=True,
        )
        result.update(zip(existing, out.stdout.split()))
    return result


def stamp_sources(repo_root: Path, paths: Iterable[str]) -> list[dict]:
    """``sources`` entries for *paths*: sorted, deduped, blob-stamped.

    Callers validate pins first, so every path exists; a vanished file
    between validation and stamping is a real error, not a stale badge.
    """
    shas = blob_shas(repo_root, paths)
    missing = [p for p, sha in shas.items() if sha is None]
    if missing:
        raise FileNotFoundError(
            f"cannot stamp sources, files missing: {', '.join(missing)}"
        )
    return [{"blob_sha": shas[p], "path": p} for p in sorted(shas)]


def changed_sources(repo_root: Path, sources: list[dict]) -> list[str]:
    """Paths in *sources* whose working-tree blob no longer matches."""
    current = blob_shas(repo_root, (s["path"] for s in sources))
    return sorted(
        s["path"] for s in sources if current.get(s["path"]) != s["blob_sha"]
    )


def is_stale(repo_root: Path, artifact: dict) -> bool:
    """True iff any of *artifact*'s stamped sources changed (ADR-019)."""
    return bool(changed_sources(repo_root, artifact.get("sources", [])))
