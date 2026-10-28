"""How many of a step's pieces run at once (ADR-184).

Parallelism trades memory for time, so each knob is one environment
variable, set to 1 for the serial run every result is checked against
(``bench/identity/``). A default is a fraction of this box's cores,
bounded so the peak stays well under its memory (ADR-184 § Memory). The
output does not depend on any of them: pieces are merged in the order the
serial run made them.
"""

from __future__ import annotations

import os

TS_JOBS_ENV = "HOBBES_TS_JOBS"
LANE_B_JOBS_ENV = "HOBBES_LANE_B_JOBS"


def _cores() -> int:
    return len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)


def _jobs(env: str, default: int) -> int:
    raw = os.environ.get(env, "").strip()
    if not raw:
        return max(1, default)
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"{env}={raw!r} is not a whole number of at least 1 (ADR-184)")
    return int(raw)


def ts_jobs() -> int:
    """Lane A TS zones at once (``HOBBES_TS_JOBS``): half the cores, at
    most 4 (this repo's 27 zones peak at 6.8 GB with 4)."""
    return _jobs(TS_JOBS_ENV, min(4, _cores() // 2))


def lane_b_jobs() -> int:
    """Lane B languages at once (``HOBBES_LANE_B_JOBS``): a quarter of the
    cores, at most 3. Units within one language stay one at a time, so no
    tool cache is written by two containers at once."""
    return _jobs(LANE_B_JOBS_ENV, min(3, _cores() // 4))
