"""The co-change factor: what is secretly one thing (agent-mapping §3.2).

Files that repeatedly change in the same commits get their coupling
strengthened. This is observation, not inference — the commits happened
— and it encodes the one thing static structure cannot: a partition
that separates a co-change hotspot manufactures rework.

The window is pinned at 200 commits (ADR-051): a count, not a time
span, so the same HEAD gives the same answer on any box. A repo whose
history cannot be read (not a git repo, empty history) contributes a
factor of 1.0 everywhere and a warning the change-spec carries — the
mapping degrades to structure-only, visibly (P6).
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

#: How many commits back the observation window reaches (ADR-051, C-35).
WINDOW = 200

#: Factor formula bounds (ADR-051): 1 + min(pairs, 8)/4, so the factor
#: is 1.0 with no shared history and saturates at 3.0 — co-change
#: strengthens coupling, it never becomes the only signal.
_CAP = 8


class CoChange:
    """Pairwise co-commit counts for a repo's recent history."""

    def __init__(self, counts: Counter, warning: str = ""):
        self._counts = counts
        #: Non-empty when history could not be read; the change-spec
        #: carries it so a structure-only partition is a stated fact.
        self.warning = warning

    def factor(self, path_a: str | None, path_b: str | None) -> float:
        """The coupling multiplier for two files, 1.0–3.0."""
        if not path_a or not path_b or path_a == path_b:
            return 1.0
        pairs = self._counts[_key(path_a, path_b)]
        return 1.0 + min(pairs, _CAP) / 4.0


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def observe(repo_root: Path, window: int = WINDOW) -> CoChange:
    """Count pairwise co-occurrence over the last *window* commits.

    Commits touching more than 50 files are skipped: a bulk rename or a
    vendored import says nothing about which two files are one thing,
    and counting it would let one commit dominate the window.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "log", f"-{window}",
             "--name-only", "--pretty=format:%H", "--no-renames"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        return CoChange(Counter(), warning=(
            "co-change history unavailable "
            f"({detail.strip().splitlines()[0] if detail.strip() else exc}); "
            "coupling is structure-only for this plan"
        ))

    counts: Counter = Counter()
    files: list[str] = []
    for line in [*out.splitlines(), ""]:
        if line and not _is_commit_hash(line):
            files.append(line)
            continue
        if 2 <= len(files) <= 50:
            unique = sorted(set(files))
            for i, a in enumerate(unique):
                for b in unique[i + 1:]:
                    counts[_key(a, b)] += 1
        files = []
    return CoChange(counts)


def _is_commit_hash(line: str) -> bool:
    return len(line) == 40 and all(c in "0123456789abcdef" for c in line)
