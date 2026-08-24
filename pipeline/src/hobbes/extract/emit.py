"""Artifact stamping and emission (ADR-006).

The stamp is the provenance every downstream claim pins to (P3): the repo's
HEAD SHA plus a ``dirty`` flag when the working tree doesn't match it. No
timestamps — the same tree must produce byte-identical artifacts (P1), which
is also what makes M2's graph diff a plain file diff.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

#: Where derived artifacts live, relative to the repo root. Gitignored —
#: never committed (architecture §10).
DERIVED_DIR = ".hobbes/derived"


class StampError(RuntimeError):
    """The repo's provenance could not be established (not a git repo,
    no commits yet, or git itself missing)."""


def ensure_hobbes_ignored(repo_root: Path) -> str | None:
    """Guarantee the repo gitignores Hobbes files (ADR-012).

    Hobbes artifacts are personal-environment files: target repos get the
    entire ``.hobbes/`` directory ignored so they can never be pushed by
    accident. A repo that already *tracks* content under ``.hobbes/`` (the
    hobbes repo dogfooding architecture §10) keeps that choice — only
    ``.hobbes/derived/`` is ensured there. Returns a description of the
    change made, or None when nothing was needed.
    """
    repo_root = Path(repo_root)
    try:
        tracked = _git(repo_root, "ls-files", ".hobbes")
    except (subprocess.CalledProcessError, OSError):
        tracked = ""  # not a git repo (hobbes init outside git): target posture
    line = ".hobbes/derived/" if tracked else ".hobbes/"
    gitignore = repo_root / ".gitignore"
    text = gitignore.read_text() if gitignore.exists() else ""
    if line in text.splitlines():
        return None
    if text and not text.endswith("\n"):
        text += "\n"
    gitignore.write_text(text + line + "\n")
    return f"added {line} to .gitignore"


def repo_stamp(repo_root: Path) -> dict:
    """``{"sha": …, "dirty": …}`` for the working tree at *repo_root*."""
    try:
        sha = _git(repo_root, "rev-parse", "HEAD")
        status = _git(repo_root, "status", "--porcelain")
    except (subprocess.CalledProcessError, OSError) as exc:
        raise StampError(
            f"cannot stamp {repo_root}: needs to be a git repo with at least "
            f"one commit ({exc})"
        ) from exc
    return {"sha": sha, "dirty": bool(status)}


def write_artifacts(repo_root: Path, documents: dict[str, dict]) -> list[Path]:
    """Write *documents* (filename → body) into ``.hobbes/derived/``.

    Output is deterministic: sorted keys, 2-space indent, trailing newline.
    """
    derived = Path(repo_root) / DERIVED_DIR
    derived.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, document in sorted(documents.items()):
        path = derived / filename
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
