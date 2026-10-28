"""Where an ingest's time goes (ADR-119).

Every step of ``extract_repo`` — each language's lane A walk, each lane
B index run, the join, the projection, the tail, the test map, the write
— is timed, and the ingest summary prints the list. Speed work without
it was a guess (C-35's own rule applied to the pipeline's clock): the
ScummVM ingest was known to take 8 min 57 s and nothing said which step.

**Never in ``graph.json``.** Two ingests of one commit are byte-identical
(P1, ``test_emit``), and a duration is a fact about the box, not the
repo. The record lives beside the summary and, one JSON line per
ingest, under the Hobbes cache (``~/.hobbes/cache/timings/``), so a
before-and-after can be read off two lines.

**Memory too (ADR-119, amended by ADR-183's review).** Each step also
records two peaks as it ends, in MB: this process's resident set since
the ingest began (``peak_rss_mb``), and the largest host child's that has
exited (``child_peak_rss_mb``: the TS/JS helper, a host-run step). Both
only rise, so the step a peak first appears at is the step that set it. A
contained step's indexer runs under podman's monitor, not as a child of
this process, so no figure here measures it; the summary says so.
"""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from hobbes.extract.staging import cache_root


def _peak_mb(who: int) -> int:
    """*who*'s peak resident set (``resource.RUSAGE_SELF`` or
    ``RUSAGE_CHILDREN``), in whole MB."""
    peak = resource.getrusage(who).ru_maxrss
    # Linux reports kilobytes, macOS bytes.
    return round(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024)


@dataclass
class Timings:
    """The steps of one ingest, in run order, each with its seconds."""

    steps: list[dict] = field(default_factory=list)
    _started: float = field(default_factory=time.perf_counter, repr=False)

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        """Time the block as *name*; a step that raises is still recorded."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.steps.append(
                {
                    "step": name,
                    "seconds": round(time.perf_counter() - started, 3),
                    "peak_rss_mb": _peak_mb(resource.RUSAGE_SELF),
                    "child_peak_rss_mb": _peak_mb(resource.RUSAGE_CHILDREN),
                }
            )

    def add(self, name: str, seconds: float) -> None:
        """Record a step timed elsewhere — on a thread of its own (ADR-184
        lever 3) — in the order the serial run would have."""
        self.steps.append(
            {
                "step": name,
                "seconds": round(seconds, 3),
                "peak_rss_mb": _peak_mb(resource.RUSAGE_SELF),
                "child_peak_rss_mb": _peak_mb(resource.RUSAGE_CHILDREN),
            }
        )

    @property
    def total(self) -> float:
        """Seconds since this record was started."""
        return round(time.perf_counter() - self._started, 3)

    def render(self) -> list[str]:
        """The summary's lines: the total and the peaks, then every step
        in run order with this process's peak as it ended."""
        lines = [f"  timings: {self.total:.2f} s in {len(self.steps)} steps"]
        if self.steps:
            last = self.steps[-1]
            lines.append(
                f"  peak memory: {last['peak_rss_mb']:,} MB this process, "
                f"{last['child_peak_rss_mb']:,} MB its largest host child; "
                "a contained step's indexer is not measured here"
            )
        width = max((len(s["step"]) for s in self.steps), default=0)
        lines += [
            f"    {s['step']:<{width}}  {s['seconds']:8.3f} s  {s['peak_rss_mb']:>7,} MB"
            for s in self.steps
        ]
        return lines


def timings_log(repo_root: Path) -> Path:
    """The append-only log for *repo_root*, keyed by the repo's path."""
    key = hashlib.sha256(str(Path(repo_root).resolve()).encode()).hexdigest()[:16]
    return cache_root() / "timings" / f"{key}.jsonl"


def record(
    repo_root: Path,
    sha: str,
    version: str | None,
    timings: Timings,
    index_cache: dict | None = None,
    lanea_cache: dict | None = None,
) -> Path:
    """Append one line for this ingest to the repo's log and return its path.

    *index_cache* is lane B's cache ledger for the run (ADR-122: hits,
    misses, the keys' seconds), so the log says why a lane B step took
    the time it took; absent when no lookup was made.
    *lanea_cache* is the same for lane A's C++ file cache (ADR-128 §4).
    """
    path = timings_log(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "repo": str(Path(repo_root).resolve()),
        "sha": sha,
        "hobbes": version,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_seconds": timings.total,
        "steps": timings.steps,
    }
    if index_cache is not None:
        line["index_cache"] = index_cache
    if lanea_cache is not None:
        line["lanea_cache"] = lanea_cache
    with path.open("a") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    return path
