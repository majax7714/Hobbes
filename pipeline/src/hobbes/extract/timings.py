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
"""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from hobbes.extract.staging import cache_root


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
                {"step": name, "seconds": round(time.perf_counter() - started, 3)}
            )

    @property
    def total(self) -> float:
        """Seconds since this record was started."""
        return round(time.perf_counter() - self._started, 3)

    def render(self) -> list[str]:
        """The summary's lines: the total, then every step in run order."""
        lines = [f"  timings: {self.total:.2f} s in {len(self.steps)} steps"]
        width = max((len(s["step"]) for s in self.steps), default=0)
        lines += [f"    {s['step']:<{width}}  {s['seconds']:8.3f} s" for s in self.steps]
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
) -> Path:
    """Append one line for this ingest to the repo's log and return its path.

    *index_cache* is lane B's cache ledger for the run (ADR-122: hits,
    misses, the keys' seconds), so the log says why a lane B step took
    the time it took; absent when no lookup was made.
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
    with path.open("a") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    return path
