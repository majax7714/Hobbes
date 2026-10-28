"""The generic result shape for Hobbes's "compare, then prompt" checks.

``Freshness`` says whether something pinned is still current: the adapter
pins against npm (``hobbes.watterson.providers.staleness``, DEC-004) and the Hobbes
graph's stamped commit against the repo's HEAD (``hobbes.watterson.freshness``,
DEC-005). Each check keeps its own status enum (a ``StrEnum``, so the
status prints as its value) and wraps ``Freshness`` with its own details.

It lives here, outside ``hobbes.watterson.providers``, so a check of the extraction
output need not import the provider layer. ``hobbes.watterson.providers.staleness``
re-exports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Freshness:
    """A generic "is the pin still current" result.

    ``pinned`` is what we ask for and ``current`` what is in place (for the
    adapters: the version in package.json and the one installed; for the
    graph: the stamped commit and HEAD). ``latest`` is the newest upstream
    (published at ``latest_at``), ``suggested`` what to move to now,
    ``behind_by`` a short human gap (e.g. "3 stable releases, 12 days" or
    "3 commits behind"). ``status`` is the check's own ``StrEnum`` member.
    ``notes`` carry extra lines and ``error`` says why something could not
    be read.
    """

    subject: str
    pinned: str | None
    current: str | None
    latest: str | None
    suggested: str | None
    behind_by: str | None
    status: str
    latest_at: datetime | None = None
    notes: tuple[str, ...] = ()
    error: str | None = None
